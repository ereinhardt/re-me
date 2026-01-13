const https = require("https");
const {
  loadContact,
  saveContact,
  messageExists,
  getAllContacts,
} = require("./users-storage");

class BravisOneGateway {
  constructor(ip, username, password) {
    this.ip = ip;
    this.username = username;
    this.password = password;
    this.token = null;
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
          "Content-Length": data.length,
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
          "Content-Length": data.length,
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

  async checkNewMessages() {
    try {
      const messages = await this.getMessages();

      messages.forEach((msg) => {
        if (msg.type === "incoming") {
          const sender =
            msg.senders && msg.senders[0] ? msg.senders[0].number : "unknown";

          if (!messageExists(sender, msg.text, msg.timestamp)) {
            const contact = loadContact(sender);
            contact.messages.push({
              text: msg.text,
              timestamp: msg.timestamp,
              type: "incoming",
            });

            saveContact(sender, contact);
          }
        }
      });
    } catch (error) {
      this.resetToken();
    }
  }

  startPolling(interval = 1000) {
    setInterval(() => this.checkNewMessages(), interval);
    this.checkNewMessages();
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
        await this.sendMessage(phone, text);

        const contact = loadContact(phone);
        contact.messages.push({
          text: text,
          timestamp: Math.floor(Date.now() / 1000).toString(),
          type: "outgoing",
        });
        saveContact(phone, contact);

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
  process.env.BRAVIS_GATEWAY_PASS || "admin"
);

function initGateway(app, pollingInterval = 1000) {
  gateway.startPolling(pollingInterval);
  gateway.registerRoutes(app);
}

module.exports = { gateway, initGateway };
