import random
from datetime import datetime
from typing import List, Dict, Optional
import card_manager as _cm

# ==================== DRIVER CARDS ====================

DRIVERS = {
    "legendary": [
        {"name": "Lewis Hamilton",      "code": "HAM", "skill": 8.8, "team": "Ferrari"},
        {"name": "Max Verstappen",      "code": "VER", "skill": 9.2, "team": "Red Bull"},
        {"name": "Lando Norris",        "code": "NOR", "skill": 8.7, "team": "McLaren"},
        {"name": "Ayrton Senna",        "code": "SEN", "skill": 9.5, "team": "McLaren"},
        {"name": "Michael Schumacher",  "code": "MSC", "skill": 9.4, "team": "Ferrari"},
        {"name": "Alain Prost",         "code": "PRO", "skill": 9.1, "team": "McLaren"},
        {"name": "Niki Lauda",          "code": "NIK", "skill": 9.0, "team": "Ferrari"},
        {"name": "Juan Manuel Fangio",  "code": "FAN", "skill": 9.6, "team": "Mercedes"},
        {"name": "Sebastian Vettel",    "code": "VET", "skill": 9.0, "team": "Aston Martin"},
    ],
    "epic": [
        {"name": "Charles Leclerc",   "code": "LEC", "skill": 8.3, "team": "Ferrari"},
        {"name": "George Russell",    "code": "RUS", "skill": 8.1, "team": "Mercedes"},
        {"name": "Carlos Sainz",      "code": "SAI", "skill": 7.9, "team": "Williams"},
        {"name": "Fernando Alonso",   "code": "ALO", "skill": 8.0, "team": "Aston Martin"},
        {"name": "Oscar Piastri",     "code": "PIA", "skill": 7.8, "team": "McLaren"},
        {"name": "Jim Clark",         "code": "CLK", "skill": 8.9, "team": "Lotus"},
        {"name": "Nigel Mansell",     "code": "MAN", "skill": 8.4, "team": "Williams"},
        {"name": "Damon Hill",        "code": "HIL", "skill": 8.2, "team": "Williams"},
        {"name": "Nico Rosberg",      "code": "ROS", "skill": 8.0, "team": "Mercedes"},
        {"name": "Jenson Button",     "code": "BUT", "skill": 7.9, "team": "Brawn GP"},
        {"name": "Kimi Raikkonen",    "code": "RAI", "skill": 8.3, "team": "Ferrari"},
    ],
    "rare": [
        {"name": "Yuki Tsunoda",        "code": "TSU", "skill": 7.2, "team": "RB"},
        {"name": "Pierre Gasly",        "code": "GAS", "skill": 7.3, "team": "Alpine"},
        {"name": "Esteban Ocon",        "code": "OCO", "skill": 7.1, "team": "Haas"},
        {"name": "Valtteri Bottas",     "code": "BOT", "skill": 7.4, "team": "Kick Sauber"},
        {"name": "Kevin Magnussen",     "code": "MAG", "skill": 7.0, "team": "Haas"},
        {"name": "Sergio Perez",        "code": "PER", "skill": 7.6, "team": "Red Bull"},
        {"name": "Mark Webber",         "code": "WEB", "skill": 7.8, "team": "Red Bull"},
        {"name": "Kimi Antonelli",      "code": "ANT", "skill": 7.4, "team": "Mercedes"},
        {"name": "Oliver Bearman",      "code": "BEA", "skill": 7.3, "team": "Haas"},
        {"name": "Gabriel Bortoleto",   "code": "BOR", "skill": 7.5, "team": "Kick Sauber"},
        {"name": "Liam Lawson",         "code": "LAW", "skill": 7.6, "team": "Red Bull"},
        {"name": "Felipe Drugovich",    "code": "DRU", "skill": 6.9, "team": "Aston Martin"},
    ],
    "common": [
        {"name": "Lance Stroll",    "code": "STR", "skill": 6.5, "team": "Aston Martin"},
        {"name": "Alex Albon",      "code": "ALB", "skill": 6.8, "team": "Williams"},
        {"name": "Nico Hulkenberg", "code": "HUL", "skill": 6.9, "team": "Kick Sauber"},
        {"name": "Zhou Guanyu",     "code": "ZHO", "skill": 6.4, "team": "Kick Sauber"},
        {"name": "Logan Sargeant",  "code": "SAR", "skill": 6.1, "team": "Williams"},
        {"name": "Jack Doohan",      "code": "DOO", "skill": 6.6, "team": "Alpine"},
        {"name": "Isack Hadjar",     "code": "HAD", "skill": 6.7, "team": "RB"},
        {"name": "Franco Colapinto", "code": "COL", "skill": 6.8, "team": "Alpine"},
    ],
}

