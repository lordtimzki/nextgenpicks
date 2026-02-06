import SwiftUI

struct FeedView: View {
    @EnvironmentObject var vm: DataViewModel
    
    // Grid Setup: 2 Columns
    let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]
    
    var body: some View {
        NavigationView {
            ZStack {
                Color.background.ignoresSafeArea()
                
                if vm.isLoading && vm.featuredProps.isEmpty {
                    ProgressView()
                        .tint(.white)
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            
                            // 1. Header
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Today's player props")
                                    .font(.subheadline)
                                    .foregroundStyle(.gray)

                                if !vm.refreshStatusText.isEmpty {
                                    HStack(spacing: 4) {
                                        Image(systemName: vm.isRefreshing ? "arrow.triangle.2.circlepath" : "clock.arrow.circlepath")
                                            .font(.caption2)
                                        Text(vm.refreshStatusText)
                                            .font(.caption)
                                    }
                                    .foregroundStyle(.gray.opacity(0.7))
                                }
                            }
                            .padding(.horizontal)
                            .padding(.top, 10)
                            
                            // 2. For You Section (top 5 picks for parlay builders)
                            if !vm.forYouProps.isEmpty {
                                VStack(alignment: .leading, spacing: 12) {
                                    HStack {
                                        Text("For You")
                                            .font(.title3)
                                            .fontWeight(.bold)
                                            .foregroundStyle(.white)

                                        Spacer()

                                        HStack(spacing: 4) {
                                            Image(systemName: "star.fill")
                                                .font(.caption)
                                            Text("Top 5 Legs")
                                                .font(.caption)
                                        }
                                        .foregroundStyle(Color.brandOrange)
                                    }
                                    .padding(.horizontal)

                                    LazyVGrid(columns: columns, spacing: 12) {
                                        ForEach(Array(vm.forYouProps.prefix(5))) { prop in
                                            PlayerPropCard(player: prop)
                                        }
                                    }
                                    .padding(.horizontal)
                                }

                                // Separator line
                                Rectangle()
                                    .fill(Color.gray.opacity(0.3))
                                    .frame(height: 1)
                                    .padding(.horizontal)
                                    .padding(.vertical, 8)
                            }

                            // 3. Quick Stats Row
                            HStack(spacing: 12) {
                                QuickStatCard(
                                    title: "Hot Props",
                                    value: "\(vm.featuredProps.filter({ $0.trending == .hot }).count)",
                                    iconName: "flame.fill",
                                    color: .brandOrange
                                )
                                QuickStatCard(
                                    title: "Live Now",
                                    value: "\(vm.games.filter({ $0.status == .live }).count)", // Using games data to show live count
                                    iconName: "clock.fill",
                                    color: .brandBlue
                                )
                                QuickStatCard(
                                    title: "Total Props",
                                    value: "\(vm.featuredProps.count)",
                                    iconName: "list.bullet",
                                    color: .brandPurple
                                )
                            }
                            .padding(.horizontal)

                            // 4. Top Picks Section (highest ranked props)
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Top Picks")
                                    .font(.title3)
                                    .fontWeight(.bold)
                                    .foregroundStyle(.white)
                                    .padding(.horizontal)

                                LazyVGrid(columns: columns, spacing: 12) {
                                    ForEach(vm.featuredProps) { prop in
                                        PlayerPropCard(player: prop)
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                        .padding(.bottom, 20)
                    }
                }
            }
            .navigationBarHidden(true)
            .task {
                await vm.loadInitialData()
            }
        }
    }
}

#Preview {
    FeedView()
        .environmentObject(DataViewModel(service: MockDataService()))
}
