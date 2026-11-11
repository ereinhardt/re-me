# ---------------------------------------------------------------------------
# Pattern: Telegram Desktop export in JSON format (result.json), Telegram version 12.10.28298.
#
# Works for the full account export ({"chats": {"list": [...]}}) as well as
# for a single exported chat ({"name", "type", "messages": [...]}). The HTML
# export is handled by pattern_telegram_html_12.10.28298.py (Telegram asks
# which formats to export: HTML, JSON or both).
# ---------------------------------------------------------------------------
import json
from collections import Counter
from datetime import datetime

# NAME is the platform (shared by all versions and formats, e.g. for
# protagonist.json), VERSION the app version this pattern was written for.
NAME = "telegram"
VERSION = "12.10.28298"


def load(path):
    """Parse the file into {"chats": [...], "me": {...}, "contacts": [...]},
    or None if it is not a Telegram JSON export."""
    if not path.lower().endswith(".json"):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("chats"), dict) and isinstance(data["chats"].get("list"), list):
        chats = data["chats"]["list"]
    elif isinstance(data.get("messages"), list) and "type" in data:
        chats = [data]
    else:
        return None
    contacts = data.get("contacts")
    return {
        "chats": chats,
        "me": data.get("personal_information") or {},
        "contacts": contacts.get("list", []) if isinstance(contacts, dict) else [],
    }


def _messages(data):
    for chat in data["chats"]:
        for message in chat.get("messages", []):
            if message.get("type") == "message" and message.get("from_id") is not None:
                yield message


def _sender_id(message):
    # Newer exports use "user123", older ones the plain number.
    return str(message["from_id"]).removeprefix("user")


def _names(data):
    """(sender id -> display name, sender id -> message count)"""
    counts = Counter()
    names = {}
    for message in _messages(data):
        sender = _sender_id(message)
        counts[sender] += 1
        names.setdefault(sender, message.get("from") or "Deleted account")
    return names, counts


def message_counts(data):
    """Sender id -> number of messages (to sort the protagonist dialog)."""
    return _names(data)[1]


def _full_name(person):
    return " ".join(filter(None, (person.get("first_name"), person.get("last_name"))))


def identities(data):
    """Sender id -> what the export knows about the sender, compared with the
    protagonist profile: the display name, for the export owner also the
    account name, phone number and username (personal_information), for
    others the phone number from the contact list if a contact with the same
    name exists."""
    names, _ = _names(data)
    contacts = {_full_name(contact): contact for contact in data["contacts"]}
    me = data["me"]
    result = {}
    for sender, name in names.items():
        identity = {"id": sender, "names": [name], "phone_numbers": [], "usernames": []}
        if str(me.get("user_id")) == sender:
            identity["names"].append(_full_name(me))
            identity["phone_numbers"].append(me.get("phone_number"))
            identity["usernames"].append(me.get("username"))
        elif name in contacts:
            identity["phone_numbers"].append(contacts[name].get("phone_number"))
        result[sender] = identity
    return result


def suggested_ids(data):
    """The export owner is the most likely protagonist."""
    user_id = data["me"].get("user_id")
    return [str(user_id)] if user_id is not None else []


def _text(message):
    # "text" is a string, or a list of strings and formatted parts. Some
    # messages use "\r" as line break; the HTML export shows "\n" for them.
    text = message.get("text", "")
    if isinstance(text, list):
        text = "".join(part if isinstance(part, str) else part.get("text", "") for part in text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def extract(data, protagonist_ids):
    """(text, timestamp) of every message written by the protagonist.
    Media without caption, stickers etc. have no text and are skipped."""
    rows = []
    for message in _messages(data):
        if _sender_id(message) not in protagonist_ids:
            continue
        text = _text(message)
        if text:
            rows.append((text, _timestamp(message)))
    return rows


def _timestamp(message):
    # "date_unixtime" is missing in older exports; "date" is local time.
    if "date_unixtime" in message:
        return int(message["date_unixtime"])
    return int(datetime.fromisoformat(message["date"]).timestamp())
