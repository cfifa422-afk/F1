import random
from datetime import datetime
from typing import List, Dict, Optional
import card_manager as _cm

# ==================== DRIVER CARDS ====================

DRIVERS = {
    "mythic": [],
    "legendary": [
        {"name": "Lewis Hamilton",      "code": "HAM", "skill": 8.8, "team": "Ferrari"},
        {"name": "Max Verstappen",      "code": "VER", "skill": 9.2, "team": "Red Bull"},
        {"name": "Ayrton Senna",        "code": "SEN", "skill": 9.5, "team": "McLaren"},
    ],
    "epic": [
        {"name": "Charles Leclerc",   "code": "LEC", "skill": 8.3, "team": "Ferrari"},
        {"name": "George Russell",    "code": "RUS", "skill": 8.1, "team": "Mercedes"},
    ],
    "rare": [
        {"name": "Yuki Tsunoda",        "code": "TSU", "skill": 7.2, "team": "RB"},
        {"name": "Pierre Gasly",        "code": "GAS", "skill": 7.3, "team": "Alpine"},
    ],
    "common": [
        {"name": "Lance Stroll",    "code": "STR", "skill": 6.5, "team": "Aston Martin"},
        {"name": "Alex Albon",      "code": "ALB", "skill": 6.8, "team": "Williams"},
    ],
}

# ==================== CAR CARDS ====================

CARS = {
    "mythic": [],
    "legendary": [
        {"name": "Mercedes AMG W14", "team": "Mercedes", "top_speed": 412, "handling": 9.2},
        {"name": "Red Bull RB19", "team": "Red Bull", "top_speed": 410, "handling": 9.4},
    ],
    "epic": [
        {"name": "Mercedes AMG W13", "team": "Mercedes", "top_speed": 392, "handling": 8.5},
        {"name": "Red Bull RB18", "team": "Red Bull", "top_speed": 390, "handling": 8.8},
    ],
    "rare": [
        {"name": "Alpine A523", "team": "Alpine", "top_speed": 368, "handling": 7.6},
    ],
    "common": [
        {"name": "Haas VF-23", "team": "Haas", "top_speed": 342, "handling": 6.5},
    ],
}

# ==================== PERKS ====================

PERKS = {
    "fuel_saver": {"name": "Fuel Saver", "description": "Reduce fuel consumption by 10%", "effect": 0.9},
    "tire_master": {"name": "Tire Master", "description": "Reduce tire wear by 15%", "effect": 0.85},
    "drs_specialist": {"name": "DRS Specialist", "description": "+0.8s when DRS is available", "effect": 0.8},
    "rain_master": {"name": "Rain Master", "description": "+2.5s in wet conditions", "effect": 2.5},
    "pit_crew_chief": {"name": "Pit Crew Chief", "description": "Reduce pit stop time by 0.5s", "effect": 0.5},
    "consistency": {"name": "Consistency", "description": "+5% lap time stability", "effect": 1.05},
}

# ==================== PACK CONFIGS ====================

PACK_CONFIGS = {
    "daily": {
        "name": "Daily Pack",
        "emoji": "🗓️",
        "card_count": 1,
        "cost": 0,
        "guaranteed": None,
        "odds": {"mythic": 0.01, "legendary": 0.01, "epic": 0.07, "rare": 0.27, "common": 0.64},
    },
    "weekly": {
        "name": "Weekly Pack",
        "emoji": "🏆",
        "card_count": 1,
        "cost": 0,
        "guaranteed": "rare",
        "odds": {"mythic": 0.01, "legendary": 0.06, "epic": 0.18, "rare": 0.36, "common": 0.39},
    },
    "bronze": {
        "name": "Bronze Pack",
        "emoji": "🥉",
        "card_count": 3,
        "cost": 500,
        "guaranteed": None,
        "odds": {"mythic": 0.01, "legendary": 0.01, "epic": 0.07, "rare": 0.30, "common": 0.61},
    },
}

# ==================== SELL VALUES ====================

SELL_VALUES = {
    "common": 75,
    "rare": 200,
    "epic": 600,
    "legendary": 1500,
    "mythic": 5000,
}

# ==================== TEAM ASSETS ====================

TEAM_ASSETS = {
    "mythic": [],
    "legendary": [
        {"name": "Adrian Newey",    "role": "Chief Designer",      "team": "Red Bull",   "effect": "aero",            "bonus": 0.15},
    ],
    "epic": [],
    "rare": [],
    "common": [],
}

