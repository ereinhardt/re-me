const p = require("path");
const { readFileSync, existsSync, statSync } = require("fs");
const ort = require("onnxruntime-node");
const { SentencePieceProcessor } = require("@sctg/sentencepiece-js");

// Retrieval configuration: Universal Sentence Encoder multilingual QA
// dual-encoder (ONNX, int8) + int8-quantized in-memory vector index.
// Incoming messages are embedded with the question encoder, the CSV messages
// (candidate replies) with the response encoder.
const MODEL_DIR = p.join(
  __dirname,
  "../models/universal-sentence-encoder-multilingual-dialogue",
);
const MODEL_VARIANT = "int8";
// The encoders output 512 dimensions; only the first 256 are kept (benchmark:
// half the storage for ~3 % lower MRR).
const EMBEDDING_DIM = 256;
const RETRIEVAL_TOP_K = 3;

// SentencePiece special ids (see tokenizer.json: add_bos + add_eos).
const BOS_ID = 1;
const EOS_ID = 2;

const MESSAGE_INDEX_PATH = p.join(
  __dirname,
  "../message-data/message_index.csv",
);

// Singletons, initialised once via initMatching().
let tokenizer = null;
let questionEncoder = null;
let responseEncoder = null;
// messageIndex = [{ content, timestamp, id, q:Int8Array, norm }]
let messageIndex = null;

// CSV helpers (RFC 4180): fields may be quoted ("...") and then contain
// commas and line breaks; a quote inside a quoted field is written as "".
// The header row is skipped.
function parseCsv(csvText) {
  const text = csvText.replace(/\r\n?/g, "\n");
  const records = [];
  let record = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c !== '"') field += c;
      else if (text[i + 1] === '"') field += text[++i];
      else quoted = false;
    } else if (c === '"') {
      quoted = true;
    } else if (c === ",") {
      record.push(field);
      field = "";
    } else if (c === "\n") {
      record.push(field);
      records.push(record);
      record = [];
      field = "";
    } else {
      field += c;
    }
  }
  if (field || record.length) {
    record.push(field);
    records.push(record);
  }

  const rows = [];
  for (const parts of records.slice(1)) {
    if (parts.length < 3) continue;
    rows.push({
      content: parts[0].trim(),
      timestamp: parts[1].trim(),
      id: parts[2].trim(),
    });
  }
  return rows;
}

// Embedding (the encoders take one unpadded text per call)
function tokenize(text) {
  return Int32Array.from([BOS_ID, ...tokenizer.encodeIds(text), EOS_ID]);
}

function idsTensor(ids) {
  return new ort.Tensor("int32", ids, [ids.length]);
}

async function embedQuestion(text) {
  const ids = tokenize(text);
  const { outputs } = await questionEncoder.run({ input_ids: idsTensor(ids) });
  return outputs.data.subarray(0, EMBEDDING_DIM);
}

async function embedResponse(text) {
  // No conversation context available: context_ids = input_ids.
  const ids = tokenize(text);
  const { outputs } = await responseEncoder.run({
    input_ids: idsTensor(ids),
    context_ids: idsTensor(ids),
  });
  return outputs.data.subarray(0, EMBEDDING_DIM);
}

// MARK: - int8 quantization

// Symmetric per-vector int8 quantization (scale = maxAbs / 127). Cosine
// similarity is scale-invariant, so only the int8 values are kept.
function quantizeVector(vec) {
  let maxAbs = 0;
  for (let i = 0; i < vec.length; i++) {
    const a = Math.abs(vec[i]);
    if (a > maxAbs) maxAbs = a;
  }
  const scale = maxAbs > 0 ? maxAbs / 127 : 1;
  const q = new Int8Array(vec.length);
  for (let i = 0; i < vec.length; i++) {
    let v = Math.round(vec[i] / scale);
    if (v > 127) v = 127;
    else if (v < -127) v = -127;
    q[i] = v;
  }
  return q;
}

// L2 norm of an int8 vector (precomputed once so search stays cheap).
function int8Norm(q) {
  let s = 0;
  for (let i = 0; i < q.length; i++) s += q[i] * q[i];
  return Math.sqrt(s);
}

