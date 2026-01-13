const fs = require("fs");
const path = require("path");

const USERS_DIR = path.join(
  __dirname,
  "..",
  process.env.USERS_FOLDER || "users"
);

if (!fs.existsSync(USERS_DIR)) {
  fs.mkdirSync(USERS_DIR);
}

function sanitizePhone(phone) {
  return phone.replace(/[^0-9+]/g, "_");
}

function getContactFile(phone) {
  return path.join(USERS_DIR, `${sanitizePhone(phone)}.json`);
}

function loadContact(phone) {
  const file = getContactFile(phone);
  if (fs.existsSync(file)) {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  }
  return { messages: [] };
}

function saveContact(phone, data) {
  const file = getContactFile(phone);
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

function getAllContacts() {
  const files = fs.readdirSync(USERS_DIR);
  return files
    .filter((f) => f.endsWith(".json"))
    .map((f) => f.replace(".json", ""));
}

function messageExists(phone, text, timestamp) {
  const contact = loadContact(phone);
  return contact.messages.some(
    (m) => m.text === text && m.timestamp === timestamp
  );
}

module.exports = {
  loadContact,
  saveContact,
  getAllContacts,
  messageExists,
};
