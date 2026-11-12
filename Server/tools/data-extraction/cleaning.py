#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Removes exact duplicates from message_index.csv: rows whose message-content
# is character-for-character identical. Of each group the oldest message
# (smallest timestamp) is kept; the order of the remaining rows is unchanged.
#
# Also embeds the protagonist profile (patterns/protagonist.json) as JSON in
# the column "protagonist" of every row, so the CSV always carries it along
# (read again by patterns/pattern_reme_csv_*.py). Files without the column
# are converted. If there is no protagonist.json, the column is left as is.
#
# Runs automatically after every import from import.py, or on its own:
#   python3 tools/data-extraction/cleaning.py
# ---------------------------------------------------------------------------
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MESSAGE_INDEX_PATH = os.path.join(HERE, "..", "..", "message-data", "message_index.csv")
PROFILE_PATH = os.path.join(HERE, "patterns", "protagonist.json")
HEADER = ["message-content", "timestamp", "message-id", "protagonist"]


def _protagonist():
    """The protagonist profile as compact JSON, or None if there is none."""
    if not os.path.exists(PROFILE_PATH):
        return None
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.dumps(json.load(f), ensure_ascii=False, separators=(",", ":"))


def _timestamp(row):
    try:
        return int(row[1])
    except (IndexError, ValueError):
        return float("inf")


def clean(path=MESSAGE_INDEX_PATH):
    """Rewrite the CSV without duplicates and with the current protagonist
    profile in every row. Returns the number of removed rows."""
    with open(path, encoding="utf-8", newline="") as f:
        _, *rows = list(csv.reader(f))
    rows = [row for row in rows if row]  # blank lines
    protagonist = _protagonist()
    for row in rows:
        row[:] = (row + [""] * len(HEADER))[: len(HEADER)]
        if protagonist is not None:
            row[3] = protagonist

    oldest = {}  # message-content -> index of the oldest row
    for i, row in enumerate(rows):
        text = row[0]
        if text not in oldest or _timestamp(row) < _timestamp(rows[oldest[text]]):
            oldest[text] = i
    keep = sorted(oldest.values())

    # Written to a temporary file first and then swapped in, so a crash while
    # writing never leaves a half-written message_index.csv behind.
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows[i] for i in keep)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)
    return len(rows) - len(keep)


if __name__ == "__main__":
    removed = clean()
    print(f"Removed {removed} duplicate message(s) from message_index.csv")
