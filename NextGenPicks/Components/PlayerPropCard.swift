import SwiftUI

struct PlayerPropCard: View {
    let player: PlayerCardData
    @State private var showingMoreMarkets: Bool = false
    @State private var showingPlayerDetail: Bool = false
    @State private var showingAIAnalysis: Bool = false

    // Computed property to get the recommended direction (from AI or algorithm)
    private var recommendation: String? {
        // Prefer AI recommendation, fall back to algorithmic recommendation
        player.aiRecommended ?? player.recommendedDirection
    }

    // Convert UTC time to user's local timezone with day of week
    private var formattedGameTime: String {
        // Try to parse ISO timestamp from gameTimeUTC
        if let utcString = player.gameTimeUTC {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

            if let date = formatter.date(from: utcString) {
                return formatGameDate(date)
            }

            // Try without fractional seconds
            formatter.formatOptions = [.withInternetDateTime]
            if let date = formatter.date(from: utcString) {
                return formatGameDate(date)
            }
        }

        // Fallback to existing gameTime string
        return player.gameTime
    }

    private func formatGameDate(_ date: Date) -> String {
        let calendar = Calendar.current
        let displayFormatter = DateFormatter()
        displayFormatter.timeZone = TimeZone.current
        displayFormatter.dateFormat = "h:mm a"
        let timeString = displayFormatter.string(from: date)

        // Check if the game is today
        if calendar.isDateInToday(date) {
            return timeString
        }

        // Check if the game is tomorrow
        if calendar.isDateInTomorrow(date) {
            return "Tmrw \(timeString)"
        }

        // Otherwise show short day of week and time
        displayFormatter.dateFormat = "E"
        let dayString = displayFormatter.string(from: date)
        displayFormatter.dateFormat = "h:mm a"
        return "\(dayString) \(timeString)"
    }

