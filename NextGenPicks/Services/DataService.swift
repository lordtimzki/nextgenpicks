import Foundation

protocol DataService {
    func fetchGames() async throws -> [Game]
    func fetchAllProps() async throws -> [PlayerCardData]
    func searchPlayers(query: String) async throws -> [PlayerCardData]
}

// MARK: - Mock Service
class MockDataService: DataService {
    func fetchGames() async throws -> [Game] {
        return [
            Game(id: 1, homeTeamId: 1610612747, awayTeamId: 1610612744, startTime: Date(), homeScore: 102, awayScore: 98, status: .live),
            Game(id: 2, homeTeamId: 1610612738, awayTeamId: 1610612748, startTime: Date().addingTimeInterval(3600), homeScore: 0, awayScore: 0, status: .scheduled)
        ]
    }

    func fetchAllProps() async throws -> [PlayerCardData] {
        return [
            PlayerCardData(
                id: "1_pts", name: "LeBron James", teamAbbr: "LAL", position: "SF",
                imageName: "lebron_headshot", opponent: "GSW", gameTime: "Live",
                trending: .hot, rankingScore: 8.5,
                statName: "Pts", line: 25.5, overOdds: -110, underOdds: -110,
                edge: 2.3, playerAverage: 27.8
            ),
            PlayerCardData(
                id: "2_3pm", name: "Stephen Curry", teamAbbr: "GSW", position: "PG",
                imageName: "curry_headshot", opponent: "LAL", gameTime: "Live",
                trending: .up, rankingScore: 7.2,
                statName: "3PM", line: 4.5, overOdds: 140, underOdds: -170,
                edge: 1.2, playerAverage: 5.7
            ),
            PlayerCardData(
                id: "3_pts", name: "Jayson Tatum", teamAbbr: "BOS", position: "SF",
                imageName: "tatum_headshot", opponent: "MIA", gameTime: "8:00 PM",
                trending: .hot, rankingScore: 7.8,
                statName: "Pts", line: 28.5, overOdds: -115, underOdds: -105,
                edge: 1.8, playerAverage: 30.3
            )
        ]
    }

    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        return try await fetchAllProps()
    }
}
