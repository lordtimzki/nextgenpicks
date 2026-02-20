import SwiftUI

enum SearchTab: String, CaseIterable {
    case players = "Players"
    case teams = "Teams"
}

struct SearchView: View {
    @EnvironmentObject var vm: DataViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var searchText: String = ""
    @State private var selectedTab: SearchTab = .players

    var body: some View {
        NavigationStack {
            ZStack {
                Color.background.ignoresSafeArea()

                VStack(spacing: 0) {
                    // Search Bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(.gray)
                        TextField("Search players or teams...", text: $searchText)
                            .foregroundStyle(.white)
                            .autocorrectionDisabled()
                        if !searchText.isEmpty {
                            Button(action: { searchText = "" }) {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.gray)
                            }
                        }
                    }
                    .padding(12)
                    .background(Color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal)
                    .padding(.top, 8)

                    // Tab Picker
                    Picker("Search Type", selection: $selectedTab) {
                        ForEach(SearchTab.allCases, id: \.self) { tab in
                            Text(tab.rawValue).tag(tab)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding()

                    // Content
                    if vm.isSearchLoading {
                        Spacer()
                        ProgressView()
                            .tint(.white)
                        Spacer()
                    } else {
                        switch selectedTab {
                        case .players:
                            PlayerSearchList(searchText: searchText)
                        case .teams:
                            TeamSearchList(searchText: searchText)
                        }
                    }
                }
            }
            .navigationTitle("Search")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading){
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .foregroundStyle(.white)
                    }
                }
            }
        }
    }
}

// MARK: - Player Search List

struct PlayerSearchList: View {
    @EnvironmentObject var vm: DataViewModel
    let searchText: String

    var filteredPlayers: [PlayerInfo] {
        vm.searchPlayers(query: searchText)
    }

    var body: some View {
        if filteredPlayers.isEmpty {
            VStack(spacing: 12) {
                Image(systemName: "person.slash")
                    .font(.system(size: 48))
                    .foregroundStyle(.gray)
                Text("No players found")
                    .font(.headline)
                    .foregroundStyle(.gray)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(filteredPlayers) { player in
                        NavigationLink(destination: PlayerDetailView(player: player)) {
                            PlayerSearchRow(player: player)
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
        }
    }
}

// MARK: - Team Search List

struct TeamSearchList: View {
    @EnvironmentObject var vm: DataViewModel
    let searchText: String

    var filteredTeams: [TeamInfo] {
        vm.searchTeams(query: searchText)
    }

    var body: some View {
        if filteredTeams.isEmpty {
            VStack(spacing: 12) {
                Image(systemName: "building.2.slash")
                    .font(.system(size: 48))
                    .foregroundStyle(.gray)
                Text("No teams found")
                    .font(.headline)
                    .foregroundStyle(.gray)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(filteredTeams) { team in
                        NavigationLink(destination: TeamDetailView(team: team)) {
                            TeamSearchRow(team: team)
                        }
                    }
                }
                .padding(.horizontal)
                .padding(.bottom, 20)
            }
        }
    }
}

// MARK: - Player Search Row

struct PlayerSearchRow: View {
    let player: PlayerInfo

    var body: some View {
        HStack(spacing: 12) {
            // Player Image
            AsyncImage(url: URL(string: player.imageName)) { phase in
                switch phase {
                case .empty:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 50, height: 50)
                        .overlay(ProgressView().tint(.gray))
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: 50, height: 50)
                        .clipShape(Circle())
                case .failure:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 50, height: 50)
                        .overlay(
                            Image(systemName: "person.fill")
                                .foregroundStyle(.gray)
                        )
                @unknown default:
                    Circle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 50, height: 50)
                }
            }

            // Player Info
            VStack(alignment: .leading, spacing: 4) {
                Text(player.name)
                    .font(.headline)
                    .foregroundStyle(.white)
                HStack(spacing: 8) {
                    Text(player.teamAbbr)
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(Color.brandEmerald)
                    Text(player.position)
                        .font(.caption)
                        .foregroundStyle(.gray)
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundStyle(.gray)
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Team Search Row

struct TeamSearchRow: View {
    let team: TeamInfo

    var body: some View {
        HStack(spacing: 12) {
            // Team Icon
            ZStack {
                Circle()
                    .fill(Color.brandEmerald.opacity(0.2))
                    .frame(width: 50, height: 50)
                Text(team.abbreviation)
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(Color.brandEmerald)
            }

            // Team Info
            VStack(alignment: .leading, spacing: 4) {
                Text(team.abbreviation)
                    .font(.headline)
                    .foregroundStyle(.white)
                Text("\(team.playerCount) players with props")
                    .font(.caption)
                    .foregroundStyle(.gray)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundStyle(.gray)
        }
        .padding(12)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

#Preview {
    SearchView()
        .environmentObject(DataViewModel(service: MockDataService()))
}
