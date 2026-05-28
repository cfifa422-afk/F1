import os
from typing import Dict, Optional

# ==================== LOCAL IMAGE PATHS ====================
# All images stored locally to avoid Wikimedia hotlink blocking in Discord.

DRIVER_LOCAL: Dict[str, str] = {
    # Custom card art (PNG)
    "ZHO": "card_images/ZHO.png",
    "SAR": "card_images/SAR.png",
    "ALB": "card_images/ALB.png",
    "VER": "card_images/VER.png",
    "GRO": "card_images/GRO.png",
    "MAG": "card_images/MAG.png",
    "SAI": "card_images/SAI.png",
    # Downloaded photos (JPG)
    "HAM": "card_images/HAM.jpg",
    "NOR": "card_images/NOR.jpg",
    "LEC": "card_images/LEC.jpg",
    "RUS": "card_images/RUS.jpg",
    "ALO": "card_images/ALO.jpg",
    "PIA": "card_images/PIA.jpg",
    "TSU": "card_images/TSU.jpg",
    "GAS": "card_images/GAS.png",
    "OCO": "card_images/OCO.jpg",
    "BOT": "card_images/BOT.jpg",
    "STR": "card_images/STR.jpg",
    "HUL": "card_images/HUL.jpg",
    "PER": "card_images/PER.jpg",
    "WEB": "card_images/WEB.jpg",
    "SEN": "card_images/SEN.jpg",
    "MSC": "card_images/MSC.jpg",
    "PRO": "card_images/PRO.jpg",
    "NIK": "card_images/NIK.jpg",
    "FAN": "card_images/FAN.jpg",
    "CLK": "card_images/CLK.jpg",
    "MAN": "card_images/MAN.jpg",
    "HIL": "card_images/HIL.jpg",
    "ROS": "card_images/ROS.jpg",
    "BUT": "card_images/BUT.jpg",
    "RAI": "card_images/RAI.jpg",
}

CAR_LOCAL: Dict[str, str] = {
    "Red Bull RB19":      "card_images/cars/Red_Bull_RB19.jpg",
    "Red Bull RB18":      "card_images/cars/Red_Bull_RB18.jpg",
    "Ferrari SF-23":      "card_images/cars/Ferrari_SF_23.jpg",
    "Ferrari SF-23+":     "card_images/cars/Ferrari_SF_23plus.jpg",
    "Ferrari F1-75":      "card_images/cars/Ferrari_F1_75.jpg",
    "Ferrari F1-75+":     "card_images/cars/Ferrari_F1_75plus.jpg",
    "McLaren MCL60":      "card_images/cars/McLaren_MCL60.jpg",
    "McLaren MCL60S":     "card_images/cars/McLaren_MCL60S.jpg",
    "McLaren MCL36":      "card_images/cars/McLaren_MCL36.jpg",
    "Aston Martin AMR23": "card_images/cars/Aston_Martin_AMR23.jpg",
    "Aston Martin AMR22": "card_images/cars/Aston_Martin_AMR22.jpg",
    "Alpine A523":        "card_images/cars/Alpine_A523.jpg",
    "Alpine A522":        "card_images/cars/Alpine_A522.jpg",
    "Mercedes AMG W14":   "card_images/cars/Mercedes_AMG_W14.jpg",
    "Mercedes AMG W13":   "card_images/cars/Mercedes_AMG_W13.jpg",
    "Williams FW45":      "card_images/cars/Williams_FW45.jpg",
    "Williams FW44":      "card_images/cars/Williams_FW44.jpg",
    "AlphaTauri AT04":    "card_images/cars/AlphaTauri_AT04.jpg",
    "Haas VF-23":         "card_images/cars/Haas_VF_23.jpg",
    "Alfa Romeo C43":     "card_images/cars/Alfa_Romeo_C43.jpg",
}


def get_local_driver_path(code: str) -> Optional[str]:
    path = DRIVER_LOCAL.get(code)
    if path and os.path.exists(path):
        return path
    return None


def get_local_car_path(name: str) -> Optional[str]:
    path = CAR_LOCAL.get(name)
    if path and os.path.exists(path):
        return path
    # Fuzzy match
    name_lower = name.lower()
    for car_name, p in CAR_LOCAL.items():
        if car_name.lower() in name_lower or name_lower in car_name.lower():
            if os.path.exists(p):
                return p
    return None


def get_local_card_path(card: dict) -> Optional[str]:
    """Return the local file path for any card type, or None if unavailable."""
    ctype = card.get("type")
    if ctype == "driver":
        return get_local_driver_path(card.get("code", ""))
    elif ctype == "car":
        return get_local_car_path(card.get("name", ""))
    return None


# ==================== LEGACY ALIASES ====================
# Kept for any code that still references these names.

DRIVER_CARD_ART = DRIVER_LOCAL

def get_card_art_path(card: dict) -> Optional[str]:
    return get_local_card_path(card)

def get_card_image(card: dict) -> Optional[str]:
    return None  # All images now served as local file attachments
