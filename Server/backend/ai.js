const p = require("path");
const { readFileSync } = require("fs");
const { GoogleGenAI } = require("@google/genai");

function save_accesing_env_field(field) {
  const value = process.env[field];
  if (!value) throw new Error(`Environment variable ${field} is not set`);
  return value;
}

function parse_ai_response(text) {
  try {
    let cleaned = text.trim();
    if (cleaned.startsWith("```")) {
      cleaned = cleaned.replace(/^```[\w]*\n?/, "").replace(/\n?```$/, "");
    }
    return JSON.parse(cleaned);
  } catch (e) {
    console.error("Failed to parse AI response:", e.message);
    return null;
  }
}

function generatePrompt(initial_message) {
  return `
  **TASK**: 
    Reply on a message you get, with 3 possible message options from the given message_index.csv dataset.
    The goal is to keep the conversation going. Options can be direct replies, follow-up questions, or prompts that encourage further dialogue.

  **REQUIREMENTS**:
  1. **Message Matching**: Given the initial message "${initial_message}", find the 3 most relevant response options from the 'message_index.csv' dataset.
  2. **Conversation Flow**: Options should keep the conversation alive — they can be answers, follow-up questions, or related topics that naturally continue the dialogue.
  3. **Source**: All message options must be selected from the provided 'message_index.csv' file. Use the exact 'message-content', 'timestamp', and 'message-id' from matching rows.
  4. **No Duplicates**: Each 'message-id' must appear only once in the response.
  5. **Language Independent**: Ignore the language of the initial message. Always pick the best matching reply from the CSV regardless of language. If for example the CSV only contains German messages but the input is in English, still reply with the best fitting German message.

  **INITIAL MESSAGE**: "${initial_message}"

  **DATA SOURCE INSTRUCTIONS**:
  - Search 'message_index.csv' to find the 3 messages that best match or reply to "${initial_message}".
  - Use the exact 'message-content', 'timestamp', and 'message-id' values from the CSV rows.
  - Never leave any field empty or blank.

  **OUTPUT FORMAT**: 
  - Provide exactly 3 message options in the following valid JSON structure.
  - CRITICAL: Every field must use exact values from the CSV. Never leave fields empty or blank.
  - Return only the JSON structure with no additional text, explanations, or formatting:

  [
      {
          "message-content-1": "",
          "timestamp-1": "",
          "message-id-1": ""
      },
      {
          "message-content-2": "",
          "timestamp-2": "",
          "message-id-2": ""
      },
      {
          "message-content-3": "",
          "timestamp-3": "",
          "message-id-3": ""
      }
  ]
    
  `;
}

function validateResponse(parsed, message_csv) {
  // 1. Valid JSON array with 3 entries
  if (!Array.isArray(parsed) || parsed.length !== 3) return false;

  // Extract valid IDs and timestamps from CSV
  const lines = message_csv.trim().split("\n").slice(1);
  const validIds = new Set();
  const validTimestamps = new Set();
  lines.forEach((line) => {
    const parts = line.split(",");
    if (parts.length >= 3) {
      validTimestamps.add(parts[1]?.trim());
      validIds.add(parts[2]?.trim());
    }
  });

  // 2. Check each entry for valid timestamp and existing message-id
  for (let i = 0; i < 3; i++) {
    const entry = parsed[i];
    const ts = entry[`timestamp-${i + 1}`];
    const id = entry[`message-id-${i + 1}`];
    if (!ts || !validTimestamps.has(ts)) return false;
    if (!id || !validIds.has(id)) return false;
  }
  return true;
}

async function getMessageSuggestions(initial_message, sender) {
  const api_key = save_accesing_env_field("GEMINI_API_KEY");
  const model = save_accesing_env_field("GEMINI_MODEL");

  const message_index_path = p.join(
    __dirname,
    "../message-data/message_index.csv",
  );
  const message_csv = readFileSync(message_index_path, { encoding: "utf8" });

  const ai = new GoogleGenAI({ apiKey: api_key });

  let cache;
  try {
    cache = await ai.caches.create({
      model: model,
      config: {
        contents: message_csv,
        ttl: "60.0s",
      },
    });

    for (let attempt = 1; attempt <= 3; attempt++) {
      console.log(
        `AI Request (attempt ${attempt}/3) for ${sender}: ${initial_message}`,
      );
      const response = await ai.models.generateContent({
        model: model,
        contents: generatePrompt(initial_message),
        config: {
          thinkingConfig: { thinkingBudget: 0 },
          cachedContent: cache.name,
        },
      });

      const parsed = parse_ai_response(response.text);
      if (validateResponse(parsed, message_csv)) {
        await ai.caches.delete({ name: cache.name });
        console.log("Delete Cache!");
        return parsed;
      }
      console.warn(`AI response validation failed (attempt ${attempt}/3)`);
    }

    await ai.caches.delete({ name: cache.name });
    console.log("Delete Cache!");
    throw new Error("AI failed validation after 3 attempts");
  } catch (error) {
    if (cache?.name) {
      try {
        await ai.caches.delete({ name: cache.name });
        console.log("Delete Cache!");
      } catch (_) {}
    }
    console.error("AI Error:", error);
    throw error;
  }
}

module.exports = { getMessageSuggestions };
