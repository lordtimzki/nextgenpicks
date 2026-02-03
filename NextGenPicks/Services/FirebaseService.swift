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

        do {
            // Temporarily fetch ALL props (no filter) to debug
            let snapshot = try await db.collection("props")
                .limit(to: 30)
                .getDocuments()

            print("🔥 FirebaseService: Found \(snapshot.documents.count) documents")

            if snapshot.documents.isEmpty {
                print("⚠️ FirebaseService: No documents found in 'props' collection!")
                print("⚠️ Check: 1) Firebase project ID matches 2) Data was written 3) Security rules allow read")
            }

            var results: [PlayerCardData] = []
            for doc in snapshot.documents {
                print("📄 Processing doc: \(doc.documentID)")
                do {
                    let data = try doc.data(as: PlayerCardData.self)
                    results.append(data)
                    print("✅ Decoded: \(data.name)")
                } catch let DecodingError.keyNotFound(key, context) {
                    print("❌ Missing key '\(key.stringValue)' in doc \(doc.documentID)")
                    print("   Context: \(context.debugDescription)")
                    print("   Raw data keys: \(doc.data().keys)")
                } catch let DecodingError.typeMismatch(type, context) {
                    print("❌ Type mismatch for \(type) in doc \(doc.documentID)")
                    print("   Path: \(context.codingPath.map { $0.stringValue }.joined(separator: "."))")
                    print("   Context: \(context.debugDescription)")
                } catch let DecodingError.valueNotFound(type, context) {
                    print("❌ Value not found for \(type) in doc \(doc.documentID)")
                    print("   Path: \(context.codingPath.map { $0.stringValue }.joined(separator: "."))")
                } catch {
                    print("❌ Failed to decode document \(doc.documentID): \(error)")
                    print("   Raw data: \(doc.data())")
                }
            }

            print("🔥 FirebaseService: Successfully decoded \(results.count) players")
            return results
        } catch {
            print("🔥❌ FirebaseService ERROR: \(error)")
            throw error
        }
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
