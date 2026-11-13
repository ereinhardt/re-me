require("dotenv").config();

if (process.env.SERVER_DEBUG !== "1") {
  console.log = () => {};
  console.warn = () => {};
  console.error = () => {};
} else {
  const _log = console.log,
    _err = console.error;
  const _ts = () =>
    `[${new Date().toISOString().replace("T", " ").slice(0, 23)}]`;
  console.log = (...a) => _log(_ts(), ...a);
  console.error = (...a) => _err(_ts(), ...a);
}

const express = require("express");
const path = require("path");
const os = require("os");
const app = express();

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

// Lokales Matching initialisieren (ONNX-Encoder laden + CSV neu embedden),
// danach das Gateway-Polling starten. Die HTTP-Routen werden sofort
// registriert, damit das Settings-Interface schon während des Modell-Ladens
// funktioniert.
const {
  registerGatewayRoutes,
  startGatewayPolling,
} = require("./backend/bravis-one-gateway");
const { initMatching, countMessages } = require("./backend/matching");

registerGatewayRoutes(app);

// Readiness of the local matching (models loaded + vector index built) and the
// number of messages in message_index.csv.
let matchingStatus = "loading"; // "loading" | "ready"
app.get("/api/status", (req, res) => {
  res.json({
    status: matchingStatus,
    messages: countMessages(),
  });
});

initMatching()
  .then(() => {
    matchingStatus = "ready";
    process.stdout.write(
      `Gateway Interface: https://${process.env.BRAVIS_GATEWAY_IP || "192.168.1.100"}\n`,
    );
    startGatewayPolling(1000);
  })
  .catch((err) => {
    process.stderr.write(`Matching initialisation failed: ${err.message}\n`);
    process.exit(1);
  });

// Static files ("/" serves frontend/index.html)
app.use(express.static(path.join(__dirname, "frontend")));

app.listen(PORT, HOST, () => {
  process.stdout.write(`Settings Interface: http://${HOST}:${PORT}\n`);
});