TEAM_ASSET_EFFECT_LABELS = {
    "aero":            "🏎️ Aerodynamics",
    "acceleration":    "🚀 Acceleration",
    "tire_wear":       "🔧 Tyre Wear",
    "fuel_efficiency": "⛽ Fuel Efficiency",
    "pit_time":        "⏱️ Pit Speed",
}

def generate_team_asset(rarity: str) -> Dict:
    pool = TEAM_ASSETS.get(rarity, TEAM_ASSETS["common"])
    if not pool:
        pool = list(TEAM_ASSETS["common"])
    asset = random.choice(pool) if pool else {"name": "Unknown", "role": "Staff", "team": "Unknown", "effect": "aero", "bonus": 0.01}
    return {
        "id": f"{random.randint(0, 0xFFFFFFF):07X}",
        "type": "team_asset",
        "name": asset["name"],
        "role": asset["role"],
        "team": asset["team"],
        "effect": asset["effect"],
        "bonus": asset["bonus"],
        "rarity": rarity,
        "obtained_at": datetime.now().isoformat(),
    }

# ==================== RARITY DISPLAY ====================

RARITY_EMOJIS = {
    "mythic": "🔱",
    "legendary": "👑",
    "epic": "💜",
    "rare": "💙",
    "common": "⚪",
}

RARITY_COLORS = {
    "mythic": 0xFF4500,
    "legendary": 0xFFD700,
    "epic": 0x9B59B6,
    "rare": 0x3498DB,
    "common": 0x95A5A6,
}

# ==================== CARD GENERATION ====================

def _roll_rarity(odds: Dict[str, float]) -> str:
    rand = random.random()
    cumulative = 0.0
    for rarity, prob in odds.items():
        cumulative += prob
        if rand < cumulative:
            return rarity
    return "common"

def _generate_card(rarity: str) -> Dict:
    card_type = random.choice(["driver", "car"])

    if card_type == "driver":
        pool = list(DRIVERS.get(rarity, DRIVERS["common"]))
        if not pool:
            pool = list(DRIVERS["common"])
        driver = random.choice(pool)
        perks = [random.choice(list(PERKS.keys()))] if random.random() < 0.30 else []
        return {
            "id": f"{random.randint(0, 0xFFFFFFF):07X}",
            "type": "driver",
            "name": driver["name"],
            "code": driver["code"],
            "skill": driver["skill"],
            "team": driver["team"],
            "rarity": rarity,
            "perks": perks,
            "obtained_at": datetime.now().isoformat(),
        }
    else:
        pool = list(CARS.get(rarity, CARS["common"]))
        if not pool:
            pool = list(CARS["common"])
        car = random.choice(pool)
        perks = [random.choice(list(PERKS.keys()))] if random.random() < 0.25 else []
        return {
            "id": f"{random.randint(0, 0xFFFFFFF):07X}",
            "type": "car",
            "name": car["name"],
            "team": car["team"],
            "top_speed": car["top_speed"],
            "handling": car["handling"],
            "rarity": rarity,
            "perks": perks,
            "obtained_at": datetime.now().isoformat(),
        }

def generate_pack(pack_type: str) -> List[Dict]:
    config = PACK_CONFIGS[pack_type]
    cards = []

    TEAM_ASSET_CHANCE = 0.20

    if config["guaranteed"]:
        cards.append(_generate_card(config["guaranteed"]))

    while len(cards) < config["card_count"]:
        rarity = _roll_rarity(config["odds"])
        if random.random() < TEAM_ASSET_CHANCE:
            cards.append(generate_team_asset(rarity))
        else:
            cards.append(_generate_card(rarity))

    return cards

def check_synergy(driver_code: str, car_team: str) -> Optional[Dict]:
    """Return a synergy dict if the driver belongs to the same team as the car, else None."""
    for rarity_pool in DRIVERS.values():
        for driver in rarity_pool:
            if driver.get("code") == driver_code:
                if driver.get("team", "").lower() == car_team.lower():
                    return {"name": f"{car_team} Synergy — home advantage!"}
                return None
    return None

def generate_spawn_card() -> Dict:
    rarity = _roll_rarity({"mythic": 0.008, "legendary": 0.03, "epic": 0.12, "rare": 0.30, "common": 0.542})
    return _generate_card(rarity)
