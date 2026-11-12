# ---------------------------------------------------------------------------
# Pattern: Signal backup export in JSON Lines format (main.jsonl), Signal
# version 8.35.1.1964.
#
# The export folder (signal-export-<date>/) contains main.jsonl with one JSON
# object per line: first a header ({"version", "backupTimeMs", ...}), then the
# account ({"account": {...}}), the recipients ({"recipient": {"id", "self" |
# "contact" | "group" | ...}}), the chats and the messages ({"chatItem":
# {"chatId", "authorId", "dateSent", "standardMessage", ...}}). "authorId" is
# the id of a recipient; own messages are written by the "self" recipient.
# Ids, timestamps (in ms) and other 64-bit numbers are strings.
# ---------------------------------------------------------------------------
import json
from collections import Counter

# NAME is the platform (shared by all versions and formats, e.g. for
# protagonist.json), VERSION the app version this pattern was written for.
NAME = "signal"
VERSION = "8.35.1.1964"

# Mentions appear in the text as this placeholder, the mentioned person in
# "bodyRanges".
MENTION = "\ufffc"


def load(path):
    """Parse the file into {"account": {...}, "recipients": {id: {...}},
    "messages": [...]}, or None if it is not a Signal JSONL export."""
    if not path.lower().endswith(".jsonl"):
        return None
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records or "backupTimeMs" not in records[0]:
        return None
    data = {"account": {}, "recipients": {}, "messages": []}
    for record in records[1:]:
        if "account" in record:
            data["account"] = record["account"]
        elif "recipient" in record:
            data["recipients"][record["recipient"]["id"]] = record["recipient"]
        elif "chatItem" in record:
            data["messages"].append(record["chatItem"])
    return data


def _sender(recipient):
    """Sender id of a recipient that stays the same across exports (the
    recipient ids are numbered per export): "self" for the own account,
    otherwise the account id (ACI), phone number or phone number id (PNI)."""
    if "self" in recipient:
        return "self"
    contact = recipient["contact"]
    return contact.get("aci") or contact.get("e164") or contact.get("pni") or "recipient " + recipient["id"]


def _texts(data):
    """(sender id, recipient, text object, message) of every message written
    by a person: normal messages and replies to stories. Calls, group changes
    etc. are skipped."""
    for message in data["messages"]:
        if "standardMessage" in message:
            text = message["standardMessage"].get("text")
        elif "directStoryReplyMessage" in message:
            text = message["directStoryReplyMessage"].get("textReply", {}).get("text")
        else:
            continue
        recipient = data["recipients"].get(message.get("authorId"), {})
        if "self" in recipient or "contact" in recipient:
            yield _sender(recipient), recipient, text or {}, message


def message_counts(data):
    """Sender id -> number of messages (to sort the protagonist dialog)."""
    return Counter(sender for sender, _, _, _ in _texts(data))


def _full_name(person, given, family):
    return " ".join(filter(None, (person.get(given), person.get(family))))


def _names(contact):
    """Name in the own address book, nickname and name of the Signal profile."""
    nickname = contact.get("nickname") or {}
    return [
        _full_name(contact, "systemGivenName", "systemFamilyName"),
        _full_name(nickname, "given", "family"),
        _full_name(contact, "profileGivenName", "profileFamilyName"),
    ]


def identities(data):
    """Sender id -> what the export reveals about the sender, compared with
    the protagonist profile. The own account has the profile name and the
    username (the own phone number is not exported); contacts have names,
    phone number (e164, without "+"), username and the account id (ACI),
    which is stored as id."""
    result = {}
    for sender, recipient, _, _ in _texts(data):
        if sender in result:
            continue
        if "self" in recipient:
            account = data["account"]
            identity = {
                "names": [_full_name(account, "givenName", "familyName")],
                "usernames": [account.get("username")],
            }
        else:
            contact = recipient["contact"]
            identity = {
                "names": _names(contact),
                "phone_numbers": [contact.get("e164")],
                "usernames": [contact.get("username")],
            }
            if contact.get("aci"):
                identity["id"] = contact["aci"]
        result[sender] = identity
    return result


def suggested_ids(data):
    """The owner of the export (the "self" recipient) is the most likely
    protagonist."""
    return ["self"]


def _mention_names(data):
    """ACI -> name of every contact, to write mentions as "@Name"."""
    names = {}
    for recipient in data["recipients"].values():
        contact = recipient.get("contact", {})
        name = next(filter(None, _names(contact)), None)
        if contact.get("aci") and name:
            names[contact["aci"]] = name
    return names


def _text(text, mention_names):
    """The message text with mentions replaced by "@Name" (or removed if the
    person is unknown). Edited messages are exported in their latest version,
    the earlier ones are in "revisions" and ignored."""
    body = text.get("body", "")
    mentions = sorted((r for r in text.get("bodyRanges", []) if "mentionAci" in r),
                      key=lambda r: int(r.get("start", 0)))
    for mention in mentions:
        name = mention_names.get(mention["mentionAci"])
        body = body.replace(MENTION, "@" + name if name else "", 1)
    return body.replace("\r\n", "\n").replace("\r", "\n").replace(MENTION, "").strip()


def extract(data, protagonist_ids):
    """(text, timestamp) of every message written by the protagonist.
    Attachments without caption, stickers, deleted messages etc. have no text
    and are skipped."""
    mention_names = _mention_names(data)
    rows = []
    for sender, _, text, message in _texts(data):
        if sender not in protagonist_ids:
            continue
        text = _text(text, mention_names)
        if text:
            rows.append((text, int(message["dateSent"]) // 1000))
    return rows