# ==================== CAR CARDS ====================

CARS = {
    "legendary": [
        {"name": "Mercedes AMG W14", "team": "Mercedes", "top_speed": 412, "handling": 9.2},
        {"name": "Red Bull RB19", "team": "Red Bull", "top_speed": 410, "handling": 9.4},
        {"name": "Ferrari SF-23+", "team": "Ferrari", "top_speed": 408, "handling": 9.0},
        {"name": "McLaren MCL60S", "team": "McLaren", "top_speed": 406, "handling": 9.1},
    ],
    "epic": [
        {"name": "Mercedes AMG W13", "team": "Mercedes", "top_speed": 392, "handling": 8.5},
        {"name": "Red Bull RB18", "team": "Red Bull", "top_speed": 390, "handling": 8.8},
        {"name": "Ferrari F1-75", "team": "Ferrari", "top_speed": 387, "handling": 8.4},
        {"name": "McLaren MCL36", "team": "McLaren", "top_speed": 385, "handling": 8.3},
    ],
    "rare": [
        {"name": "Alpine A523", "team": "Alpine", "top_speed": 368, "handling": 7.6},
        {"name": "Aston Martin AMR23", "team": "Aston Martin", "top_speed": 365, "handling": 7.8},
        {"name": "Williams FW45", "team": "Williams", "top_speed": 360, "handling": 7.3},
        {"name": "AlphaTauri AT04", "team": "RB", "top_speed": 358, "handling": 7.1},
    ],
    "common": [
        {"name": "Haas VF-23", "team": "Haas", "top_speed": 342, "handling": 6.5},
        {"name": "Alfa Romeo C43", "team": "Alfa Romeo", "top_speed": 340, "handling": 6.4},
        {"name": "Williams FW44", "team": "Williams", "top_speed": 338, "handling": 6.2},
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
        "odds": {"legendary": 0.01, "epic": 0.07, "rare": 0.27, "common": 0.65},
    },
    "weekly": {
        "name": "Weekly Pack",
        "emoji": "🏆",
        "card_count": 1,
        "cost": 0,
        "guaranteed": "rare",
        "odds": {"legendary": 0.06, "epic": 0.18, "rare": 0.36, "common": 0.40},
    },
    "bronze": {
        "name": "Bronze Pack",
        "emoji": "🥉",
        "card_count": 3,
        "cost": 500,
        "guaranteed": None,
        "odds": {"legendary": 0.01, "epic": 0.07, "rare": 0.30, "common": 0.62},
    },
    "silver": {
        "name": "Silver Pack",
        "emoji": "🥈",
        "card_count": 3,
        "cost": 1500,
        "guaranteed": "rare",
        "odds": {"legendary": 0.04, "epic": 0.14, "rare": 0.37, "common": 0.45},
    },
    "gold": {
        "name": "Gold Pack",
        "emoji": "🥇",
        "card_count": 5,
        "cost": 3500,
        "guaranteed": "epic",
        "odds": {"legendary": 0.10, "epic": 0.30, "rare": 0.45, "common": 0.15},
    },
    "platinum": {
        "name": "Platinum Pack",
        "emoji": "💎",
        "card_count": 5,
        "cost": 8000,
        "guaranteed": "legendary",
        "odds": {"legendary": 0.25, "epic": 0.40, "rare": 0.30, "common": 0.05},
    },
}

# ==================== SELL VALUES ====================

SELL_VALUES = {
    "common": 75,
    "rare": 200,
    "epic": 600,
    "legendary": 1500,
}

# ==================== TEAM ASSETS ====================

