
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
    case fade
}

// Hit rate result for a single game
struct HitRateGame: Codable {
    let value: Double
    let hit: Bool
    let date: String
    let matchup: String

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Handle value as Double or Int
        if let doubleValue = try? container.decode(Double.self, forKey: .value) {
            self.value = doubleValue
        } else if let intValue = try? container.decode(Int.self, forKey: .value) {
            self.value = Double(intValue)
        } else {
            self.value = 0
        }

        self.hit = try container.decode(Bool.self, forKey: .hit)
        self.date = try container.decodeIfPresent(String.self, forKey: .date) ?? ""
        self.matchup = try container.decodeIfPresent(String.self, forKey: .matchup) ?? ""
    }

    init(value: Double, hit: Bool, date: String, matchup: String) {
        self.value = value
        self.hit = hit
        self.date = date
        self.matchup = matchup
    }
}

// Hit rate data (up to 10 games, recency-weighted)
struct HitRate: Codable {
    let hits: Int
    let total: Int
    let results: [HitRateGame]
    let weightedPct: Double

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.hits = try container.decodeIfPresent(Int.self, forKey: .hits) ?? 0
        self.total = try container.decodeIfPresent(Int.self, forKey: .total) ?? 0
        self.results = try container.decodeIfPresent([HitRateGame].self, forKey: .results) ?? []

        if let d = try? container.decode(Double.self, forKey: .weightedPct) { self.weightedPct = d }
        else if let i = try? container.decode(Int.self, forKey: .weightedPct) { self.weightedPct = Double(i) }
        else { self.weightedPct = 0 }
    }

    init(hits: Int, total: Int, results: [HitRateGame], weightedPct: Double = 0) {
        self.hits = hits
        self.total = total
        self.results = results
        self.weightedPct = weightedPct
    }
}

struct PlayerAverages: Codable {
    let pts: Double
    let reb: Double
    let ast: Double
    let fg3m: Double

    // Custom decoder to handle Int or Double from Firestore
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Handle pts as Double or Int
        if let doublePts = try? container.decode(Double.self, forKey: .pts) {
            self.pts = doublePts
        } else if let intPts = try? container.decode(Int.self, forKey: .pts) {
            self.pts = Double(intPts)
        } else {
            self.pts = 0
        }

        // Handle reb as Double or Int
        if let doubleReb = try? container.decode(Double.self, forKey: .reb) {
            self.reb = doubleReb
        } else if let intReb = try? container.decode(Int.self, forKey: .reb) {
            self.reb = Double(intReb)
        } else {
            self.reb = 0
        }

        // Handle ast as Double or Int
        if let doubleAst = try? container.decode(Double.self, forKey: .ast) {
            self.ast = doubleAst
        } else if let intAst = try? container.decode(Int.self, forKey: .ast) {
            self.ast = Double(intAst)
        } else {
            self.ast = 0
        }

        // Handle fg3m as Double or Int
        if let doubleFg3m = try? container.decode(Double.self, forKey: .fg3m) {
            self.fg3m = doubleFg3m
        } else if let intFg3m = try? container.decode(Int.self, forKey: .fg3m) {
            self.fg3m = Double(intFg3m)
        } else {
            self.fg3m = 0
        }
    }

    // Regular initializer for programmatic creation
    init(pts: Double, reb: Double, ast: Double, fg3m: Double = 0) {
        self.pts = pts
        self.reb = reb
        self.ast = ast
        self.fg3m = fg3m
    }
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

// Section types for feed organization
enum PropSection: String, Codable {
    case topPicks
    case forYou
    case allProps
}

struct TrendData: Codable {
    let trend: String
    let declinePct: Double
    let surgePct: Double
    let recentAvg: Double
    let fullAvg: Double

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.trend = try container.decodeIfPresent(String.self, forKey: .trend) ?? ""

        if let d = try? container.decode(Double.self, forKey: .declinePct) { self.declinePct = d }
        else if let i = try? container.decode(Int.self, forKey: .declinePct) { self.declinePct = Double(i) }
        else { self.declinePct = 0 }

        if let d = try? container.decode(Double.self, forKey: .surgePct) { self.surgePct = d }
        else if let i = try? container.decode(Int.self, forKey: .surgePct) { self.surgePct = Double(i) }
        else { self.surgePct = 0 }

        if let d = try? container.decode(Double.self, forKey: .recentAvg) { self.recentAvg = d }
        else if let i = try? container.decode(Int.self, forKey: .recentAvg) { self.recentAvg = Double(i) }
        else { self.recentAvg = 0 }

