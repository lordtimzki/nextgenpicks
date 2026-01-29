import SwiftUI

struct HomeView: View {
    let games: [Game] = MockData.games
    
    var body: some View {
        NavigationView {
            List(games) { game in
                GameRowView(game: game)
                    .listRowSeparator(.hidden) 
            }
            .listStyle(.plain)
            .navigationTitle("Live Games")
        }
    }
}

#Preview {
    HomeView()
}
