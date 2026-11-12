#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Chat export import.
#
# Opens a small window to choose one or more chat exports (as handed out by
# the apps, e.g. raw-data/whatsapp/*.zip, raw-data/telegram/.../result.json
# or, for Telegram's HTML export, .../export_results.html), or a CSV in the
# format of message_index.csv itself (e.g. a backup or another dataset).
# For every file the pattern is detected, the protagonist is determined, and
# only the protagonist's messages are appended to
# message-data/message_index.csv. Afterwards cleaning.py removes exact
# duplicates and embeds the protagonist profile (protagonist.json) in every
# row of the CSV. The export files themselves are not modified.
#
# Patterns live in the patterns/ folder and are named after the app (and
# export format, if the app offers several) and the app version they were
# written for, e.g. pattern_whatsapp_26.44.72.py or
# pattern_telegram_html_12.10.28298.py. If a platform changes its export
# format, add a new file for the new version next to the old one; all
# pattern_*.py files are picked up automatically.
#
# The protagonist is asked for only once, on the very first import, from the
# senders of all files chosen (sorted by the number of files they appear in,
# so the protagonist is usually on top), and stored
# as one profile for all platforms in patterns/protagonist.json: names, phone
# numbers, usernames and platform ids. Every pattern reports what an export
# reveals about each sender (identities()); a sender is the protagonist if any
# of it matches the profile, e.g. the WhatsApp display name equals the Telegram
# account name, or a phone number known from Telegram shows up in WhatsApp.
# Whatever a matched sender reveals in addition is added to the profile, so
# later imports of other platforms recognise the protagonist as well. Names
# and usernames are compared regardless of case, spacing and invisible
# characters; phone numbers without country code ("+49 152 …" = "0152 …").
# Files without a match are skipped (chats in which the protagonist never
# wrote), as are files no pattern can read or that cause an error; after the
# import a short message says in how many files no pattern or no protagonist
# was found. If the
# protagonist goes by a name not known yet, add it to
# patterns/protagonist.json. Patterns with PROTAGONIST_ONLY = True (the
# message_index.csv format) read files that contain only the protagonist's
# messages; all of them are taken without asking or matching. The profile
# embedded in such a file is added to protagonist.json if no profile exists
# yet or if it matches the existing one (i.e. it is the same person).
#
# "Reset Chat Data" deletes message_index.csv and protagonist.json (after a
# confirmation), so the next import starts from scratch.
#
# Usage (from the Server directory):
#   python3 tools/data-extraction/import.py
# Restart the server afterwards so the embedding index is rebuilt.
# ---------------------------------------------------------------------------
import csv
import glob
import importlib.util
import json
import os
import sys
import tkinter as tk
import unicodedata
import uuid
from tkinter import filedialog, messagebox

import cleaning

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(HERE, "..", "..", "raw-data")
PATTERNS_DIR = os.path.join(HERE, "patterns")
PROFILE_PATH = cleaning.PROFILE_PATH
MESSAGE_INDEX_PATH = cleaning.MESSAGE_INDEX_PATH
PROFILE_FIELDS = ("names", "phone_numbers", "usernames")
# Direction marks, zero-width spaces etc. the apps put around names/numbers.
INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"))
# Country calling codes are prefix-free: these have 1 or 2 digits, all
# others 3.
SHORT_COUNTRY_CODES = {
    "1", "7", "20", "27", "30", "31", "32", "33", "34", "36", "39", "40", "41", "43", "44", "45", "46", "47",
    "48", "49", "51", "52", "53", "54", "55", "56", "57", "58", "60", "61", "62", "63", "64", "65", "66",
    "81", "82", "84", "86", "90", "91", "92", "93", "94", "95", "98",
}


def load_patterns():
    """All pattern_<platform>_<app version>.py files in the patterns/ folder.
    They are loaded by path because the version dots are not valid in module
    names. Newer versions of a platform are tried first. The folder is put on
    the import path so the patterns can import their helpers (dates.py)."""
    sys.path.insert(0, PATTERNS_DIR)
    patterns = []
    for path in glob.glob(os.path.join(PATTERNS_DIR, "pattern_*.py")):
        name = os.path.basename(path)[:-3].replace(".", "_")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        patterns.append(module)
    version = lambda p: tuple(int(n) for n in p.VERSION.split("."))
    return sorted(patterns, key=lambda p: (p.NAME, version(p)), reverse=True)


