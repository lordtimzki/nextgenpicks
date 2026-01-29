import Foundation

protocol DataService {
    func fetchGames() async throws -> [Game]
    func fetchLiveProps() async throws -> [PlayerCardData]
    func searchPlayers(query: String) async throws -> [PlayerCardData]
}

// MARK: - Mock Service
// This acts as a placeholder until the real FirebaseService is connected.
struct MockDataService: DataService {
    
    func fetchGames() async throws -> [Game] {
        // Simulate network delay
        try? await Task.sleep(nanoseconds: 500_000_000) // 0.5s
        return MockData.games
    }
    
    func fetchLiveProps() async throws -> [PlayerCardData] {
        try? await Task.sleep(nanoseconds: 800_000_000) // 0.8s
        return MockData.samplePlayers
    }
    
    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        try? await Task.sleep(nanoseconds: 300_000_000) // 0.3s
        
        let lowerQuery = query.lowercased()
        if lowerQuery.isEmpty { return [] }
        
        return MockData.samplePlayers.filter {
            $0.name.lowercased().contains(lowerQuery) ||
            $0.teamAbbr.lowercased().contains(lowerQuery)
        }
    }
}
