#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Chat export import.
#
# Opens a small window to choose one or more chat exports (as handed out by
# the apps, e.g. raw-data/whatsapp/*.zip, raw-data/telegram/.../result.json
# or, for Telegram's HTML export, .../export_results.html).
# For every file the pattern is detected, the protagonist is determined, and
# only the protagonist's messages are appended to
# message-data/message_index.csv. Afterwards cleaning.py removes exact
# duplicates. The export files themselves are not modified.
#
# Patterns live in the patterns/ folder and are named after the app (and
# export format, if the app offers several) and the app version they were
# written for, e.g. pattern_whatsapp_26.44.72.py or
# pattern_telegram_html_12.10.28298.py. If a platform changes its export
# format, add a new file for the new version next to the old one; all
# pattern_*.py files are picked up automatically.
#
# The protagonist is asked for only once, on the very first import, and stored
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
# wrote), as are files no pattern can read or that cause an error; if the
# protagonist goes by a name not known yet, add it to
# patterns/protagonist.json.
#
# Usage (from the Server directory):
#   python3 tools/data-extraction/start.py
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
PROFILE_PATH = os.path.join(PATTERNS_DIR, "protagonist.json")
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


def matches(profile, platform, identity):
    if identity.get("id") in profile["ids"].get(platform, []):
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
    if identity.get("id"):
        ids = profile["ids"].setdefault(platform, [])
        if identity["id"] not in ids:
            ids.append(identity["id"])
            new.append(f"{platform} id {identity['id']}")
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
    """Append (text, timestamp) rows with a new UUID as message id. The
    message-data folder and the CSV (with header) are created if missing."""
    content = ""
    if os.path.exists(MESSAGE_INDEX_PATH):
        with open(MESSAGE_INDEX_PATH, encoding="utf-8", newline="") as f:
            content = f.read()
    needs_newline = bool(content) and not content.endswith("\n")

    os.makedirs(os.path.dirname(MESSAGE_INDEX_PATH), exist_ok=True)
    with open(MESSAGE_INDEX_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not content:
            writer.writerow(["message-content", "timestamp", "message-id"])
        elif needs_newline:
            f.write("\r\n")
        for text, timestamp in rows:
            writer.writerow([text, timestamp, str(uuid.uuid4())])


class ProtagonistDialog(tk.Toplevel):
    """Asks which sender(s) in a file are the protagonist (only while the
    profile is still empty). Each sender is shown with exactly the
    information that is stored in protagonist.json when it is chosen; senders
    with the most messages come first. `result` is the list of chosen sender
    ids, or None if the file should be skipped."""

    def __init__(self, parent, pattern, identities, counts, suggested):
        super().__init__(parent)
        self.title("Protagonist")
        self.transient(parent)
        self.result = None

        tk.Label(self, text="Choose Protagonist:").pack(anchor="w", padx=10, pady=(10, 4))

        self.ids = sorted(identities, key=lambda s: -counts.get(s, 0))
        self.listbox = tk.Listbox(self, selectmode=tk.MULTIPLE, width=70, height=min(len(self.ids), 15))
        for i, sender in enumerate(self.ids):
            self.listbox.insert(tk.END, describe(pattern.NAME, identities[sender]))
            if sender in suggested:
                self.listbox.selection_set(i)
        self.listbox.pack(fill="both", expand=True, padx=10)

        tk.Label(self, text="This choice cannot be changed later.").pack(anchor="w", padx=10, pady=(6, 0))

        buttons = tk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=10)
        tk.Button(buttons, text="OK", command=self.ok).pack(side="right")
        tk.Button(buttons, text="Skip file", command=self.destroy).pack(side="right", padx=6)

        self.grab_set()
        self.wait_window()

    def ok(self):
        selection = [self.ids[i] for i in self.listbox.curselection()]
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

        self.button = tk.Button(self, text="Choose export file(s)…", command=self.run)
        self.button.pack(padx=20, pady=20)

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
        identities = pattern.identities(data)
        if any(profile[field] for field in PROFILE_FIELDS) or any(profile["ids"].values()):
            chosen = [s for s, identity in identities.items() if matches(profile, pattern.NAME, identity)]
        else:
            suggested = getattr(pattern, "suggested_ids", lambda d: [])(data)
            dialog = ProtagonistDialog(self, pattern, identities, pattern.message_counts(data), suggested)
            chosen = dialog.result or []
        return {s: identities[s] for s in chosen}

    def run(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Choose chat exports",
            initialdir=os.path.abspath(RAW_DATA_DIR),
            filetypes=[("Chat exports", "*.zip *.txt *.json *.html"), ("All files", "*")],
        )
        if not paths:
            return

        self.button.configure(state="disabled")
        self.update_idletasks()
        try:
            self.import_files(paths)
        finally:
            self.update_total()
            # Clicks made during the import are handled (and ignored) while
            # the button is still disabled.
            self.update()
            self.button.configure(state="normal")

    def import_files(self, paths):
        profile = load_profile()
        rows = []

        for path in paths:
            try:
                pattern, data = detect(path)
                if not pattern:
                    continue
                protagonist = self.protagonist_for(pattern, data, profile)
                if not protagonist:
                    continue
                rows.extend(pattern.extract(data, set(protagonist)))
            except Exception:
                continue  # unreadable or unexpected file: skipped
            # Learned only from files that were read without error.
            if any([learn(profile, pattern.NAME, identity) for identity in protagonist.values()]):
                save_profile(profile)

        if rows:
            append_to_index(rows)
            cleaning.clean()


if __name__ == "__main__":
    App().mainloop()
