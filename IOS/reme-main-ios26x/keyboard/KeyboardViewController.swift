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
        
        // Make the keyboard's inputView fully transparent
        // so the system's native keyboard background shows through
        self.view.backgroundColor = .clear
        if let inputView = self.inputView {
            inputView.backgroundColor = .clear
        }
        
        // Perform custom UI setup here
        let hostingController = UIHostingController(rootView: KeyboardView(viewController: self))
               hostingController.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
               hostingController.view.backgroundColor = .clear
               hostingController.view.isOpaque = false
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
    
    override func viewWillLayoutSubviews() {
        super.viewWillLayoutSubviews()
        self.nextKeyboardButton.isHidden = !self.needsInputModeSwitchKey
    }

}

struct KeyboardView: View {
    var viewController: KeyboardViewController
    @State private var lastPasteboardChangeCount: Int = -1
    @State private var lastPasteboardString: String = ""
    private let pasteboardTimer = Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()
    @State private var messages: GeneratedMessageReponse?
    @State private var isLoading: Bool = false  // Loading indicator state
    @State private var gen_messages: Bool = false
    @State private var server_error: Int = -1
    @StateObject private var netzwerkMonitor = NetzwerkMonitor()
    @ObservedObject private var obs: TextDocumentProxyObserver
    
    init(viewController: KeyboardViewController) {
        self.viewController = viewController
        self.obs = TextDocumentProxyObserver(textDocumentProxy: viewController.textDocumentProxy)
        // Freeze clipboard state on open – only new copy actions should trigger a load
        _lastPasteboardChangeCount = State(initialValue: UIPasteboard.general.changeCount)
        _lastPasteboardString = State(initialValue: UIPasteboard.general.string ?? "")
    }

    
    
    var body: some View {
        
        VStack {
            
            if isLoading {
                // Show loading spinner when isLoading is true
                ProgressView()  // Loading spinner
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
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task {
            if viewController.textDocumentProxy.hasText {
                if let text = viewController.textDocumentProxy.documentContextBeforeInput {
                    for _ in 0 ..< text.count {
                        viewController.textDocumentProxy.deleteBackward()
                    }
                }
            }
        }
        .onReceive(pasteboardTimer) { _ in
            Task {
                await checkPasteboard()
            }
        }

    }
    
    private func checkPasteboard() async {
        let currentCount = UIPasteboard.general.changeCount
        if lastPasteboardChangeCount != currentCount {
            lastPasteboardChangeCount = currentCount
            
            if UIPasteboard.general.hasStrings {
                if let str = UIPasteboard.general.string, !str.isEmpty, str != lastPasteboardString {
                    lastPasteboardString = str
                    await updatePasteboardString(context: str)
                }
            }
        }
    }
    
    private func updatePasteboardString(context: String) async {
        guard netzwerkMonitor.connected else {
                server_error = 0
                return
            }
            
            isLoading = true  // Show loading spinner
            
            do {
                server_error = -1
                let res = try await GENERATE(context: context)
                    // Handle successful result
                    messages = res
                    gen_messages = true
            } catch {
                // Handle error
                gen_messages = false
                if "\(error)".contains("validation") || "\(error)".contains("3 attempts") {
                    server_error = 2
                } else {
                    server_error = 1
                }
            }
            
            isLoading = false  // Hide loading spinner when done
    }
}