PATTERNS = load_patterns()


def load_profile():
    profile = {}
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, encoding="utf-8") as f:
            profile = json.load(f)
    for field in PROFILE_FIELDS:
        profile.setdefault(field, [])
    profile.setdefault("ids", {})
    return profile


def save_profile(profile):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
        f.write("\n")


def national_number(value):
    """Phone number in national form, i.e. the country code replaced by "0",
    so that "+49 152 1234567", "0049 152 1234567" and "0152 1234567" all
    become "01521234567". Numbers without "+", "00" or "0" already include
    the country code (e.g. "49152…" in Telegram's JSON contacts)."""
    digits = "".join(str(unicodedata.decimal(c)) for c in value if c.isdecimal())
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        return digits
    for length in (1, 2):
        if digits[:length] in SHORT_COUNTRY_CODES:
            return "0" + digits[length:]
    return "0" + digits[3:]


def normalize(field, value):
    """Stored form of a profile value: without invisible characters and
    surplus spaces, phone numbers in national form, usernames without "@"."""
    value = unicodedata.normalize("NFC", str(value).translate(INVISIBLE))
    value = " ".join(value.split())
    if field == "phone_numbers":
        return national_number(value)
    if field == "usernames":
        return value.removeprefix("@")
    return value


def key(field, value):
    """Compared form of a profile value: case and Unicode variants (e.g. "ö"
    as one or as two characters) do not matter."""
    return unicodedata.normalize("NFKC", normalize(field, value)).casefold()


def values(identity, field):
    return [v for v in (normalize(field, v) for v in identity.get(field, []) if v) if v]


def platform_ids(platform, identity):
    """Platform -> ids of a sender: its "id" on this platform, plus the "ids"
    of all platforms of a profile embedded in message_index.csv."""
    ids = {p: list(i) for p, i in identity.get("ids", {}).items()}
    if identity.get("id"):
        ids.setdefault(platform, []).append(identity["id"])
    return ids


def matches(profile, platform, identity):
    for p, ids in platform_ids(platform, identity).items():
        if any(i in profile["ids"].get(p, []) for i in ids):
            return True
    for field in PROFILE_FIELDS:
        known = {key(field, v) for v in profile[field]}
        if any(key(field, v) in known for v in values(identity, field)):
            return True
    return False


def learn(profile, platform, identity):
    """Add what is known about a protagonist sender to the profile. Returns
    the new values."""
    new = []
    for p, ids in platform_ids(platform, identity).items():
        known = profile["ids"].setdefault(p, [])
        for i in ids:
            if i not in known:
                known.append(i)
                new.append(f"{p} id {i}")
    for field in PROFILE_FIELDS:
        for v in values(identity, field):
            if key(field, v) not in {key(field, known) for known in profile[field]}:
                profile[field].append(v)
                new.append(v)
    return new


def describe(platform, identity):
    """The values learn() would store for a sender, as shown in the dialog."""
    parts = []
    for field in PROFILE_FIELDS:
        for v in values(identity, field):
            v = "@" + v if field == "usernames" else v
            if v not in parts:
                parts.append(v)
    if identity.get("id"):
        parts.append(f"{platform} id {identity['id']}")
    return ", ".join(parts)


def has_profile(profile):
    return any(profile[field] for field in PROFILE_FIELDS) or any(profile["ids"].values())


def protagonist_only(pattern):
    """True for patterns whose files contain only the protagonist's messages."""
    return getattr(pattern, "PROTAGONIST_ONLY", False)


def detect(path):
    """(pattern module, parsed data) of the first matching pattern, or (None, None).
    A pattern that fails on the file counts as not matching."""
    for pattern in PATTERNS:
        try:
            data = pattern.load(path)
        except Exception:
            continue
        if data:
            return pattern, data
    return None, None


