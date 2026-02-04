import Foundation

protocol DataService {
    func fetchGames() async throws -> [Game]
    func fetchLiveProps() async throws -> [PlayerCardData]  // Top picks section
    func fetchForYouProps() async throws -> [PlayerCardData]  // For You section
    func fetchAllProps() async throws -> [PlayerCardData]  // All props for search
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
        // Mock top picks - individual prop cards
        return [
            PlayerCardData(
                id: "1_pts",
                name: "LeBron James",
                teamAbbr: "LAL",
                position: "SF",
                imageName: "lebron_headshot",
                opponent: "GSW",
                gameTime: "Live",
                trending: .hot,
                statName: "Pts",
                line: 25.5,
                overOdds: -110,
                underOdds: -110,
                edge: 2.3,
                playerAverage: 27.8,
                section: .topPicks
            ),
            PlayerCardData(
                id: "2_3pm",
                name: "Stephen Curry",
                teamAbbr: "GSW",
                position: "PG",
                imageName: "curry_headshot",
                opponent: "LAL",
                gameTime: "Live",
                trending: .up,
                statName: "3PM",
                line: 4.5,
                overOdds: 140,
                underOdds: -170,
                edge: 1.2,
                playerAverage: 5.7,
                section: .topPicks
            ),
            PlayerCardData(
                id: "3_pts",
                name: "Jayson Tatum",
                teamAbbr: "BOS",
                position: "SF",
                imageName: "tatum_headshot",
                opponent: "MIA",
                gameTime: "8:00 PM",
                trending: .hot,
                statName: "Pts",
                line: 28.5,
                overOdds: -115,
                underOdds: -105,
                edge: 1.8,
                playerAverage: 30.3,
                section: .topPicks
            )
        ]
    }

    func fetchForYouProps() async throws -> [PlayerCardData] {
        // Mock "For You" section - games starting soon
        return [
            PlayerCardData(
                id: "4_reb",
                name: "Anthony Davis",
                teamAbbr: "LAL",
                position: "PF",
                imageName: "davis_headshot",
                opponent: "GSW",
                gameTime: "Starting Soon",
                trending: .up,
                statName: "Reb",
                line: 10.5,
                overOdds: -105,
                underOdds: -115,
                edge: 1.5,
                playerAverage: 12.0,
                urgencyScore: 10,
                section: .forYou
            ),
            PlayerCardData(
                id: "5_ast",
                name: "Luka Doncic",
                teamAbbr: "DAL",
                position: "PG",
                imageName: "luka_headshot",
                opponent: "PHX",
                gameTime: "In 2 Hours",
                trending: .hot,
                statName: "Ast",
                line: 8.5,
                overOdds: -110,
                underOdds: -110,
                edge: 1.0,
                playerAverage: 9.5,
                urgencyScore: 10,
                section: .forYou
            )
        ]
    }

    func fetchAllProps() async throws -> [PlayerCardData] {
        // Combine all mock data
        let topPicks = try await fetchLiveProps()
        let forYou = try await fetchForYouProps()
        return topPicks + forYou
    }

    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        // Return a static list for now or filter the mock data if needed
        return try await fetchLiveProps()
    }
}
