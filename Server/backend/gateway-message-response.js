const { getMessageSuggestions } = require("./matching");
const { isAllowed } = require("./country-codes");
const { isBlacklisted } = require("./blacklist");
const { getMessageRequests, saveMessageRequests } = require("./users-storage");

const MAX_MESSAGE_REQUESTS = parseInt(process.env.MAX_MESSAGE_REQUESTS) || 0;

// Counter and "limit notified" flag live in users/<phone>.json (messageRequests).
function checkAndIncrementUserRequests(sender) {
  const requests = getMessageRequests(sender);
  if (MAX_MESSAGE_REQUESTS > 0 && requests.count >= MAX_MESSAGE_REQUESTS) {
    return false;
  }
  requests.count++;
  saveMessageRequests(sender, requests);
  return true;
}

function shouldNotifyLimit(sender) {
  const requests = getMessageRequests(sender);
  if (requests.limitNotified) return false;
  requests.limitNotified = true;
  saveMessageRequests(sender, requests);
  return true;
}

// Track latest message per sender to skip outdated requests
const latestMessage = new Map();
let processing = false;
const queue = [];

async function processQueue(gateway) {
  if (processing || queue.length === 0) return;
  processing = true;

  while (queue.length > 0) {
    const { msg, sender } = queue.shift();

    // Skip if a newer message from this sender exists
    if (latestMessage.get(sender) !== msg.timestamp) {
      console.log(
        `Skipping outdated message from ${sender}: "${msg.text.substring(0, 30)}..."`,
      );
      continue;
    }

    try {
      const suggestions = await getMessageSuggestions(msg.text, sender);

      // Check again after AI call – a newer message may have arrived
      if (latestMessage.get(sender) !== msg.timestamp) {
        console.log(
          `Discarding AI result, newer message from ${sender} arrived`,
        );
        continue;
      }

      // Log all 3 options
      for (let i = 0; i < 3; i++) {
        const opt = suggestions[i];
        console.log(
          `  Option ${i + 1}: ${opt[`message-content-${i + 1}`]},${opt[`timestamp-${i + 1}`]},${opt[`message-id-${i + 1}`]}`,
        );
      }

      // Random pick among the options without a blacklisted word; if all 3
      // contain one, nothing is sent.
      const allowed = [0, 1, 2].filter(
        (i) => !isBlacklisted(suggestions[i][`message-content-${i + 1}`]),
      );
      if (allowed.length === 0) {
        console.log(`All options blacklisted, no reply sent to ${sender}`);
        continue;
      }
      const pick = allowed[Math.floor(Math.random() * allowed.length)];
      const chosen = suggestions[pick];
      const text = chosen[`message-content-${pick + 1}`];
      const timestamp = chosen[`timestamp-${pick + 1}`];
      const id = chosen[`message-id-${pick + 1}`];

      console.log(`AI picked option ${pick + 1}: ${text},${timestamp},${id}`);

      await gateway.sendAndStore(sender, text);

      console.log(`Reply sent to ${sender}`);
    } catch (err) {
      console.error("AI suggestion error:", err.message);

      try {
        await gateway.sendAndStore(sender, "Bad Server-Response!");

        console.log(`Fallback reply sent to ${sender}`);
      } catch (sendErr) {
        console.error("Failed to send fallback message:", sendErr.message);
      }
    }
  }

  processing = false;
}

function handleIncomingMessage(msg, gateway) {
  const now = Math.floor(Date.now() / 1000);
  const msgAge = now - parseInt(msg.timestamp);
  const sender = msg.senders && msg.senders[0] ? msg.senders[0].number : null;

  // Only query AI if the message is recent (within last 60 seconds)
  if (msgAge <= 60 && sender) {
    if (!isAllowed(sender)) {
      console.log(`Skipping ${sender}: country code not whitelisted`);
      return;
    }
    if (!checkAndIncrementUserRequests(sender)) {
      console.log(`User ${sender} reached daily message limit`);
      if (shouldNotifyLimit(sender)) {
        gateway
          .sendAndStore(
            sender,
            "Users message limit reached. Try again tomorrow.",
          )
          .catch((e) => console.error("Failed to send message:", e.message));
      }
      return;
    }
    latestMessage.set(sender, msg.timestamp);
    queue.push({ msg, sender });
    processQueue(gateway);
  }
}

module.exports = { handleIncomingMessage };