// Brute-force cosine top-K (no vector DB needed for this dataset size). The
// query stays in full precision; documents are int8. Cosine is scale-invariant,
// so comparing the float query against the raw int8 values (divided by the
// precomputed int8 norm) yields the same ranking as full-precision vectors.
function cosineSimilarity(query, queryNorm, row) {
  const q = row.q;
  let dot = 0;
  for (let i = 0; i < EMBEDDING_DIM; i++) dot += query[i] * q[i];
  const denom = queryNorm * row.norm;
  return denom === 0 ? 0 : dot / denom;
}

function topK(rows, queryVector, k) {
  let s = 0;
  for (let i = 0; i < EMBEDDING_DIM; i++) s += queryVector[i] * queryVector[i];
  const queryNorm = Math.sqrt(s);
  return rows
    .map((row) => ({ row, score: cosineSimilarity(queryVector, queryNorm, row) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}

// Initialise the matching: load the ONNX encoders and (re)build the vector
// index from the CSV. Called once on start.
async function initMatching() {
  console.log(`Loading embedding model: ${MODEL_DIR} (${MODEL_VARIANT})`);
  tokenizer = new SentencePieceProcessor();
  await tokenizer.load(p.join(MODEL_DIR, "spm.model"));
  questionEncoder = await ort.InferenceSession.create(
    p.join(MODEL_DIR, `question_encoder_${MODEL_VARIANT}.onnx`),
  );
  responseEncoder = await ort.InferenceSession.create(
    p.join(MODEL_DIR, `response_encoder_${MODEL_VARIANT}.onnx`),
  );

  // (Re)build the index from the CSV.
  const csvText = readFileSync(MESSAGE_INDEX_PATH, { encoding: "utf8" });
  const rows = parseCsv(csvText);
  const total = rows.length;
  console.log(`Embedding ${total} messages from message_index.csv ...`);

  const indexedRows = [];
  for (const row of rows) {
    const q = quantizeVector(await embedResponse(row.content));
    indexedRows.push({
      content: row.content,
      timestamp: row.timestamp,
      id: row.id,
      q,
      norm: int8Norm(q),
    });
    if (indexedRows.length % 32 === 0 || indexedRows.length === total) {
      reportEmbedProgress(indexedRows.length, total);
    }
  }

  messageIndex = indexedRows;
  console.log("Matching initialisation complete.");
}

// Progress reporter for the embedding loop. On a TTY it rewrites a single line
// via carriage return; when stdout is piped (e.g. the test-pipeline.py bridge)
// it emits a "__PROGRESS__done/total" marker line that the reader renders as an
// updating line.
function reportEmbedProgress(done, total) {
  if (process.stdout.isTTY) {
    process.stdout.write(`\rEmbedding ${done}/${total} ...`);
    if (done >= total) process.stdout.write("\n");
  } else {
    process.stdout.write(`__PROGRESS__${done}/${total}\n`);
  }
}

// Retrieval: the 3 replies whose response embedding best matches the message,
// as suggestion objects (best match first).
async function getMessageSuggestions(initial_message, sender) {
  if (!messageIndex) {
    throw new Error(
      "Matching is not initialised yet. Call initMatching() first.",
    );
  }

  console.log(`Match request for ${sender}: ${initial_message}`);

  const queryEmbedding = await embedQuestion(initial_message);
  const candidates = topK(messageIndex, queryEmbedding, RETRIEVAL_TOP_K);
  if (candidates.length < RETRIEVAL_TOP_K) {
    throw new Error("Not enough candidate messages retrieved from vector index");
  }
  return candidates.map(({ row }, i) => ({
    [`message-content-${i + 1}`]: row.content,
    [`timestamp-${i + 1}`]: row.timestamp,
    [`message-id-${i + 1}`]: row.id,
  }));
}

// Number of messages in message_index.csv, re-read only when the file changes
// (shown in the settings interface).
let messageCount = { mtimeMs: null, count: 0 };
function countMessages() {
  if (!existsSync(MESSAGE_INDEX_PATH)) return 0;
  const { mtimeMs } = statSync(MESSAGE_INDEX_PATH);
  if (mtimeMs !== messageCount.mtimeMs) {
    const csvText = readFileSync(MESSAGE_INDEX_PATH, { encoding: "utf8" });
    messageCount = { mtimeMs, count: parseCsv(csvText).length };
  }
  return messageCount.count;
}

module.exports = {
  initMatching,
  getMessageSuggestions,
  countMessages,
};
