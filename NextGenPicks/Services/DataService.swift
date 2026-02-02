import Foundation

protocol DataService {
    func fetchGames() async throws -> [Game]
    func fetchLiveProps() async throws -> [PlayerCardData]
    func searchPlayers(query: String) async throws -> [PlayerCardData]
}

// MARK: - Mock Service
// This acts as a placeholder until the real FirebaseService is connected.
class MockDataService: DataService {
    func fetchGames() async throws -> [Game] {
        return [
            Game(id: 1, homeTeamId: 1610612747, awayTeamId: 1610612744, startTime: Date(), homeScore: 102, awayScore: 98, status: .live),
            Game(id: 2, homeTeamId: 1610612738, awayTeamId: 1610612748, startTime: Date().addingTimeInterval(3600), homeScore: 0, awayScore: 0, status: .scheduled)
        ]
    }
    
    func fetchLiveProps() async throws -> [PlayerCardData] {
        return [
            PlayerCardData(
                id: 1,
                name: "LeBron James",
                teamAbbr: "LAL",
                position: "SF",
                imageName: "lebron_headshot",
                props: [
                    PlayerProp(statName: "Points", line: 25.5, overOdds: -110, underOdds: -110)
                ],
                opponent: "GSW",
                gameTime: "Live",
                trending: .hot
            ),
            PlayerCardData(
                id: 2,
                name: "Stephen Curry",
                teamAbbr: "GSW",
                position: "PG",
                imageName: "curry_headshot",
                props: [
                    PlayerProp(statName: "3PM", line: 4.5, overOdds: 140, underOdds: -170)
                ],
                opponent: "LAL",
                gameTime: "Live",
                trending: .up
            ),
            PlayerCardData(
                id: 3,
                name: "Jayson Tatum",
                teamAbbr: "BOS",
                position: "SF",
                imageName: "tatum_headshot",
                props: [
                    PlayerProp(statName: "Points", line: 28.5, overOdds: -115, underOdds: -105)
                ],
                opponent: "MIA",
                gameTime: "8:00 PM",
                trending: .hot // Replaced invalid .cold with .hot or .up since .cold doesn't exist
            )
        ]
    }
    
    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        // Return a static list for now or filter the mock data if needed
        return try await fetchLiveProps()
    }
}
