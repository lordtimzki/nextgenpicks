import Foundation

// MARK: - Enums
enum RiskTolerance: String, Codable, CaseIterable {
    case noPreference = "No Preference"
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
    case ptsReb = "Points + Rebounds"
    case ptsAst = "Points + Assists"
    case rebAst = "Rebounds + Assists"
}

// MARK: - Models
struct UserSettings: Codable {
    // --- 1. RISK TOLERANCE (Explicit Context) ---
    var riskTolerance: RiskTolerance = .noPreference

    // --- 2. FILTERING (Explicit Context) ---
    var favoriteNBATeams: [String] = []
    var focusedStats: [String] = StatFilter.allCases.map { $0.rawValue } // All selected by default
    var hideFades: Bool = false
    var hideLineSkepticism: Bool = false
    var maxHitRate: Double = 1.0  // 1.0 = no filter, 0.8 = hide 80%+ hit rates
    var minRankingScore: Double = 0.0

    // --- 3. DISPLAY ---
    var propsPerSection: Int = 10

    // --- HELPER ---
    static var `default`: UserSettings {
        UserSettings()
    }
}
