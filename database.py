import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

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
    def __init__(self, db_file: str = "f1_data.json"):
        self.db_file = db_file
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._create_empty_db()

    def _create_empty_db(self) -> Dict:
        return {"players": {}, "matches": [], "spawn_channels": {}}

    def _save_data(self):
        with open(self.db_file, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def _migrate_player(self, player: Dict) -> Dict:
        player.setdefault("coins", 0)
        player.setdefault("equipped", {"driver_id": None, "car_id": None, "team_assets": []})
        player.setdefault("last_daily_pack", None)
        player.setdefault("last_weekly_pack", None)
        player.setdefault("last_vote_claimed", None)
        player.setdefault("vote_bonus_matches", 0)
        player.setdefault("upgrades", {s: 0 for s in UPGRADE_STATS})
        if "cards" not in player:
            player["cards"] = {"drivers": [], "cars": [], "team_assets": []}
        return player

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
            "cards": {"drivers": [], "cars": [], "team_assets": []},
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

    def can_claim_daily(self, player_id: str) -> Tuple[bool, int]:
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
        player = self.get_player(player_id)
        if not player:
            return True, 0
        last = player.get("last_weekly_pack")
        if not last:
            return True, 0
        last_dt = datetime.fromisoformat(last)
        next_dt = last_dt + timedelta(hours=168)
        now = datetime.now()
        if now >= next_dt:
            return True, 0
        return False, int((next_dt - now).total_seconds())

    def mark_weekly_claimed(self, player_id: str):
        player = self.get_player(player_id)
        if player:
            player["last_weekly_pack"] = datetime.now().isoformat()
            self._save_data()

    def update_player_stats(self, player_id: str, result: Dict):
        player = self.get_player(player_id)
        if not player:
            return
        stats = player.setdefault("stats", {"wins": 0, "losses": 0, "dnf": 0, "total_races": 0})
        status = result.get("status", "")
        if status == "win":
            stats["wins"] = stats.get("wins", 0) + 1
        elif status == "loss":
            stats["losses"] = stats.get("losses", 0) + 1
        elif status == "dnf":
            stats["dnf"] = stats.get("dnf", 0) + 1
        stats["total_races"] = stats.get("total_races", 0) + 1
        self._save_data()

    def set_equipped(self, player_id: str, card_type: str, card_id: str) -> bool:
        player = self.get_player(player_id)
        if not player:
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

    def add_card_to_player(self, player_id: str, card: Dict, card_type: str):
        player = self.get_player(player_id)
        if not player:
            return
        now = datetime.now().isoformat()
        card["obtained_at"] = now
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
        return player["cards"]

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
        player = self.get_player(player_id)
        if not player:
            return False
        for key in ("drivers", "cars", "team_assets"):
            lst = player["cards"].get(key, [])
            for i, card in enumerate(lst):
                if card["id"] == card_id:
                    lst.pop(i)
                    self._save_data()
                    return True
        return False

    def get_upgrades(self, player_id: str) -> Dict:
        player = self.get_player(player_id)
        if not player:
            return {s: 0 for s in UPGRADE_STATS}
        return player.setdefault("upgrades", {s: 0 for s in UPGRADE_STATS})

    def get_upgrade_multipliers(self, player_id: str) -> Dict:
        """
        Convert raw upgrade levels (0-5) into float multipliers.
        Values > 1.0 improve the stat. Brakes < 1.0 reduces tyre wear rate.
        """
        upgrades = self.get_upgrades(player_id)
        return {
            "engine":       1.0 + upgrades.get("engine",       0) * 0.03,
            "acceleration": 1.0 + upgrades.get("acceleration", 0) * 0.025,
            "aero":         1.0 + upgrades.get("aero",         0) * 0.025,
            "suspension":   1.0 + upgrades.get("suspension",   0) * 0.02,
            "brakes":       1.0 - upgrades.get("brakes",       0) * 0.04,
        }

    def should_send_promo_dm(self, player_id: str) -> bool:
        player = self.get_player(player_id)
        if not player:
            return False
        last = player.get("last_promo_dm_at")
        if not last:
            return True
        try:
            return (datetime.now() - datetime.fromisoformat(last)).total_seconds() >= 7 * 24 * 3600
        except Exception:
            return False

    def set_promo_dm_sent(self, player_id: str):
        player = self.get_player(player_id)
        if player:
            player["last_promo_dm_at"] = datetime.now().isoformat()
            self._save_data()

    def get_team_bonuses(self, player_id: str) -> Dict:
        """
        Sum bonus values from all equipped team asset cards.
        Returns a dict keyed by effect (aero, acceleration, tire_wear,
        fuel_efficiency, pit_time), values are total bonus floats.
        """
        defaults = {
            "aero": 0.0, "acceleration": 0.0,
            "tire_wear": 0.0, "fuel_efficiency": 0.0, "pit_time": 0.0,
        }
        player = self.get_player(player_id)
        if not player:
            return defaults

        equipped_ids = player.get("equipped", {}).get("team_assets", [])
        if not equipped_ids:
            return defaults

        all_assets = player.get("cards", {}).get("team_assets", [])
        bonuses = dict(defaults)
        for asset in all_assets:
            if asset.get("id") in equipped_ids:
                effect = asset.get("effect", "")
                if effect in bonuses:
                    bonuses[effect] += float(asset.get("bonus", 0.0))
        return bonuses

    def upgrade_stat(self, player_id: str, stat: str):
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

    def can_claim_vote(self, player_id: str) -> bool:
        player = self.data["players"].get(player_id)
        if not player:
            return False
        last = player.get("last_vote_claimed")
        if not last:
            return True
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() >= 12 * 3600

    def set_vote_claimed(self, player_id: str):
        player = self.data["players"].get(player_id)
        if player:
            player["last_vote_claimed"] = datetime.now().isoformat()
            self._save_data()

    def get_vote_bonus_matches(self, player_id: str) -> int:
        player = self.data["players"].get(player_id)
        return player.get("vote_bonus_matches", 0) if player else 0

    def add_vote_bonus_match(self, player_id: str):
        player = self.data["players"].get(player_id)
        if player:
            player["vote_bonus_matches"] = player.get("vote_bonus_matches", 0) + 1
            self._save_data()

    def use_vote_bonus_match(self, player_id: str) -> bool:
        player = self.data["players"].get(player_id)
        if not player:
            return False
        cur = player.get("vote_bonus_matches", 0)
        if cur <= 0:
            return False
        player["vote_bonus_matches"] = cur - 1
        career = player.get("career", {})
        if career:
            today = datetime.now().date().isoformat()
            if career.get("daily_reset_date") == today and career.get("daily_used", 0) > 0:
                career["daily_used"] = career.get("daily_used", 0) - 1
        self._save_data()
        return True

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
        career["match_results"].append({
            "match_num":  result["match_num"],
            "position":   result["position"],
            "points":     result["points"],
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

    def get_all_cards_sorted(self, player_id: str) -> List[Dict]:
        """Return all cards for a player sorted by rarity (best first)."""
        player = self.get_player(player_id)
        if not player:
            return []
        rarity_order = {"special": 0, "mythic": 1, "legendary": 2, "epic": 3, "rare": 4, "common": 5}
        all_cards = (
            player["cards"].get("drivers", [])
            + player["cards"].get("cars", [])
            + player["cards"].get("team_assets", [])
        )
        return sorted(all_cards, key=lambda c: rarity_order.get(c.get("rarity", "common"), 5))

    def get_special_cards(self, player_id: str) -> List[Dict]:
        """Return only 'special' rarity cards owned by the player."""
        return [c for c in self.get_all_cards_sorted(player_id) if c.get("rarity") == "special"]

    def count_wild_catches(self, player_id: str) -> int:
        """Count how many wild-spawned cards the player has caught."""
        all_cards = self.get_all_cards_sorted(player_id)
        return sum(
            1 for c in all_cards
            if (c.get("caught_at") or c.get("obtained_by") == "catch")
            and c.get("rarity") != "special"
        )

    def has_card_name(self, player_id: str, name: str, card_type: str) -> bool:
        """Return True if the player already owns a card with this name and type."""
        player = self.get_player(player_id)
        if not player:
            return False
        type_key = {"driver": "drivers", "car": "cars", "team_asset": "team_assets"}.get(card_type, card_type + "s")
        for card in player["cards"].get(type_key, []):
            if card.get("name") == name:
                return True
        return False

    def get_all_player_ids(self) -> List[str]:
        return list(self.data["players"].keys())

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

    # ==================== TRADE HISTORY ====================

    def record_trade(self, player1_id: str, player2_id: str,
                     p1_gave: List[Dict], p2_gave: List[Dict]):
        import time as _t, random as _r
        record = {
            "id": f"trade_{int(_t.time())}_{_r.randint(1000, 9999)}",
            "player1_id": player1_id,
            "player2_id": player2_id,
            "p1_gave": [{"id": c.get("id"), "name": c.get("name"),
                         "rarity": c.get("rarity"), "type": c.get("type")} for c in p1_gave],
            "p2_gave": [{"id": c.get("id"), "name": c.get("name"),
                         "rarity": c.get("rarity"), "type": c.get("type")} for c in p2_gave],
            "completed_at": datetime.now().isoformat(),
        }
        self.data.setdefault("trade_history", []).append(record)
        if len(self.data["trade_history"]) > 500:
            self.data["trade_history"] = self.data["trade_history"][-500:]
        self._save_data()

    def get_trade_history(self, player_id: str, other_id: Optional[str] = None,
                          limit: int = 20) -> List[Dict]:
        trades = self.data.get("trade_history", [])
        result = [t for t in trades
                  if t["player1_id"] == player_id or t["player2_id"] == player_id]
        if other_id:
            result = [t for t in result
                      if t["player1_id"] == other_id or t["player2_id"] == other_id]
        return sorted(result, key=lambda t: t["completed_at"], reverse=True)[:limit]

    # ==================== FRIENDS ====================

    def get_friends(self, player_id: str) -> List[str]:
        p = self.get_player(player_id)
        return p.setdefault("friends", []) if p else []

    def add_friend(self, player_id: str, friend_id: str) -> bool:
        p1 = self.get_player(player_id)
        p2 = self.get_player(friend_id)
        if not p1 or not p2:
            return False
        changed = False
        if friend_id not in p1.setdefault("friends", []):
            p1["friends"].append(friend_id)
            changed = True
        if player_id not in p2.setdefault("friends", []):
            p2["friends"].append(player_id)
            changed = True
        if changed:
            self._save_data()
        return True

    def remove_friend(self, player_id: str, friend_id: str) -> bool:
        p1 = self.get_player(player_id)
        p2 = self.get_player(friend_id)
        changed = False
        if p1 and friend_id in p1.get("friends", []):
            p1["friends"].remove(friend_id)
            changed = True
        if p2 and player_id in p2.get("friends", []):
            p2["friends"].remove(player_id)
            changed = True
        if changed:
            self._save_data()
        return changed

    def are_friends(self, player_id: str, other_id: str) -> bool:
        p = self.get_player(player_id)
        return bool(p and other_id in p.get("friends", []))

    def get_pending_requests(self, player_id: str) -> List[str]:
        p = self.get_player(player_id)
        return p.get("pending_friend_requests", []) if p else []

    def add_pending_request(self, from_id: str, to_id: str) -> bool:
        p = self.get_player(to_id)
        if not p:
            return False
        reqs = p.setdefault("pending_friend_requests", [])
        if from_id not in reqs:
            reqs.append(from_id)
            self._save_data()
            return True
        return False

    def remove_pending_request(self, from_id: str, to_id: str):
        p = self.get_player(to_id)
        if p:
            reqs = p.get("pending_friend_requests", [])
            if from_id in reqs:
                reqs.remove(from_id)
                self._save_data()

    # ==================== BLOCKS ====================

    def get_blocks(self, player_id: str) -> List[str]:
        p = self.get_player(player_id)
        return p.get("blocked_users", []) if p else []

    def add_block(self, player_id: str, target_id: str) -> bool:
        p = self.get_player(player_id)
        if not p:
            return False
        blocked = p.setdefault("blocked_users", [])
        if target_id in blocked:
            return False
        blocked.append(target_id)
        if target_id in p.get("friends", []):
            p["friends"].remove(target_id)
        target = self.get_player(target_id)
        if target and player_id in target.get("friends", []):
            target["friends"].remove(player_id)
        self._save_data()
        return True

    def remove_block(self, player_id: str, target_id: str) -> bool:
        p = self.get_player(player_id)
        if not p:
            return False
        blocked = p.get("blocked_users", [])
        if target_id in blocked:
            blocked.remove(target_id)
            self._save_data()
            return True
        return False

    def is_blocked(self, player_id: str, target_id: str) -> bool:
        p1 = self.get_player(player_id)
        p2 = self.get_player(target_id)
        if p1 and target_id in p1.get("blocked_users", []):
            return True
        if p2 and player_id in p2.get("blocked_users", []):
            return True
        return False

    # ==================== PRIVACY ====================

    def get_privacy(self, player_id: str) -> Dict:
        p = self.get_player(player_id)
        if not p:
            return {"inventory": "public", "donation": "ask"}
        return p.setdefault("privacy", {"inventory": "public", "donation": "ask"})

    def set_privacy(self, player_id: str, key: str, value: str) -> bool:
        p = self.get_player(player_id)
        if not p:
            return False
        p.setdefault("privacy", {})[key] = value
        self._save_data()
        return True

    # ==================== GUILD CONFIG ====================

    def get_guild_config(self, guild_id: str) -> Dict:
        self.data.setdefault("guild_configs", {})
        return self.data["guild_configs"].setdefault(str(guild_id), {
            "spawn_enabled": True,
            "blacklist": [],
        })

    def set_guild_spawn_enabled(self, guild_id: str, enabled: bool):
        cfg = self.get_guild_config(guild_id)
        cfg["spawn_enabled"] = enabled
        self._save_data()

    def is_spawn_enabled(self, guild_id: str) -> bool:
        cfg = self.get_guild_config(guild_id)
        return cfg.get("spawn_enabled", True)

    def guild_blacklist_add(self, guild_id: str, user_id: str) -> bool:
        cfg = self.get_guild_config(guild_id)
        bl = cfg.setdefault("blacklist", [])
        if user_id not in bl:
            bl.append(user_id)
            self._save_data()
            return True
        return False

    def guild_blacklist_remove(self, guild_id: str, user_id: str) -> bool:
        cfg = self.get_guild_config(guild_id)
        bl = cfg.get("blacklist", [])
        if user_id in bl:
            bl.remove(user_id)
            self._save_data()
            return True
        return False

    def is_guild_blacklisted(self, guild_id: str, user_id: str) -> bool:
        cfg = self.get_guild_config(guild_id)
        return user_id in cfg.get("blacklist", [])

    # ==================== LEADERBOARD ====================

    def get_leaderboard(self, metric: str = "cards", limit: int = 10) -> List[Dict]:
        results = []
        for pid, player in self.data["players"].items():
            if metric == "cards":
                score = (
                    len(player.get("cards", {}).get("drivers", []))
                    + len(player.get("cards", {}).get("cars", []))
                    + len(player.get("cards", {}).get("team_assets", []))
                )
            elif metric == "wins":
                score = player.get("stats", {}).get("wins", 0)
            elif metric == "coins":
                score = player.get("coins", 0)
            elif metric == "career":
                career = player.get("career", {})
                score = career.get("championship_points", 0) if career else 0
            elif metric == "catches":
                all_cards = (
                    player.get("cards", {}).get("drivers", [])
                    + player.get("cards", {}).get("cars", [])
                    + player.get("cards", {}).get("team_assets", [])
                )
                score = sum(1 for c in all_cards
                            if c.get("obtained_by") == "catch" or c.get("caught_at"))
            else:
                score = 0
            results.append({
                "player_id": pid,
                "username": player.get("username", "Unknown"),
                "score": score,
            })
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
