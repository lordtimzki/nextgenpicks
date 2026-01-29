import SwiftUI

struct QuickStatCard: View {
    let title: String
    let value: String
    let iconName: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 4) {
                Image(systemName: iconName)
                    .font(.caption)
                    .foregroundStyle(color)
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.gray)
            }
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundStyle(.white)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            LinearGradient(
                colors: [color.opacity(0.2), color.opacity(0.05)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(color.opacity(0.3), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

#Preview {
    ZStack {
        Color.background.ignoresSafeArea()
        HStack {
            QuickStatCard(title: "Hot Props", value: "24", iconName: "flame.fill", color: .brandEmerald)
            QuickStatCard(title: "Live Now", value: "12", iconName: "clock.fill", color: .brandBlue)
        }
        .padding()
    }
}
