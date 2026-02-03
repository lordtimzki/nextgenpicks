import SwiftUI

struct PlayerPropCard: View {
    let player: PlayerCardData
    @State private var showingMoreMarkets: Bool = false

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

        // Check if the game is today
        if calendar.isDateInToday(date) {
            displayFormatter.dateFormat = "h:mm a"
            return "Today \(displayFormatter.string(from: date))"
        }

        // Check if the game is tomorrow
        if calendar.isDateInTomorrow(date) {
            displayFormatter.dateFormat = "h:mm a"
            return "Tomorrow \(displayFormatter.string(from: date))"
        }

        // Otherwise show day of week and time
        displayFormatter.dateFormat = "EEE h:mm a"
        return displayFormatter.string(from: date)
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
                
                // Trending Badge (Top Right)
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
                    .padding(8)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                } else {
                    HStack(spacing: 4) {
                        Image(systemName: "chart.line.uptrend.xyaxis")
                            .font(.caption2)
                        Text("TRENDING")
                            .font(.caption2)
                            .fontWeight(.bold)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.brandEmerald.opacity(0.9))
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding(8)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                }
                
                // Player Info (Bottom Left)
                VStack(alignment: .leading, spacing: 4) {
                    Text(player.teamAbbr)
                        .font(.caption2)
                        .fontWeight(.bold)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.white.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                    Text(player.name)
                        .font(.headline)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .lineLimit(1)
                }
                .padding(12)
            }
            
            // 2. Game Info Bar
            HStack(spacing: 8) {
                Image(systemName: "clock")
                    .font(.caption2)
                Text("\(player.opponent) • \(formattedGameTime)")
                    .font(.caption)
            }
            .foregroundStyle(.gray)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(Color.white.opacity(0.03))
            .overlay(
                Rectangle()
                    .frame(height: 1)
                    .foregroundStyle(Color.border),
                alignment: .bottom
            )
            
            // 3. Main Prop Section
            if let mainProp = player.props.first {
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
                    
                    HStack(spacing: 8) {
                        PropButton(label: "Over", odds: mainProp.overOdds, color: .brandEmerald)
                        PropButton(label: "Under", odds: mainProp.underOdds, color: .brandRed)
                    }
                }
                .padding(12)
            }
            
            // 4. More Markets Button
            if player.props.count > 1 {
                Button(action: { showingMoreMarkets = true }) {
                    HStack(spacing: 4) {
                        Text("+\(player.props.count - 1) More Markets")
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
            ForEach(player.props) { prop in
                PropRow(prop: prop)
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
    
    enum ButtonSize {
        case regular, small
    }
    
    var body: some View {
        Button(action: {}) {
            VStack(spacing: 0) {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.gray)
                Text(odds > 0 ? "+\(odds)" : "\(odds)")
                    .font(size == .regular ? .subheadline : .caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(color)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, size == .regular ? 8 : 4)
            .background(color.opacity(0.1))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(color.opacity(0.3), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }
}
