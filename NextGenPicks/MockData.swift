import Foundation

struct MockData {
    static let sampleGame1 = Game(
        id: 1001,
        homeTeamId: 1610612747,
        awayTeamId: 1610612758,
        startTime: Date(),
        homeScore: 0,
        awayScore: 0,
        status: .scheduled
    )

    static let sampleGame2 = Game(
        id: 1002,
        homeTeamId: 1610612744,
        awayTeamId: 1610612747,
        startTime: Date(),
        homeScore: 0,
        awayScore: 0,
        status: .scheduled
    )
    
    static let games: [Game] = [sampleGame1, sampleGame2]
}
