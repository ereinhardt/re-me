# ---------------------------------------------------------------------------
# Pattern: WhatsApp chat export, WhatsApp version 26.44.72.
#
# Accepts the ZIP exactly as WhatsApp hands it out ("WhatsApp Chat - X.zip",
# containing _chat.txt) or the extracted .txt file. Supported line formats:
#   iOS:     [05.06.25, 17:29:57] Name: text
#   Android: 05.06.25, 17:29 - Name: text
# Lines that do not start with a header belong to the previous message
# (multi-line messages). Times are interpreted as local time of this machine.
# ---------------------------------------------------------------------------
import re
import zipfile
from collections import Counter
from datetime import datetime

# NAME is the platform (shared by all versions, e.g. for protagonist.json),
# VERSION the app version this pattern was written for.
NAME = "whatsapp"
VERSION = "26.44.72"

# Header lines of media/system messages start with an invisible
# left-to-right mark (\u200e).
LINE_FORMATS = [
    re.compile(r"^\u200e?\[(\d{1,2}\.\d{1,2}\.\d{2,4}), (\d{1,2}:\d{2}(?::\d{2})?)\] ([^:]+): (.*)$"),
    re.compile(r"^\u200e?(\d{1,2}\.\d{1,2}\.\d{2,4}), (\d{1,2}:\d{2}(?::\d{2})?) - ([^:]+): (.*)$"),
]
PHONE_NUMBER = re.compile(r"^\+[\d\s()-]{6,}$")


def _read_text(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".txt")]
            if not names:
                return None
            name = "_chat.txt" if "_chat.txt" in names else names[0]
            return archive.read(name).decode("utf-8-sig", errors="replace")
    if path.lower().endswith(".txt"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    return None


def _parse_time(date, time):
    day, month, year = date.split(".")
    year = int(year) + (2000 if len(year) == 2 else 0)
    hour, minute, second = ([int(p) for p in time.split(":")] + [0])[:3]
    return int(datetime(year, int(month), int(day), hour, minute, second).timestamp())


def load(path):
    """Parse the file into a list of [sender, timestamp, raw text], or None if
    it is not a WhatsApp export."""
    text = _read_text(path)
    if not text:
        return None

    messages = []
    for line in text.replace("\r", "").split("\n"):
        match = next((m for m in (f.match(line) for f in LINE_FORMATS) if m), None)
        if match:
            date, time, sender, body = match.groups()
            messages.append([sender.strip(), _parse_time(date, time), body])
        elif messages:
            messages[-1][2] += "\n" + line
        elif line.strip():
            # Text before the first message header: not a WhatsApp export.
            return None
    return messages or None


def message_counts(messages):
    """Sender id -> number of messages (to sort the protagonist dialog)."""
    return Counter(sender for sender, _, _ in messages)


def identities(messages):
    """Sender id -> what the export reveals about the sender, compared with
    the protagonist profile: contacts appear by name, unsaved numbers as
    phone number (wrapped in invisible direction marks). WhatsApp has no
    sender ids, and the own messages always appear under the own name."""
    result = {}
    for sender in {sender for sender, _, _ in messages}:
        plain = sender.strip("\u202a\u202c\u200e").strip()
        if PHONE_NUMBER.match(plain):
            result[sender] = {"phone_numbers": [plain]}
        else:
            result[sender] = {"names": [plain]}
    return result


def extract(messages, protagonist_ids):
    """(text, timestamp) of every message written by the protagonist. The
    text is taken as exported, including WhatsApp's own notices ("Bild
    weggelassen", "Du hast diese Nachricht gelöscht." etc.)."""
    rows = []
    for sender, timestamp, raw in messages:
        if sender not in protagonist_ids:
            continue
        text = raw.strip()
        if text:
            rows.append((text, timestamp))
    return rows
