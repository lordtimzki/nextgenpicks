import SwiftUI

struct FeedView: View {
    @EnvironmentObject var vm: DataViewModel
    @State private var showSearch = false
    @State private var showForYouInfo = false

    let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]

    var body: some View {
        NavigationView {
            ZStack {
                Color.background.ignoresSafeArea()

                if vm.isLoading && vm.allProps.isEmpty {
                    ProgressView()
                        .tint(.white)
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {

                            // 1. Header with search + settings
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Today's player props")
                                        .font(.subheadline)
                                        .foregroundStyle(.gray)

                                    if !vm.refreshStatusText.isEmpty {
                                        HStack(spacing: 4) {
                                            Image(systemName: vm.refreshComplete ? "checkmark.circle.fill" : (vm.isRefreshing ? "arrow.triangle.2.circlepath" : "clock.arrow.circlepath"))
                                                .font(.caption2)
                                            Text(vm.refreshStatusText)
                                                .font(.caption)
                                        }
                                        .foregroundStyle(vm.refreshComplete ? Color.brandEmerald.opacity(0.8) : .gray.opacity(0.7))
                                    }
                                }

                                Spacer()

                                Button { showSearch = true } label: {
                                    Image(systemName: "magnifyingglass")
                                        .font(.title2)
                                        .foregroundStyle(.white)
                                        .padding(10)
                                        .background(Color.white.opacity(0.1))
                                        .clipShape(Circle())
                                }

                                Button { vm.showSettings = true } label: {
                                    Image(systemName: "gearshape.fill")
                                        .font(.title2)
                                        .foregroundStyle(.white)
                                        .padding(10)
                                        .background(Color.white.opacity(0.1))
                                        .clipShape(Circle())
                                }
                            }
                            .padding(.horizontal)
                            .padding(.top, 10)

                            // 2. Quick Stats Row
                            HStack(spacing: 12) {
                                QuickStatCard(
                                    title: "Hot Props",
                                    value: "\(vm.allProps.filter({ $0.trending == .hot }).count)",
                                    iconName: "flame.fill",
                                    color: .brandOrange
                                )
                                QuickStatCard(
                                    title: "Total Props",
                                    value: "\(vm.allProps.count)",
                                    iconName: "list.bullet",
                                    color: .brandPurple
                                )
                            }
                            .padding(.horizontal)

                            // 3. For You Section (personalized picks)
                            if !vm.forYouProps.isEmpty {
                                VStack(alignment: .leading, spacing: 12) {
                                    HStack {
                                        Text("For You")
                                            .font(.title3)
                                            .fontWeight(.bold)
                                            .foregroundStyle(.white)

                                        Button {
                                            showForYouInfo = true
                                        } label: {
                                            Image(systemName: "info.circle")
                                                .font(.subheadline)
                                                .foregroundStyle(.gray)
                                        }

                                        Spacer()
                                    }
                                    .padding(.horizontal)

                                    LazyVGrid(columns: columns, spacing: 12) {
                                        ForEach(vm.forYouProps) { prop in
                                            PlayerPropCard(player: prop)
                                        }
                                    }
                                    .padding(.horizontal)
                                }
                            }

                            // 4. Picks Section (all filtered props)
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Picks")
                                    .font(.title3)
                                    .fontWeight(.bold)
                                    .foregroundStyle(.white)
                                    .padding(.horizontal)

                                LazyVGrid(columns: columns, spacing: 12) {
                                    ForEach(vm.topPicks) { prop in
                                        PlayerPropCard(player: prop)
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                        .padding(.bottom, 20)
                    }
                    .refreshable {
                        await vm.loadInitialData()
                    }
                }
            }
            .navigationBarHidden(true)
            .task {
                await vm.loadInitialData()
            }
        }
        .fullScreenCover(isPresented: $showSearch) {
            SearchView()
                .environmentObject(vm)
        }
        .sheet(isPresented: $vm.showSettings) {
            SettingsView()
                .environmentObject(vm)
        }
        .alert("How For You Works", isPresented: $showForYouInfo) {
            Button("Got it", role: .cancel) {}
        } message: {
            Text("Picks are personalized using your settings and live game context:\n\n"
                 + "- Favorite teams get a boost\n"
                 + "- Your focused stats are prioritized\n"
                 + "- High-confidence picks (70%+ hit rate) rank higher\n"
                 + "- Confirmed starters are preferred\n"
                 + "- Upcoming games get a slight edge\n\n"
                 + "One pick per player for variety.")
        }
    }
}

#Preview {
    FeedView()
        .environmentObject(DataViewModel(service: MockDataService()))
}
