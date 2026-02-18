import Foundation

// MARK: - "Risk & Style" Category
enum RiskTolerance: String, Codable, CaseIterable {
    case conservative = "Conservative"
    case balanced = "Balanced"
    case aggressive = "Aggressive"
}

enum BettingStyle: String, Codable, CaseIterable {
    case singles = "Singles"
    case parlays = "Parlays"
    case both = "Both"
}

enum PropOutcome: String, Codable {
    case pending = "Pending"
    case win = "Win"
    case loss = "Loss"
}

// MARK: - Models
struct TrackedProp: Codable, Identifiable {
    let id: String
    let playerName: String
    let statName: String
    let line: Double
    let type: String // "Over" or "Under"
    var outcome: PropOutcome = .pending
    let date: Date
}

struct UserSettings: Codable {
    // --- 1. RISK & STYLE  ---
    var riskTolerance: RiskTolerance = .balanced
    var bettingStyle: BettingStyle = .both
    var minConfidence: String = "Show All" // Options: "Show All", "Lean+", "Strong Only"
    
    // --- 2. FILTERING (Explicit Context) ---
    var favoriteTeams: [String] = []
    var focusedStats: [String] = ["Points", "Rebounds", "Assists", "3PM", "PRA"]
    var hideFades: Bool = false 
    var minRankingScore: Double = 0.0 
    
    // --- 3. DISPLAY  ---
    var propsPerSection: Int = 10 // Stepper 5-20
    var sectionPriority: [String] = ["Top Picks", "For You", "Trends"]
    
    // --- 4. TRACKING & IMPLICIT CONTEXT ---
    var trackedHistory: [TrackedProp] = [] 
    
    // PlayerName: ClickCount 'Implicit Interest' multiplier)
    var interactionHistory: [String: Int] = [:] 

    // --- HELPER FOR DATA PERSISTENCE ---
    static var `default`: UserSettings {
        UserSettings()
    }
}