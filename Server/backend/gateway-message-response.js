const { getMessageSuggestions } = require("./ai");
const { loadContact, saveContact } = require("./users-storage");

// Queue to process AI requests sequentially
const queue = [];
let processing = false;

async function processQueue(gateway) {
  if (processing || queue.length === 0) return;
  processing = true;

  while (queue.length > 0) {
    const { msg, sender } = queue.shift();
    try {
      const suggestions = await getMessageSuggestions(msg.text, sender);

      // Log all 3 options
      for (let i = 0; i < 3; i++) {
        const opt = suggestions[i];
        console.log(`  Option ${i + 1}: ${opt[`message-content-${i + 1}`]},${opt[`timestamp-${i + 1}`]},${opt[`message-id-${i + 1}`]}`);
      }

      const pick = Math.floor(Math.random() * 3);
      const chosen = suggestions[pick];
      const text = chosen[`message-content-${pick + 1}`];
      const timestamp = chosen[`timestamp-${pick + 1}`];
      const id = chosen[`message-id-${pick + 1}`];

      console.log(`AI picked option ${pick + 1}: ${text},${timestamp},${id}`);

      if (sender) {
        await gateway.sendMessage(sender, text);

        const contact = loadContact(sender);
        contact.messages.push({
          text: text,
          timestamp: Math.floor(Date.now() / 1000).toString(),
          type: "outgoing",
        });
        saveContact(sender, contact);

        console.log(`Reply sent to ${sender}`);
      }
    } catch (err) {
      console.error("AI suggestion error:", err.message);
    }
  }

  processing = false;
}

function handleIncomingMessage(msg, gateway) {
  const now = Math.floor(Date.now() / 1000);
  const msgAge = now - parseInt(msg.timestamp);
  const sender = msg.senders && msg.senders[0] ? msg.senders[0].number : null;

  // Only query AI if the message is recent (within last 60 seconds)
  if (msgAge <= 60) {
    queue.push({ msg, sender });
    processQueue(gateway);
  }
}

module.exports = { handleIncomingMessage };