    var body: some View {
        VStack(spacing: 0) {
            // 1. Image Header Section
            ZStack(alignment: .bottomLeading) {

                // Player Image from URL
                AsyncImage(url: URL(string: player.imageName)) { phase in
                    switch phase {
                    case .empty:
                        // Loading state
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))
                            .aspectRatio(1, contentMode: .fit)
                            .overlay(
                                ProgressView()
                                    .tint(.gray)
                            )
                    case .success(let image):
                        // Loaded image
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(minWidth: 0, maxWidth: .infinity)
                            .aspectRatio(1, contentMode: .fit)
                            .clipped()
                    case .failure:
                        // Error fallback
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))
                            .aspectRatio(1, contentMode: .fit)
                            .overlay(
                                Image(systemName: "person.fill")
                                    .resizable()
                                    .padding(40)
                                    .foregroundStyle(.gray)
                                    .opacity(0.5)
                            )
                    @unknown default:
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))
                            .aspectRatio(1, contentMode: .fit)
                    }
                }
                
                // Gradient Overlay
                LinearGradient(
                    colors: [.surface.opacity(0), .surface.opacity(1)],
                    startPoint: .center,
                    endPoint: .bottom
                )
                
                // Badges (Top Right) - Hot/Fade Badge + Ranking
                VStack(alignment: .trailing, spacing: 4) {
                    // Hot Badge (only show for high-confidence picks)
                    if player.trending == .hot {
                        HStack(spacing: 4) {
                            Image(systemName: "flame.fill")
                                .font(.caption2)
                            Text("HOT")
                                .font(.caption2)
                                .fontWeight(.bold)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.brandOrange.opacity(0.9))
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // Fade Badge (show for props AI recommends avoiding)
                    if player.trending == .fade || player.isFade == true {
                        HStack(spacing: 4) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption2)
                            Text("FADE")
                                .font(.caption2)
                                .fontWeight(.bold)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.gray.opacity(0.9))
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // Ranking Score Badge (if available)
                    if let score = player.rankingScore {
                        HStack(spacing: 3) {
                            Image(systemName: "star.fill")
                                .font(.system(size: 8))
                            Text(String(format: "%.1f", score))
                                .font(.caption2)
                                .fontWeight(.semibold)
                        }
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Color.brandPurple.opacity(0.9))
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
                .padding(8)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                
                // Player Name (Bottom Left)
                Text(player.name)
                    .font(.headline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .lineLimit(1)
                    .padding(12)
            }
            
            // 2. Game Info Bar
            HStack {
                Text(player.opponent)
                    .font(.caption)
                    .fontWeight(.medium)

                // Lineup status badge
                if player.lineupStatus == "STARTING" {
                    HStack(spacing: 2) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.caption2)
                        Text("Confirmed")
                            .font(.system(size: 9, weight: .medium))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(Color.brandEmerald.opacity(0.85))
                    .clipShape(Capsule())
                } else if player.lineupStatus == "GTD" {
                    HStack(spacing: 2) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.caption2)
                        Text("GTD")
                            .font(.system(size: 9, weight: .medium))
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 2)
                    .background(Color.brandOrange.opacity(0.85))
                    .clipShape(Capsule())
                }

                Spacer()
                HStack(spacing: 4) {
                    Image(systemName: "clock")
                        .font(.caption2)
                    Text(formattedGameTime)
                        .font(.caption)
                }
            }
            .foregroundStyle(.gray)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color.white.opacity(0.03))
            .overlay(
                Rectangle()
                    .frame(height: 1)
                    .foregroundStyle(Color.border),
                alignment: .bottom
            )
            
            // 3. Main Prop Section
            if let mainProp = player.mainProp {
                VStack(spacing: 12) {
                    VStack(spacing: 2) {
                        Text(mainProp.statName)
                            .font(.caption)
                            .foregroundStyle(Color.secondaryText)
                        Text("\(String(format: "%.1f", mainProp.line))")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                    }

                    // Show edge indicator and hit rate
                    HStack(spacing: 12) {
                        // Edge indicator
                        if let edge = player.edge, let avg = player.playerAverage, edge != 0 {
                            HStack(spacing: 4) {
                                Image(systemName: edge > 0 ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                                    .font(.caption2)
                                Text("Avg: \(String(format: "%.1f", avg))")
                                    .font(.caption2)
                            }
                            .foregroundStyle(edge > 0 ? Color.brandEmerald : Color.brandRed)
                        }

                        // Hit rate indicator (Last 5 games)
                        if let hitRate = player.hitRate, hitRate.total > 0 {
                            HStack(spacing: 3) {
                                // Visual dots for last 5 games
                                ForEach(0..<hitRate.results.count, id: \.self) { index in
                                    Circle()
                                        .fill(hitRate.results[index].hit ? Color.brandEmerald : Color.brandRed.opacity(0.5))
                                        .frame(width: 6, height: 6)
                                }
                                Text("\(hitRate.hits)/\(hitRate.total)")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundStyle(hitRate.hits >= 3 ? Color.brandEmerald : Color.secondaryText)
                            }
                        }
                    }

                    // Recommendation indicator (combines AI + algorithmic recommendation)
                    if let rec = recommendation {
                        HStack(spacing: 4) {
                            Image(systemName: "chart.line.uptrend.xyaxis")
                                .font(.caption2)
                            Text("Lean: \(rec)")
                                .font(.caption2)
                                .fontWeight(.bold)
                        }
                        .foregroundStyle(rec == "Over" ? Color.brandEmerald : Color.brandRed)
                        .padding(.top, 2)
                    }

                    // Over/Under buttons with recommendation highlight and AI indicator
                    HStack(spacing: 8) {
                        PropButton(
                            label: "Over",
                            odds: mainProp.overOdds,
                            color: .brandEmerald,
                            isRecommended: recommendation == "Over",
                            hasAIAnalysis: recommendation == "Over" && player.ai_analysis != nil && !player.ai_analysis!.isEmpty,
                            onAITap: { showingAIAnalysis = true }
                        )
                        PropButton(
                            label: "Under",
                            odds: mainProp.underOdds,
                            color: .brandRed,
                            isRecommended: recommendation == "Under",
                            hasAIAnalysis: recommendation == "Under" && player.ai_analysis != nil && !player.ai_analysis!.isEmpty,
                            onAITap: { showingAIAnalysis = true }
                        )
                    }
                }
                .padding(12)
            }

            // 4. More Markets Button (only show for legacy multi-prop cards)
            if let props = player.props, props.count > 1 {
                Button(action: { showingMoreMarkets = true }) {
                    HStack(spacing: 4) {
                        Text("+\(props.count - 1) More Markets")
                        Image(systemName: "chevron.right")
                    }
                    .font(.caption)
                    .foregroundStyle(.gray)
                    .padding(.bottom, 12)
                }
            }
        }
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.border, lineWidth: 1)
        )
        .sheet(isPresented: $showingMoreMarkets) {
            MoreMarketsSheet(player: player)
        }
        .sheet(isPresented: $showingAIAnalysis) {
            if let analysis = player.ai_analysis, !analysis.isEmpty {
                AIAnalysisSheet(
                    playerName: player.name,
                    statName: player.mainProp?.statName ?? "",
                    line: player.mainProp?.line ?? 0,
                    recommendation: recommendation,
                    analysis: analysis
                )
            }
        }
    }
}

