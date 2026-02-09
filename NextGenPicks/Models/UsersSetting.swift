import Foundation

enum RiskTolerance: String, Codable, CaseIterable {
    case conservative = "Conservative"
    case balanced = "Balanced"
    case aggressive = "Aggressive"
}

enum PropOutcome: String, Codable {
    case pending = "Pending"
    case win = "Win"
    case loss = "Loss"
}

struct TrackedProp: Codable, Identifiable {
    let id: String
    let playerName: String
    let statName: String
    let line: Double
    let type: String // Over or Under
    var outcome: PropOutcome = .pending
    let date: Date
}

struct UserSettings: Codable {
    var favoriteTeams: [String] = []
    var focusedStats: [String] = ["Points"]
    
    // Explicit Context Signals
    var minRankingScore: Double = 6.5 // 0.0 - 10.0 scale
    var riskTolerance: RiskTolerance = .balanced
    var hideFades: Bool = true               
    
    // UI Personalization
    var sectionPriority: [String] = ["Top Picks", "For You", "Trends"]
    
    // Tracking and Implicit Context
    var trackedHistory: [TrackedProp] = [] 
    var interactionHistory: [String: Int] = [:] // Tracks [PlayerName: ClickCount]
}