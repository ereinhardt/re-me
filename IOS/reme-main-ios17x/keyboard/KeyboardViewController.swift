//
//  KeyboardViewController.swift
//  keyboard
//
//  Created by Finn Jakob Reinhardt & Erik Anton Reinhardt on 02.06.24.
//

import UIKit
import SwiftUI

class TextDocumentProxyObserver: ObservableObject {
    @Published var hasText: Bool = false
    private var timer: Timer?
    private var textDocumentProxy: UITextDocumentProxy

    init(textDocumentProxy: UITextDocumentProxy) {
        self.textDocumentProxy = textDocumentProxy
        self.hasText = textDocumentProxy.hasText
        
    }

     func startMonitoring() {
        // Invalidate any existing timer
        timer?.invalidate()

        // Create a new timer to check for changes every 0.1 seconds
         timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            self?.checkForChanges()
        }
    }
    
    func reload(){
        hasText = true
        self.startMonitoring()
    }

    private func checkForChanges() {
        let currentHasText = textDocumentProxy.hasText
        if hasText != currentHasText {
            DispatchQueue.main.async { [weak self] in
                self?.hasText = currentHasText
            }
        }
    }

    deinit {
        timer?.invalidate()
    }
}

class KeyboardViewController: UIInputViewController {

    @IBOutlet var nextKeyboardButton: UIButton!

    override func viewDidLoad() {
        
        super.viewDidLoad()
        
    
        
        // Perform custom UI setup here
        let hostingController = UIHostingController(rootView: KeyboardView(viewController: self))
               hostingController.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
               view.addSubview(hostingController.view)
               addChild(hostingController)
        
        self.nextKeyboardButton = UIButton(type: .system)
        
        self.nextKeyboardButton.setTitle(NSLocalizedString("Next Keyboard", comment: "Title for 'Next Keyboard' button"), for: [])
        self.nextKeyboardButton.sizeToFit()
        self.nextKeyboardButton.translatesAutoresizingMaskIntoConstraints = false
        
        self.nextKeyboardButton.addTarget(self, action: #selector(handleInputModeList(from:with:)), for: .allTouchEvents)
        
        self.view.addSubview(self.nextKeyboardButton)
        
        self.nextKeyboardButton.leftAnchor.constraint(equalTo: self.view.leftAnchor).isActive = true
        self.nextKeyboardButton.bottomAnchor.constraint(equalTo: self.view.bottomAnchor).isActive = true
    }
    
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        self.nextKeyboardButton.isHidden = !self.needsInputModeSwitchKey
    }
    
    override func textDidChange(_ textInput: UITextInput?) {
        // The app has just changed the document's contents, the document context has been updated.
        
        var textColor: UIColor
        let proxy = self.textDocumentProxy
        if proxy.keyboardAppearance == UIKeyboardAppearance.dark {
            textColor = UIColor.white
        } else {
            textColor = UIColor.black
        }
        self.nextKeyboardButton.setTitleColor(textColor, for: [])
    }

}

struct KeyboardView: View {
    var viewController: KeyboardViewController
    @State var is_first_appeance: Bool = true
    @State private var messages: GeneratedMessageReponse?
    @State private var isLoading: Bool = false  // Lade-Indikator Status
    @State private var gen_messages: Bool = false
    @State private var server_error: Int = -1
    @StateObject private var netzwerkMonitor = NetzwerkMonitor()
    @ObservedObject private var obs: TextDocumentProxyObserver
    
    init(viewController: KeyboardViewController) {
        self.viewController = viewController
        self.obs = TextDocumentProxyObserver(textDocumentProxy: self.viewController.textDocumentProxy)
        
    }

    
    
    var body: some View {
        
        Color(uiColor: .systemGray4).overlay(content: {
            VStack {
                
                if isLoading {
                    // Lade-Circle anzeigen, wenn isLoading true ist
                    ProgressView()  // Das ist der Lade-Circle in SwiftUI
                        .progressViewStyle(CircularProgressViewStyle())
                        .padding()
                        .scaleEffect(1.5)
                    
                } else {
                    if gen_messages {
                        Messages(inputDelegate: viewController, textProxyMonitor: obs, message: messages, isVisible: $gen_messages)
                    } else {
                        
                        if server_error >= 0 {
                            initalUI(error: server_error)
                        }
                        else if netzwerkMonitor.connected {
                            initalUI(error: -1)
                        } else {
                            initalUI(error: 0)
                        }
                    }
                }
            }
            .task {
            if (viewController.textDocumentProxy).hasText {
                    if let text = viewController.textDocumentProxy.documentContextBeforeInput {
for _ in 0 ..< text.count {
                        viewController.textDocumentProxy.deleteBackward()
                    }
                }
               }
           await updatePasteboardString()
              
            }
        })

    }
    
    private func updatePasteboardString() async {
        if !is_first_appeance {
            guard netzwerkMonitor.connected else {
                server_error = 0
                return
            }
            
            isLoading = true  // Lade-Circle anzeigen
            
            do {
                server_error = -1
                let pasteboard = UIPasteboard.general
                if let pasteString = pasteboard.string {
                    let res = try await GENERATE(context: pasteString)
                    // Erfolgreiches Ergebnis behandeln
                    messages = res
                    gen_messages = true
                }
            } catch {
                // Fehler behandeln
                gen_messages = false
                if "\(error)".contains("validation") || "\(error)".contains("3 attempts") {
                    server_error = 2
                } else {
                    server_error = 1
                }
            }
            
            isLoading = false  // Lade-Circle verstecken, wenn fertig
        }
        
        is_first_appeance = false
    }
}
