import random
from typing import List, Dict, Tuple

# ==================== DRIVER CARDS ====================

DRIVERS = {
    "legendary": [
        {"name": "Lewis Hamilton", "code": "HAM", "skill": 8.8, "team": "Mercedes"},
        {"name": "Max Verstappen", "code": "VER", "skill": 9.2, "team": "Red Bull"},
        {"name": "Lando Norris", "code": "LAN", "skill": 8.5, "team": "McLaren"},
    ],
    "epic": [
        {"name": "Charles Leclerc", "code": "LEC", "skill": 8.3, "team": "Ferrari"},
        {"name": "George Russell", "code": "RUS", "skill": 8.1, "team": "Mercedes"},
        {"name": "Carlos Sainz", "code": "SAI", "skill": 7.9, "team": "Ferrari"},
    ],
    "rare": [
        {"name": "Oscar Piastri", "code": "PIA", "skill": 7.6, "team": "McLaren"},
        {"name": "Fernando Alonso", "code": "ALO", "skill": 7.8, "team": "Aston Martin"},
        {"name": "Yuki Tsunoda", "code": "TSU", "skill": 7.2, "team": "AlphaTauri"},
    ],
    "common": [
        {"name": "Lance Stroll", "code": "STR", "skill": 6.5, "team": "Aston Martin"},
        {"name": "Alex Albon", "code": "ALB", "skill": 6.8, "team": "Williams"},
        {"name": "Nico Hulkenberg", "code": "HUL", "skill": 6.9, "team": "Haas"},
    ]
}

# ==================== CAR CARDS ====================

CARS = {
    "legendary": [
        {"name": "Mercedes AMG W14", "team": "Mercedes", "top_speed": 410, "handling": 9.0},
        {"name": "Red Bull RB19", "team": "Red Bull", "top_speed": 408, "handling": 9.2},
        {"name": "Ferrari F1-75+", "team": "Ferrari", "top_speed": 407, "handling": 8.8},
    ],
    "epic": [
        {"name": "Mercedes AMG W13", "team": "Mercedes", "top_speed": 390, "handling": 8.5},
        {"name": "Red Bull RB18", "team": "Red Bull", "top_speed": 388, "handling": 8.8},
        {"name": "Ferrari F1-75", "team": "Ferrari", "top_speed": 385, "handling": 8.2},
        {"name": "McLaren MCL36", "team": "McLaren", "top_speed": 383, "handling": 8.3},
    ],
    "rare": [
        {"name": "Alpine A522", "team": "Alpine", "top_speed": 365, "handling": 7.6},
        {"name": "Aston Martin AMR22", "team": "Aston Martin", "top_speed": 360, "handling": 7.5},
        {"name": "Williams FW44", "team": "Williams", "top_speed": 358, "handling": 7.2},
        {"name": "AlphaTauri AT03", "team": "AlphaTauri", "top_speed": 355, "handling": 7.0},
    ],
    "common": [
        {"name": "Haas VF-22", "team": "Haas", "top_speed": 340, "handling": 6.5},
        {"name": "Alfa Romeo C42", "team": "Alfa Romeo", "top_speed": 338, "handling": 6.3},
    ]
}

# ==================== SPECIAL PERKS ====================

PERKS = {
    "fuel_saver": {
        "name": "Fuel Saver",
        "description": "Reduce fuel consumption by 10%",
        "effect": 0.9
    },
    "tire_master": {
        "name": "Tire Master",
        "description": "Reduce tire wear by 15%",
        "effect": 0.85
    },
    "drs_specialist": {
        "name": "DRS Specialist",
        "description": "+0.8s when DRS is available",
        "effect": 0.8
    },
    "rain_master": {
        "name": "Rain Master",
        "description": "+2.5s in wet conditions",
        "effect": 2.5
    },
    "pit_crew_chief": {
        "name": "Pit Crew Chief",
        "description": "Reduce pit stop time by 0.5s",
        "effect": 0.5
    },
    "consistency": {
        "name": "Consistency",
        "description": "+5% lap time stability",
        "effect": 1.05
    }
}

# ==================== CARD PACK SYSTEM ====================

