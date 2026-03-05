//
//  ai.swift
//  reme
//
//  Created by Finn Jakob Reinhardt & Erik Anton Reinhardt on 21.06.24.
//

import Foundation
import Network
import Combine

// MARK: - Network Monitor

class NetzwerkMonitor: ObservableObject {
    @Published var connected: Bool = false
    private var monitor: NWPathMonitor
    private let queue = DispatchQueue.global(qos: .background)
    private var timer: Timer?
    
    init() {
        monitor = NWPathMonitor()
        
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.connected = (path.status == .satisfied)
            }
        }
        monitor.start(queue: queue)
        
        // Polling-Fallback: prüfe alle 2s den aktuellen Status
        DispatchQueue.main.async { [weak self] in
            self?.timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
                guard let self else { return }
                let current = self.monitor.currentPath.status == .satisfied
                if self.connected != current {
                    self.connected = current
                }
            }
        }
    }
    
    deinit {
        monitor.cancel()
        timer?.invalidate()
    }
}

extension String: Error {}

// MARK: - Models

struct GeneratedMessage: Decodable {
    let Date: String
    let Messagecontent: String
    let Name: String
    let Time: String
}

struct GeneratedMessageReponse: Decodable {
    let error: Bool
    let data: [GeneratedMessage]
    let message: String
}

private struct GeminiResponse: Decodable {
    struct Candidate: Decodable {
        struct Content: Decodable {
            struct Part: Decodable { let text: String }
            let parts: [Part]
        }
        let content: Content
    }
    let candidates: [Candidate]?
}

// MARK: - Gemini REST API Helpers

private let BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

private func geminiRequest(path: String, apiKey: String, body: [String: Any]) -> URLRequest {
    let url = URL(string: "\(BASE_URL)/\(path)?key=\(apiKey)")!
    var req = URLRequest(url: url)
    req.httpMethod = "POST"
    req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    req.httpBody = try? JSONSerialization.data(withJSONObject: body)
    return req
}

private func createCache(apiKey: String, model: String, csvData: String) async -> String? {
    let body: [String: Any] = [
        "model": "models/\(model)",
        "contents": [["role": "user", "parts": [["text": csvData]]]],
        "ttl": "60s"
    ]
    let req = geminiRequest(path: "cachedContents", apiKey: apiKey, body: body)
    guard let (data, _) = try? await URLSession.shared.data(for: req),
          let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let name = json["name"] as? String else { return nil }
    return name
}

private func deleteCache(name: String?, apiKey: String) async {
    guard let name else { return }
    let url = URL(string: "\(BASE_URL)/\(name)?key=\(apiKey)")!
    var req = URLRequest(url: url)
    req.httpMethod = "DELETE"
    _ = try? await URLSession.shared.data(for: req)
}

private func parseTimestamp(_ timestamp: String) -> (date: String, time: String) {
    if let unix = TimeInterval(timestamp) {
        let d = Date(timeIntervalSince1970: unix)
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        let date = fmt.string(from: d)
        fmt.dateFormat = "HH:mm:ss"
        return (date, fmt.string(from: d))
    }
    let sep: Character = timestamp.contains("T") ? "T" : " "
    let parts = timestamp.split(separator: sep, maxSplits: 1).map(String.init)
    return parts.count >= 2 ? (parts[0], parts[1]) : (timestamp, "12:00")
}

private func parseCSVValidationSets(_ csvData: String) -> (ids: Set<String>, timestamps: Set<String>) {
    let lines = csvData.trimmingCharacters(in: .whitespacesAndNewlines).components(separatedBy: "\n")
    guard let header = lines.first else { return ([], []) }
    
    let cols = header.lowercased().components(separatedBy: ",").map { $0.trimmingCharacters(in: .whitespaces) }
    let tsCol = cols.firstIndex { $0.contains("timestamp") } ?? 1
    let idCol = cols.firstIndex { $0.contains("message-id") } ?? 2
    let minCols = max(tsCol, idCol) + 1
    
    var ids: Set<String> = []
    var timestamps: Set<String> = []
    
    for line in lines.dropFirst() {
        let clean = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { continue }
        let parts = clean.components(separatedBy: ",")
        guard parts.count >= minCols else { continue }
        timestamps.insert(parts[tsCol].trimmingCharacters(in: .whitespacesAndNewlines))
        ids.insert(parts[idCol].trimmingCharacters(in: .whitespacesAndNewlines))
    }
    return (ids, timestamps)
}

