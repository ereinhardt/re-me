//
//  initialText.swift
//  keyboard
//
//  Created by Finn Jakob Reinhardt & Erik Anton Reinhardt on 05.06.24.
//

import Foundation
import SwiftUI

struct initalUI: View {
    var error: Int;
    var body: some View {
        Color(uiColor: UIColor.systemGray4).overlay(content: {
            
            switch error {
            case 0:
                Text("No Internet-Connection!").foregroundStyle(Color(uiColor: UIColor.systemGray))
            case 1:
                Text("No Server-Connection!").foregroundStyle(Color(uiColor: UIColor.systemGray))
            case 2:
                Text("Bad Server-Response!").foregroundStyle(Color(uiColor: UIColor.systemGray))
            default:
                Text("No Message selected!").foregroundStyle(Color(uiColor: UIColor.systemGray))

            }
            
        })
       
    }
}
