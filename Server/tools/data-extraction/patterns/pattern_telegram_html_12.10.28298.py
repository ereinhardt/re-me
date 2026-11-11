# ---------------------------------------------------------------------------
# Pattern: Telegram Desktop export in HTML format, Telegram version 12.10.28298.
#
# Choose export_results.html of a full account export (all chats in
# chats/*/messages*.html are read) or any messages*.html of a chat (all pages
# of that chat are read). The JSON export is handled by
# pattern_telegram_json_12.10.28298.py (Telegram asks which formats to
# export: HTML, JSON or both).
#
# Unlike the JSON export, the HTML has no sender ids: senders are identified
# by their display name. Follow-up messages ("joined") carry no name and
# belong to the previous sender. Dates are written in the language of the
# app ("18 Mai 2026, 12:01:01") and read by dates.py.
# ---------------------------------------------------------------------------
import glob
import os
import re
from collections import Counter
from html.parser import HTMLParser

import dates

# NAME is the platform (shared by all versions and formats, e.g. for
# protagonist.json), VERSION the app version this pattern was written for.
NAME = "telegram"
VERSION = "12.10.28298"

AUTHOR_PHOTO = re.compile(r"photos/author_(\d+)")
PHONE_NUMBER = re.compile(r"^\+?[\d\s]{6,}$")


class _Divs(HTMLParser):
    """Flat list of [classes, attrs, text] in document order for every <div>
    with one of the `wanted` classes and every userpic <img>. Text is only
    collected for divs with one of the `captured` classes (<br> as newline)."""

    def __init__(self, wanted, captured):
        super().__init__()
        self.wanted = set(wanted)
        self.captured = set(captured)
        self.items = []
        self.open = []  # one entry per open <div>: its item if captured, else None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "div":
            item = None
            if self.wanted.intersection(classes):
                item = [classes, attrs, ""]
                self.items.append(item)
            self.open.append(item if self.captured.intersection(classes) else None)
        elif tag == "img" and "userpic" in classes:
            self.items.append([classes, attrs, ""])
        elif tag == "br":
            self.handle_data("\n")

    def handle_endtag(self, tag):
        if tag == "div" and self.open:
            self.open.pop()

    def handle_data(self, data):
        for item in self.open:
            if item is not None:
                item[2] += data


def _divs(path, wanted, captured):
    parser = _Divs(wanted, captured)
    with open(path, encoding="utf-8", errors="replace") as f:
        parser.feed(f.read())
    parser.close()
    return parser.items


def _page_number(path):
    # messages.html, messages2.html, ..., messages10.html
    number = os.path.basename(path)[len("messages"):-len(".html")]
    return int(number) if number else 1


def _chat_pages(path):
    """Message pages per chat, each chat's pages in order."""
    folder = os.path.dirname(os.path.abspath(path))
    if os.path.basename(path).lower() == "export_results.html":
        chat_folders = sorted(glob.glob(os.path.join(folder, "chats", "*")))
    elif re.fullmatch(r"messages\d*\.html", os.path.basename(path).lower()):
        chat_folders = [folder]
    else:
        return []
    chats = []
    for chat_folder in chat_folders:
        pages = sorted(glob.glob(os.path.join(chat_folder, "messages*.html")), key=_page_number)
        if pages:
            chats.append(pages)
    return chats


