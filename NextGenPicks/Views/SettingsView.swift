import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var vm: DataViewModel
    @Environment(\.dismiss) private var dismiss

    // Local draft — changes only apply when "Done" is tapped
    @State private var draft: UserSettings = .default

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
                                Picker("Risk Tolerance", selection: $draft.riskTolerance) {
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
                                        let isSelected = draft.favoriteNBATeams.contains(team)
                                        Button {
                                            if isSelected {
                                                draft.favoriteNBATeams.removeAll { $0 == team }
                                            } else {
                                                draft.favoriteNBATeams.append(team)
                                            }
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
                                    let isSelected = draft.focusedStats.contains(stat.rawValue)
                                    Button {
                                        if isSelected {
                                            draft.focusedStats.removeAll { $0 == stat.rawValue }
                                        } else {
                                            draft.focusedStats.append(stat.rawValue)
                                        }
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
                                Toggle("Hide Fades", isOn: $draft.hideFades)
                                    .tint(Color.brandEmerald)

                                Toggle("Hide Line Skepticism", isOn: $draft.hideLineSkepticism)
                                    .tint(Color.brandEmerald)
                                Text("Remove props where the line is set far above the player's average (books pricing in role changes)")
                                    .font(.caption2)
                                    .foregroundStyle(.gray)

                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Max Hits (Last 5): \(draft.maxLast5Hits >= 5 ? "Off" : "\(draft.maxLast5Hits)/5")")
                                        .font(.caption)
                                        .foregroundStyle(.gray)
                                    Slider(
                                        value: Binding(
                                            get: { Double(draft.maxLast5Hits) },
                                            set: { draft.maxLast5Hits = Int($0) }
                                        ),
                                        in: 1...5, step: 1
                                    )
                                    .tint(Color.brandEmerald)
                                    Text("Hide props that hit more than this in the last 5 games (avoids Vegas traps)")
                                        .font(.caption2)
                                        .foregroundStyle(.gray)
                                }

                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Minimum Ranking Score: \(String(format: "%.1f", draft.minRankingScore))")
                                        .font(.caption)
                                        .foregroundStyle(.gray)
                                    Slider(value: $draft.minRankingScore, in: 0...10, step: 0.5)
                                        .tint(Color.brandEmerald)
                                }
                            }
                        }

                        // MARK: - Display
                        settingsSection("Display") {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Props Per Section: \(draft.propsPerSection)")
                                    .font(.caption)
                                    .foregroundStyle(.gray)
                                Stepper("", value: $draft.propsPerSection, in: 5...30, step: 5)
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
                        vm.userSettings = draft
                        vm.saveSettingsLocally()
                        dismiss()
                    }
                    .foregroundStyle(Color.brandEmerald)
                }
            }
            .onAppear {
                draft = vm.userSettings
            }
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