// Sheet view for additional markets
struct MoreMarketsSheet: View {
    let player: PlayerCardData
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            sheetContent
                .background(Color.background)
                .navigationTitle("All Markets")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("Done") { dismiss() }
                            .foregroundStyle(Color.brandEmerald)
                    }
                }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private var sheetContent: some View {
        ScrollView {
            VStack(spacing: 16) {
                playerHeader
                Divider().background(Color.border)
                propsList
            }
            .padding(.vertical)
        }
    }

    private var playerHeader: some View {
        HStack(spacing: 12) {
            playerImage
            VStack(alignment: .leading, spacing: 2) {
                Text(player.name)
                    .font(.headline)
                    .fontWeight(.bold)
                Text(player.teamAbbr)
                    .font(.caption)
                    .foregroundStyle(.gray)
            }
            Spacer()
        }
        .padding(.horizontal)
    }

    private var playerImage: some View {
        AsyncImage(url: URL(string: player.imageName)) { image in
            image
                .resizable()
                .aspectRatio(contentMode: .fill)
        } placeholder: {
            Image(systemName: "person.fill")
                .foregroundStyle(.gray)
        }
        .frame(width: 50, height: 50)
        .clipShape(Circle())
    }

    private var propsList: some View {
        VStack(spacing: 12) {
            if let props = player.props {
                ForEach(props) { prop in
                    PropRow(prop: prop)
                }
            } else if let mainProp = player.mainProp {
                // For single-prop cards, just show the one prop
                PropRow(prop: mainProp)
            }
        }
        .padding(.horizontal)
    }
}

// Individual prop row for the sheet
struct PropRow: View {
    let prop: PlayerProp

    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Text(prop.statName)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                Spacer()
                Text(String(format: "%.1f", prop.line))
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }
            HStack(spacing: 12) {
                PropButton(label: "Over", odds: prop.overOdds, color: .brandEmerald)
                PropButton(label: "Under", odds: prop.underOdds, color: .brandRed)
            }
        }
        .padding()
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.border, lineWidth: 1)
        )
    }
}

// Helper Subview for Buttons
struct PropButton: View {
    let label: String
    let odds: Int
    let color: Color
    var size: ButtonSize = .regular
    var isRecommended: Bool = false
    var hasAIAnalysis: Bool = false
    var onAITap: (() -> Void)? = nil

    enum ButtonSize {
        case regular, small
    }

    var body: some View {
        Button(action: {
            if hasAIAnalysis, let tap = onAITap {
                tap()
            }
        }) {
            VStack(spacing: 2) {
                HStack(spacing: 3) {
                    if isRecommended {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 8))
                            .foregroundStyle(color)
                    }
                    Text(label)
                        .font(.caption2)
                        .foregroundStyle(isRecommended ? color : .gray)

                    // AI Analysis indicator on the recommended button
                    if hasAIAnalysis {
                        Image(systemName: "sparkles")
                            .font(.system(size: 9))
                            .foregroundStyle(Color.brandPurple)
                    }
                }
                Text(odds > 0 ? "+\(odds)" : "\(odds)")
                    .font(size == .regular ? .subheadline : .caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(color)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, size == .regular ? 8 : 4)
            .background(color.opacity(isRecommended ? 0.2 : 0.1))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(color.opacity(isRecommended ? 0.6 : 0.3), lineWidth: isRecommended ? 2 : 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }
}

// AI Analysis Sheet
struct AIAnalysisSheet: View {
    let playerName: String
    let statName: String
    let line: Double
    let recommendation: String?
    let analysis: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkles")
                            .font(.title2)
                            .foregroundStyle(Color.brandPurple)
                        Text("AI Analysis")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                    }

                    Text("\(playerName) - \(statName) \(String(format: "%.1f", line))")
                        .font(.subheadline)
                        .foregroundStyle(Color.secondaryText)
                }

                // Recommendation badge
                if let rec = recommendation {
                    HStack(spacing: 6) {
                        Image(systemName: rec == "Over" ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                            .font(.body)
                        Text("Recommended: \(rec)")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                    }
                    .foregroundStyle(rec == "Over" ? Color.brandEmerald : Color.brandRed)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background((rec == "Over" ? Color.brandEmerald : Color.brandRed).opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                // Analysis text
                Text(analysis)
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.9))
                    .lineSpacing(4)

                Spacer()

                // Disclaimer
                Text("AI analysis is for informational purposes only. Always do your own research.")
                    .font(.caption2)
                    .foregroundStyle(Color.secondaryText)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.background)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(Color.brandEmerald)
                }
            }
        }
        .presentationDetents([.medium])
        .presentationDragIndicator(.visible)
    }
}
