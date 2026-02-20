import Foundation
import SwiftUI
import Combine

@MainActor
class DataViewModel: ObservableObject {

    // MARK: - Published Properties
    @Published var games: [Game] = []
    @Published var allProps: [PlayerCardData] = []
    @Published var searchResults: [PlayerCardData] = []

    // User preferences (persisted locally)
    @Published var userSettings = UserSettings()

    @Published var isLoading: Bool = false
    @Published var isSearchLoading: Bool = false
    @Published var errorMessage: String?
    @Published var refreshStatusText: String = ""
    @Published var isRefreshing: Bool = false
    @Published var refreshComplete: Bool = false
    @Published var showSettings: Bool = false

    // MARK: - Private Properties
    private let service: DataService
    private var refreshTimer: AnyCancellable?
    private var completeDismissTask: Task<Void, Never>?
    private var lastRefreshDate: Date?
    private var hasLoadedInitialData: Bool = false

    init(service: DataService) {
        self.service = service
        loadSettingsLocally()
    }

    // MARK: - Filtered Props (client-side)

    /// All props sorted by ranking score (no personalization — pure ranking)
    var filteredProps: [PlayerCardData] {
        allProps
            .sorted { ($0.rankingScore ?? 0) > ($1.rankingScore ?? 0) }
            .filter { prop in
                // Minimum ranking score
                guard (prop.rankingScore ?? 0) >= userSettings.minRankingScore else { return false }

                // Focused stats filter
                if let statFull = prop.statNameFull, !userSettings.focusedStats.contains(statFull) {
                    return false
                }

                // Hide fades
                if userSettings.hideFades && (prop.trending == .fade || prop.isFade == true) { return false }

                // Risk tolerance
                let edgePct = (prop.edge ?? 0) / (prop.line ?? 1.0)
                let hitRate = Double(prop.hitRate?.hits ?? 0) / Double(max(prop.hitRate?.total ?? 1, 1))
                let odds = prop.overOdds ?? prop.underOdds ?? -110

                switch userSettings.riskTolerance {
                case .noPreference:
                    return true
                case .conservative:
                    return odds <= -150 && edgePct > 0.10 && hitRate >= 0.80
                case .balanced:
                    return odds >= -110 && odds <= 110 && edgePct > 0.05 && hitRate >= 0.60
                case .aggressive:
                    return true
                }
            }
    }

    /// Top picks: first N props by ranking
    var topPicks: [PlayerCardData] {
        Array(filteredProps.prefix(userSettings.propsPerSection))
    }

    /// For You: personalized curated picks based on user preferences
    var forYouProps: [PlayerCardData] {
        let now = Date()
        let hasFavoriteTeams = !userSettings.favoriteNBATeams.isEmpty

        // Score each prop with a personalized relevance score
        let scored: [(prop: PlayerCardData, score: Double)] = allProps.compactMap { prop in
            // Skip fades
            if prop.isFade == true || prop.trending == .fade { return nil }

            let baseRank = prop.rankingScore ?? 0
            var score = baseRank

            // 1. Favorite team boost (+3.0) — strongest signal
            if hasFavoriteTeams && userSettings.favoriteNBATeams.contains(prop.teamAbbr) {
                score += 3.0
            }

            // 2. Focused stat boost (+1.0)
            if userSettings.focusedStats.contains(prop.statNameFull ?? "") {
                score += 1.0
            }

            // 3. High-confidence boost — hit rate 7/10+ gets a bump
            let hits = prop.hitRate?.hits ?? 0
            let total = prop.hitRate?.total ?? 1
            let hitRate = Double(hits) / Double(max(total, 1))
            if hitRate >= 0.7 && total >= 5 {
                score += 1.5
            }

            // 4. Lineup confirmed boost — STARTING players are more actionable
            if prop.lineupStatus == "STARTING" {
                score += 1.0
            }

            // 5. Time-awareness — slight boost for upcoming (not started) games
            if let gameTime = parseGameTime(prop.gameTimeUTC), gameTime > now {
                score += 0.5
            }

            return (prop, score)
        }

        // Sort by personalized score, then enforce diversity (max 1 prop per player)
        let sorted = scored.sorted { $0.score > $1.score }
        var result: [PlayerCardData] = []
        var seenPlayers: Set<String> = []

        for item in sorted {
            let playerKey = item.prop.name
            if seenPlayers.contains(playerKey) { continue }
            seenPlayers.insert(playerKey)
            result.append(item.prop)
            if result.count >= 5 { break }
        }

        return result
    }

