# re-me

## Configuration

1. Create a `users` folder in the root of this software.
2. For the configuration, you need to create a `.env` file in the root of this software with the following fields:

```env
LOCALHOST="0" // Flag "1" to host on localhost, "0" to automatically use your (Server) current network IP
SERVER_PORT="5002" // Port of file server, e.g., 5002
BRAVIS_GATEWAY_IP=192.168.1.100
BRAVIS_GATEWAY_USER=admin
BRAVIS_GATEWAY_PASS=admin
USERS_FOLDER=users
GEMINI_API_KEY=""
GEMINI_MODEL="gemini-3-flash-preview"

```
