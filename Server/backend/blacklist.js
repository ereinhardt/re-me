const fs = require("fs");
const path = require("path");

// Words / phrases a reply must not contain. Edited in the settings interface
// (one entry per line) and stored as a JSON array of strings.
const BLACKLIST_FILE = path.join(__dirname, "blacklist.json");

function loadBlacklist() {
  if (fs.existsSync(BLACKLIST_FILE)) {
    try {
      const terms = JSON.parse(fs.readFileSync(BLACKLIST_FILE, "utf8"));
      if (Array.isArray(terms)) return terms;
    } catch {}
  }
  return [];
}

function saveBlacklist(terms) {
  fs.writeFileSync(BLACKLIST_FILE, JSON.stringify(terms, null, 2));
}

// Compared form: case, Unicode variants and surplus whitespace do not matter.
function normalize(text) {
  return String(text).normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
}

// True if the text contains any blacklisted entry (also inside longer words,
// e.g. "idiot" blocks "Idioten").
function isBlacklisted(text) {
  const t = normalize(text);
  return loadBlacklist().some((term) => {
    const n = normalize(term);
    return n && t.includes(n);
  });
}

function registerRoutes(app) {
  app.get("/api/blacklist", (req, res) => {
    res.json(loadBlacklist());
  });
  // Body: { text: "<one entry per line>" }
  app.post("/api/blacklist", (req, res) => {
    const text = (req.body && req.body.text) || "";
    saveBlacklist(
      String(text)
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    );
    res.json({ success: true });
  });
}

module.exports = { isBlacklisted, registerRoutes };
