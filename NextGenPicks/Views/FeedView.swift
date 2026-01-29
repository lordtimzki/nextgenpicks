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
                            
                            // 3. Featured Props Grid
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Featured Props")
                                    .font(.title3)
                                    .fontWeight(.bold)
                                    .foregroundStyle(.white)
                                    .padding(.horizontal)
                                
                                LazyVGrid(columns: columns, spacing: 12) {
                                    ForEach(vm.featuredProps) { player in
                                        PlayerPropCard(player: player)
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
