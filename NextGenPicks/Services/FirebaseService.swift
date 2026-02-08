import Foundation
import FirebaseFirestore

class FirebaseService: DataService {
    
    // Computed property to ensure we don't access Firestore before FirebaseApp.configure()
    private var db: Firestore { Firestore.firestore() }
    
    func fetchGames() async throws -> [Game] {
        let snapshot = try await db.collection("games")
            .whereField("status", isNotEqualTo: "final") // Fetch active/scheduled games
            .getDocuments()
        
        return snapshot.documents.compactMap { doc in
            try? doc.data(as: Game.self)
        }
    }
    
    /// Fetch top picks props (highest ranked individual prop cards)
    func fetchLiveProps() async throws -> [PlayerCardData] {
        print("🔥 FirebaseService: Fetching top picks props...")

        do {
            // Fetch "topPicks" section, ordered by ranking score (highest first)
            // Note: This query requires a composite index on (section, rankingScore)
            let snapshot = try await db.collection("props")
                .whereField("section", isEqualTo: "topPicks")
                .order(by: "rankingScore", descending: true)
                .limit(to: 15)
                .getDocuments()

            print("🔥 FirebaseService: Found \(snapshot.documents.count) top picks")

            if snapshot.documents.isEmpty {
                print("⚠️ FirebaseService: No top picks found, falling back to all props...")
                return try await fetchAllProps()
            }

            let results = decodeDocuments(snapshot.documents)
            print("🔥 FirebaseService: Successfully decoded \(results.count) top picks")
            return results
        } catch {
            print("🔥❌ FirebaseService ERROR: \(error)")
            throw error
        }
    }

    /// Fetch "For You" section props (top 5 best-ranked for parlay builders)
    func fetchForYouProps() async throws -> [PlayerCardData] {
        print("🔥 FirebaseService: Fetching 'For You' props...")

        do {
            let snapshot = try await db.collection("props")
                .whereField("section", isEqualTo: "forYou")
                .order(by: "rankingScore", descending: true)
                .limit(to: 5)
                .getDocuments()

            print("🔥 FirebaseService: Found \(snapshot.documents.count) 'For You' props")
            return decodeDocuments(snapshot.documents)
        } catch {
            print("🔥❌ FirebaseService fetchForYouProps ERROR: \(error)")
            throw error
        }
    }

    /// Fetch both sections for the feed
    func fetchFeedProps() async throws -> (topPicks: [PlayerCardData], forYou: [PlayerCardData]) {
        async let topPicks = fetchLiveProps()
        async let forYou = fetchForYouProps()

        return try await (topPicks, forYou)
    }

    /// Fetch all props (for search functionality)
    func fetchAllProps() async throws -> [PlayerCardData] {
        print("🔥 FirebaseService: Fetching all props...")

        let snapshot = try await db.collection("props")
            .order(by: "rankingScore", descending: true)
            .getDocuments()

        let results = decodeDocuments(snapshot.documents)
        print("🔥 FirebaseService: Fetched \(results.count) total props")
        return results
    }

    /// Helper to decode documents with detailed error logging
    private func decodeDocuments(_ documents: [QueryDocumentSnapshot]) -> [PlayerCardData] {
        var results: [PlayerCardData] = []
        for doc in documents {
            do {
                let data = try doc.data(as: PlayerCardData.self)
                results.append(data)
            } catch let DecodingError.keyNotFound(key, context) {
                print("❌ Missing key '\(key.stringValue)' in doc \(doc.documentID)")
                print("   Context: \(context.debugDescription)")
            } catch let DecodingError.typeMismatch(type, context) {
                print("❌ Type mismatch for \(type) in doc \(doc.documentID)")
                print("   Path: \(context.codingPath.map { $0.stringValue }.joined(separator: "."))")
            } catch {
                print("❌ Failed to decode document \(doc.documentID): \(error)")
            }
        }
        return results
    }
    
    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        // Search across ALL players in props collection (not just featured)
        // Uses prefix matching on player name
        let snapshot = try await db.collection("props")
            .whereField("name", isGreaterThanOrEqualTo: query)
            .whereField("name", isLessThan: query + "\u{f8ff}")
            .limit(to: 20)
            .getDocuments()

        return snapshot.documents.compactMap { doc in
            try? doc.data(as: PlayerCardData.self)
        }
    }

    /// Search all players without the featured filter
    /// Use this for the Search tab to allow users to find any player
    func searchAllPlayers(query: String) async throws -> [PlayerCardData] {
        print("🔍 FirebaseService: Searching for '\(query)'...")

        // Search in props collection with prefix match on name
        let snapshot = try await db.collection("props")
            .whereField("name", isGreaterThanOrEqualTo: query)
            .whereField("name", isLessThan: query + "\u{f8ff}")
            .order(by: "name")
            .limit(to: 20)
            .getDocuments()

        let results = snapshot.documents.compactMap { doc in
            try? doc.data(as: PlayerCardData.self)
        }

        print("🔍 FirebaseService: Found \(results.count) players matching '\(query)'")
        return results
    }
    /// Personalization Methods

    /// Saves the UserSettings model to a specific user's config document
    func saveUserSettings(userId: String, settings: UserSettings) async throws {
        print("🔥 FirebaseService: Saving settings for user \(userId)...")
        
        let docRef = db.collection("users").document(userId)
            .collection("config").document("settings")
        
        // Converts the Swift UserSettings struct into a Firestore dictionary
        try docRef.setData(from: settings)
    }

    /// Retrieves the UserSettings model for a specific user
    func fetchUserSettings(userId: String) async throws -> UserSettings? {
        print("🔥 FirebaseService: Fetching settings for user \(userId)...")
        
        let docRef = db.collection("users").document(userId)
            .collection("config").document("settings")
        
        let snapshot = try await docRef.getDocument()
        
        // Returns nil if the user hasn't set preferences yet
        return try? snapshot.data(as: UserSettings.self)
    }
}
