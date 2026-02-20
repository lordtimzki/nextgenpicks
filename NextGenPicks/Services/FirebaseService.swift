import Foundation
import FirebaseFirestore

struct RefreshMetadata {
    let completedAt: Date
    let propsWritten: Int
    let aiAnalyzed: Int
}

class FirebaseService: DataService {

    // Computed property to ensure we don't access Firestore before FirebaseApp.configure()
    private var db: Firestore { Firestore.firestore() }
    private var refreshListener: ListenerRegistration?

    /// Listen for backend refresh completions in real-time
    func listenForRefresh(onChange: @escaping (RefreshMetadata) -> Void) {
        refreshListener?.remove()
        refreshListener = db.collection("metadata").document("lastRefresh")
            .addSnapshotListener { snapshot, error in
                guard let data = snapshot?.data(), error == nil else { return }

                let timestamp = (data["completedAt"] as? Timestamp)?.dateValue() ?? Date()
                let propsWritten = data["propsWritten"] as? Int ?? 0
                let aiAnalyzed = data["aiAnalyzed"] as? Int ?? 0

                onChange(RefreshMetadata(
                    completedAt: timestamp,
                    propsWritten: propsWritten,
                    aiAnalyzed: aiAnalyzed
                ))
            }
    }

    func stopListening() {
        refreshListener?.remove()
        refreshListener = nil
    }

    func fetchGames() async throws -> [Game] {
        let snapshot = try await db.collection("games")
            .whereField("status", isNotEqualTo: "final")
            .getDocuments()

        return snapshot.documents.compactMap { doc in
            try? doc.data(as: Game.self)
        }
    }

    /// Fetch all props ordered by ranking score
    func fetchAllProps() async throws -> [PlayerCardData] {
        let snapshot = try await db.collection("props")
            .order(by: "rankingScore", descending: true)
            .getDocuments()

        return decodeDocuments(snapshot.documents)
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
        let snapshot = try await db.collection("props")
            .whereField("name", isGreaterThanOrEqualTo: query)
            .whereField("name", isLessThan: query + "\u{f8ff}")
            .limit(to: 20)
            .getDocuments()

        return snapshot.documents.compactMap { doc in
            try? doc.data(as: PlayerCardData.self)
        }
    }

    // MARK: - User Settings

    func saveUserSettings(userId: String, settings: UserSettings) async throws {
        let docRef = db.collection("users").document(userId)
            .collection("config").document("settings")
        try docRef.setData(from: settings)
    }

    func fetchUserSettings(userId: String) async throws -> UserSettings? {
        let docRef = db.collection("users").document(userId)
            .collection("config").document("settings")
        let snapshot = try await docRef.getDocument()
        return try? snapshot.data(as: UserSettings.self)
    }
}
