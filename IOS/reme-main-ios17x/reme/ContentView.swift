//
//  ContentView.swift
//  reme
//
//  Created by Finn Jakob Reinhardt & Erik Anton Reinhardt on 02.06.24.
//

import SwiftUI
import UniformTypeIdentifiers


struct ContentView: View {
    
    
    @State private var gemini_api_key: String = UserDefaults(suiteName: "group.com.ereinhardt.reme")!.string(forKey: "gemini_api_key") ?? ""
    @State private var gemini_model: String = UserDefaults(suiteName: "group.com.ereinhardt.reme")!.string(forKey: "gemini_model") ?? "gemini-2.0-flash"
    @State private var isImporting: Bool = false
    @State private var csv_loaded: Bool = (UserDefaults(suiteName: "group.com.ereinhardt.reme")!.string(forKey: "message_index_csv") != nil)
        
        

    
    var body: some View {
        NavigationStack {
            List {
                
                
                Section(header: Text("Gemini API Key")) {
       
                    SecureField("Enter API Key", text: $gemini_api_key)
                    .background(Color.white) // Hintergrundfarbe der Section
                    .cornerRadius(5)
                    .onChange(of: gemini_api_key, {
                        UserDefaults(suiteName: "group.com.ereinhardt.reme")!.set(gemini_api_key, forKey:"gemini_api_key")
                    })
                    
                    
                }
                
                
                Section(header: Text("Gemini Model")) {
       
                    TextField("Model (e.g. gemini-2.0-flash)", text: $gemini_model)
                    .background(Color.white) // Hintergrundfarbe der Section
                    .cornerRadius(5)
                    .onChange(of: gemini_model, {
                        UserDefaults(suiteName: "group.com.ereinhardt.reme")!.set(gemini_model, forKey:"gemini_model")
                
                    })
                    
                    
                }
                
                  
                Section(header: Text("Dataset (CSV)")) {
                    Button(action: {
                        isImporting = true
                    }) {
                        HStack {
                            Text("Import message_index.csv")
                            Spacer()
                            if csv_loaded {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Settings")
            .fileImporter(
                isPresented: $isImporting,
                allowedContentTypes: [.commaSeparatedText, .plainText],
                allowsMultipleSelection: false
            ) { result in
                do {
                    guard let selectedFile: URL = try result.get().first else { return }
                    if selectedFile.startAccessingSecurityScopedResource() {
                        let csvData = try String(contentsOf: selectedFile, encoding: .utf8)
                        UserDefaults(suiteName: "group.com.ereinhardt.reme")!.set(csvData, forKey: "message_index_csv")
                        csv_loaded = true
                        selectedFile.stopAccessingSecurityScopedResource()
                    }
                } catch {
                }
            }
        }
    }
}

