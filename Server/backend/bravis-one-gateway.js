const https = require("https");
const { loadContact, addMessage, getAllContacts } = require("./users-storage");
const { handleIncomingMessage } = require("./gateway-message-response");

class BravisOneGateway {
  constructor(ip, username, password) {
    this.ip = ip;
    this.username = username;
    this.password = password;
    this.token = null;
    // The gateway only serves to send and receive: messages received before
    // the server started are ignored, and already handled ones are tracked in
    // memory instead of being looked up in the stored history.
    this.startedAt = Math.floor(Date.now() / 1000);
    this.seenMessages = new Set();
  }

  async login() {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify({
        username: this.username,
        password: this.password,
      });

      const options = {
        hostname: this.ip,
        path: "/api/signin",
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
        },
        rejectUnauthorized: false,
      };

      const req = https.request(options, (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          try {
            const json = JSON.parse(body);
            this.token = json.jwt;
            resolve(this.token);
          } catch (e) {
            reject(e);
          }
        });
      });
      req.on("error", reject);
      req.write(data);
      req.end();
    });
  }

  async getMessages() {
    if (!this.token) await this.login();

    return new Promise((resolve, reject) => {
      const options = {
        hostname: this.ip,
        path: "/api/messages",
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
        rejectUnauthorized: false,
      };

      const req = https.request(options, (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          try {
            const json = JSON.parse(body);
            resolve(json);
          } catch (e) {
            reject(e);
          }
        });
      });
      req.on("error", reject);
      req.end();
    });
  }

  async sendMessage(recipient, text) {
    if (!this.token) await this.login();

    return new Promise((resolve, reject) => {
      const data = JSON.stringify({
        recipients: [{ to: recipient, target: "number" }],
        text: text,
        provider: "sms",
      });

      const options = {
        hostname: this.ip,
        path: "/api/messages",
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.token}`,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
        },
        rejectUnauthorized: false,
      };

      const req = https.request(options, (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          try {
            const json = JSON.parse(body);
            if (res.statusCode === 200) {
              resolve(json);
            } else {
              reject(new Error(json.message || "Gateway error"));
            }
          } catch (e) {
            reject(e);
          }
        });
      });
      req.on("error", reject);
      req.write(data);
      req.end();
    });
  }

  // Send and store the message in the local chat history. Failed messages are
  // stored too, marked with `failed: true` and the gateway's `error` (null if
  // there is no error text); the error is rethrown so callers can react.
  async sendAndStore(recipient, text) {
    const entry = {
      text,
      timestamp: Math.floor(Date.now() / 1000).toString(),
      type: "outgoing",
    };
    try {
      await this.sendMessage(recipient, text);
    } catch (error) {
      entry.failed = true;
      if (error && error.message) entry.error = error.message;
      throw error;
    } finally {
      addMessage(recipient, entry);
    }
  }

  async checkNewMessages() {
    try {
      const messages = await this.getMessages();

      messages.forEach((msg) => {
        if (msg.type !== "incoming") return;
        if (parseInt(msg.timestamp) < this.startedAt) return;

        const sender =
          msg.senders && msg.senders[0] ? msg.senders[0].number : "unknown";
        const key = `${sender}|${msg.timestamp}|${msg.text}`;
        if (this.seenMessages.has(key)) return;
        this.seenMessages.add(key);

        // Only text is accepted: images, videos, audio, stickers etc. arrive
        // without text and are neither stored, counted nor answered.
        if (typeof msg.text !== "string" || msg.text.trim() === "") {
          console.log(`Ignoring non-text message from ${sender}`);
          return;
        }

        addMessage(sender, {
          text: msg.text,
          timestamp: msg.timestamp,
          type: "incoming",
        });

        handleIncomingMessage(msg, this);
      });
    } catch (error) {
      this.resetToken();
    }
  }

  startPolling(interval) {
    // Self-scheduling loop: the next poll is only queued once the current one
    // has finished. Using setInterval here would fire every `interval` ms even
    // if the previous request is still pending, stacking up overlapping
    // requests and overloading a slow gateway (causing growing latency).
    const loop = async () => {
      await this.checkNewMessages();
      setTimeout(loop, interval);
    };
    loop();
  }

  registerRoutes(app) {
    app.get("/api/contacts", (req, res) => {
      const contactList = getAllContacts().map((phone) => ({ phone }));
      res.json(contactList);
    });

    app.get("/api/messages/:phone", (req, res) => {
      const phone = req.params.phone;
      const contact = loadContact(phone);
      res.json(contact.messages);
    });

    app.post("/api/messages/:phone", async (req, res) => {
      const phone = req.params.phone;
      const { text } = req.body;

      try {
        await this.sendAndStore(phone, text);
        res.json({ success: true });
      } catch (error) {
        this.resetToken();
        res.status(500).json({ error: error.message });
      }
    });
  }

  resetToken() {
    this.token = null;
  }
}

const gateway = new BravisOneGateway(
  process.env.BRAVIS_GATEWAY_IP || "192.168.1.100",
  process.env.BRAVIS_GATEWAY_USER || "admin",
  process.env.BRAVIS_GATEWAY_PASS || "admin",
);

// Register the HTTP routes (settings interface). Safe to call immediately at
// startup, independent of the matching model loading.
function registerGatewayRoutes(app) {
  gateway.registerRoutes(app);
  require("./country-codes").registerRoutes(app);
  require("./blacklist").registerRoutes(app);
}

// Start polling the gateway for incoming SMS. Should run only after the
// matching is ready, so replies can actually be generated.
function startGatewayPolling(pollingInterval) {
  gateway.startPolling(pollingInterval);
}

module.exports = { registerGatewayRoutes, startGatewayPolling };
