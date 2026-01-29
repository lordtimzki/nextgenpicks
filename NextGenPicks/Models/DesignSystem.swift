import SwiftUI

extension Color {
    static let background = Color(hex: "0a0a0a")
    static let surface = Color(hex: "1a1a1a")
    static let primaryText = Color.white
    static let secondaryText = Color.gray
    
    // Brand Colors
    static let brandEmerald = Color(hex: "10b981") // Emerald-500
    static let brandBlue = Color(hex: "3b82f6")    // Blue-500
    static let brandPurple = Color(hex: "a855f7")  // Purple-500
    static let brandOrange = Color(hex: "f97316")  // Orange-500
    static let brandRed = Color(hex: "ef4444")     // Red-500
    
    // UI Borders/Separators
    static let border = Color(hex: "1f2937")       // Gray-800
}

// Helper to allow Hex initialization
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
