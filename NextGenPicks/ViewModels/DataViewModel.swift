import Foundation
import SwiftUI
import Combine

@MainActor
class DataViewModel: ObservableObject {

    @Published var games: [Game] = []
    @Published var featuredProps: [PlayerCardData] = []  // Top picks section
    @Published var forYouProps: [PlayerCardData] = []    // For You section
    @Published var allProps: [PlayerCardData] = []       // All props for search
    @Published var searchResults: [PlayerCardData] = []
    @Published var isLoading: Bool = false
    @Published var isSearchLoading: Bool = false
    @Published var errorMessage: String?
    @Published var refreshStatusText: String = ""
    @Published var isRefreshing: Bool = false

    // Switch this to FirebaseService() when ready
    private let service: DataService
    private var refreshTimer: AnyCancellable?
    private var isTimerRefresh: Bool = false

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
        if !isTimerRefresh {
            startRefreshTimer()
        }
    }

    /// Start a 30-second timer to update countdown and auto-refresh at the top of each hour
    func startRefreshTimer() {
        refreshTimer?.cancel()
        computeRefreshStatus()
        refreshTimer = Timer.publish(every: 30, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                Task { @MainActor in
                    self?.computeRefreshStatus()
                }
            }
    }

    /// Compute refresh status text based on current PT time
    func computeRefreshStatus() {
        let now = Date()
        guard let pt = TimeZone(identifier: "America/Los_Angeles") else { return }

        var calendar = Calendar.current
        calendar.timeZone = pt

        let hour = calendar.component(.hour, from: now)
        let minute = calendar.component(.minute, from: now)

        // Outside schedule (2 AM - 5 AM PT) — no games running
        if hour >= 2 && hour < 6 {
            isRefreshing = false
            refreshStatusText = "Next refresh: 6:00 AM PT"
            return
        }

        // First 5 minutes of each hour — data is refreshing
        if minute < 5 {
            if !isRefreshing {
                isRefreshing = true
                refreshStatusText = "Refreshing..."
                Task {
                    isTimerRefresh = true
                    await loadInitialData()
                    isTimerRefresh = false
                }
            }
            return
        }

        // Normal countdown
        isRefreshing = false
        let remaining = 60 - minute
        refreshStatusText = "Refreshes in: \(remaining)m"
    }

    /// Load all props for search functionality
    func loadAllProps() async {
        guard allProps.isEmpty else { return }  // Only load once

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