class CardPack:
    """Generate card packs based on rarity"""
    
    @staticmethod
    def generate_win_pack() -> Dict:
        """Generate a card pack for winning a race"""
        pack = {
            "cards": [],
            "total_cards": 5,
            "guaranteed_rarity": "rare"
        }
        
        # Guaranteed rare
        pack["cards"].append(CardPack._generate_card("rare"))
        
        # 4 random cards (weighted distribution)
        for _ in range(4):
            rarity = CardPack._roll_rarity(base_guaranteed=False)
            pack["cards"].append(CardPack._generate_card(rarity))
        
        return pack
    
    @staticmethod
    def generate_loss_pack() -> Dict:
        """Generate a card pack for losing/participating"""
        pack = {
            "cards": [],
            "total_cards": 3,
            "guaranteed_rarity": "common"
        }
        
        # 3 random cards (weighted toward common/rare)
        for _ in range(3):
            rarity = CardPack._roll_rarity(base_guaranteed=False, lose_multiplier=2)
            pack["cards"].append(CardPack._generate_card(rarity))
        
        return pack
    
    @staticmethod
    def _roll_rarity(base_guaranteed: bool = True, lose_multiplier: int = 1) -> str:
        """Roll for card rarity"""
        rand = random.random() * lose_multiplier
        
        if rand < 0.01:
            return "legendary"
        elif rand < 0.06:
            return "epic"
        elif rand < 0.25:
            return "rare"
        else:
            return "common"
    
    @staticmethod
    def _generate_card(rarity: str) -> Dict:
        """Generate a single card"""
        card_type = random.choice(["driver", "car"])
        
        if card_type == "driver":
            driver = random.choice(DRIVERS.get(rarity, []))
            return {
                "id": f"driver_{driver['code']}_{random.randint(1000, 9999)}",
                "type": "driver",
                "name": driver["name"],
                "code": driver["code"],
                "skill": driver["skill"],
                "team": driver["team"],
                "rarity": rarity,
                "perks": [random.choice(list(PERKS.keys()))] if random.random() < 0.3 else []
            }
        else:
            car = random.choice(CARS.get(rarity, []))
            return {
                "id": f"car_{car['team']}_{random.randint(1000, 9999)}",
                "type": "car",
                "name": car["name"],
                "team": car["team"],
                "top_speed": car["top_speed"],
                "handling": car["handling"],
                "rarity": rarity,
                "perks": [random.choice(list(PERKS.keys()))] if random.random() < 0.25 else []
            }

# ==================== CARD SYNERGIES ====================

SYNERGIES = {
    "mercedes_combo": {
        "name": "Mercedes Dominance",
        "description": "HAM in Mercedes car",
        "bonus": {"acceleration": 1.1, "handling": 1.15},
        "drivers": ["HAM"],
        "cars": ["Mercedes"]
    },
    "red_bull_combo": {
        "name": "Red Bull Supremacy",
        "description": "VER in Red Bull car",
        "bonus": {"acceleration": 1.15, "top_speed": 1.08},
        "drivers": ["VER"],
        "cars": ["Red Bull"]
    },
    "ferrari_combo": {
        "name": "Rosso Corsa",
        "description": "LEC in Ferrari car",
        "bonus": {"handling": 1.2, "acceleration": 1.12},
        "drivers": ["LEC"],
        "cars": ["Ferrari"]
    },
    "mclaren_duo": {
        "name": "Papaya Power",
        "description": "LAN in McLaren car",
        "bonus": {"consistency": 1.1, "fuel_efficiency": 1.1},
        "drivers": ["LAN"],
        "cars": ["McLaren"]
    }
}

def check_synergy(driver_code: str, car_team: str) -> Dict:
    """Check if driver and car have synergy bonus"""
    for synergy_key, synergy in SYNERGIES.items():
        if driver_code in synergy["drivers"] and car_team in synergy["cars"]:
            return synergy
    return None

# ==================== CARD RARITY EMOJIS ====================

RARITY_EMOJIS = {
    "legendary": "👑",
    "epic": "💜",
    "rare": "💙",
    "common": "⚪"
}

RARITY_COLORS = {
    "legendary": 0xFFD700,  # Gold
    "epic": 0x9370DB,       # Purple
    "rare": 0x4169E1,       # Royal Blue
    "common": 0x808080      # Gray
}

def format_card(card: Dict) -> str:
    """Format a card for display"""
    emoji = RARITY_EMOJIS.get(card["rarity"], "❓")
    
    if card["type"] == "driver":
        return f"{emoji} **{card['name']}** ({card['code']}) - {card['rarity'].title()}"
    else:
        return f"{emoji} **{card['name']}** ({card['team']}) - {card['top_speed']}km/h - {card['rarity'].title()}"
