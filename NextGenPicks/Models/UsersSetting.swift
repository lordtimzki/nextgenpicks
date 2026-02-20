import Foundation

// MARK: - Enums
enum RiskTolerance: String, Codable, CaseIterable {
    case conservative = "Conservative"
    case balanced = "Balanced"
    case aggressive = "Aggressive"
}

// MARK: - All available stat filters
enum StatFilter: String, Codable, CaseIterable {
    case points = "Points"
    case rebounds = "Rebounds"
    case assists = "Assists"
    case threePointers = "3-Pointers Made"
    case pra = "Pts + Rebs + Asts"
    case ptsReb = "Pts + Rebs"
    case ptsAst = "Pts + Asts"
    case rebAst = "Rebs + Asts"
}

// MARK: - Models
struct UserSettings: Codable {
    // --- 1. RISK TOLERANCE (Explicit Context) ---
    var riskTolerance: RiskTolerance = .aggressive

    // --- 2. FILTERING (Explicit Context) ---
    var favoriteNBATeams: [String] = []
    var focusedStats: [String] = StatFilter.allCases.map { $0.rawValue } // All selected by default
    var hideFades: Bool = false
    var minRankingScore: Double = 0.0

    // --- 3. DISPLAY ---
    var propsPerSection: Int = 10

    // --- HELPER ---
    static var `default`: UserSettings {
        UserSettings()
    }
}
