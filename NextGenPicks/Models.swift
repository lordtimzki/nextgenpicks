
import Foundation

enum SportLeague: String, Codable {
    case nba = "NBA"
    case nfl = "NFL"
    case mlb = "MLB"
    case nhl = "NHL"
}

struct Team: Identifiable, Codable {
    let id: Int
    let league: SportLeague
    let name: String
    let city: String
    let abbreviation: String
    let logoName: String
}

enum GameStatus: String, Codable {
    case scheduled
    case live
    case final
    case postponed
}

struct Game: Identifiable, Codable {
    let id: Int
    let homeTeamId: Int
    let awayTeamId: Int
    let startTime: Date
    var homeScore: Int
    var awayScore: Int
    var status: GameStatus
}