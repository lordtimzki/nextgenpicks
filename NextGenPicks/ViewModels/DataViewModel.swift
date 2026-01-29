import Foundation
import SwiftUI
import Combine

@MainActor
class DataViewModel: ObservableObject {
    
    @Published var games: [Game] = []
    @Published var featuredProps: [PlayerCardData] = []
    @Published var searchResults: [PlayerCardData] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    // Switch this to FirebaseService() when ready
    private let service: DataService
    
    init(service: DataService) {
        self.service = service
    }
    
    func loadInitialData() async {
        isLoading = true
        errorMessage = nil
        
        do {
            async let fetchedGames = service.fetchGames()
            async let fetchedProps = service.fetchLiveProps()
            
            self.games = try await fetchedGames
            self.featuredProps = try await fetchedProps
        } catch {
            self.errorMessage = "Failed to load data: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    func search(query: String) {
        guard !query.isEmpty else {
            searchResults = []
            return
        }
        
        Task {
            do {
                self.searchResults = try await service.searchPlayers(query: query)
            } catch {
                print("Search error: \(error)")
            }
        }
    }
}
