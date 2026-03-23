# re-me – Server-Version (v.2.1-3-2026)

"re: me – Server" automatically responds to incoming SMS with a matching message from its dataset.

---

## Configuration

For the configuration, you need to create a `.env` file in the root of this software with the following fields:

```env
LOCALHOST="0" // Flag "1" to host on localhost, "0" to automatically use your (Server) current network IP
SERVER_PORT="5002" // Port of Web Interface, e.g., 5002
BRAVIS_GATEWAY_IP="192.168.1.100"
BRAVIS_GATEWAY_USER="admin"
BRAVIS_GATEWAY_PASS="admin"
USERS_FOLDER="users"
GEMINI_API_KEY=""
GEMINI_MODEL="gemini-3-flash-preview"
```

**Note**:

1. Delete all the // comments from the `.env`.
2. Manage your Google Gemini (GenAI) API Settings and Costs at: https://console.cloud.google.com

## Start (re-me – Server) Software

```bash
npm i
npm run start_backend
```