TEAM_ASSETS = {
    "legendary": [
        {"name": "Adrian Newey",    "role": "Chief Designer",      "team": "Red Bull",   "effect": "aero",            "bonus": 0.15, "description": "+15% aerodynamics & cornering"},
        {"name": "James Allison",   "role": "Technical Director",  "team": "Mercedes",   "effect": "acceleration",    "bonus": 0.12, "description": "+12% acceleration out of corners"},
        {"name": "Ross Brawn",      "role": "Team Principal",      "team": "Brawn GP",   "effect": "pit_time",        "bonus": 0.80, "description": "-0.8s off every pit stop"},
    ],
    "epic": [
        {"name": "Red Bull Pit Crew",       "role": "Pit Crew",         "team": "Red Bull",   "effect": "pit_time",        "bonus": 0.60, "description": "-0.6s off every pit stop"},
        {"name": "Pirelli Engineers",       "role": "Tyre Specialists", "team": "Pirelli",    "effect": "tire_wear",       "bonus": 0.20, "description": "-20% tyre degradation rate"},
        {"name": "Ferrari Strategy Team",   "role": "Strategists",      "team": "Ferrari",    "effect": "fuel_efficiency", "bonus": 0.12, "description": "+12% fuel efficiency per lap"},
        {"name": "Mercedes Data Team",      "role": "Data Engineers",   "team": "Mercedes",   "effect": "acceleration",    "bonus": 0.10, "description": "+10% acceleration boost"},
    ],
    "rare": [
        {"name": "McLaren Mechanics",       "role": "Mechanics",        "team": "McLaren",    "effect": "tire_wear",       "bonus": 0.10, "description": "-10% tyre degradation rate"},
        {"name": "Aston Martin Aero Dept",  "role": "Aerodynamicists",  "team": "Aston Martin","effect": "aero",           "bonus": 0.08, "description": "+8% aerodynamics boost"},
        {"name": "Williams Engineers",      "role": "Race Engineers",   "team": "Williams",   "effect": "fuel_efficiency", "bonus": 0.08, "description": "+8% fuel efficiency"},
        {"name": "Alpine Pit Crew",         "role": "Pit Crew",         "team": "Alpine",     "effect": "pit_time",        "bonus": 0.30, "description": "-0.3s off every pit stop"},
    ],
    "common": [
        {"name": "Haas Mechanics",          "role": "Mechanics",        "team": "Haas",       "effect": "tire_wear",       "bonus": 0.05, "description": "-5% tyre degradation rate"},
        {"name": "Alfa Romeo Engineers",    "role": "Engineers",        "team": "Alfa Romeo", "effect": "fuel_efficiency", "bonus": 0.05, "description": "+5% fuel efficiency"},
        {"name": "AlphaTauri Data Team",    "role": "Data Analysts",    "team": "RB",         "effect": "aero",            "bonus": 0.04, "description": "+4% aerodynamics boost"},
    ],
}

TEAM_ASSET_EFFECT_LABELS = {
    "aero":            "🏎️ Aerodynamics",
    "acceleration":    "🚀 Acceleration",
    "tire_wear":       "🔧 Tyre Wear",
    "fuel_efficiency": "⛽ Fuel Efficiency",
    "pit_time":        "⏱️ Pit Speed",
}


def generate_team_asset(rarity: str) -> Dict:
    """Generate a random team asset card of the given rarity."""
    pool = TEAM_ASSETS.get(rarity, TEAM_ASSETS["common"])
    asset = random.choice(pool)
    return {
        "id": f"{random.randint(0, 0xFFFFFFF):07X}",
        "type": "team_asset",
        "name": asset["name"],
        "role": asset["role"],
        "team": asset["team"],
        "effect": asset["effect"],
        "bonus": asset["bonus"],
        "description": asset["description"],
        "rarity": rarity,
        "obtained_at": datetime.now().isoformat(),
    }

# ==================== WILD SPAWN ====================

SPAWN_ODDS = {
    "common": 0.55,
    "rare": 0.30,
    "epic": 0.12,
    "legendary": 0.03,
}

SPAWN_TEAM_CHANCE = 0.25  # 25% of wild spawns are team assets


