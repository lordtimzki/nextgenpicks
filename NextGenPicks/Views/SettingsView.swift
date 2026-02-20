import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var vm: DataViewModel
    @Environment(\.dismiss) private var dismiss

    private let nbaTeams = [
        "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN",
        "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA",
        "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
        "POR", "SAC", "SAS", "TOR", "UTA", "WAS"
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                Color.background.ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {

                        // MARK: - Risk & Style
                        settingsSection("Risk & Style") {
                            VStack(alignment: .leading, spacing: 16) {
                                Text("Risk Tolerance")
                                    .font(.caption)
                                    .foregroundStyle(.gray)
                                Picker("Risk Tolerance", selection: $vm.userSettings.riskTolerance) {
                                    ForEach(RiskTolerance.allCases, id: \.self) { level in
                                        Text(level.rawValue).tag(level)
                                    }
                                }
                                .pickerStyle(.segmented)
                            }
                        }

                        // MARK: - NBA
                        settingsSection("NBA") {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Favorite Teams")
                                    .font(.caption)
                                    .foregroundStyle(.gray)

                                LazyVGrid(columns: [
                                    GridItem(.adaptive(minimum: 60), spacing: 8)
                                ], spacing: 8) {
                                    ForEach(nbaTeams, id: \.self) { team in
                                        let isSelected = vm.userSettings.favoriteNBATeams.contains(team)
                                        Button {
                                            if isSelected {
                                                vm.userSettings.favoriteNBATeams.removeAll { $0 == team }
                                            } else {
                                                vm.userSettings.favoriteNBATeams.append(team)
                                            }
                                            vm.saveSettingsLocally()
                                        } label: {
                                            Text(team)
                                                .font(.caption)
                                                .fontWeight(.semibold)
                                                .frame(maxWidth: .infinity)
                                                .padding(.vertical, 8)
                                                .background(isSelected ? Color.brandEmerald.opacity(0.3) : Color.white.opacity(0.05))
                                                .foregroundStyle(isSelected ? Color.brandEmerald : .gray)
                                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: 8)
                                                        .stroke(isSelected ? Color.brandEmerald.opacity(0.5) : Color.clear, lineWidth: 1)
                                                )
                                        }
                                    }
                                }
                            }
                        }

                        // MARK: - Focused Stats
                        settingsSection("Focused Stats") {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Select the stat types you want to see")
                                    .font(.caption)
                                    .foregroundStyle(.gray)

                                ForEach(StatFilter.allCases, id: \.self) { stat in
                                    let isSelected = vm.userSettings.focusedStats.contains(stat.rawValue)
                                    Button {
                                        if isSelected {
                                            vm.userSettings.focusedStats.removeAll { $0 == stat.rawValue }
                                        } else {
                                            vm.userSettings.focusedStats.append(stat.rawValue)
                                        }
                                        vm.saveSettingsLocally()
                                    } label: {
                                        HStack {
                                            Text(stat.rawValue)
                                                .font(.subheadline)
                                                .foregroundStyle(.white)
                                            Spacer()
                                            Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                                                .foregroundStyle(isSelected ? Color.brandEmerald : .gray)
                                        }
                                        .padding(.vertical, 4)
                                    }
                                }
                            }
                        }

                        // MARK: - Filtering
                        settingsSection("Filtering") {
                            VStack(alignment: .leading, spacing: 16) {
                                Toggle("Hide Fades", isOn: $vm.userSettings.hideFades)
                                    .tint(Color.brandEmerald)

                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Minimum Ranking Score: \(String(format: "%.1f", vm.userSettings.minRankingScore))")
                                        .font(.caption)
                                        .foregroundStyle(.gray)
                                    Slider(value: $vm.userSettings.minRankingScore, in: 0...10, step: 0.5)
                                        .tint(Color.brandEmerald)
                                }
                            }
                        }

                        // MARK: - Display
                        settingsSection("Display") {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Props Per Section: \(vm.userSettings.propsPerSection)")
                                    .font(.caption)
                                    .foregroundStyle(.gray)
                                Stepper("", value: $vm.userSettings.propsPerSection, in: 5...30, step: 5)
                                    .labelsHidden()
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        vm.saveSettingsLocally()
                        dismiss()
                    }
                    .foregroundStyle(Color.brandEmerald)
                }
            }
            .onChange(of: vm.userSettings.riskTolerance) { vm.saveSettingsLocally() }
            .onChange(of: vm.userSettings.hideFades) { vm.saveSettingsLocally() }
            .onChange(of: vm.userSettings.minRankingScore) { vm.saveSettingsLocally() }
            .onChange(of: vm.userSettings.propsPerSection) { vm.saveSettingsLocally() }
        }
    }

    private func settingsSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            content()
                .padding(16)
                .background(Color.surface)
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

#Preview {
    SettingsView()
        .environmentObject(DataViewModel(service: MockDataService()))
}