def count_messages():
    """Number of messages in message_index.csv (without the header)."""
    if not os.path.exists(MESSAGE_INDEX_PATH):
        return 0
    with open(MESSAGE_INDEX_PATH, encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def append_to_index(rows):
    """Append (text, timestamp) rows with a new UUID as message id, or
    (text, timestamp, message id) rows with their own id if it is not empty.
    The message-data folder and the CSV (with header) are created if missing.
    The column "protagonist" is filled in by cleaning.clean() afterwards."""
    content = ""
    if os.path.exists(MESSAGE_INDEX_PATH):
        with open(MESSAGE_INDEX_PATH, encoding="utf-8", newline="") as f:
            content = f.read()
    needs_newline = bool(content) and not content.endswith("\n")

    os.makedirs(os.path.dirname(MESSAGE_INDEX_PATH), exist_ok=True)
    with open(MESSAGE_INDEX_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not content:
            writer.writerow(cleaning.HEADER)
        elif needs_newline:
            f.write("\r\n")
        for text, timestamp, *message_id in rows:
            writer.writerow([text, timestamp, (message_id and message_id[0]) or str(uuid.uuid4())])


class ProtagonistDialog(tk.Toplevel):
    """Asks which sender(s) are the protagonist (only while the profile is
    still empty). Shows the senders of all chosen files together, each with
    exactly the information that is stored in protagonist.json when it is
    chosen; senders found in the most files come first (the protagonist is
    usually in all of them), then those with the most messages. `candidates`
    maps (platform, sender) to [identity, files, messages]. `result` is the
    list of chosen keys, or None if the import is cancelled."""

    def __init__(self, parent, candidates, suggested):
        super().__init__(parent)
        self.title("Protagonist")
        self.transient(parent)
        self.result = None

        tk.Label(self, text="Choose Protagonist:").pack(anchor="w", padx=10, pady=(10, 4))

        self.keys = sorted(candidates, key=lambda k: (-candidates[k][1], -candidates[k][2]))
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, width=80, height=min(len(self.keys), 15),
                                  yscrollcommand=scrollbar.set)
        scrollbar.configure(command=self.listbox.yview)
        for i, (platform, sender) in enumerate(self.keys):
            identity, files, messages = candidates[(platform, sender)]
            self.listbox.insert(tk.END, f"{describe(platform, identity)}   ({files} file(s), {messages} messages)")
            if (platform, sender) in suggested:
                self.listbox.selection_set(i)
        self.listbox.pack(side="left", fill="both", expand=True)

        tk.Label(self, text="This choice cannot be changed later.").pack(anchor="w", padx=10, pady=(6, 0))

        buttons = tk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=10)
        tk.Button(buttons, text="OK", command=self.ok).pack(side="right")
        tk.Button(buttons, text="Cancel import", command=self.destroy).pack(side="right", padx=6)

        self.grab_set()
        self.wait_window()

    def ok(self):
        selection = [self.keys[i] for i in self.listbox.curselection()]
        if not selection:
            messagebox.showwarning("Protagonist", "Please select at least one sender.", parent=self)
            return
        self.result = selection
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("re: me – Chat import")

        self.total = tk.Label(self)
        self.total.pack(padx=20, pady=(20, 0))
        self.total_mtime = -1  # forces the first count
        self.watch_total()

        self.button = tk.Button(self, text="Import Chat Data", command=self.run)
        self.button.pack(padx=20, pady=(20, 6))

        self.reset_button = tk.Button(self, text="Reset Chat Data", command=self.reset)
        self.reset_button.pack(padx=20, pady=(0, 20))

    def update_total(self):
        """Show the number of messages in message_index.csv (recounted only
        if the file changed)."""
        mtime = os.path.getmtime(MESSAGE_INDEX_PATH) if os.path.exists(MESSAGE_INDEX_PATH) else None
        if mtime != self.total_mtime:
            self.total_mtime = mtime
            self.total.configure(text=f"Total messages: {count_messages()}")

    def watch_total(self):
        # Checked every 2 seconds, so changes made elsewhere (e.g. cleaning.py)
        # show up too.
        self.update_total()
        self.after(2000, self.watch_total)

    def protagonist_for(self, pattern, data, profile):
        """Protagonist sender -> identity; empty if no sender matches the
        profile."""
        identities = pattern.identities(data)
        if protagonist_only(pattern):
            # The file contains only the protagonist's messages. What it
            # reveals about them is learned only if it is the same person.
            return {s: identity if not has_profile(profile) or matches(profile, pattern.NAME, identity) else {}
                    for s, identity in identities.items()}
        return {s: identity for s, identity in identities.items() if matches(profile, pattern.NAME, identity)}

    def choose_protagonist(self, files, profile):
        """Ask for the protagonist among the senders of all (pattern, data)
        `files` and add the chosen senders to the profile. Returns False if
        the import is cancelled."""
        candidates = {}  # (platform, sender) -> [identity, files, messages]
        suggested = set()
        for pattern, data in files:
            try:
                identities = pattern.identities(data)
                counts = pattern.message_counts(data)
                suggested.update((pattern.NAME, s) for s in getattr(pattern, "suggested_ids", lambda d: [])(data))
            except Exception:
                continue  # counted as unreadable when imported
            for sender, identity in identities.items():
                candidate = candidates.setdefault((pattern.NAME, sender), [identity, 0, 0])
                candidate[1] += 1
                candidate[2] += counts.get(sender, 0)
        if not candidates:
            return True
        dialog = ProtagonistDialog(self, candidates, suggested)
        if dialog.result is None:
            return False
        for key_ in dialog.result:
            learn(profile, key_[0], candidates[key_][0])
        save_profile(profile)
        return True

    def run(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Choose chat exports",
            initialdir=os.path.abspath(RAW_DATA_DIR),
            filetypes=[("Chat exports", "*.zip *.txt *.json *.html *.csv"), ("All files", "*")],
        )
        if not paths:
            return

        self.button.configure(state="disabled")
        self.reset_button.configure(state="disabled")
        self.update_idletasks()
        try:
            self.import_files(paths)
        finally:
            self.update_total()
            # Clicks made during the import are handled (and ignored) while
            # the buttons are still disabled.
            self.update()
            self.button.configure(state="normal")
            self.reset_button.configure(state="normal")

    def reset(self):
        """Delete message_index.csv and protagonist.json after confirmation,
        so the next import starts from scratch (and asks for the protagonist
        again)."""
        if not messagebox.askyesno(
            "Reset Chat Data",
            "Delete all imported messages (message_index.csv) and the protagonist profile "
            "(protagonist.json)?\n\nThis cannot be undone.",
            icon="warning",
            default="no",
            parent=self,
        ):
            return
        for path in (MESSAGE_INDEX_PATH, PROFILE_PATH):
            if os.path.exists(path):
                os.remove(path)
        self.update_total()

    def import_files(self, paths):
        profile = load_profile()
        rows = []
        profile_changed = False
        # Number of files without a matching pattern (incl. unreadable files)
        # and without the protagonist, shown after the import.
        no_pattern = no_protagonist = 0

        files = []
        for path in paths:
            pattern, data = detect(path)
            if pattern:
                files.append((pattern, data))
            else:
                no_pattern += 1
        # Files with only the protagonist's messages first: the profile
        # embedded in them may already identify the protagonist.
        files.sort(key=lambda f: not protagonist_only(f[0]))

        asked = False
        for pattern, data in files:
            try:
                if not protagonist_only(pattern) and not has_profile(profile) and not asked:
                    asked = True
                    if not self.choose_protagonist([f for f in files if not protagonist_only(f[0])], profile):
                        return  # cancelled: nothing is imported
                    profile_changed = True
                protagonist = self.protagonist_for(pattern, data, profile)
                if not protagonist:
                    no_protagonist += 1
                    continue
                rows.extend(pattern.extract(data, set(protagonist)))
            except Exception:
                no_pattern += 1
                continue
            # Learned only from files that were read without error.
            if any([learn(profile, pattern.NAME, identity) for identity in protagonist.values()]):
                save_profile(profile)
                profile_changed = True

        if rows:
            append_to_index(rows)
        # Also without new rows if the profile changed, so the CSV always
        # carries the current protagonist profile.
        if (rows or profile_changed) and os.path.exists(MESSAGE_INDEX_PATH):
            cleaning.clean()

        lines = []
        if no_pattern:
            lines.append(f"Pattern not found in {no_pattern} of {len(paths)} file(s).")
        if no_protagonist:
            lines.append(f"Protagonist not found in {no_protagonist} of {len(paths)} file(s).")
        if lines:
            messagebox.showerror("Import", "\n".join(lines), parent=self)


if __name__ == "__main__":
    App().mainloop()
