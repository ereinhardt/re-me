# ---------------------------------------------------------------------------
# Pattern: re: me message index, re: me version 3.1.
#
# Accepts a CSV in the format of the final message-data/message_index.csv
# (e.g. a backup or the dataset of another installation):
#   message-content,timestamp,message-id,protagonist
# The file is recognised by exactly this header (older files without the
# column "protagonist" as well). It contains only messages of the protagonist
# and no senders, so PROTAGONIST_ONLY tells import.py to take all rows without
# determining the protagonist. Existing message ids are kept; rows without
# one get a new id when appended.
#
# The column "protagonist" holds the protagonist profile as JSON (embedded by
# cleaning.py, same structure as protagonist.json). The profiles of all rows
# are merged and reported by identities(), so import.py can add them to
# protagonist.json.
# ---------------------------------------------------------------------------
import csv
import json

# NAME is the platform (shared by all versions), VERSION the re: me version
# whose message_index.csv this pattern reads.
NAME = "reme"
VERSION = "3.1"
PROTAGONIST_ONLY = True

HEADER = ["message-content", "timestamp", "message-id", "protagonist"]
SENDER = "protagonist"
PROFILE_FIELDS = ("names", "phone_numbers", "usernames")


def _merge(profile, embedded):
    """Add the values of an embedded profile (JSON) to `profile`; invalid
    JSON is ignored."""
    try:
        embedded = json.loads(embedded)
    except ValueError:
        return
    if not isinstance(embedded, dict):
        return
    for field in PROFILE_FIELDS:
        for value in embedded.get(field) or []:
            if value not in profile[field]:
                profile[field].append(value)
    for platform, ids in (embedded.get("ids") or {}).items():
        known = profile["ids"].setdefault(platform, [])
        known.extend(i for i in ids if i not in known)
    for platform in embedded.get("platforms") or []:
        if platform not in profile["platforms"]:
            profile["platforms"].append(platform)


def load(path):
    """Parse the file into {"messages": [(text, timestamp, message id)],
    "profile": {...}}, or None if it is not a message index."""
    if not path.lower().endswith(".csv"):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        header, *rows = list(csv.reader(f)) or [[]]
    if [h.strip() for h in header] not in (HEADER, HEADER[:3]):
        return None

    messages = []
    profile = {field: [] for field in PROFILE_FIELDS}
    profile["ids"] = {}
    profile["platforms"] = []
    for row in rows:
        if len(row) < 2:
            continue
        if len(row) > 3 and row[3].strip():
            _merge(profile, row[3])
        text = row[0].strip()
        try:
            timestamp = int(row[1])
        except ValueError:
            continue
        if text:
            messages.append((text, timestamp, row[2].strip() if len(row) > 2 else ""))
    return {"messages": messages, "profile": profile} if messages else None


def message_counts(data):
    return {SENDER: len(data["messages"])}


def identities(data):
    """One sender with the embedded protagonist profile (ids of all
    platforms under "ids", the platforms already asked for under
    "platforms")."""
    return {SENDER: data["profile"]}


def extract(data, protagonist_ids):
    """(text, timestamp, message id) of every message."""
    return list(data["messages"])
