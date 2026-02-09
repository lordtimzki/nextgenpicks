import Foundation
import SwiftUI
import Combine

@MainActor
class DataViewModel: ObservableObject {

    @Published var games: [Game] = []
    @Published var featuredProps: [PlayerCardData] = []
    @Published var forYouProps: [PlayerCardData] = []
    @Published var allProps: [PlayerCardData] = []
    @Published var searchResults: [PlayerCardData] = []
    @Published var isLoading: Bool = false
    @Published var isSearchLoading: Bool = false
    @Published var errorMessage: String?
    @Published var refreshStatusText: String = ""
    @Published var isRefreshing: Bool = false
    @Published var refreshComplete: Bool = false

    private let service: DataService
    private var refreshTimer: AnyCancellable?
    private var completeDismissTask: Task<Void, Never>?
    private var lastRefreshDate: Date?
    private var hasLoadedInitialData: Bool = false

    init(service: DataService) {
        self.service = service
    }

    func loadInitialData() async {
        isLoading = true
        errorMessage = nil

        do {
            async let fetchedGames = service.fetchGames()
            async let fetchedTopPicks = service.fetchLiveProps()
            async let fetchedForYou = service.fetchForYouProps()

            self.games = try await fetchedGames
            self.featuredProps = try await fetchedTopPicks
            self.forYouProps = try await fetchedForYou
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

    // MARK: - Real-time Refresh Listener

    /// Listen for backend refresh completions via Firestore metadata doc
    func startRefreshListener() {
        guard let firebaseService = service as? FirebaseService else {
            // Mock service — fall back to timer-based refresh
            return
        }

        firebaseService.listenForRefresh { [weak self] metadata in
            Task { @MainActor in
                guard let self else { return }

                // Ignore the initial snapshot (before any real refresh happens)
                if self.lastRefreshDate == nil {
                    self.lastRefreshDate = metadata.completedAt
                    self.updateCountdown()
                    return
                }

                // Only react if this is a NEW refresh (timestamp changed)
                guard metadata.completedAt > self.lastRefreshDate! else { return }
                self.lastRefreshDate = metadata.completedAt

                // Show refreshing state and re-fetch data
                self.isRefreshing = true
                self.refreshComplete = false
                self.refreshStatusText = "Refreshing..."

                await self.reloadProps()

                // Show completion
                self.isRefreshing = false
                self.refreshComplete = true
                let df = DateFormatter()
                df.dateFormat = "h:mm a"
                self.refreshStatusText = "Updated at \(df.string(from: metadata.completedAt)) — \(metadata.propsWritten) props"

                // After 15 seconds, switch back to countdown
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

    /// Re-fetch props without showing full loading state
    private func reloadProps() async {
        do {
            async let fetchedTopPicks = service.fetchLiveProps()
            async let fetchedForYou = service.fetchForYouProps()

            self.featuredProps = try await fetchedTopPicks
            self.forYouProps = try await fetchedForYou

            // Also refresh allProps if they were previously loaded (for search)
            if !allProps.isEmpty {
                self.allProps = try await service.fetchAllProps()
            }
        } catch {
            print("Failed to reload props: \(error)")
        }
    }

    // MARK: - Countdown Timer

    /// Update the countdown text every 30 seconds
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

    /// Compute countdown text based on scheduler schedule (hourly)
    func updateCountdown() {
        guard !isRefreshing, !refreshComplete else { return }

        let now = Date()
        guard let pt = TimeZone(identifier: "America/Los_Angeles") else { return }

        var calendar = Calendar.current
        calendar.timeZone = pt

        let hour = calendar.component(.hour, from: now)
        let minute = calendar.component(.minute, from: now)

        // Outside schedule (2 AM - 5 AM PT)
        if hour >= 2 && hour < 6 {
            refreshStatusText = "Next refresh: 6:00 AM PT"
            return
        }

        // Show time since last refresh if we have it
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

    // MARK: - Search Data

    /// Load all props for search functionality
    func loadAllProps() async {
        guard allProps.isEmpty else { return }

        isSearchLoading = true
        do {
            self.allProps = try await service.fetchAllProps()
        } catch {
            print("Failed to load all props: \(error)")
        }
        isSearchLoading = false
    }

    /// Get unique players from all props
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

    /// Get unique teams from all props
    var uniqueTeams: [TeamInfo] {
        var teamDict: [String: TeamInfo] = [:]

        for prop in allProps {
            let abbr = prop.teamAbbr
            if !abbr.isEmpty && teamDict[abbr] == nil {
                teamDict[abbr] = TeamInfo(
                    abbreviation: abbr,
                    playerCount: 0
                )
            }
            if var team = teamDict[abbr] {
                team.playerCount += 1
                teamDict[abbr] = team
            }
        }

        // Count unique players per team
        var playersByTeam: [String: Set<String>] = [:]
        for prop in allProps {
            let abbr = prop.teamAbbr
            let playerId = prop.player_id ?? prop.id
            if playersByTeam[abbr] == nil {
                playersByTeam[abbr] = Set<String>()
            }
            playersByTeam[abbr]?.insert(playerId)
        }

        return teamDict.values.map { team in
            TeamInfo(
                abbreviation: team.abbreviation,
                playerCount: playersByTeam[team.abbreviation]?.count ?? 0
            )
        }.sorted { $0.abbreviation < $1.abbreviation }
    }

    /// Search players by name
    func searchPlayers(query: String) -> [PlayerInfo] {
        guard !query.isEmpty else { return uniquePlayers }
        let lowercased = query.lowercased()
        return uniquePlayers.filter { $0.name.lowercased().contains(lowercased) }
    }

    /// Search teams by abbreviation
    func searchTeams(query: String) -> [TeamInfo] {
        guard !query.isEmpty else { return uniqueTeams }
        let lowercased = query.lowercased()
        return uniqueTeams.filter { $0.abbreviation.lowercased().contains(lowercased) }
    }

    /// Get all props for a specific player
    func propsForPlayer(playerId: String) -> [PlayerCardData] {
        return allProps.filter { ($0.player_id ?? $0.id) == playerId }
    }

    /// Get all players for a specific team
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

// MARK: - Search Data Models

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
