#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Removes exact duplicates from message_index.csv: rows whose message-content
# is character-for-character identical. Of each group the oldest message
# (smallest timestamp) is kept; the order of the remaining rows is unchanged.
#
# Runs automatically after every import from start.py, or on its own:
#   python3 tools/data-extraction/cleaning.py
# ---------------------------------------------------------------------------
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MESSAGE_INDEX_PATH = os.path.join(HERE, "..", "..", "message-data", "message_index.csv")


def _timestamp(row):
    try:
        return int(row[1])
    except (IndexError, ValueError):
        return float("inf")


def clean(path=MESSAGE_INDEX_PATH):
    """Rewrite the CSV without duplicates. Returns the number of removed rows."""
    with open(path, encoding="utf-8", newline="") as f:
        header, *rows = list(csv.reader(f))

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
        writer.writerow(header)
        writer.writerows(rows[i] for i in keep)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)
    return len(rows) - len(keep)


if __name__ == "__main__":
    removed = clean()
    print(f"Removed {removed} duplicate message(s) from message_index.csv")
