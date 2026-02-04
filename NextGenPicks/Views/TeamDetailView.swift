import SwiftUI

struct TeamDetailView: View {
    @EnvironmentObject var vm: DataViewModel
    let team: TeamInfo

    var teamPlayers: [PlayerInfo] {
        vm.playersForTeam(teamAbbr: team.abbreviation)
    }

    var body: some View {
        ZStack {
            Color.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    // Team Header
                    teamHeader

                    // Players List
                    if teamPlayers.isEmpty {
                        emptyState
                    } else {
                        playersSection
                    }
                }
                .padding(.bottom, 20)
            }
        }
        .navigationTitle(team.abbreviation)
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Team Header

    private var teamHeader: some View {
        VStack(spacing: 16) {
            // Team Icon
            ZStack {
                Circle()
                    .fill(Color.brandEmerald.opacity(0.2))
                    .frame(width: 100, height: 100)
                Text(team.abbreviation)
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundStyle(Color.brandEmerald)
            }

            // Team Info
            VStack(spacing: 4) {
                Text(team.abbreviation)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            // Player count badge
            HStack(spacing: 6) {
                Image(systemName: "person.2.fill")
                    .font(.caption)
                Text("\(teamPlayers.count) Players with Props")
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundStyle(Color.brandPurple)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(Color.brandPurple.opacity(0.15))
            .clipShape(Capsule())
        }
        .padding(.top, 20)
    }

    // MARK: - Players Section

    private var playersSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Players")
                .font(.headline)
                .foregroundStyle(.white)
                .padding(.horizontal)

            LazyVStack(spacing: 8) {
                ForEach(teamPlayers) { player in
                    NavigationLink(destination: PlayerDetailView(player: player)) {
                        PlayerSearchRow(player: player)
                    }
                }
            }
            .padding(.horizontal)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.2.slash")
                .font(.system(size: 48))
                .foregroundStyle(.gray)
            Text("No players available")
                .font(.headline)
                .foregroundStyle(.gray)
            Text("Check back later for new props")
                .font(.subheadline)
                .foregroundStyle(.gray.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 60)
    }
}

#Preview {
    NavigationStack {
        TeamDetailView(team: TeamInfo(abbreviation: "LAL", playerCount: 5))
            .environmentObject(DataViewModel(service: MockDataService()))
    }
}
