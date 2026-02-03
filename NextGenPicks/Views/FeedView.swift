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
                                Text("Welcome Back")
                                    .font(.largeTitle)
                                    .fontWeight(.bold)
                                    .foregroundStyle(.white)
                                Text("Trending player props for today")
                                    .font(.subheadline)
                                    .foregroundStyle(.gray)
                            }
                            .padding(.horizontal)
                            .padding(.top, 10)
                            
                            // 2. Quick Stats Row
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
                                    title: "Trending",
                                    value: "\(vm.featuredProps.filter({ $0.trending == .up }).count)",
                                    iconName: "chart.line.uptrend.xyaxis",
                                    color: .brandPurple
                                )
                            }
                            .padding(.horizontal)
                            
                            // 3. Top Picks Section (highest ranked props)
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

                            // 4. For You Section (urgency-based, personalized)
                            if !vm.forYouProps.isEmpty {
                                VStack(alignment: .leading, spacing: 12) {
                                    HStack {
                                        Text("For You")
                                            .font(.title3)
                                            .fontWeight(.bold)
                                            .foregroundStyle(.white)

                                        Spacer()

                                        HStack(spacing: 4) {
                                            Image(systemName: "clock.fill")
                                                .font(.caption)
                                            Text("Starting Soon")
                                                .font(.caption)
                                        }
                                        .foregroundStyle(Color.brandOrange)
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
