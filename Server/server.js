require('dotenv').config();
const express = require('express');
const path = require('path');
const os = require('os');
const app = express();

// Funktion um die Netzwerk-IP zu ermitteln
function getNetworkIP() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

const LOCALHOST_FLAG = process.env.LOCALHOST || '0';
const HOST = LOCALHOST_FLAG === '1' ? 'localhost' : getNetworkIP();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, 'frontend')));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

app.listen(PORT, HOST, () => {
  console.log(`Settings Interface: http://${HOST}:${PORT}`);
});