def _read_chat(pages):
    """[{"sender", "photo_id", "timestamp", "text"}] of all messages of a chat.
    Service messages (dates, calls, pins, ...) are skipped."""
    messages = []
    current = None
    sender = None
    for page in pages:
        for classes, attrs, text in _divs(page, ("message", "date", "from_name", "text"), ("from_name", "text")):
            if "message" in classes:
                current = None
                if "default" in classes:
                    current = {"sender": None if "joined" in classes else "", "photo_id": None, "timestamp": None, "text": ""}
                    messages.append(current)
            elif current is None:
                continue
            elif "userpic" in classes:
                match = AUTHOR_PHOTO.search(attrs.get("src") or "")
                current["photo_id"] = match and match[1]
            elif "date" in classes and current["timestamp"] is None and attrs.get("title"):
                current["timestamp"] = dates.timestamp(attrs["title"])
            elif "from_name" in classes:
                sender = text.strip()
                current["sender"] = sender
            elif "text" in classes and not current["text"]:
                current["text"] = text.strip()
            if current is not None and current["sender"] is None:
                current["sender"] = sender  # joined: same sender as before
    return [m for m in messages if m["sender"] and m["timestamp"] is not None]


def _personal_information(folder):
    """{"name", "username", "phone_number"} of the export owner, if the
    export contains personal_information.html."""
    path = os.path.join(folder, "personal_information.html")
    if not os.path.exists(path):
        return {}
    values = [text.strip() for _, _, text in _divs(path, ("value",), ("value",))]
    me = {}
    for value in values:
        if value.startswith("@"):
            me["username"] = value[1:]
        elif PHONE_NUMBER.match(value):
            me["phone_number"] = value
        elif "name" not in me:
            me["name"] = value
    return me


def _contacts(folder):
    """Contact name -> phone number from contacts.html."""
    path = os.path.join(folder, "contacts.html")
    if not os.path.exists(path):
        return {}
    contacts = {}
    name = None
    for classes, _, text in _divs(path, ("name", "subname"), ("name", "subname")):
        if "name" in classes:
            name = text.strip()
        elif name and PHONE_NUMBER.match(text.strip()):
            contacts[name] = text.strip()
    return contacts


def load(path):
    """Parse the export into {"messages": [...], "me": {...}, "contacts": {...}},
    or None if it is not a Telegram HTML export."""
    chats = _chat_pages(path)
    if not chats:
        return None
    with open(chats[0][0], encoding="utf-8", errors="replace") as f:
        if 'class="history"' not in f.read():
            return None
    messages = [m for pages in chats for m in _read_chat(pages)]
    if not messages:
        return None

    # A full export has personal_information.html next to export_results.html,
    # i.e. two levels above the message pages.
    root = os.path.dirname(os.path.abspath(path))
    if os.path.basename(path).lower() != "export_results.html":
        root = os.path.dirname(os.path.dirname(root))
    return {"messages": messages, "me": _personal_information(root), "contacts": _contacts(root)}


def message_counts(data):
    """Sender -> number of messages (to sort the protagonist dialog)."""
    return Counter(m["sender"] for m in data["messages"])


def identities(data):
    """Sender -> what the export knows about the sender, compared with the
    protagonist profile: the display name, the Telegram id if the sender has a
    profile photo (photos/author_<id>.jpg), for the export owner also phone
    number and username, for others the phone number from contacts.html."""
    photo_ids = {}
    for m in data["messages"]:
        if m["photo_id"]:
            photo_ids.setdefault(m["sender"], m["photo_id"])
    me = data["me"]
    result = {}
    for sender in {m["sender"] for m in data["messages"]}:
        identity = {"names": [sender], "phone_numbers": [], "usernames": []}
        if sender in photo_ids:
            identity["id"] = photo_ids[sender]
        if sender == me.get("name"):
            identity["phone_numbers"].append(me.get("phone_number"))
            identity["usernames"].append(me.get("username"))
        else:
            identity["phone_numbers"].append(data["contacts"].get(sender))
        result[sender] = identity
    return result


def suggested_ids(data):
    """The export owner is the most likely protagonist."""
    name = data["me"].get("name")
    return [name] if name else []


def extract(data, protagonist_ids):
    """(text, timestamp) of every message written by the protagonist.
    Media without caption, stickers etc. have no text and are skipped."""
    return [(m["text"], m["timestamp"]) for m in data["messages"] if m["sender"] in protagonist_ids and m["text"]]
