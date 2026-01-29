import SwiftUI

struct GameRowView: View{
    let game: Game

    var body: some View {
        let homeTeam = TeamDatabase.getTeam(id: game.homeTeamId)
        let awayTeam = TeamDatabase.getTeam(id: game.awayTeamId)

        HStack {
            Image(systemName: "questionmark.circle")
                .resizable()
                .frame(width: 50, height: 50)
            VStack {
                Text(awayTeam.name)
                Text(homeTeam.name)
            }
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(10)
        .shadow(radius: 5)
    }
}

#Preview {
    GameRowView(game: MockData.sampleGame1)
}