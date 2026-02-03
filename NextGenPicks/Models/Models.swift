
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

enum TrendingStatus: String, Codable {
    case up
    case hot
}

struct PlayerProp: Identifiable, Codable, Hashable {
    let id: String  // UUID string from Firestore - must match Python's str(uuid.uuid4())
    let statName: String
    let line: Double
    let overOdds: Int
    let underOdds: Int

    // Custom decoder to handle line being Int or Double in Firebase
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        self.id = try container.decode(String.self, forKey: .id)
        self.statName = try container.decode(String.self, forKey: .statName)

        // Handle line as Double or Int
        if let doubleLine = try? container.decode(Double.self, forKey: .line) {
            self.line = doubleLine
        } else if let intLine = try? container.decode(Int.self, forKey: .line) {
            self.line = Double(intLine)
        } else {
            throw DecodingError.dataCorruptedError(forKey: .line, in: container, debugDescription: "line must be Double or Int")
        }

        self.overOdds = try container.decode(Int.self, forKey: .overOdds)
        self.underOdds = try container.decode(Int.self, forKey: .underOdds)
    }

    // Regular initializer for programmatic creation
    init(id: String, statName: String, line: Double, overOdds: Int, underOdds: Int) {
        self.id = id
        self.statName = statName
        self.line = line
        self.overOdds = overOdds
        self.underOdds = underOdds
    }
}

struct PlayerCardData: Identifiable, Codable {
    let id: String  // Changed to String to support both NBA API int IDs and Underdog UUIDs
    let name: String
    let teamAbbr: String
    let position: String
    let imageName: String
    let props: [PlayerProp]
    let opponent: String
    let gameTime: String
    let trending: TrendingStatus

    // Optional fields from the new Underdog data source
    var ai_analysis: String?
    var source: String?
    var last_updated: String?

    // Regular initializer for programmatic creation (mocks, previews)
    init(id: Any, name: String, teamAbbr: String, position: String, imageName: String,
         props: [PlayerProp], opponent: String, gameTime: String, trending: TrendingStatus,
         ai_analysis: String? = nil, source: String? = nil, last_updated: String? = nil) {
        // Accept Int or String for id
        if let intId = id as? Int {
            self.id = String(intId)
        } else if let stringId = id as? String {
            self.id = stringId
        } else {
            self.id = String(describing: id)
        }
        self.name = name
        self.teamAbbr = teamAbbr
        self.position = position
        self.imageName = imageName
        self.props = props
        self.opponent = opponent
        self.gameTime = gameTime
        self.trending = trending
        self.ai_analysis = ai_analysis
        self.source = source
        self.last_updated = last_updated
    }

    // Custom decoder to handle id being either Int or String in Firebase
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Try decoding id as String first, then as Int (convert to String)
        if let stringId = try? container.decode(String.self, forKey: .id) {
            self.id = stringId
        } else if let intId = try? container.decode(Int.self, forKey: .id) {
            self.id = String(intId)
        } else {
            throw DecodingError.dataCorruptedError(forKey: .id, in: container, debugDescription: "ID must be String or Int")
        }

        self.name = try container.decode(String.self, forKey: .name)
        self.teamAbbr = try container.decode(String.self, forKey: .teamAbbr)
        self.position = try container.decode(String.self, forKey: .position)
        self.imageName = try container.decode(String.self, forKey: .imageName)
        self.props = try container.decode([PlayerProp].self, forKey: .props)
        self.opponent = try container.decode(String.self, forKey: .opponent)
        self.gameTime = try container.decode(String.self, forKey: .gameTime)
        self.trending = try container.decode(TrendingStatus.self, forKey: .trending)
        self.ai_analysis = try container.decodeIfPresent(String.self, forKey: .ai_analysis)
        self.source = try container.decodeIfPresent(String.self, forKey: .source)
        self.last_updated = try container.decodeIfPresent(String.self, forKey: .last_updated)
    }
}