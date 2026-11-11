const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");

const USERS_DIR = path.join(__dirname, "..", "users");

if (!fs.existsSync(USERS_DIR)) {
  fs.mkdirSync(USERS_DIR);
}

// Reversible file name for a phone number / sender name: digits, letters and
// "+" stay readable, everything else (incl. "/") is percent-encoded, so
// different senders never share a file and no path can escape USERS_DIR.
function encodePhone(phone) {
  return encodeURIComponent(phone).replace(/%2B/g, "+");
}

function decodePhone(name) {
  try {
    return decodeURIComponent(name);
  } catch {
    return name;
  }
}

function getContactFile(phone) {
  return path.join(USERS_DIR, `${encodePhone(phone)}.json`);
}

function loadContact(phone) {
  const file = getContactFile(phone);
  if (!fs.existsSync(file)) return { messages: [] };
  let contact;
  try {
    contact = JSON.parse(fs.readFileSync(file, "utf8"));
    if (!Array.isArray(contact.messages)) contact.messages = [];
  } catch (e) {
    // Keep the unreadable file for inspection instead of overwriting it on
    // the next save, and start with an empty history.
    const backup = `${file}.broken-${Date.now()}`;
    fs.renameSync(file, backup);
    console.error(`Corrupt contact file moved to ${backup}:`, e.message);
    return { messages: [] };
  }

  // Bring messages stored in an older format up to date (persisted right away).
  const normalized = contact.messages.map(normalizeMessage);
  if (JSON.stringify(normalized) !== JSON.stringify(contact.messages)) {
    contact.messages = normalized;
    saveContact(phone, contact);
  }
  return contact;
}

// Every message has the same fields: its own UUID, plus `failed` and `error`
// (false / null when it was sent or received without problems).
function normalizeMessage(message) {
  return {
    id: message.id || randomUUID(),
    ...message,
    failed: message.failed === true,
    error: message.error ?? null,
  };
}

function saveContact(phone, data) {
  const file = getContactFile(phone);
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

// Append a message (incoming or outgoing) with its own UUID.
function addMessage(phone, message) {
  const contact = loadContact(phone);
  contact.messages.push(normalizeMessage(message));
  saveContact(phone, contact);
}

// Daily message-request counter, kept in the contact file so it survives
// server restarts. A counter from an earlier day (server time) starts at 0.
function getMessageRequests(phone) {
  const today = new Date().toDateString();
  const stored = loadContact(phone).messageRequests;
  if (stored && stored.day === today) return stored;
  return { day: today, count: 0, limitNotified: false };
}

function saveMessageRequests(phone, requests) {
  const contact = loadContact(phone);
  contact.messageRequests = requests;
  saveContact(phone, contact);
}

function getAllContacts() {
  const files = fs.readdirSync(USERS_DIR);
  return files
    .filter((f) => f.endsWith(".json"))
    .map((f) => decodePhone(f.slice(0, -".json".length)));
}

// Bring all existing messages up to date once at startup.
getAllContacts().forEach(loadContact);

module.exports = {
  loadContact,
  addMessage,
  getAllContacts,
  getMessageRequests,
  saveMessageRequests,
};
