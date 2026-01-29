//
//  NextGenPicksApp.swift
//  NextGenPicks
//
//  Created by timdac on 1/26/26.
//

import SwiftUI
import FirebaseCore

@main
struct NextGenPicksApp: App {
    // Use Real FirebaseService since we have the plist. 
    // If you want to use Mock data, swap this to MockDataService()
    @StateObject private var dataViewModel = DataViewModel(service: FirebaseService())
    
    init() {
        // Only valid if Firebase is linked. 
        // We use a safe check ensuring the app doesn't crash if GoogleService-Info.plist is missing at runtime
        // but compile time import is expected.
        if Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist") != nil {
            // For now, we assume the user might need to add `import FirebaseCore` manually if not using SPM yet.
            // But we will add the code assuming it's available or will be.
            // Ensure you have added the Firebase package!
            FirebaseApp.configure() 
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(dataViewModel)
        }
    }
}
