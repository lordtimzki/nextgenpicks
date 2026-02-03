import SwiftUI

struct PlayerPropCard: View {
    let player: PlayerCardData
    @State private var isExpanded: Bool = false
    
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
                    HStack(spacing: 6) {
                        Text(player.teamAbbr)
                            .font(.caption2)
                            .fontWeight(.bold)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.white.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                        
                        Text(player.position)
                            .font(.caption2)
                            .foregroundStyle(.gray)
                    }
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
                Text("\(player.opponent) • \(player.gameTime)")
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
            
            // 4. Expanded Props
            if isExpanded && player.props.count > 1 {
                VStack(spacing: 12) {
                    ForEach(player.props.dropFirst()) { prop in
                        VStack(spacing: 8) {
                            Text(prop.statName + " " + String(format: "%.1f", prop.line))
                                .font(.caption)
                                .foregroundStyle(.gray)
                            
                            HStack(spacing: 8) {
                                PropButton(label: "Over", odds: prop.overOdds, color: .brandEmerald, size: .small)
                                PropButton(label: "Under", odds: prop.underOdds, color: .brandRed, size: .small)
                            }
                        }
                        .padding(8)
                        .background(Color.black.opacity(0.3))
                        .cornerRadius(8)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 12)
            }
            
            // 5. Expand Button
            if player.props.count > 1 {
                Button(action: { withAnimation { isExpanded.toggle() } }) {
                    HStack(spacing: 4) {
                        Text(isExpanded ? "Show Less" : "+\(player.props.count - 1) More Markets")
                        Image(systemName: "chevron.down")
                            .rotationEffect(Angle(degrees: isExpanded ? 180 : 0))
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
