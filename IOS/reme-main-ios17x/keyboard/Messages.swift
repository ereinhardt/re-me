//
//  Messages.swift
//  keyboard
//
//  Created by Finn Jakob Reinhardt & Erik Anton Reinhardt on 05.06.24.
//

import SwiftUI


struct DateText: View {
    let date: String
    var body: some View {
        Text(get_date()).foregroundColor(Color(uiColor: UIColor.systemGray)).font(.system(size: 10))
    }
    
    private func str_to_date() -> Date {
        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        var d = dateFormatter.date(from: date)
        
        if d == nil {
            dateFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm"
            d = dateFormatter.date(from: date)
        }


        
        return d ?? Date()
    }

    private func get_date() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "dd. MMMM yyyy 'at' HH:mm"
        return formatter.string(from: str_to_date())
    }
    
}


struct Message: View {
    var m: String;
    var color: Color;

    var body: some View {
        HStack {
            Spacer().frame(width: UIScreen.main.bounds.width * 0.2)
            
                Text(m).padding(EdgeInsets(top: 7, leading: 13, bottom: 7, trailing: 18)).foregroundColor(Color.white).background(color).clipShape(BubbleShape(reme: true))
            
           
            
        }
    }
}

struct Messages: View {
    var inputDelegate: UIInputViewController
    @ObservedObject var textProxyMonitor: TextDocumentProxyObserver
    var message: GeneratedMessageReponse?
    @Binding var isVisible: Bool
    @State private var current_index: Int = -1;
    
    init(inputDelegate: UIInputViewController, textProxyMonitor: TextDocumentProxyObserver, message: GeneratedMessageReponse? = nil, isVisible: Binding<Bool>) {
        self.inputDelegate = inputDelegate
        self.textProxyMonitor = textProxyMonitor
        self.message = message
        self._isVisible = isVisible
    }
    

    var body: some View {
        ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(0..<3) {i in
                            VStack(content: {
                                if let msg = message?.data[i] {
                                HStack(alignment: .center, content: {
                                    DateText(date: msg.Date + "T" + msg.Time)
                                }).frame(maxWidth: .infinity, alignment: .center)
                                
                                    Message(
                                        m: msg.Messagecontent,
                                        color: i == current_index ? Color.blue : Color(uiColor: UIColor.systemGray)  // Default color
                                    )
                                    .frame(maxWidth: .infinity, alignment: .trailing)
                                    .onTapGesture(perform: {
                                        if let text = inputDelegate.textDocumentProxy.documentContextBeforeInput {
                                            for _ in 0..<text.count {
                                                inputDelegate.textDocumentProxy.deleteBackward()
                                            }
                                        }
                                        if let msg = message?.data[i] {
                                            inputDelegate.textDocumentProxy.insertText(msg.Messagecontent + " ")
                                        }
                                        self.textProxyMonitor.reload()
                                        current_index = i
                                    })
                                }
                                
                            })
                          
                            
                        }.frame(maxWidth: .infinity, alignment: .trailing)
                    }.padding()
                }.frame(maxWidth: .infinity)
                    .background(Color(uiColor: UIColor.systemGray4))
                    .onChange(of: textProxyMonitor.hasText) {
                        if !textProxyMonitor.hasText && current_index != -1 {
                            isVisible = false
                        }
                    }
    };
}