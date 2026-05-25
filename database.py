import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class Database:
    """Simple JSON-based database for F1 racing bot"""
    
    def __init__(self, db_file: str = "f1_data.json"):
        self.db_file = db_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Load data from JSON file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return json.load(f)
            except:
                return self._create_empty_db()
        return self._create_empty_db()
    
    def _create_empty_db(self) -> Dict:
        """Create empty database structure"""
        return {
            "players": {},
            "matches": [],
            "cards": [],
            "leaderboard": []
        }
    
    def _save_data(self):
        """Save data to JSON file"""
        with open(self.db_file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    # ==================== PLAYER DATA ====================
    
    def create_player(self, player_id: str, username: str) -> Dict:
        """Create a new player profile"""
        player = {
            "id": player_id,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "stats": {
                "wins": 0,
                "losses": 0,
                "dnf": 0,
                "total_races": 0,
                "win_rate": 0.0,
                "ranking_points": 0,
                "rank": "Bronze"
            },
            "cards": {
                "drivers": [],
                "cars": []
            },
            "achievements": []
        }
        self.data["players"][player_id] = player
        self._save_data()
        return player
    
    def get_player(self, player_id: str) -> Optional[Dict]:
        """Get player data"""
        return self.data["players"].get(player_id)
    
    def player_exists(self, player_id: str) -> bool:
        """Check if player exists"""
        return player_id in self.data["players"]
    
    def update_player_stats(self, player_id: str, result: Dict):
        """Update player stats after a race"""
        if player_id not in self.data["players"]:
            return
        
        player = self.data["players"][player_id]
        stats = player["stats"]
        
        if result["status"] == "win":
            stats["wins"] += 1
            stats["ranking_points"] += 50
        elif result["status"] == "loss":
            stats["losses"] += 1
            stats["ranking_points"] += 10
        elif result["status"] == "dnf":
            stats["dnf"] += 1
        
        stats["total_races"] += 1
        stats["win_rate"] = stats["wins"] / stats["total_races"] if stats["total_races"] > 0 else 0
        
        # Update rank
        stats["rank"] = self._calculate_rank(stats["ranking_points"])
        
        self._save_data()
    
    def _calculate_rank(self, points: int) -> str:
        """Calculate player rank based on points"""
        if points >= 5000:
            return "Diamond"
        elif points >= 3000:
            return "Platinum"
        elif points >= 1500:
            return "Gold"
        elif points >= 500:
            return "Silver"
        else:
            return "Bronze"
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top players by ranking points"""
        players = list(self.data["players"].values())
        sorted_players = sorted(players, key=lambda x: x["stats"]["ranking_points"], reverse=True)
        return sorted_players[:limit]
    
    # ==================== CARD DATA ====================
    
    def add_card_to_player(self, player_id: str, card: Dict, card_type: str):
        """Add a card to player's deck"""
        if player_id not in self.data["players"]:
            return
        
        player = self.data["players"][player_id]
        
        if card_type == "driver":
            player["cards"]["drivers"].append(card)
        elif card_type == "car":
            player["cards"]["cars"].append(card)
        
        self._save_data()
    
    def get_player_cards(self, player_id: str) -> Dict:
        """Get all cards for a player"""
        player = self.get_player(player_id)
        return player["cards"] if player else {"drivers": [], "cars": []}
    
    # ==================== MATCH HISTORY ====================
    
    def save_match(self, match_data: Dict):
        """Save match to history"""
        match = {
            "id": len(self.data["matches"]),
            "timestamp": datetime.now().isoformat(),
            "p1_id": match_data["p1_id"],
            "p2_id": match_data["p2_id"],
            "p1_car": match_data["p1_car"],
            "p2_car": match_data["p2_car"],
            "winner": match_data["winner"],
            "gap": match_data["gap"],
            "laps_completed": match_data["laps_completed"],
            "pit_stops": match_data["pit_stops"],
            "dnf": match_data.get("dnf"),
            "weather_events": match_data.get("events", [])
        }
        self.data["matches"].append(match)
        self._save_data()
    
    def get_match_history(self, player_id: str, limit: int = 10) -> List[Dict]:
        """Get match history for a player"""
        player_matches = [
            m for m in self.data["matches"]
            if m["p1_id"] == player_id or m["p2_id"] == player_id
        ]
        return sorted(player_matches, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    # ==================== ACHIEVEMENTS ====================
    
    def unlock_achievement(self, player_id: str, achievement: str):
        """Unlock an achievement for a player"""
        if player_id not in self.data["players"]:
            return
        
        player = self.data["players"][player_id]
        if achievement not in player["achievements"]:
            player["achievements"].append(achievement)
            self._save_data()
    
    def get_achievements(self, player_id: str) -> List[str]:
        """Get all achievements for a player"""
        player = self.get_player(player_id)
        return player["achievements"] if player else []


# ==================== SAMPLE DATA ====================

STARTER_CARS = [
    {
        "id": "merc-a",
        "name": "Mercedes AMG W13",
        "team": "Mercedes",
        "top_speed": 390,
        "rarity": "rare"
    },
    {
        "id": "rb-a",
        "name": "Red Bull RB18",
        "team": "Red Bull",
        "top_speed": 388,
        "rarity": "rare"
    },
    {
        "id": "ferrari-a",
        "name": "Ferrari F1-75",
        "team": "Ferrari",
        "top_speed": 385,
        "rarity": "rare"
    }
]

STARTER_DRIVERS = [
    {
        "id": "ham",
        "name": "Lewis Hamilton",
        "code": "HAM",
        "skill": 8.5,
        "rarity": "rare"
    },
    {
        "id": "ver",
        "name": "Max Verstappen",
        "code": "VER",
        "skill": 9.0,
        "rarity": "rare"
    },
    {
        "id": "lec",
        "name": "Charles Leclerc",
        "code": "LEC",
        "skill": 8.7,
        "rarity": "rare"
    }
]

ACHIEVEMENTS = {
    "first_win": {
        "name": "First Victory",
        "description": "Win your first race",
        "icon": "🥇"
    },
    "perfect_race": {
        "name": "Perfect Race",
        "description": "Win without any pit stops",
        "icon": "✨"
    },
    "comeback_king": {
        "name": "Comeback King",
        "description": "Overtake from 5+ seconds behind in final lap",
        "icon": "🏆"
    },
    "tire_master": {
        "name": "Tire Master",
        "description": "Win using 2+ different tire types",
        "icon": "🛞"
    },
    "rain_specialist": {
        "name": "Rain Specialist",
        "description": "Win a race in rainy conditions",
        "icon": "🌧️"
    },
    "ten_wins": {
        "name": "Racing Veteran",
        "description": "Achieve 10 wins",
        "icon": "🎖️"
    },
    "50_races": {
        "name": "True Competitor",
        "description": "Complete 50 races",
        "icon": "🔥"
    }
}
