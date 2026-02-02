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
    
    func fetchLiveProps() async throws -> [PlayerCardData] {
        print("🔥 FirebaseService: Fetching live props...")
        
        // Temporarily fetch ALL props (no filter) to debug
        let snapshot = try await db.collection("props")
            .limit(to: 30)
            .getDocuments()
        
        print("🔥 FirebaseService: Found \(snapshot.documents.count) documents")
        
        var results: [PlayerCardData] = []
        for doc in snapshot.documents {
            do {
                let data = try doc.data(as: PlayerCardData.self)
                results.append(data)
                print("✅ Decoded: \(data.name)")
            } catch {
                print("❌ Failed to decode document \(doc.documentID): \(error)")
                // Print raw data for debugging
                print("   Raw data: \(doc.data())")
            }
        }
        
        print("🔥 FirebaseService: Successfully decoded \(results.count) players")
        return results
    }
    
    func searchPlayers(query: String) async throws -> [PlayerCardData] {
        // Defines a simple search. For advanced search (fuzzy matching), 
        // usually rely on Algolia or a separate index, but simple prefix match works for now.
        // Note: Firestore doesn't do native substring search easily without 3rd party.
        // We will simulate it by fetching or using a specific "keywords" array if implemented.
        // For now, let's assume we fetch a reasonable list or use a specific search collection.
        
        // MVP: Fetch top players and filter locally, or use exact match if ID.
        // real implementation would likely use: .whereField("name", isGreaterThanOrEqualTo: query)
        
        let snapshot = try await db.collection("players")
            .whereField("name", isGreaterThanOrEqualTo: query)
            .whereField("name", isLessThan: query + "\u{f8ff}")
            .limit(to: 10)
            .getDocuments()
            
        return snapshot.documents.compactMap { doc in
            try? doc.data(as: PlayerCardData.self)
        }
    }
}
