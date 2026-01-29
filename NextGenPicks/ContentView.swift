//
//  ContentView.swift
//  NextGenPicks
//
//  Created by timdac on 1/26/26.
//

import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            HomeView()
            .tabItem {
                Label("Home", systemImage: "house")
            }
            Text("Search")
            .tabItem {
                Label("Search", systemImage: "magnifyingglass")
            }
            Text("Profile")
            .tabItem {
                Label("Profile", systemImage: "person")
            }
        }
        .padding()
    }
}

#Preview {
    Text("Home Screen")
}
