import Foundation

struct TeamDatabase {
    static func getTeam(id: Int) -> Team {
        return teams[id] ?? Team(
            id: 0,
            league: .nba,
            name: "Unknown Team",
            city: "Unknown",
            abbreviation: "UNK",
            logoName: "questionmark.shield"
        )
    }
    
    // Total: ~124 Teams across 4 Major Leagues
    static let teams: [Int: Team] = [
        
        // MARK: - NBA (IDs: 1610612...)
        // Atlantic
        1610612738: Team(id: 1610612738, league: .nba, name: "Boston Celtics", city: "Boston", abbreviation: "BOS", logoName: "nba_bos"),
        1610612751: Team(id: 1610612751, league: .nba, name: "Brooklyn Nets", city: "Brooklyn", abbreviation: "BKN", logoName: "nba_bkn"),
        1610612752: Team(id: 1610612752, league: .nba, name: "New York Knicks", city: "New York", abbreviation: "NYK", logoName: "nba_nyk"),
        1610612755: Team(id: 1610612755, league: .nba, name: "Philadelphia 76ers", city: "Philadelphia", abbreviation: "PHI", logoName: "nba_phi"),
        1610612761: Team(id: 1610612761, league: .nba, name: "Toronto Raptors", city: "Toronto", abbreviation: "TOR", logoName: "nba_tor"),
        // Central
        1610612741: Team(id: 1610612741, league: .nba, name: "Chicago Bulls", city: "Chicago", abbreviation: "CHI", logoName: "nba_chi"),
        1610612739: Team(id: 1610612739, league: .nba, name: "Cleveland Cavaliers", city: "Cleveland", abbreviation: "CLE", logoName: "nba_cle"),
        1610612765: Team(id: 1610612765, league: .nba, name: "Detroit Pistons", city: "Detroit", abbreviation: "DET", logoName: "nba_det"),
        1610612754: Team(id: 1610612754, league: .nba, name: "Indiana Pacers", city: "Indiana", abbreviation: "IND", logoName: "nba_ind"),
        1610612749: Team(id: 1610612749, league: .nba, name: "Milwaukee Bucks", city: "Milwaukee", abbreviation: "MIL", logoName: "nba_mil"),
        // Southeast
        1610612737: Team(id: 1610612737, league: .nba, name: "Atlanta Hawks", city: "Atlanta", abbreviation: "ATL", logoName: "nba_atl"),
        1610612766: Team(id: 1610612766, league: .nba, name: "Charlotte Hornets", city: "Charlotte", abbreviation: "CHA", logoName: "nba_cha"),
        1610612748: Team(id: 1610612748, league: .nba, name: "Miami Heat", city: "Miami", abbreviation: "MIA", logoName: "nba_mia"),
        1610612753: Team(id: 1610612753, league: .nba, name: "Orlando Magic", city: "Orlando", abbreviation: "ORL", logoName: "nba_orl"),
        1610612764: Team(id: 1610612764, league: .nba, name: "Washington Wizards", city: "Washington", abbreviation: "WAS", logoName: "nba_was"),
        // Northwest
        1610612743: Team(id: 1610612743, league: .nba, name: "Denver Nuggets", city: "Denver", abbreviation: "DEN", logoName: "nba_den"),
        1610612750: Team(id: 1610612750, league: .nba, name: "Minnesota Timberwolves", city: "Minnesota", abbreviation: "MIN", logoName: "nba_min"),
        1610612760: Team(id: 1610612760, league: .nba, name: "Oklahoma City Thunder", city: "Oklahoma City", abbreviation: "OKC", logoName: "nba_okc"),
        1610612757: Team(id: 1610612757, league: .nba, name: "Portland Trail Blazers", city: "Portland", abbreviation: "POR", logoName: "nba_por"),
        1610612762: Team(id: 1610612762, league: .nba, name: "Utah Jazz", city: "Utah", abbreviation: "UTA", logoName: "nba_uta"),
        // Pacific
        1610612744: Team(id: 1610612744, league: .nba, name: "Golden State Warriors", city: "San Francisco", abbreviation: "GSW", logoName: "nba_gsw"),
        1610612746: Team(id: 1610612746, league: .nba, name: "Los Angeles Clippers", city: "Los Angeles", abbreviation: "LAC", logoName: "nba_lac"),
        1610612747: Team(id: 1610612747, league: .nba, name: "Los Angeles Lakers", city: "Los Angeles", abbreviation: "LAL", logoName: "nba_lal"),
        1610612756: Team(id: 1610612756, league: .nba, name: "Phoenix Suns", city: "Phoenix", abbreviation: "PHX", logoName: "nba_phx"),
        1610612758: Team(id: 1610612758, league: .nba, name: "Sacramento Kings", city: "Sacramento", abbreviation: "SAC", logoName: "nba_sac"),
        // Southwest
        1610612742: Team(id: 1610612742, league: .nba, name: "Dallas Mavericks", city: "Dallas", abbreviation: "DAL", logoName: "nba_dal"),
        1610612745: Team(id: 1610612745, league: .nba, name: "Houston Rockets", city: "Houston", abbreviation: "HOU", logoName: "nba_hou"),
        1610612763: Team(id: 1610612763, league: .nba, name: "Memphis Grizzlies", city: "Memphis", abbreviation: "MEM", logoName: "nba_mem"),
        1610612740: Team(id: 1610612740, league: .nba, name: "New Orleans Pelicans", city: "New Orleans", abbreviation: "NOP", logoName: "nba_nop"),
        1610612759: Team(id: 1610612759, league: .nba, name: "San Antonio Spurs", city: "San Antonio", abbreviation: "SAS", logoName: "nba_sas"),
        
        // MARK: - NFL (IDs: 100-132 for simplicity)
        // AFC East
        101: Team(id: 101, league: .nfl, name: "Buffalo Bills", city: "Buffalo", abbreviation: "BUF", logoName: "nfl_buf"),
        102: Team(id: 102, league: .nfl, name: "Miami Dolphins", city: "Miami", abbreviation: "MIA", logoName: "nfl_mia"),
        103: Team(id: 103, league: .nfl, name: "New England Patriots", city: "New England", abbreviation: "NE", logoName: "nfl_ne"),
        104: Team(id: 104, league: .nfl, name: "New York Jets", city: "New York", abbreviation: "NYJ", logoName: "nfl_nyj"),
        // AFC North
        105: Team(id: 105, league: .nfl, name: "Baltimore Ravens", city: "Baltimore", abbreviation: "BAL", logoName: "nfl_bal"),
        106: Team(id: 106, league: .nfl, name: "Cincinnati Bengals", city: "Cincinnati", abbreviation: "CIN", logoName: "nfl_cin"),
        107: Team(id: 107, league: .nfl, name: "Cleveland Browns", city: "Cleveland", abbreviation: "CLE", logoName: "nfl_cle"),
        108: Team(id: 108, league: .nfl, name: "Pittsburgh Steelers", city: "Pittsburgh", abbreviation: "PIT", logoName: "nfl_pit"),
        // AFC South
        109: Team(id: 109, league: .nfl, name: "Houston Texans", city: "Houston", abbreviation: "HOU", logoName: "nfl_hou"),
        110: Team(id: 110, league: .nfl, name: "Indianapolis Colts", city: "Indianapolis", abbreviation: "IND", logoName: "nfl_ind"),
        111: Team(id: 111, league: .nfl, name: "Jacksonville Jaguars", city: "Jacksonville", abbreviation: "JAX", logoName: "nfl_jax"),
        112: Team(id: 112, league: .nfl, name: "Tennessee Titans", city: "Tennessee", abbreviation: "TEN", logoName: "nfl_ten"),
        // AFC West
        113: Team(id: 113, league: .nfl, name: "Denver Broncos", city: "Denver", abbreviation: "DEN", logoName: "nfl_den"),
        114: Team(id: 114, league: .nfl, name: "Kansas City Chiefs", city: "Kansas City", abbreviation: "KC", logoName: "nfl_kc"),
        115: Team(id: 115, league: .nfl, name: "Las Vegas Raiders", city: "Las Vegas", abbreviation: "LV", logoName: "nfl_lv"),
        116: Team(id: 116, league: .nfl, name: "Los Angeles Chargers", city: "Los Angeles", abbreviation: "LAC", logoName: "nfl_lac"),
        // NFC East
        117: Team(id: 117, league: .nfl, name: "Dallas Cowboys", city: "Dallas", abbreviation: "DAL", logoName: "nfl_dal"),
        118: Team(id: 118, league: .nfl, name: "New York Giants", city: "New York", abbreviation: "NYG", logoName: "nfl_nyg"),
        119: Team(id: 119, league: .nfl, name: "Philadelphia Eagles", city: "Philadelphia", abbreviation: "PHI", logoName: "nfl_phi"),
        120: Team(id: 120, league: .nfl, name: "Washington Commanders", city: "Washington", abbreviation: "WAS", logoName: "nfl_was"),
        // NFC North
        121: Team(id: 121, league: .nfl, name: "Chicago Bears", city: "Chicago", abbreviation: "CHI", logoName: "nfl_chi"),
        122: Team(id: 122, league: .nfl, name: "Detroit Lions", city: "Detroit", abbreviation: "DET", logoName: "nfl_det"),
        123: Team(id: 123, league: .nfl, name: "Green Bay Packers", city: "Green Bay", abbreviation: "GB", logoName: "nfl_gb"),
        124: Team(id: 124, league: .nfl, name: "Minnesota Vikings", city: "Minnesota", abbreviation: "MIN", logoName: "nfl_min"),
        // NFC South
        125: Team(id: 125, league: .nfl, name: "Atlanta Falcons", city: "Atlanta", abbreviation: "ATL", logoName: "nfl_atl"),
        126: Team(id: 126, league: .nfl, name: "Carolina Panthers", city: "Carolina", abbreviation: "CAR", logoName: "nfl_car"),
        127: Team(id: 127, league: .nfl, name: "New Orleans Saints", city: "New Orleans", abbreviation: "NO", logoName: "nfl_no"),
        128: Team(id: 128, league: .nfl, name: "Tampa Bay Buccaneers", city: "Tampa Bay", abbreviation: "TB", logoName: "nfl_tb"),
        // NFC West
        129: Team(id: 129, league: .nfl, name: "Arizona Cardinals", city: "Arizona", abbreviation: "ARI", logoName: "nfl_ari"),
        130: Team(id: 130, league: .nfl, name: "Los Angeles Rams", city: "Los Angeles", abbreviation: "LAR", logoName: "nfl_lar"),
        131: Team(id: 131, league: .nfl, name: "San Francisco 49ers", city: "San Francisco", abbreviation: "SF", logoName: "nfl_sf"),
        132: Team(id: 132, league: .nfl, name: "Seattle Seahawks", city: "Seattle", abbreviation: "SEA", logoName: "nfl_sea"),
        
        // MARK: - MLB (IDs: 201-230)
        201: Team(id: 201, league: .mlb, name: "Arizona Diamondbacks", city: "Arizona", abbreviation: "ARI", logoName: "mlb_ari"),
        202: Team(id: 202, league: .mlb, name: "Atlanta Braves", city: "Atlanta", abbreviation: "ATL", logoName: "mlb_atl"),
        203: Team(id: 203, league: .mlb, name: "Baltimore Orioles", city: "Baltimore", abbreviation: "BAL", logoName: "mlb_bal"),
        204: Team(id: 204, league: .mlb, name: "Boston Red Sox", city: "Boston", abbreviation: "BOS", logoName: "mlb_bos"),
        205: Team(id: 205, league: .mlb, name: "Chicago White Sox", city: "Chicago", abbreviation: "CWS", logoName: "mlb_cws"),
        206: Team(id: 206, league: .mlb, name: "Chicago Cubs", city: "Chicago", abbreviation: "CHC", logoName: "mlb_chc"),
        207: Team(id: 207, league: .mlb, name: "Cincinnati Reds", city: "Cincinnati", abbreviation: "CIN", logoName: "mlb_cin"),
        208: Team(id: 208, league: .mlb, name: "Cleveland Guardians", city: "Cleveland", abbreviation: "CLE", logoName: "mlb_cle"),
        209: Team(id: 209, league: .mlb, name: "Colorado Rockies", city: "Colorado", abbreviation: "COL", logoName: "mlb_col"),
        210: Team(id: 210, league: .mlb, name: "Detroit Tigers", city: "Detroit", abbreviation: "DET", logoName: "mlb_det"),
        211: Team(id: 211, league: .mlb, name: "Houston Astros", city: "Houston", abbreviation: "HOU", logoName: "mlb_hou"),
        212: Team(id: 212, league: .mlb, name: "Kansas City Royals", city: "Kansas City", abbreviation: "KC", logoName: "mlb_kc"),
        213: Team(id: 213, league: .mlb, name: "Los Angeles Angels", city: "Los Angeles", abbreviation: "LAA", logoName: "mlb_laa"),
        214: Team(id: 214, league: .mlb, name: "Los Angeles Dodgers", city: "Los Angeles", abbreviation: "LAD", logoName: "mlb_lad"),
        215: Team(id: 215, league: .mlb, name: "Miami Marlins", city: "Miami", abbreviation: "MIA", logoName: "mlb_mia"),
        216: Team(id: 216, league: .mlb, name: "Milwaukee Brewers", city: "Milwaukee", abbreviation: "MIL", logoName: "mlb_mil"),
        217: Team(id: 217, league: .mlb, name: "Minnesota Twins", city: "Minnesota", abbreviation: "MIN", logoName: "mlb_min"),
        218: Team(id: 218, league: .mlb, name: "New York Yankees", city: "New York", abbreviation: "NYY", logoName: "mlb_nyy"),
        219: Team(id: 219, league: .mlb, name: "New York Mets", city: "New York", abbreviation: "NYM", logoName: "mlb_nym"),
        220: Team(id: 220, league: .mlb, name: "Oakland Athletics", city: "Oakland", abbreviation: "OAK", logoName: "mlb_oak"),
        221: Team(id: 221, league: .mlb, name: "Philadelphia Phillies", city: "Philadelphia", abbreviation: "PHI", logoName: "mlb_phi"),
        222: Team(id: 222, league: .mlb, name: "Pittsburgh Pirates", city: "Pittsburgh", abbreviation: "PIT", logoName: "mlb_pit"),
        223: Team(id: 223, league: .mlb, name: "San Diego Padres", city: "San Diego", abbreviation: "SD", logoName: "mlb_sd"),
        224: Team(id: 224, league: .mlb, name: "San Francisco Giants", city: "San Francisco", abbreviation: "SF", logoName: "mlb_sf"),
        225: Team(id: 225, league: .mlb, name: "Seattle Mariners", city: "Seattle", abbreviation: "SEA", logoName: "mlb_sea"),
        226: Team(id: 226, league: .mlb, name: "St. Louis Cardinals", city: "St. Louis", abbreviation: "STL", logoName: "mlb_stl"),
        227: Team(id: 227, league: .mlb, name: "Tampa Bay Rays", city: "Tampa Bay", abbreviation: "TB", logoName: "mlb_tb"),
        228: Team(id: 228, league: .mlb, name: "Texas Rangers", city: "Texas", abbreviation: "TEX", logoName: "mlb_tex"),
        229: Team(id: 229, league: .mlb, name: "Toronto Blue Jays", city: "Toronto", abbreviation: "TOR", logoName: "mlb_tor"),
        230: Team(id: 230, league: .mlb, name: "Washington Nationals", city: "Washington", abbreviation: "WSH", logoName: "mlb_wsh"),
        
        // MARK: - NHL (IDs: 301-332)
        301: Team(id: 301, league: .nhl, name: "Anaheim Ducks", city: "Anaheim", abbreviation: "ANA", logoName: "nhl_ana"),
        302: Team(id: 302, league: .nhl, name: "Arizona Coyotes", city: "Arizona", abbreviation: "ARI", logoName: "nhl_ari"),
        303: Team(id: 303, league: .nhl, name: "Boston Bruins", city: "Boston", abbreviation: "BOS", logoName: "nhl_bos"),
        304: Team(id: 304, league: .nhl, name: "Buffalo Sabres", city: "Buffalo", abbreviation: "BUF", logoName: "nhl_buf"),
        305: Team(id: 305, league: .nhl, name: "Calgary Flames", city: "Calgary", abbreviation: "CGY", logoName: "nhl_cgy"),
        306: Team(id: 306, league: .nhl, name: "Carolina Hurricanes", city: "Carolina", abbreviation: "CAR", logoName: "nhl_car"),
        307: Team(id: 307, league: .nhl, name: "Chicago Blackhawks", city: "Chicago", abbreviation: "CHI", logoName: "nhl_chi"),
        308: Team(id: 308, league: .nhl, name: "Colorado Avalanche", city: "Colorado", abbreviation: "COL", logoName: "nhl_col"),
        309: Team(id: 309, league: .nhl, name: "Columbus Blue Jackets", city: "Columbus", abbreviation: "CBJ", logoName: "nhl_cbj"),
        310: Team(id: 310, league: .nhl, name: "Dallas Stars", city: "Dallas", abbreviation: "DAL", logoName: "nhl_dal"),
        311: Team(id: 311, league: .nhl, name: "Detroit Red Wings", city: "Detroit", abbreviation: "DET", logoName: "nhl_det"),
        312: Team(id: 312, league: .nhl, name: "Edmonton Oilers", city: "Edmonton", abbreviation: "EDM", logoName: "nhl_edm"),
        313: Team(id: 313, league: .nhl, name: "Florida Panthers", city: "Florida", abbreviation: "FLA", logoName: "nhl_fla"),
        314: Team(id: 314, league: .nhl, name: "Los Angeles Kings", city: "Los Angeles", abbreviation: "LAK", logoName: "nhl_lak"),
        315: Team(id: 315, league: .nhl, name: "Minnesota Wild", city: "Minnesota", abbreviation: "MIN", logoName: "nhl_min"),
        316: Team(id: 316, league: .nhl, name: "Montreal Canadiens", city: "Montreal", abbreviation: "MTL", logoName: "nhl_mtl"),
        317: Team(id: 317, league: .nhl, name: "Nashville Predators", city: "Nashville", abbreviation: "NSH", logoName: "nhl_nsh"),
        318: Team(id: 318, league: .nhl, name: "New Jersey Devils", city: "New Jersey", abbreviation: "NJD", logoName: "nhl_njd"),
        319: Team(id: 319, league: .nhl, name: "New York Islanders", city: "New York", abbreviation: "NYI", logoName: "nhl_nyi"),
        320: Team(id: 320, league: .nhl, name: "New York Rangers", city: "New York", abbreviation: "NYR", logoName: "nhl_nyr"),
        321: Team(id: 321, league: .nhl, name: "Ottawa Senators", city: "Ottawa", abbreviation: "OTT", logoName: "nhl_ott"),
        322: Team(id: 322, league: .nhl, name: "Philadelphia Flyers", city: "Philadelphia", abbreviation: "PHI", logoName: "nhl_phi"),
        323: Team(id: 323, league: .nhl, name: "Pittsburgh Penguins", city: "Pittsburgh", abbreviation: "PIT", logoName: "nhl_pit"),
        324: Team(id: 324, league: .nhl, name: "San Jose Sharks", city: "San Jose", abbreviation: "SJS", logoName: "nhl_sjs"),
        325: Team(id: 325, league: .nhl, name: "Seattle Kraken", city: "Seattle", abbreviation: "SEA", logoName: "nhl_sea"),
        326: Team(id: 326, league: .nhl, name: "St. Louis Blues", city: "St. Louis", abbreviation: "STL", logoName: "nhl_stl"),
        327: Team(id: 327, league: .nhl, name: "Tampa Bay Lightning", city: "Tampa Bay", abbreviation: "TBL", logoName: "nhl_tbl"),
        328: Team(id: 328, league: .nhl, name: "Toronto Maple Leafs", city: "Toronto", abbreviation: "TOR", logoName: "nhl_tor"),
        329: Team(id: 329, league: .nhl, name: "Utah Hockey Club", city: "Utah", abbreviation: "UTA", logoName: "nhl_uta"),
        330: Team(id: 330, league: .nhl, name: "Vancouver Canucks", city: "Vancouver", abbreviation: "VAN", logoName: "nhl_van"),
        331: Team(id: 331, league: .nhl, name: "Vegas Golden Knights", city: "Vegas", abbreviation: "VGK", logoName: "nhl_vgk"),
        332: Team(id: 332, league: .nhl, name: "Washington Capitals", city: "Washington", abbreviation: "WSH", logoName: "nhl_wsh"),
        333: Team(id: 333, league: .nhl, name: "Winnipeg Jets", city: "Winnipeg", abbreviation: "WPG", logoName: "nhl_wpg")
    ]
}