        if let d = try? container.decode(Double.self, forKey: .fullAvg) { self.fullAvg = d }
        else if let i = try? container.decode(Int.self, forKey: .fullAvg) { self.fullAvg = Double(i) }
        else { self.fullAvg = 0 }
    }

    init(trend: String, declinePct: Double, surgePct: Double, recentAvg: Double, fullAvg: Double) {
        self.trend = trend
        self.declinePct = declinePct
        self.surgePct = surgePct
        self.recentAvg = recentAvg
        self.fullAvg = fullAvg
    }
}

struct PlayerAdvanced: Codable {
    let usgPct: Double?
    let tsPct: Double?
    let rebPct: Double?
    let astPct: Double?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        if let d = try? container.decode(Double.self, forKey: .usgPct) { self.usgPct = d }
        else if let i = try? container.decode(Int.self, forKey: .usgPct) { self.usgPct = Double(i) }
        else { self.usgPct = nil }

        if let d = try? container.decode(Double.self, forKey: .tsPct) { self.tsPct = d }
        else if let i = try? container.decode(Int.self, forKey: .tsPct) { self.tsPct = Double(i) }
        else { self.tsPct = nil }

        if let d = try? container.decode(Double.self, forKey: .rebPct) { self.rebPct = d }
        else if let i = try? container.decode(Int.self, forKey: .rebPct) { self.rebPct = Double(i) }
        else { self.rebPct = nil }

        if let d = try? container.decode(Double.self, forKey: .astPct) { self.astPct = d }
        else if let i = try? container.decode(Int.self, forKey: .astPct) { self.astPct = Double(i) }
        else { self.astPct = nil }
    }

    init(usgPct: Double?, tsPct: Double?, rebPct: Double?, astPct: Double?) {
        self.usgPct = usgPct
        self.tsPct = tsPct
        self.rebPct = rebPct
        self.astPct = astPct
    }
}

struct PlayerCardData: Identifiable, Codable {
    let id: String  // Changed to String to support both NBA API int IDs and Underdog UUIDs
    let name: String
    let teamAbbr: String
    let position: String
    let imageName: String
    let opponent: String
    let gameTime: String
    let trending: TrendingStatus

    // Legacy: array of props (optional for backward compatibility)
    var props: [PlayerProp]?

    // NEW: Single prop fields (for individual prop cards)
    var statName: String?
    var statNameFull: String?
    var line: Double?
    var overOdds: Int?
    var underOdds: Int?
    var propId: String?
    var edge: Double?
    var playerAverage: Double?
    var urgencyScore: Double?
    var section: PropSection?
    var player_id: String?
    var recommendedDirection: String?  // "Over" or "Under" based on player avg vs line

    // Optional fields from the Underdog data source
    var source: String?
    var last_updated: String?
    var gameTimeUTC: String?  // ISO timestamp for local time conversion

    // Ranking system fields
    var featured: Bool?
    var rankingScore: Double?
    var playerAverages: PlayerAverages?
    var hitRate: HitRate?  // Last 5 games hit rate for this prop
    var isFade: Bool?  // AI marked as fade (avoid this prop)
    var lineupStatus: String?  // "STARTING", "GTD", or ""
    var trendData: TrendData?

    // Ranking breakdown fields
    var matchupScore: Double?
    var oppDefRank: Int?
    var oppPaceRank: Int?
    var efficiencyScore: Double?
    var playerAdvanced: PlayerAdvanced?
    var restStatus: String?
    var teamInjuries: String?
    var oppInjuries: String?
    var opponentAbbr: String?

    // v5 ranking fields
    var isHome: Bool?
    var homeAwayModifier: Double?
    var minutesConfidence: Double?
    var avgMinutes: Double?
    var usageVacuum: Double?

    // Computed property: get the main prop (either from single prop fields or first of array)
    var mainProp: PlayerProp? {
        // If we have single prop fields, create a PlayerProp from them
        if let statName = statName, let line = line {
            return PlayerProp(
                id: propId ?? id,
                statName: statName,
                line: line,
                overOdds: overOdds ?? -110,
                underOdds: underOdds ?? -110
            )
        }
        // Otherwise fall back to first prop in array
        return props?.first
    }

    // Computed property: check if this is a single prop card
    var isSinglePropCard: Bool {
        return statName != nil && line != nil
    }

