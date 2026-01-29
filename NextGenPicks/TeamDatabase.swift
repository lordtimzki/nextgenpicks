import Foundation

struct TeamDatabase {

    static let teams: [Int: Team] = [
        1610612747: Team(
            id: 1610612747,
            league: .nba,
            name: "Los Angeles Lakers",
            city: "Los Angeles",
            abbreviation: "LAL",
            logoName: "los-angeles-lakers"
        ),
        1610612758: Team(
            id: 1610612758,
            league: .nba,
            name: "Sacramento Kings",
            city: "Sacramento",
            abbreviation: "SAC",
            logoName: "sacramento-kings"
        ),
        1610612744: Team(
            id: 1610612744,
            league: .nba,
            name: "Golden State Warriors",
            city: "Golden State",
            abbreviation: "GSW",
            logoName: "golden-state-warriors",
        )
    ]
    
    static func getTeam(id: Int) -> Team {
        return teams[id] ?? Team(id: 0, league: .nba, name: "Unknown", city: "Unknown", abbreviation: "UNK", logoName: "questionmark.circle")
    }
}
