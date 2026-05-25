import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class Database:
    """JSON-based database for F1 racing bot"""

    def __init__(self, db_file: str = "f1_data.json"):
        self.db_file = db_file
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r") as f:
                    return json.load(f)
            except Exception:
                return self._create_empty_db()
        return self._create_empty_db()

    def _create_empty_db(self) -> Dict:
        return {"players": {}, "matches": [], "leaderboard": []}

    def _save_data(self):
        with open(self.db_file, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def _migrate_player(self, player: Dict) -> Dict:
        """Ensure old players have all new fields."""
        player.setdefault("coins", 0)
        player.setdefault("equipped", {"driver_id": None, "car_id": None})
        player.setdefault("last_daily_pack", None)
        player.setdefault("last_weekly_pack", None)
        player.setdefault("achievements", [])
        if "cards" not in player:
            player["cards"] = {"drivers": [], "cars": []}
        player["cards"].setdefault("drivers", [])
        player["cards"].setdefault("cars", [])
        return player

    # ==================== PLAYER ====================

    def ensure_player(self, player_id: str, username: str) -> Dict:
        if not self.player_exists(player_id):
            return self.create_player(player_id, username)
        player = self.data["players"][player_id]
        player["username"] = username
        return self._migrate_player(player)

    def create_player(self, player_id: str, username: str) -> Dict:
        player = {
            "id": player_id,
            "username": username,
            "created_at": datetime.now().isoformat(),
            "coins": 0,
            "equipped": {"driver_id": None, "car_id": None},
            "last_daily_pack": None,
            "last_weekly_pack": None,
            "stats": {
                "wins": 0,
                "losses": 0,
                "dnf": 0,
                "total_races": 0,
                "win_rate": 0.0,
                "ranking_points": 0,
                "rank": "Bronze",
            },
            "cards": {"drivers": [], "cars": []},
            "achievements": [],
        }
        self.data["players"][player_id] = player
        self._save_data()
        return player

    def get_player(self, player_id: str) -> Optional[Dict]:
        player = self.data["players"].get(player_id)
        if player:
            return self._migrate_player(player)
        return None

    def player_exists(self, player_id: str) -> bool:
        return player_id in self.data["players"]

    # ==================== ECONOMY ====================

    def get_coins(self, player_id: str) -> int:
        player = self.get_player(player_id)
        return player["coins"] if player else 0

    def add_coins(self, player_id: str, amount: int) -> int:
        player = self.get_player(player_id)
        if not player:
            return 0
        player["coins"] = player.get("coins", 0) + amount
        self._save_data()
        return player["coins"]

    def spend_coins(self, player_id: str, amount: int) -> bool:
        player = self.get_player(player_id)
        if not player or player.get("coins", 0) < amount:
            return False
        player["coins"] -= amount
        self._save_data()
        return True

    # ==================== PACK COOLDOWNS ====================

    def can_claim_daily(self, player_id: str) -> Tuple[bool, int]:
        """Returns (can_claim, seconds_remaining)"""
        player = self.get_player(player_id)
        if not player:
            return True, 0
        last = player.get("last_daily_pack")
        if not last:
            return True, 0
        last_dt = datetime.fromisoformat(last)
        next_dt = last_dt + timedelta(hours=24)
        now = datetime.now()
        if now >= next_dt:
            return True, 0
        return False, int((next_dt - now).total_seconds())

    def mark_daily_claimed(self, player_id: str):
        player = self.get_player(player_id)
        if player:
            player["last_daily_pack"] = datetime.now().isoformat()
            self._save_data()

    def can_claim_weekly(self, player_id: str) -> Tuple[bool, int]:
        """Returns (can_claim, seconds_remaining)"""
        player = self.get_player(player_id)
        if not player:
            return True, 0
        last = player.get("last_weekly_pack")
        if not last:
            return True, 0
        last_dt = datetime.fromisoformat(last)
        next_dt = last_dt + timedelta(days=7)
        now = datetime.now()
        if now >= next_dt:
            return True, 0
        return False, int((next_dt - now).total_seconds())

    def mark_weekly_claimed(self, player_id: str):
        player = self.get_player(player_id)
        if player:
            player["last_weekly_pack"] = datetime.now().isoformat()
            self._save_data()

    # ==================== EQUIP ====================

    def set_equipped(self, player_id: str, card_type: str, card_id: str) -> bool:
        player = self.get_player(player_id)
        if not player:
            return False
        card = self.get_card_by_id(player_id, card_id)
        if not card:
            return False
        equipped = player.setdefault("equipped", {"driver_id": None, "car_id": None})
        if card_type == "driver":
            equipped["driver_id"] = card_id
        elif card_type == "car":
            equipped["car_id"] = card_id
        self._save_data()
        return True

    def get_equipped(self, player_id: str) -> Dict:
        player = self.get_player(player_id)
        if not player:
            return {"driver_id": None, "car_id": None}
        return player.get("equipped", {"driver_id": None, "car_id": None})

    # ==================== CARDS ====================

    def add_card_to_player(self, player_id: str, card: Dict, card_type: str):
        player = self.get_player(player_id)
        if not player:
            return
        card["obtained_at"] = datetime.now().isoformat()
        if card_type == "driver":
            player["cards"]["drivers"].append(card)
        elif card_type == "car":
            player["cards"]["cars"].append(card)
        self._save_data()

    def get_player_cards(self, player_id: str) -> Dict:
        player = self.get_player(player_id)
        return player["cards"] if player else {"drivers": [], "cars": []}

    def get_card_by_id(self, player_id: str, card_id: str) -> Optional[Dict]:
        player = self.get_player(player_id)
        if not player:
            return None
        for card in player["cards"]["drivers"] + player["cards"]["cars"]:
            if card["id"] == card_id:
                return card
        return None

    def has_card_name(self, player_id: str, name: str, card_type: str) -> bool:
        """Check if player already owns a card with this exact name."""
        player = self.get_player(player_id)
        if not player:
            return False
        key = "drivers" if card_type == "driver" else "cars"
        return any(c["name"] == name for c in player["cards"][key])

    def get_all_cards_sorted(self, player_id: str) -> List[Dict]:
        """Return all cards (drivers + cars) sorted by obtained_at descending."""
        player = self.get_player(player_id)
        if not player:
            return []
        all_cards = player["cards"]["drivers"] + player["cards"]["cars"]
        all_cards.sort(key=lambda c: c.get("obtained_at", ""), reverse=True)
        return all_cards

    # ==================== STATS ====================

    def update_player_stats(self, player_id: str, result: Dict):
        if not self.player_exists(player_id):
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
        stats["win_rate"] = (
            stats["wins"] / stats["total_races"] if stats["total_races"] > 0 else 0
        )
        stats["rank"] = self._calculate_rank(stats["ranking_points"])
        self._save_data()

    def _calculate_rank(self, points: int) -> str:
        if points >= 5000:
            return "Diamond"
        elif points >= 3000:
            return "Platinum"
        elif points >= 1500:
            return "Gold"
        elif points >= 500:
            return "Silver"
        return "Bronze"

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        players = list(self.data["players"].values())
        return sorted(
            players,
            key=lambda x: x["stats"]["ranking_points"],
            reverse=True,
        )[:limit]

    def save_match(self, match_data: Dict):
        match = {"id": len(self.data["matches"]), "timestamp": datetime.now().isoformat(), **match_data}
        self.data["matches"].append(match)
        self._save_data()

    def get_match_history(self, player_id: str, limit: int = 10) -> List[Dict]:
        matches = [
            m for m in self.data["matches"]
            if m.get("p1_id") == player_id or m.get("p2_id") == player_id
        ]
        return sorted(matches, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def unlock_achievement(self, player_id: str, achievement: str):
        if not self.player_exists(player_id):
            return
        player = self.data["players"][player_id]
        if achievement not in player.get("achievements", []):
            player.setdefault("achievements", []).append(achievement)
            self._save_data()

    def get_achievements(self, player_id: str) -> List[str]:
        player = self.get_player(player_id)
        return player["achievements"] if player else []


# ==================== STATIC DATA ====================

STARTER_CARS = [
    {"id": "merc-a", "name": "Mercedes AMG W13", "team": "Mercedes", "top_speed": 390, "rarity": "rare"},
    {"id": "rb-a", "name": "Red Bull RB18", "team": "Red Bull", "top_speed": 388, "rarity": "rare"},
    {"id": "ferrari-a", "name": "Ferrari F1-75", "team": "Ferrari", "top_speed": 385, "rarity": "rare"},
]

STARTER_DRIVERS = [
    {"id": "ham", "name": "Lewis Hamilton", "code": "HAM", "skill": 8.5, "rarity": "rare"},
    {"id": "ver", "name": "Max Verstappen", "code": "VER", "skill": 9.0, "rarity": "rare"},
    {"id": "lec", "name": "Charles Leclerc", "code": "LEC", "skill": 8.7, "rarity": "rare"},
]

ACHIEVEMENTS = {
    "first_win": {"name": "First Victory", "description": "Win your first race", "icon": "🥇"},
    "perfect_race": {"name": "Perfect Race", "description": "Win without any pit stops", "icon": "✨"},
    "comeback_king": {"name": "Comeback King", "description": "Overtake from 5+ seconds behind in final lap", "icon": "🏆"},
    "tire_master": {"name": "Tire Master", "description": "Win using 2+ different tire types", "icon": "🛞"},
    "rain_specialist": {"name": "Rain Specialist", "description": "Win a race in rainy conditions", "icon": "🌧️"},
    "ten_wins": {"name": "Racing Veteran", "description": "Achieve 10 wins", "icon": "🎖️"},
    "fifty_races": {"name": "True Competitor", "description": "Complete 50 races", "icon": "🔥"},
}