    private func parseGameTime(_ isoString: String?) -> Date? {
        guard let str = isoString else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter.date(from: str) ?? ISO8601DateFormatter().date(from: str)
    }

    // MARK: - Data Loading

    func loadInitialData() async {
        isLoading = true
        errorMessage = nil

        do {
            async let fetchedGames = service.fetchGames()
            async let fetchedProps = service.fetchAllProps()

            self.games = try await fetchedGames
            self.allProps = try await fetchedProps
        } catch {
            self.errorMessage = "Failed to load data: \(error.localizedDescription)"
        }

        isLoading = false

        if !hasLoadedInitialData {
            hasLoadedInitialData = true
            startRefreshListener()
            startCountdownTimer()
        }
    }

    // MARK: - Settings Persistence

    func saveSettingsLocally() {
        if let encoded = try? JSONEncoder().encode(userSettings) {
            UserDefaults.standard.set(encoded, forKey: "user_settings")
        }
    }

    private func loadSettingsLocally() {
        if let data = UserDefaults.standard.data(forKey: "user_settings"),
           var decoded = try? JSONDecoder().decode(UserSettings.self, from: data) {
            // Migrate old stat filter names to match Underdog API names
            let migrations: [String: String] = [
                "Pts + Rebs": "Points + Rebounds",
                "Pts + Asts": "Points + Assists",
                "Rebs + Asts": "Rebounds + Assists",
            ]
            var migrated = false
            for (old, new) in migrations {
                if let idx = decoded.focusedStats.firstIndex(of: old) {
                    decoded.focusedStats[idx] = new
                    migrated = true
                }
            }
            self.userSettings = decoded
            if migrated { saveSettingsLocally() }
        }
    }

    // MARK: - Real-time Refresh Listener

    func startRefreshListener() {
        guard let firebaseService = service as? FirebaseService else { return }

        firebaseService.listenForRefresh { [weak self] metadata in
            Task { @MainActor in
                guard let self else { return }

                if self.lastRefreshDate == nil {
                    self.lastRefreshDate = metadata.completedAt
                    self.updateCountdown()
                    return
                }

                guard metadata.completedAt > self.lastRefreshDate! else { return }
                self.lastRefreshDate = metadata.completedAt

                self.isRefreshing = true
                self.refreshComplete = false
                self.refreshStatusText = "Refreshing..."

                await self.reloadProps()

                self.isRefreshing = false
                self.refreshComplete = true
                let df = DateFormatter()
                df.dateFormat = "h:mm a"
                self.refreshStatusText = "Updated at \(df.string(from: metadata.completedAt)) — \(metadata.propsWritten) props"

                self.completeDismissTask?.cancel()
                self.completeDismissTask = Task {
                    try? await Task.sleep(nanoseconds: 15_000_000_000)
                    if !Task.isCancelled {
                        self.refreshComplete = false
                        self.updateCountdown()
                    }
                }
            }
        }
    }

    private func reloadProps() async {
        do {
            self.allProps = try await service.fetchAllProps()
        } catch {
            print("Failed to reload props: \(error)")
        }
    }

    // MARK: - Countdown Timer

    func startCountdownTimer() {
        refreshTimer?.cancel()
        updateCountdown()
        refreshTimer = Timer.publish(every: 30, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                Task { @MainActor in
                    guard let self, !self.isRefreshing, !self.refreshComplete else { return }
                    self.updateCountdown()
                }
            }
    }

