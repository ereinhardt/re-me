require("dotenv").config();
const express = require("express");
const fs = require("fs");
const path = require("path");
const os = require("os");
const app = express();

// Users-Ordner erstellen, falls nicht vorhanden
const usersDir = path.join(__dirname, "users");
if (!fs.existsSync(usersDir)) {
  fs.mkdirSync(usersDir);
}

// Message-Data-Ordner erstellen, falls nicht vorhanden
const messageDataDir = path.join(__dirname, "message-data");
if (!fs.existsSync(messageDataDir)) {
  fs.mkdirSync(messageDataDir);
}

app.use(express.json());

// Funktion um die Netzwerk-IP zu ermitteln
function getNetworkIP() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === "IPv4" && !iface.internal) {
        return iface.address;
      }
    }
  }
  return "localhost";
}

const LOCALHOST_FLAG = process.env.LOCALHOST || "0";
const HOST = LOCALHOST_FLAG === "1" ? "localhost" : getNetworkIP();
const PORT = process.env.SERVER_PORT || 3000;

// Gateway initialisieren
const { initGateway } = require("./backend/bravis-one-gateway");
initGateway(app, 1000);

// Static files
app.use(express.static(path.join(__dirname, "frontend")));

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "frontend", "index.html"));
});

app.listen(PORT, HOST, () => {
  console.log(`Settings Interface: http://${HOST}:${PORT}`);
});