    // Regular initializer for programmatic creation (mocks, previews)
    init(id: Any, name: String, teamAbbr: String, position: String, imageName: String,
         props: [PlayerProp]? = nil, opponent: String, gameTime: String, trending: TrendingStatus,
         source: String? = nil, last_updated: String? = nil, gameTimeUTC: String? = nil,
         featured: Bool? = nil, rankingScore: Double? = nil, playerAverages: PlayerAverages? = nil, hitRate: HitRate? = nil, isFade: Bool? = nil, lineupStatus: String? = nil, trendData: TrendData? = nil,
         statName: String? = nil, statNameFull: String? = nil, line: Double? = nil,
         overOdds: Int? = nil, underOdds: Int? = nil, propId: String? = nil,
         edge: Double? = nil, playerAverage: Double? = nil, urgencyScore: Double? = nil,
         section: PropSection? = nil, player_id: String? = nil, recommendedDirection: String? = nil,
         matchupScore: Double? = nil, oppDefRank: Int? = nil, oppPaceRank: Int? = nil,
         efficiencyScore: Double? = nil, playerAdvanced: PlayerAdvanced? = nil,
         restStatus: String? = nil, teamInjuries: String? = nil, oppInjuries: String? = nil, opponentAbbr: String? = nil,
         isHome: Bool? = nil, homeAwayModifier: Double? = nil, minutesConfidence: Double? = nil, avgMinutes: Double? = nil, usageVacuum: Double? = nil) {
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
        self.source = source
        self.last_updated = last_updated
        self.gameTimeUTC = gameTimeUTC
        self.featured = featured
        self.rankingScore = rankingScore
        self.playerAverages = playerAverages
        self.hitRate = hitRate
        self.isFade = isFade
        self.lineupStatus = lineupStatus
        self.trendData = trendData
        // New single prop fields
        self.statName = statName
        self.statNameFull = statNameFull
        self.line = line
        self.overOdds = overOdds
        self.underOdds = underOdds
        self.propId = propId
        self.edge = edge
        self.playerAverage = playerAverage
        self.urgencyScore = urgencyScore
        self.section = section
        self.player_id = player_id
        self.recommendedDirection = recommendedDirection
        self.matchupScore = matchupScore
        self.oppDefRank = oppDefRank
        self.oppPaceRank = oppPaceRank
        self.efficiencyScore = efficiencyScore
        self.playerAdvanced = playerAdvanced
        self.restStatus = restStatus
        self.teamInjuries = teamInjuries
        self.oppInjuries = oppInjuries
        self.opponentAbbr = opponentAbbr
        self.isHome = isHome
        self.homeAwayModifier = homeAwayModifier
        self.minutesConfidence = minutesConfidence
        self.avgMinutes = avgMinutes
        self.usageVacuum = usageVacuum
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
        self.opponent = try container.decode(String.self, forKey: .opponent)
        self.gameTime = try container.decode(String.self, forKey: .gameTime)
        self.trending = try container.decode(TrendingStatus.self, forKey: .trending)

        // Legacy props array (optional for new single-prop format)
        self.props = try container.decodeIfPresent([PlayerProp].self, forKey: .props)

        // NEW: Single prop fields
        self.statName = try container.decodeIfPresent(String.self, forKey: .statName)
        self.statNameFull = try container.decodeIfPresent(String.self, forKey: .statNameFull)
        self.propId = try container.decodeIfPresent(String.self, forKey: .propId)
        self.player_id = try container.decodeIfPresent(String.self, forKey: .player_id)
        self.section = try container.decodeIfPresent(PropSection.self, forKey: .section)
        self.recommendedDirection = try container.decodeIfPresent(String.self, forKey: .recommendedDirection)

        // Handle line as Double or Int
        if let doubleLine = try? container.decodeIfPresent(Double.self, forKey: .line) {
            self.line = doubleLine
        } else if let intLine = try? container.decodeIfPresent(Int.self, forKey: .line) {
            self.line = Double(intLine)
        } else {
            self.line = nil
        }

        self.overOdds = try container.decodeIfPresent(Int.self, forKey: .overOdds)
        self.underOdds = try container.decodeIfPresent(Int.self, forKey: .underOdds)

        // Handle edge as Double or Int
        if let doubleEdge = try? container.decodeIfPresent(Double.self, forKey: .edge) {
            self.edge = doubleEdge
        } else if let intEdge = try? container.decodeIfPresent(Int.self, forKey: .edge) {
            self.edge = Double(intEdge)
        } else {
            self.edge = nil
        }

        // Handle playerAverage as Double or Int
        if let doubleAvg = try? container.decodeIfPresent(Double.self, forKey: .playerAverage) {
            self.playerAverage = doubleAvg
        } else if let intAvg = try? container.decodeIfPresent(Int.self, forKey: .playerAverage) {
            self.playerAverage = Double(intAvg)
        } else {
            self.playerAverage = nil
        }

        // Handle urgencyScore as Double or Int
        if let doubleUrgency = try? container.decodeIfPresent(Double.self, forKey: .urgencyScore) {
            self.urgencyScore = doubleUrgency
        } else if let intUrgency = try? container.decodeIfPresent(Int.self, forKey: .urgencyScore) {
            self.urgencyScore = Double(intUrgency)
        } else {
            self.urgencyScore = nil
        }

        // Optional metadata fields
        self.source = try container.decodeIfPresent(String.self, forKey: .source)
        self.last_updated = try container.decodeIfPresent(String.self, forKey: .last_updated)
        self.gameTimeUTC = try container.decodeIfPresent(String.self, forKey: .gameTimeUTC)

        // Ranking system fields
        self.featured = try container.decodeIfPresent(Bool.self, forKey: .featured)
        // Handle rankingScore as Double or Int
        if let doubleScore = try? container.decodeIfPresent(Double.self, forKey: .rankingScore) {
            self.rankingScore = doubleScore
        } else if let intScore = try? container.decodeIfPresent(Int.self, forKey: .rankingScore) {
            self.rankingScore = Double(intScore)
        } else {
            self.rankingScore = nil
        }
        self.playerAverages = try container.decodeIfPresent(PlayerAverages.self, forKey: .playerAverages)
        self.hitRate = try container.decodeIfPresent(HitRate.self, forKey: .hitRate)
        self.isFade = try container.decodeIfPresent(Bool.self, forKey: .isFade)
        self.lineupStatus = try container.decodeIfPresent(String.self, forKey: .lineupStatus)
        self.trendData = try container.decodeIfPresent(TrendData.self, forKey: .trendData)

        // Ranking breakdown fields
        if let d = try? container.decodeIfPresent(Double.self, forKey: .matchupScore) { self.matchupScore = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .matchupScore) { self.matchupScore = Double(i) }
        else { self.matchupScore = nil }

        self.oppDefRank = try container.decodeIfPresent(Int.self, forKey: .oppDefRank)
        self.oppPaceRank = try container.decodeIfPresent(Int.self, forKey: .oppPaceRank)

        if let d = try? container.decodeIfPresent(Double.self, forKey: .efficiencyScore) { self.efficiencyScore = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .efficiencyScore) { self.efficiencyScore = Double(i) }
        else { self.efficiencyScore = nil }

        self.playerAdvanced = try container.decodeIfPresent(PlayerAdvanced.self, forKey: .playerAdvanced)
        self.restStatus = try container.decodeIfPresent(String.self, forKey: .restStatus)
        self.teamInjuries = try container.decodeIfPresent(String.self, forKey: .teamInjuries)
        self.oppInjuries = try container.decodeIfPresent(String.self, forKey: .oppInjuries)
        self.opponentAbbr = try container.decodeIfPresent(String.self, forKey: .opponentAbbr)

        // v5 ranking fields
        self.isHome = try container.decodeIfPresent(Bool.self, forKey: .isHome)

        if let d = try? container.decodeIfPresent(Double.self, forKey: .homeAwayModifier) { self.homeAwayModifier = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .homeAwayModifier) { self.homeAwayModifier = Double(i) }
        else { self.homeAwayModifier = nil }

        if let d = try? container.decodeIfPresent(Double.self, forKey: .minutesConfidence) { self.minutesConfidence = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .minutesConfidence) { self.minutesConfidence = Double(i) }
        else { self.minutesConfidence = nil }

        if let d = try? container.decodeIfPresent(Double.self, forKey: .avgMinutes) { self.avgMinutes = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .avgMinutes) { self.avgMinutes = Double(i) }
        else { self.avgMinutes = nil }

        if let d = try? container.decodeIfPresent(Double.self, forKey: .usageVacuum) { self.usageVacuum = d }
        else if let i = try? container.decodeIfPresent(Int.self, forKey: .usageVacuum) { self.usageVacuum = Double(i) }
        else { self.usageVacuum = nil }
    }
}