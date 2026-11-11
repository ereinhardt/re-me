#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Interactive matching pipeline tester.
#
# The pipeline itself lives in Node (../backend/matching.js), so this script starts
# a small Node bridge as a subprocess (models load once), then lets you type a
# message and press Enter to see the 3 suggestions the matching pipeline returns.
# Suggestions containing a word from the settings blacklist are marked; the
# server never sends those.
# Type "exit" or press Ctrl+C to quit.
#
# Usage (from the Server directory):
#   python3 tools/test-pipeline.py
#   SERVER_DEBUG=1 python3 tools/test-pipeline.py   (also prints raw model output)
# ---------------------------------------------------------------------------
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MATCHING_MODULE = os.path.join(HERE, "..", "backend", "matching.js")
BLACKLIST_MODULE = os.path.join(HERE, "..", "backend", "blacklist.js")

# Node bridge: load the real pipeline, then answer one line of stdin per request.
BRIDGE = r"""
const { initMatching, getMessageSuggestions } = require(process.argv[1]);
const { isBlacklisted } = require(process.argv[2]);
const readline = require("readline");
(async () => {
  await initMatching();
  process.stdout.write("__READY__\n");
  const rl = readline.createInterface({ input: process.stdin });
  rl.on("line", async (line) => {
    try {
      const s = await getMessageSuggestions(line, "cli");
      const blocked = s.map((o, i) => isBlacklisted(o[`message-content-${i + 1}`]));
      process.stdout.write("__RESULT__" + JSON.stringify({ s, blocked }) + "\n");
    } catch (e) {
      process.stdout.write("__ERROR__" + (e && e.message ? e.message : e) + "\n");
    }
  });
})().catch((e) => {
  process.stdout.write("__FATAL__" + (e && e.message ? e.message : e) + "\n");
});
"""


def main():
    print("Loading matching pipeline (this can take a moment on first run)...")

    proc = subprocess.Popen(
        ["node", "-e", BRIDGE, MATCHING_MODULE, BLACKLIST_MODULE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        # Node speaks UTF-8; without this Windows would use its ANSI code page.
        encoding="utf-8",
        bufsize=1,
    )

    # Wait until the bridge signals it is ready, echoing the loading logs.
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line == "__READY__":
            sys.stdout.write("\n")  # finish the progress line
            sys.stdout.flush()
            break
        if line.startswith("__PROGRESS__"):
            # Overwrite the same line: "Embedding 32/5447 ..."
            sys.stdout.write("\rEmbedding " + line[len("__PROGRESS__"):] + " ...")
            sys.stdout.flush()
            continue
        if line.startswith("__FATAL__"):
            print("Failed to start pipeline:", line[len("__FATAL__"):])
            return 1
        if line:
            print(line)

    print("\nReady. Type a message and press Enter to test the pipeline.")
    print('Type "exit" or press Ctrl+C to quit.\n')

    try:
        while True:
            try:
                text = input("message> ").strip()
            except EOFError:
                break
            if not text:
                continue
            if text in ("exit", "quit"):
                break

            started = time.time()
            proc.stdin.write(text + "\n")
            proc.stdin.flush()

            # Read lines until a protocol marker arrives (other lines are logs).
            result = None
            error = None
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line.startswith("__RESULT__"):
                    result = json.loads(line[len("__RESULT__"):])
                    break
                if line.startswith("__ERROR__"):
                    error = line[len("__ERROR__"):]
                    break
                if line.startswith("__FATAL__"):
                    error = line[len("__FATAL__"):]
                    break
                if line:
                    print(line)

            elapsed = time.time() - started
            if error is not None:
                print(f"\nError: {error}\n")
                continue

            print(f"\nSuggestions ({elapsed:.1f}s):")
            for i, entry in enumerate(result["s"]):
                n = i + 1
                content = entry[f"message-content-{n}"]
                mid = entry[f"message-id-{n}"]
                ts = entry[f"timestamp-{n}"]
                blocked = "  (blacklisted)" if result["blocked"][i] else ""
                print(f"  {n}. {content}  [id={mid}, ts={ts}]{blocked}")
            print("")
    except KeyboardInterrupt:
        pass
    finally:
        print("\nBye.")
        proc.terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