def generate_spawn_card() -> Dict:
    """Generate a single wild card — always a driver or car (no team assets in wild spawns)."""
    rarity = _roll_rarity(SPAWN_ODDS)
    return _generate_card(rarity)

# ==================== RARITY DISPLAY ====================

RARITY_EMOJIS = {
    "legendary": "👑",
    "epic": "💜",
    "rare": "💙",
    "common": "⚪",
}

RARITY_COLORS = {
    "legendary": 0xFFD700,
    "epic": 0x9B59B6,
    "rare": 0x3498DB,
    "common": 0x95A5A6,
}

RARITY_LABELS = {
    "legendary": "LEGENDARY",
    "epic": "EPIC",
    "rare": "RARE",
    "common": "COMMON",
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
        pool.extend(_cm.get_drivers_by_rarity(rarity))
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
        pool.extend(_cm.get_cars_by_rarity(rarity))
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
    """Generate a list of cards for the given pack type.
    Higher-tier packs include a higher chance of team asset cards.
    """
    config = PACK_CONFIGS[pack_type]
    cards = []

    TEAM_ASSET_CHANCE = {
        "daily": 0.15, "weekly": 0.25,
        "bronze": 0.20, "silver": 0.30, "gold": 0.35, "platinum": 0.45,
    }.get(pack_type, 0.20)

    if config["guaranteed"]:
        cards.append(_generate_card(config["guaranteed"]))

    while len(cards) < config["card_count"]:
        rarity = _roll_rarity(config["odds"])
        if random.random() < TEAM_ASSET_CHANCE:
            cards.append(generate_team_asset(rarity))
        else:
            cards.append(_generate_card(rarity))

    return cards


# ==================== LEGACY PACK CLASS (kept for race rewards) ====================

class CardPack:
    @staticmethod
    def generate_win_pack() -> Dict:
        pack = {"cards": [], "total_cards": 3, "guaranteed_rarity": "rare"}
        pack["cards"].append(_generate_card("rare"))
        for _ in range(2):
            rarity = _roll_rarity(PACK_CONFIGS["daily"]["odds"])
            pack["cards"].append(_generate_card(rarity))
        return pack

    @staticmethod
    def generate_loss_pack() -> Dict:
        pack = {"cards": [], "total_cards": 2, "guaranteed_rarity": "common"}
        for _ in range(2):
            rarity = _roll_rarity({"legendary": 0.005, "epic": 0.03, "rare": 0.15, "common": 0.815})
            pack["cards"].append(_generate_card(rarity))
        return pack


# ==================== SYNERGIES ====================

SYNERGIES = {
    "mercedes_combo": {
        "name": "Mercedes Dominance",
        "description": "HAM in Mercedes car",
        "bonus": {"acceleration": 1.1, "handling": 1.15},
        "drivers": ["HAM"],
        "cars": ["Mercedes"],
    },
    "red_bull_combo": {
        "name": "Red Bull Supremacy",
        "description": "VER in Red Bull car",
        "bonus": {"acceleration": 1.15, "top_speed": 1.08},
        "drivers": ["VER"],
        "cars": ["Red Bull"],
    },
    "ferrari_combo": {
        "name": "Rosso Corsa",
        "description": "LEC in Ferrari car",
        "bonus": {"handling": 1.2, "acceleration": 1.12},
        "drivers": ["LEC"],
        "cars": ["Ferrari"],
    },
    "mclaren_duo": {
        "name": "Papaya Power",
        "description": "NOR in McLaren car",
        "bonus": {"consistency": 1.1, "fuel_efficiency": 1.1},
        "drivers": ["NOR"],
        "cars": ["McLaren"],
    },
}


def check_synergy(driver_code: str, car_team: str) -> Optional[Dict]:
    for synergy in SYNERGIES.values():
        if driver_code in synergy["drivers"] and car_team in synergy["cars"]:
            return synergy
    return None


def format_card(card: Dict) -> str:
    emoji = RARITY_EMOJIS.get(card["rarity"], "❓")
    if card["type"] == "driver":
        return f"{emoji} **{card['name']}** ({card['code']}) — {card['rarity'].title()}"
    else:
        return f"{emoji} **{card['name']}** ({card['team']}) — {card['top_speed']}km/h — {card['rarity'].title()}"