// MARK: - Main Generate Function

func GENERATE(context: String) async throws -> GeneratedMessageReponse {
    let defaults = UserDefaults(suiteName: "group.com.ereinhardt.reme")!
    let apiKey = defaults.string(forKey: "gemini_api_key") ?? ""
    let model = defaults.string(forKey: "gemini_model") ?? "gemini-2.0-flash"
    let csvData = defaults.string(forKey: "message_index_csv") ?? ""
    
    let initial_message = context.count > 500 ? String(context.prefix(500)) + "..." : context
    
    // Create cache & build validation sets
    let cacheName = await createCache(apiKey: apiKey, model: model, csvData: csvData)
    let (validIds, validTimestamps) = parseCSVValidationSets(csvData)

    let promptText = """
      **TASK**: 
        Reply on a message you get, with 3 possible message options from the given message_index.csv dataset.
        The goal is to keep the conversation going. Options can be direct replies, follow-up questions, or prompts that encourage further dialogue.

      **REQUIREMENTS**:
      1. **Message Matching**: Given the initial message "\(initial_message)", find the 3 most relevant response options from the 'message_index.csv' dataset.
      2. **Conversation Flow**: Options should keep the conversation alive — they can be answers, follow-up questions, or related topics that naturally continue the dialogue.
      3. **Source**: All message options must be selected from the provided 'message_index.csv' file. Use the exact 'message-content', 'timestamp', and 'message-id' from matching rows.
      4. **No Duplicates**: Each 'message-id' must appear only once in the response.
      5. **Language Independent**: Ignore the language of the initial message. Always pick the best matching reply from the CSV regardless of language. If for example the CSV only contains German messages but the input is in English, still reply with the best fitting German message.

      **INITIAL MESSAGE**: "\(initial_message)"

      **DATA SOURCE INSTRUCTIONS**:
      - Search 'message_index.csv' to find the 3 messages that best match or reply to "\(initial_message)".
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
    """

    var body: [String: Any] = [
        "contents": [["role": "user", "parts": [["text": promptText]]]],
        "generationConfig": [
            "responseMimeType": "application/json",
            "thinkingConfig": ["thinkingBudget": 0]
        ]
    ]
    if let name = cacheName { body["cachedContent"] = name }
    
    let request = geminiRequest(path: "models/\(model):generateContent", apiKey: apiKey, body: body)
    
    // Retry up to 3 times
    for _ in 1...3 {
        let (data, _) = try await URLSession.shared.data(for: request)
        
        guard let text = try? JSONDecoder().decode(GeminiResponse.self, from: data)
            .candidates?.first?.content.parts.first?.text else {
            await deleteCache(name: cacheName, apiKey: apiKey)
            throw "Invalid Gemini Response"
        }
        
        // Parse JSON array from response
        var cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if cleaned.hasPrefix("```") {
            if let nl = cleaned.firstIndex(of: "\n") { cleaned.removeSubrange(cleaned.startIndex...nl) }
            if cleaned.hasSuffix("```") { cleaned.removeLast(3) }
        }
        
        guard let jsonData = cleaned.data(using: .utf8),
              let entries = try? JSONSerialization.jsonObject(with: jsonData) as? [[String: Any]],
              entries.count == 3 else { continue }
        
        // Validate all 3 entries against CSV
        let isValid = (0..<3).allSatisfy { i in
            let idx = i + 1
            let ts = entries[i]["timestamp-\(idx)"] as? String ?? ""
            let id = entries[i]["message-id-\(idx)"] as? String ?? ""
            return validTimestamps.contains(ts) && validIds.contains(id)
        }
        guard isValid else { continue }
        
        // Build response
        let messages = (0..<3).map { i -> GeneratedMessage in
            let idx = i + 1
            let content = entries[i]["message-content-\(idx)"] as? String ?? ""
            let ts = entries[i]["timestamp-\(idx)"] as? String ?? ""
            let (date, time) = parseTimestamp(ts)
            return GeneratedMessage(Date: date, Messagecontent: content, Name: "Gemini", Time: time)
        }
        
        await deleteCache(name: cacheName, apiKey: apiKey)
        return GeneratedMessageReponse(error: false, data: messages, message: "Success")
    }
    
    await deleteCache(name: cacheName, apiKey: apiKey)
    throw "AI failed validation after 3 attempts"
}
