# re-me – Server-Version (v.3.1-11-2026)

"re: me – Server" automatically responds to incoming SMS with a matching message from its dataset.

---
## Data Extraction Tool (Chat Import)

Imports the protagonist's own messages from chat exports into `message-data/message_index.csv`, the dataset the server answers from. Requires Python 3 with tkinter.

```bash
python3 tools/data-extraction/start.py
```

Click "Choose export file(s)…" and select one or more exports:

- **WhatsApp**: the ZIP as exported by the app (`WhatsApp Chat - X.zip`) or the extracted `.txt`
- **Telegram Desktop**: `result.json` (JSON export) or `export_results.html` (HTML export)

## Configuration

For the configuration, you need to create a `.env` file in the root of this software with the following fields:

```env
LOCALHOST="0" // Flag "1" to host on localhost, "0" to automatically use your (Server) current network IP
SERVER_PORT="5002" // Port of Web Interface, e.g., 5002
BRAVIS_GATEWAY_IP="192.168.1.100"
BRAVIS_GATEWAY_USER="admin"
BRAVIS_GATEWAY_PASS="admin"
MAX_MESSAGE_REQUESTS="25" // Per-user daily message limit (server time 00:00-23:59)
SERVER_DEBUG="0" // "1" to enable console logs, "0" to disable
```

**Note**:

1. Delete all the // comments from the `.env`.

## Model

Download the files of the `onnx` folder from [universal-sentence-encoder-multilingual-dialogue](https://huggingface.co/ereinhardt/universal-sentence-encoder-multilingual-dialogue/tree/main/universal-sentence-encoder-multilingual-dialogue/onnx) (Hugging Face) and put them into `models/universal-sentence-encoder-multilingual-dialogue/`.

## Start (re-me – Server) Software

```bash
npm i
npm run start_backend
```