    func updateCountdown() {
        guard !isRefreshing, !refreshComplete else { return }

        let now = Date()
        guard let pt = TimeZone(identifier: "America/Los_Angeles") else { return }

        var calendar = Calendar.current
        calendar.timeZone = pt

        let hour = calendar.component(.hour, from: now)
        let minute = calendar.component(.minute, from: now)

        if hour >= 2 && hour < 6 {
            refreshStatusText = "Next refresh: 6:00 AM PT"
            return
        }

        if let lastRefresh = lastRefreshDate {
            let df = DateFormatter()
            df.dateFormat = "h:mm a"
            let remaining = 60 - minute
            refreshStatusText = "Last: \(df.string(from: lastRefresh)) · Next in \(remaining)m"
        } else {
            let remaining = 60 - minute
            refreshStatusText = "Refreshes in: \(remaining)m"
        }
    }

    // MARK: - Search

    var uniquePlayers: [PlayerInfo] {
        var seen = Set<String>()
        var players: [PlayerInfo] = []

        for prop in allProps {
            let playerId = prop.player_id ?? prop.id
            if !seen.contains(playerId) {
                seen.insert(playerId)
                players.append(PlayerInfo(
                    id: playerId,
                    name: prop.name,
                    teamAbbr: prop.teamAbbr,
                    position: prop.position,
                    imageName: prop.imageName
                ))
            }
        }
        return players.sorted { $0.name < $1.name }
    }

    var uniqueTeams: [TeamInfo] {
        var teamDict: [String: TeamInfo] = [:]
        var playersByTeam: [String: Set<String>] = [:]

        for prop in allProps {
            let abbr = prop.teamAbbr
            if !abbr.isEmpty && teamDict[abbr] == nil {
                teamDict[abbr] = TeamInfo(abbreviation: abbr, playerCount: 0)
            }
            let playerId = prop.player_id ?? prop.id
            if playersByTeam[abbr] == nil { playersByTeam[abbr] = Set() }
            playersByTeam[abbr]?.insert(playerId)
        }

        return teamDict.values.map { team in
            TeamInfo(abbreviation: team.abbreviation, playerCount: playersByTeam[team.abbreviation]?.count ?? 0)
        }.sorted { $0.abbreviation < $1.abbreviation }
    }

    func searchPlayers(query: String) -> [PlayerInfo] {
        guard !query.isEmpty else { return uniquePlayers }
        let lowercased = query.lowercased()
        return uniquePlayers.filter { $0.name.lowercased().contains(lowercased) }
    }

    func searchTeams(query: String) -> [TeamInfo] {
        guard !query.isEmpty else { return uniqueTeams }
        let lowercased = query.lowercased()
        return uniqueTeams.filter { $0.abbreviation.lowercased().contains(lowercased) }
    }

    func propsForPlayer(playerId: String) -> [PlayerCardData] {
        return allProps.filter { ($0.player_id ?? $0.id) == playerId }
    }

    func playersForTeam(teamAbbr: String) -> [PlayerInfo] {
        var seen = Set<String>()
        var players: [PlayerInfo] = []

        for prop in allProps where prop.teamAbbr == teamAbbr {
            let playerId = prop.player_id ?? prop.id
            if !seen.contains(playerId) {
                seen.insert(playerId)
                players.append(PlayerInfo(
                    id: playerId,
                    name: prop.name,
                    teamAbbr: prop.teamAbbr,
                    position: prop.position,
                    imageName: prop.imageName
                ))
            }
        }
        return players.sorted { $0.name < $1.name }
    }

    func search(query: String) {
        guard !query.isEmpty else {
            searchResults = []
            return
        }
        Task {
            do {
                self.searchResults = try await service.searchPlayers(query: query)
            } catch {
                print("Search error: \(error)")
            }
        }
    }
}

// MARK: - Search Models

struct PlayerInfo: Identifiable, Hashable {
    let id: String
    let name: String
    let teamAbbr: String
    let position: String
    let imageName: String
}

struct TeamInfo: Identifiable, Hashable {
    var id: String { abbreviation }
    let abbreviation: String
    var playerCount: Int
}
