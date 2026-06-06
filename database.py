import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

try:
    from replit import db as _replit_db
    _REPLIT_DB_KEY = "f1_data_backup"
    _USE_REPLIT_DB = True
except Exception:
    _USE_REPLIT_DB = False

# ==================== UPGRADE CONSTANTS ====================

UPGRADE_STATS = ["engine", "aero", "brakes", "acceleration", "suspension"]
UPGRADE_COSTS = [500, 1000, 2000, 4000, 8000]
UPGRADE_MAX_LEVEL = 5

UPGRADE_INFO = {
    "engine":       {"emoji": "🔴", "label": "Engine",       "description": "Boosts top speed & raw power"},
    "aero":         {"emoji": "🔵", "label": "Aerodynamics", "description": "Improves handling & cornering"},
    "brakes":       {"emoji": "🟡", "label": "Brakes",       "description": "Reduces tyre wear under braking"},
    "acceleration": {"emoji": "🟢", "label": "Acceleration", "description": "Faster out of corners"},
    "suspension":   {"emoji": "⚪", "label": "Suspension",   "description": "Stability in all conditions"},
}


class Database:
    """JSON-based database for F1 racing bot"""

    def __init__(self, db_file: str = "f1_data.json"):
        self.db_file = db_file
        self.data = self._load_data()
        self._backup_to_replit_db()

    def _load_data(self) -> Dict:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r") as f:
                    data = json.load(f)
                if data.get("players"):
                    return data
            except Exception:
                pass
        # Local file missing or empty — try to restore from Replit DB
        if _USE_REPLIT_DB:
            try:
                backup = _replit_db.get(_REPLIT_DB_KEY)
                if backup:
                    data = json.loads(str(backup))
                    print("✅ Restored f1_data from Replit DB backup")
                    with open(self.db_file, "w") as f:
                        json.dump(data, f, indent=2, default=str)
                    return data
            except Exception as e:
                print(f"⚠️ Could not restore from Replit DB: {e}")
        return self._create_empty_db()

    def _create_empty_db(self) -> Dict:
        return {"players": {}, "matches": [], "leaderboard": [], "spawn_channels": {}}

    def _backup_to_replit_db(self):
        if _USE_REPLIT_DB and self.data.get("players"):
            try:
                _replit_db[_REPLIT_DB_KEY] = json.dumps(self.data, default=str)
                print(f"☁️  Replit DB backup saved ({len(self.data['players'])} players)")
            except Exception as e:
                print(f"⚠️ Replit DB backup failed: {e}")

    def _save_data(self):
        with open(self.db_file, "w") as f:
            json.dump(self.data, f, indent=2, default=str)
        self._backup_to_replit_db()

    def _migrate_player(self, player: Dict) -> Dict:
        """Ensure old players have all new fields."""
        player.setdefault("coins", 0)
        player.setdefault("equipped", {"driver_id": None, "car_id": None, "team_assets": []})
        player["equipped"].setdefault("team_assets", [])
        player.setdefault("last_daily_pack", None)
        player.setdefault("last_weekly_pack", None)
        player.setdefault("last_promo_dm", None)
        player.setdefault("achievements", [])
        player.setdefault("upgrades", {s: 0 for s in UPGRADE_STATS})
        if "cards" not in player:
            player["cards"] = {"drivers": [], "cars": [], "team_assets": []}
        player["cards"].setdefault("drivers", [])
        player["cards"].setdefault("cars", [])
        player["cards"].setdefault("team_assets", [])
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
            "equipped": {"driver_id": None, "car_id": None, "team_assets": []},
            "last_daily_pack": None,
            "last_weekly_pack": None,
            "last_promo_dm": None,
            "stats": {
                "wins": 0,
                "losses": 0,
                "dnf": 0,
                "total_races": 0,
                "win_rate": 0.0,
                "ranking_points": 0,
                "rank": "Bronze",
            },
            "cards": {"drivers": [], "cars": [], "team_assets": []},
            "achievements": [],
            "upgrades": {s: 0 for s in UPGRADE_STATS},
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
        now = datetime.now().isoformat()
        card["obtained_at"] = now
        card["caught_at"] = now
        if card_type == "driver":
            player["cards"]["drivers"].append(card)
        elif card_type == "car":
            player["cards"]["cars"].append(card)
        elif card_type == "team_asset":
            player["cards"].setdefault("team_assets", []).append(card)
        self._save_data()

    def get_player_cards(self, player_id: str) -> Dict:
        player = self.get_player(player_id)
        if not player:
            return {"drivers": [], "cars": [], "team_assets": []}
        cards = player["cards"]
        cards.setdefault("team_assets", [])
        return cards

    def get_card_by_id(self, player_id: str, card_id: str) -> Optional[Dict]:
        player = self.get_player(player_id)
        if not player:
            return None
        all_cards = (
            player["cards"]["drivers"]
            + player["cards"]["cars"]
            + player["cards"].get("team_assets", [])
        )
        for card in all_cards:
            if card["id"] == card_id:
                return card
        return None

    def remove_card(self, player_id: str, card_id: str) -> bool:
        """Remove a card from player's collection by card ID. Returns True if removed."""
        player = self.get_player(player_id)
        if not player:
            return False
        for key in ("drivers", "cars", "team_assets"):
            lst = player["cards"].get(key, [])
            for i, card in enumerate(lst):
                if card["id"] == card_id:
                    lst.pop(i)
                    equipped = player.get("equipped", {})
                    if equipped.get("driver_id") == card_id:
                        equipped["driver_id"] = None
                    if equipped.get("car_id") == card_id:
                        equipped["car_id"] = None
                    ta = equipped.get("team_assets", [])
                    if card_id in ta:
                        ta.remove(card_id)
                    self._save_data()
                    return True
        return False

    def has_card_name(self, player_id: str, name: str, card_type: str) -> bool:
        """Check if player already owns a card with this exact name."""
        player = self.get_player(player_id)
        if not player:
            return False
        key = {"driver": "drivers", "car": "cars", "team_asset": "team_assets"}.get(card_type, "drivers")
        return any(c["name"] == name for c in player["cards"].get(key, []))

    def get_all_cards_sorted(self, player_id: str) -> List[Dict]:
        """Return all cards (drivers + cars + team assets) sorted by obtained_at descending."""
        player = self.get_player(player_id)
        if not player:
            return []
        all_cards = (
            player["cards"]["drivers"]
            + player["cards"]["cars"]
            + player["cards"].get("team_assets", [])
        )
        all_cards.sort(key=lambda c: c.get("obtained_at", ""), reverse=True)
        return all_cards

    # ==================== UPGRADES ====================

    def get_upgrades(self, player_id: str) -> Dict:
        player = self.get_player(player_id)
        if not player:
            return {s: 0 for s in UPGRADE_STATS}
        return player.setdefault("upgrades", {s: 0 for s in UPGRADE_STATS})

    def upgrade_stat(self, player_id: str, stat: str):
        """Attempt to upgrade a stat. Returns (success: bool, message: str)."""
        if stat not in UPGRADE_STATS:
            return False, "Unknown upgrade stat."
        player = self.get_player(player_id)
        if not player:
            return False, "Player not found."
        upgrades = player.setdefault("upgrades", {s: 0 for s in UPGRADE_STATS})
        current = upgrades.get(stat, 0)
        if current >= UPGRADE_MAX_LEVEL:
            return False, "Already at maximum level (5/5)!"
        cost = UPGRADE_COSTS[current]
        if player.get("coins", 0) < cost:
            short = cost - player.get("coins", 0)
            return False, f"Need **{cost:,} coins** — short by **{short:,}**."
        player["coins"] -= cost
        upgrades[stat] = current + 1
        self._save_data()
        return True, current + 1

    def get_upgrade_multipliers(self, player_id: str) -> Dict:
        """Return stat multipliers based on upgrade levels."""
        upgrades = self.get_upgrades(player_id)
        return {
            "engine":       1.0 + upgrades.get("engine", 0) * 0.06,
            "aero":         1.0 + upgrades.get("aero", 0) * 0.06,
            "brakes":       max(0.20, 1.0 - upgrades.get("brakes", 0) * 0.12),
            "acceleration": 1.0 + upgrades.get("acceleration", 0) * 0.06,
            "suspension":   1.0 + upgrades.get("suspension", 0) * 0.04,
        }

    # ==================== TEAM ASSETS ====================

    def equip_team_asset(self, player_id: str, card_id: str) -> Tuple[bool, str]:
        player = self.get_player(player_id)
        if not player:
            return False, "Player not found."
        card = self.get_card_by_id(player_id, card_id)
        if not card or card.get("type") != "team_asset":
            return False, "Card not found or not a team asset."
        equipped = player.setdefault("equipped", {})
        ta = equipped.setdefault("team_assets", [])
        if card_id in ta:
            return False, "Already equipped."
        if len(ta) >= 3:
            return False, "Already have 3 team assets equipped. Unequip one first."
        ta.append(card_id)
        self._save_data()
        return True, f"Equipped **{card['name']}**!"

    def unequip_team_asset(self, player_id: str, card_id: str) -> Tuple[bool, str]:
        player = self.get_player(player_id)
        if not player:
            return False, "Player not found."
        ta = player.get("equipped", {}).get("team_assets", [])
        if card_id not in ta:
            return False, "Not currently equipped."
        ta.remove(card_id)
        self._save_data()
        card = self.get_card_by_id(player_id, card_id)
        name = card["name"] if card else "asset"
        return True, f"Unequipped **{name}**."

    def get_equipped_team_assets(self, player_id: str) -> List[Dict]:
        """Return full card dicts for all equipped team assets."""
        player = self.get_player(player_id)
        if not player:
            return []
        ta_ids = player.get("equipped", {}).get("team_assets", [])
        return [c for c in player["cards"].get("team_assets", []) if c["id"] in ta_ids]

    def get_team_bonuses(self, player_id: str) -> Dict:
        """Aggregate all bonuses from equipped team assets."""
        bonuses = {"aero": 0.0, "acceleration": 0.0, "tire_wear": 0.0, "fuel_efficiency": 0.0, "pit_time": 0.0}
        for asset in self.get_equipped_team_assets(player_id):
            effect = asset.get("effect")
            if effect in bonuses:
                bonuses[effect] += asset.get("bonus", 0.0)
        return bonuses

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

    def get_all_player_ids(self) -> List[str]:
        return list(self.data["players"].keys())

    def should_send_promo_dm(self, player_id: str) -> bool:
        player = self.get_player(player_id)
        if not player:
            return False
        last = player.get("last_promo_dm")
        if not last:
            return True
        last_date = datetime.fromisoformat(last).date()
        return (datetime.now().date() - last_date).days >= 5

    def set_promo_dm_sent(self, player_id: str):
        player = self.data["players"].get(player_id)
        if player:
            player["last_promo_dm"] = datetime.now().isoformat()
            self._save_data()

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

    # ==================== SPAWN CHANNELS ====================

    def get_spawn_channels(self, guild_id: str) -> List[int]:
        self.data.setdefault("spawn_channels", {})
        return self.data["spawn_channels"].get(guild_id, [])

    def add_spawn_channel(self, guild_id: str, channel_id: int) -> bool:
        self.data.setdefault("spawn_channels", {})
        channels = self.data["spawn_channels"].setdefault(guild_id, [])
        if channel_id not in channels:
            channels.append(channel_id)
            self._save_data()
            return True
        return False

    def remove_spawn_channel(self, guild_id: str, channel_id: int) -> bool:
        self.data.setdefault("spawn_channels", {})
        channels = self.data["spawn_channels"].get(guild_id, [])
        if channel_id in channels:
            channels.remove(channel_id)
            self._save_data()
            return True
        return False

    # ==================== CAREER ====================

    def get_career(self, player_id: str) -> Optional[Dict]:
        player = self.get_player(player_id)
        return player.get("career") if player else None

    def set_career(self, player_id: str, career: Dict):
        player = self.get_player(player_id)
        if player:
            player["career"] = career
            self._save_data()

    def create_career(self, player_id: str, car_snap: Dict, driver_snap: Dict) -> Dict:
        career = {
            "status":               "active",
            "car_snapshot":         car_snap,
            "driver_snapshot":      driver_snap,
            "matches_completed":    0,
            "championship_points":  0,
            "coins_earned":         0,
            "match_results":        [],
            "daily_used":           0,
            "daily_reset_date":     None,
            "last_match_at":        None,
            "reward_claimed":       False,
            "signed_at":            datetime.now().isoformat(),
        }
        player = self.get_player(player_id)
        if player:
            player["career"] = career
            self._save_data()
        return career

    def record_career_match(self, player_id: str, result: Dict):
        """Save match result and update career totals. result keys: match_num, position, points, coins, track."""
        career = self.get_career(player_id)
        if not career:
            return
        today = datetime.now().date().isoformat()
        if career.get("daily_reset_date") != today:
            career["daily_used"]       = 0
            career["daily_reset_date"] = today
        career["daily_used"]           = career.get("daily_used", 0) + 1
        career["last_match_at"]        = datetime.now().isoformat()
        career["matches_completed"]    = career.get("matches_completed", 0) + 1
        career["championship_points"]  = career.get("championship_points", 0) + result.get("points", 0)
        career["coins_earned"]         = career.get("coins_earned", 0) + result.get("coins", 0)
        career["match_results"].append({
            "match_num":  result["match_num"],
            "position":   result["position"],
            "points":     result["points"],
            "coins":      result["coins"],
            "track":      result.get("track", {}).get("name", ""),
            "completed_at": datetime.now().isoformat(),
        })
        from career import TOTAL_MATCHES
        if career["matches_completed"] >= TOTAL_MATCHES:
            career["status"] = "completed"
        self.add_coins(player_id, result.get("coins", 0))
        player = self.get_player(player_id)
        if player:
            player["career"] = career
            self._save_data()

    def get_career_standings(self) -> List[Dict]:
        """All players with active/completed careers, sorted by championship points."""
        standings = []
        for pid, player in self.data["players"].items():
            career = player.get("career")
            if career and career.get("status") in ("active", "completed"):
                standings.append({
                    "player_id":            pid,
                    "username":             player.get("username", "Unknown"),
                    "status":               career["status"],
                    "championship_points":  career.get("championship_points", 0),
                    "matches_completed":    career.get("matches_completed", 0),
                })
        standings.sort(key=lambda x: x["championship_points"], reverse=True)
        return standings

    def get_career_player_position(self, player_id: str) -> Optional[int]:
        standings = self.get_career_standings()
        for i, s in enumerate(standings, 1):
            if s["player_id"] == player_id:
                return i
        return None


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
