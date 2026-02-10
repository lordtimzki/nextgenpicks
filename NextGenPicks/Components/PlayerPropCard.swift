import SwiftUI

struct PlayerPropCard: View {
    let player: PlayerCardData
    @State private var showingMoreMarkets: Bool = false
    @State private var showingPlayerDetail: Bool = false
    @State private var showingRankingBreakdown: Bool = false

    private var recommendation: String? {
        player.recommendedDirection
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

                    // Ranking Score Badge (clickable for breakdown)
                    if let score = player.rankingScore {
                        Button(action: { showingRankingBreakdown = true }) {
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
                }
                .padding(8)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                
                // Player Name (Bottom Left)
                Text(player.name)
                    .font(.system(size: 16, weight:. bold))
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

                        // Hit rate indicator (Last 5 games) - direction-aware
                        if let hitRate = player.hitRate, hitRate.total > 0 {
                            let isUnder = player.recommendedDirection == "Under"
                            let directionHits = isUnder ? (hitRate.total - hitRate.hits) : hitRate.hits
                            HStack(spacing: 3) {
                                // Visual dots: green = confirms recommendation
                                ForEach(0..<hitRate.results.count, id: \.self) { index in
                                    let confirmsDirection = isUnder ? !hitRate.results[index].hit : hitRate.results[index].hit
                                    Circle()
                                        .fill(confirmsDirection ? Color.brandEmerald : Color.brandRed.opacity(0.5))
                                        .frame(width: 6, height: 6)
                                }
                                Text("\(directionHits)/\(hitRate.total)")
                                    .font(.caption2)
                                    .fontWeight(.medium)
                                    .foregroundStyle(directionHits >= (hitRate.total / 2 + 1) ? Color.brandEmerald : Color.secondaryText)
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
                            isRecommended: recommendation == "Over"
                        )
                        PropButton(
                            label: "Under",
                            odds: mainProp.underOdds,
                            color: .brandRed,
                            isRecommended: recommendation == "Under"
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
        .sheet(isPresented: $showingRankingBreakdown) {
            RankingBreakdownSheet(player: player)
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

    enum ButtonSize {
        case regular, small
    }

    var body: some View {
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

// MARK: - Ranking Breakdown Sheet

struct RankingBreakdownSheet: View {
    let player: PlayerCardData
    @Environment(\.dismiss) private var dismiss

    // Recompute component scores from stored data to show the math
    private var edgeScore: Double {
        guard let edge = player.edge, let line = player.mainProp?.line, line > 0 else { return 0 }
        return min(10.0, (abs(edge) / line) * 40.0)
    }

    private var hitRateScore: Double {
        guard let hr = player.hitRate, hr.total > 0 else { return 5.0 }
        let directionalPct = player.recommendedDirection == "Under" ? (1.0 - hr.weightedPct) : hr.weightedPct
        return directionalPct * 10.0
    }

    private var oddsScore: Double {
        // Direction-aware: use the odds matching the recommendation
        let odds: Int
        if player.recommendedDirection == "Under" {
            odds = player.underOdds ?? -110
        } else {
            odds = player.overOdds ?? -110
        }
        if odds >= 100 { return 10.0 }
        else if odds >= -105 { return 8.0 }
        else if odds >= -110 { return 5.0 }
        else if odds >= -120 { return 3.0 }
        else { return 2.0 }
    }

    private var lineupMultiplier: String? {
        if player.lineupStatus == "GTD" { return "0.4x (Game-Time Decision)" }
        if player.lineupStatus == "STARTING" {
            let label = player.recommendedDirection == "Over" ? "1.1x boost" : "0.95x risk penalty"
            return "\(label) (Confirmed Starter)"
        }
        return nil
    }

    private var trendModifier: String? {
        guard let td = player.trendData else { return nil }
        if td.trend == "declining" {
            let penalty = min(30.0, td.declinePct)
            let direction = player.recommendedDirection == "Over" ? "penalty" : "boost"
            return "\(direction) based on \(String(format: "%.0f", penalty))% decline"
        } else if td.trend == "surging" {
            let direction = player.recommendedDirection == "Over" ? "1.05x boost" : "0.95x risk penalty"
            return "\(direction) (Surging)"
        }
        return nil
    }

    private var homeAwayModifier: String? {
        guard let mod = player.homeAwayModifier, mod != 1.0 else { return nil }
        let venue = player.isHome == true ? "Home" : "Away"
        let impact = mod > 1.0 ? "boost" : "penalty"
        return String(format: "%.2fx (%@ %@)", mod, venue, impact)
    }

    private var minutesModifier: String? {
        guard let mod = player.minutesConfidence, mod != 1.0 else { return nil }
        let mpg = player.avgMinutes.map { String(format: "%.1f MPG", $0) } ?? ""
        let impact = mod > 1.0 ? "Volume boost" : "Volume penalty"
        return String(format: "%.2fx (%@ %@)", mod, mpg, impact)
    }
    
    private var usageVacuumModifier: String? {
        guard let mod = player.usageVacuum, mod != 1.0 else { return nil }
        let directionLabel = player.recommendedDirection == "Over" ? "Usage boost" : "Usage penalty"
        return String(format: "%.2fx (%@ - Missing teammates)", mod, directionLabel)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    // Header with total score
                    headerSection

                    // Formula
                    formulaSection

                    Divider().background(Color.border)

                    // Component breakdown
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Components")
                            .font(.subheadline)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)

                        edgeRow
                        matchupRow
                        hitRateRow
                        efficiencyRow
                        oddsRow
                        usageVacuumRow
                    }

                    // Modifiers
                    if lineupMultiplier != nil || trendModifier != nil || homeAwayModifier != nil || minutesModifier != nil || usageVacuumModifier != nil {
                        Divider().background(Color.border)
                        modifiersSection
                    }

                    // Context info
                    if hasContextInfo {
                        Divider().background(Color.border)
                        contextSection
                    }
                }
                .padding(20)
            }
            .background(Color.background)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                        .foregroundStyle(Color.brandEmerald)
                }
            }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack(spacing: 12) {
            // Score circle
            ZStack {
                Circle()
                    .stroke(scoreColor.opacity(0.3), lineWidth: 4)
                    .frame(width: 56, height: 56)
                Circle()
                    .trim(from: 0, to: (player.rankingScore ?? 0) / 10.0)
                    .stroke(scoreColor, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .frame(width: 56, height: 56)
                    .rotationEffect(.degrees(-90))
                Text(String(format: "%.1f", player.rankingScore ?? 0))
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Ranking Score")
                    .font(.headline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Text("\(player.name) - \(player.mainProp?.statName ?? "") \(String(format: "%.1f", player.mainProp?.line ?? 0))")
                    .font(.caption)
                    .foregroundStyle(Color.secondaryText)
                if let rec = player.recommendedDirection {
                    HStack(spacing: 4) {
                        Image(systemName: rec == "Over" ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                            .font(.caption2)
                        Text("Lean: \(rec)")
                            .font(.caption)
                            .fontWeight(.semibold)
                    }
                    .foregroundStyle(rec == "Over" ? Color.brandEmerald : Color.brandRed)
                }
            }

            Spacer()
        }
    }

    private var scoreColor: Color {
        let score = player.rankingScore ?? 0
        if score >= 7 { return .brandEmerald }
        if score >= 4 { return .brandOrange }
        return .brandRed
    }

    // MARK: - Formula

    private var formulaSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Formula (v6)")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(Color.secondaryText)
            Text("(Edge x 0.35) + (Matchup x 0.20-25) + (Hit Rate x 0.20) + (Efficiency x 0.10) + (Odds x 0.15)")
                .font(.caption2)
                .foregroundStyle(Color.secondaryText.opacity(0.8))
                .fixedSize(horizontal: false, vertical: true)
            Text("Directional Modifiers: Lineup, Trend, Venue, Volume, Usage Vacuum")
                .font(.caption2)
                .foregroundStyle(Color.secondaryText.opacity(0.6))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    // MARK: - Component Rows

    private var edgeRow: some View {
        ComponentRow(
            icon: "arrow.up.arrow.down",
            label: "Edge",
            weight: "35%",
            score: edgeScore,
            color: .brandEmerald,
            details: edgeDetails
        )
    }

    private var edgeDetails: String {
        guard let avg = player.playerAverage, let line = player.mainProp?.line else { return "No data" }
        let edge = player.edge ?? (avg - line)
        let pct = (abs(edge) / (line > 0 ? line : 1)) * 100
        let dir = edge >= 0 ? "above" : "below"
        return "Avg \(String(format: "%.1f", avg)) is \(String(format: "%.1f%%", pct)) \(dir) the line (\(String(format: "%.1f", line)))"
    }

    private var matchupRow: some View {
        ComponentRow(
            icon: "shield.lefthalf.filled",
            label: "Matchup",
            weight: "20-25%",
            score: player.matchupScore ?? 5.0,
            color: .brandBlue,
            details: matchupDetails
        )
    }

    private var matchupDetails: String {
        var parts: [String] = []
        if let defRank = player.oppDefRank {
            parts.append("Def Rank: #\(defRank)/30")
        }
        if let paceRank = player.oppPaceRank {
            parts.append("Pace Rank: #\(paceRank)/30")
        }
        if let opp = player.opponentAbbr, !opp.isEmpty {
            parts.insert("vs \(opp)", at: 0)
        }
        return parts.isEmpty ? "Default (neutral)" : parts.joined(separator: " | ")
    }

    private var hitRateRow: some View {
        ComponentRow(
            icon: "target",
            label: "Hit Rate",
            weight: "20%",
            score: hitRateScore,
            color: .brandOrange,
            details: hitRateDetails
        )
    }

    private var hitRateDetails: String {
        guard let hr = player.hitRate, hr.total > 0 else { return "No recent data" }
        let isUnder = player.recommendedDirection == "Under"
        let directionHits = isUnder ? (hr.total - hr.hits) : hr.hits
        let games = hr.results.prefix(5).map { result in
            let confirmsDirection = isUnder ? !result.hit : result.hit
            return confirmsDirection ? "HIT" : "MISS"
        }.joined(separator: ", ")
        let directionalPct = isUnder ? (1.0 - hr.weightedPct) : hr.weightedPct
        let weightedStr = String(format: "%.0f%%", directionalPct * 100)
        let dirLabel = isUnder ? "Under" : "Over"
        return "\(directionHits)/\(hr.total) \(dirLabel) | Weighted: \(weightedStr) (\(games))"
    }

    private var efficiencyRow: some View {
        ComponentRow(
            icon: "chart.bar.fill",
            label: "Efficiency",
            weight: "10%",
            score: player.efficiencyScore ?? 5.0,
            color: .brandPurple,
            details: efficiencyDetails
        )
    }

    private var efficiencyDetails: String {
        guard let adv = player.playerAdvanced else { return "No advanced stats" }
        var parts: [String] = []
        if let usg = adv.usgPct { parts.append("USG: \(String(format: "%.1f", usg))%") }
        if let ts = adv.tsPct { parts.append("TS: \(String(format: "%.1f", ts))%") }
        if let reb = adv.rebPct { parts.append("REB: \(String(format: "%.1f", reb))%") }
        if let ast = adv.astPct { parts.append("AST: \(String(format: "%.1f", ast))%") }
        return parts.isEmpty ? "No advanced stats" : parts.joined(separator: " | ")
    }

    private var oddsRow: some View {
        ComponentRow(
            icon: "dollarsign.circle.fill",
            label: "Odds Value",
            weight: "15%",
            score: oddsScore,
            color: Color(hex: "eab308"),
            details: oddsDetails
        )
    }

    private var oddsDetails: String {
        let direction = player.recommendedDirection ?? "Over"
        let odds: Int
        if direction == "Under" {
            odds = player.underOdds ?? -110
        } else {
            odds = player.overOdds ?? -110
        }
        let formatted = odds > 0 ? "+\(odds)" : "\(odds)"
        let tier: String
        if odds >= 100 { tier = "Plus Money" }
        else if odds >= -105 { tier = "Near Even" }
        else if odds >= -110 { tier = "Standard" }
        else if odds >= -120 { tier = "Below Avg" }
        else { tier = "Poor Value" }
        return "\(direction) odds: \(formatted) (\(tier))"
    }
    
    private var usageVacuumRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let mod = player.usageVacuum, mod != 1.0 {
                HStack {
                    Image(systemName: "person.3.fill")
                        .font(.caption)
                        .foregroundStyle(Color.brandEmerald)
                        .frame(width: 16)
                    Text("Usage Vacuum")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                    Spacer()
                    Text("Impact: \(String(format: "%.2fx", mod))")
                        .font(.caption2)
                        .foregroundStyle(Color.brandEmerald)
                }
                Text("Missing teammates opening up \(String(format: "%.0f%%", (mod - 1.0) * 100 * 2)) usage potential.")
                    .font(.caption2)
                    .foregroundStyle(Color.secondaryText)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(modExists ? 10 : 0)
        .background(modExists ? Color.surface : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
    
    private var modExists: Bool {
        return (player.usageVacuum ?? 1.0) != 1.0
    }

    // MARK: - Modifiers

    private var modifiersSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Modifiers Applied")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            if let lineup = lineupMultiplier {
                HStack(spacing: 8) {
                    Image(systemName: player.lineupStatus == "STARTING" ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundStyle(player.lineupStatus == "STARTING" ? Color.brandEmerald : Color.brandOrange)
                    Text("Lineup: \(lineup)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.9))
                }
            }

            if let trend = trendModifier {
                HStack(spacing: 8) {
                    Image(systemName: player.trendData?.trend == "surging" ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption)
                        .foregroundStyle(player.trendData?.trend == "surging" ? Color.brandEmerald : Color.brandRed)
                    Text("Trend: \(trend)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.9))
                }
            }

            if let ha = homeAwayModifier {
                HStack(spacing: 8) {
                    Image(systemName: player.isHome == true ? "house.fill" : "airplane")
                        .font(.caption)
                        .foregroundStyle((player.homeAwayModifier ?? 1.0) >= 1.0 ? Color.brandEmerald : Color.brandRed)
                    Text("Venue: \(ha)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.9))
                }
            }

            if let mins = minutesModifier {
                HStack(spacing: 8) {
                    Image(systemName: "clock.fill")
                        .font(.caption)
                        .foregroundStyle((player.minutesConfidence ?? 1.0) >= 1.0 ? Color.brandEmerald : Color.brandOrange)
                    Text("Volume: \(mins)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.9))
                }
            }
            
            if let uv = usageVacuumModifier {
                HStack(spacing: 8) {
                    Image(systemName: "person.3.sequence.fill")
                        .font(.caption)
                        .foregroundStyle(Color.brandEmerald)
                    Text("Teammates: \(uv)")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.9))
                }
            }
        }
    }

    // MARK: - Context

    private var hasContextInfo: Bool {
        (player.restStatus != nil && !player.restStatus!.isEmpty) ||
        (player.teamInjuries != nil && !player.teamInjuries!.isEmpty) ||
        (player.oppInjuries != nil && !player.oppInjuries!.isEmpty)
    }

    private var contextSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Context")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            if let rest = player.restStatus, !rest.isEmpty {
                contextRow(icon: "bed.double.fill", label: "Rest", value: formatRestStatus(rest))
            }
            if let injuries = player.teamInjuries, !injuries.isEmpty {
                contextRow(icon: "cross.case.fill", label: "Team Injuries", value: injuries)
            }
            if let oppInj = player.oppInjuries, !oppInj.isEmpty {
                contextRow(icon: "cross.case", label: "Opp. Injuries", value: oppInj)
            }
        }
    }

    private func formatRestStatus(_ rest: String) -> String {
        if rest == "B2B" {
            return "Back-to-Back (2nd game — played yesterday)"
        } else if rest.hasPrefix("B2B vs") {
            let detail = rest.replacingOccurrences(of: "B2B vs ", with: "")
            return "Back-to-Back (2nd game — played \(detail) yesterday)"
        }
        return rest
    }

    private func contextRow(icon: String, label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(Color.secondaryText)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(Color.secondaryText)
                Text(value)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.9))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

// MARK: - Component Row (reusable for breakdown)

private struct ComponentRow: View {
    let icon: String
    let label: String
    let weight: String
    let score: Double
    let color: Color
    let details: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(color)
                    .frame(width: 16)
                Text(label)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.white)
                Text(weight)
                    .font(.caption2)
                    .foregroundStyle(Color.secondaryText)
                Spacer()
                Text(String(format: "%.1f", score))
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(scoreColor)
                Text("/ 10")
                    .font(.caption2)
                    .foregroundStyle(Color.secondaryText)
            }

            // Score bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(color.opacity(0.15))
                        .frame(height: 6)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(color)
                        .frame(width: geo.size.width * min(1.0, score / 10.0), height: 6)
                }
            }
            .frame(height: 6)

            // Details
            Text(details)
                .font(.caption2)
                .foregroundStyle(Color.secondaryText)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .background(Color.surface)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var scoreColor: Color {
        if score >= 7 { return .brandEmerald }
        if score >= 4 { return .brandOrange }
        return .brandRed
    }
}
