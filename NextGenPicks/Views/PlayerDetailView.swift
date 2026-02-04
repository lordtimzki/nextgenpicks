import SwiftUI

struct PlayerDetailView: View {
    @EnvironmentObject var vm: DataViewModel
    let player: PlayerInfo

    let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]

    var playerProps: [PlayerCardData] {
        vm.propsForPlayer(playerId: player.id)
    }

    var body: some View {
        ZStack {
            Color.background.ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    // Player Header
                    playerHeader

                    // Props Grid
                    if playerProps.isEmpty {
                        emptyState
                    } else {
                        propsSection
                    }
                }
                .padding(.bottom, 20)
            }
        }
        .navigationTitle(player.name)
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Player Header

    private var playerHeader: some View {
        VStack(spacing: 16) {
            // Player Image
            AsyncImage(url: URL(string: player.imageName)) { phase in
                switch phase {
                case .empty:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 100, height: 100)
                        .overlay(ProgressView().tint(.gray))
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 100, height: 100)
                        .clipShape(Circle())
                        .overlay(
                            Circle()
                                .stroke(Color.brandEmerald, lineWidth: 3)
                        )
                case .failure:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 100, height: 100)
                        .overlay(
                            Image(systemName: "person.fill")
                                .font(.system(size: 40))
                                .foregroundStyle(.gray)
                        )
                @unknown default:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 100, height: 100)
                }
            }

            // Player Info
            VStack(spacing: 4) {
                Text(player.name)
                    .font(.title2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)

                HStack(spacing: 12) {
                    Label(player.teamAbbr, systemImage: "building.2")
                        .font(.subheadline)
                        .foregroundStyle(Color.brandEmerald)
                    Label(player.position, systemImage: "person.fill")
                        .font(.subheadline)
                        .foregroundStyle(.gray)
                }
            }

            // Props count badge
            HStack(spacing: 6) {
                Image(systemName: "chart.bar.fill")
                    .font(.caption)
                Text("\(playerProps.count) Available Props")
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

    // MARK: - Props Section

    private var propsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Available Props")
                .font(.headline)
                .foregroundStyle(.white)
                .padding(.horizontal)

            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(playerProps) { prop in
                    PlayerPropCard(player: prop)
                }
            }
            .padding(.horizontal)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.bar.xaxis")
                .font(.system(size: 48))
                .foregroundStyle(.gray)
            Text("No props available")
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
        PlayerDetailView(player: PlayerInfo(
            id: "123",
            name: "LeBron James",
            teamAbbr: "LAL",
            position: "SF",
            imageName: "https://cdn.nba.com/headshots/nba/latest/1040x760/2544.png"
        ))
        .environmentObject(DataViewModel(service: MockDataService()))
    }
}
