import Foundation

struct UserSettings: Codable {
    var favoriteTeams: [String] = []
    var focusedStats: [String] = ["Points"] // Points, Rebounds, Assists, Default value is points
    var minConfidence: Double = 65.0       // The Threshold filter, user can adjust, the confidence of the AI predicition of a prop.
}