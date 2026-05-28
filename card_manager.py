"""
Custom Card Manager
===================
Handles adding / removing / listing custom cards that live outside the
hardcoded card pools in cards.py.  Data is persisted in custom_cards.json.

Usage (from bot commands):
    import card_manager as cm
    cm.add_driver("Andrea Antonelli", "ANT", 7.5, "Mercedes", "rare")
    cm.add_car("Williams FW47", "Williams", 355, 7.0, "rare")
    cm.remove_driver("ANT")
    data = cm.list_all()
"""

import json
import os
from typing import Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM_CARDS_FILE = os.path.join(_HERE, "custom_cards.json")


def _load() -> Dict:
    if os.path.exists(CUSTOM_CARDS_FILE):
        try:
            with open(CUSTOM_CARDS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"drivers": [], "cars": []}


def _save(data: Dict) -> None:
    with open(CUSTOM_CARDS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_drivers_by_rarity(rarity: str) -> List[Dict]:
    """Return custom driver pool entries for the given rarity."""
    return [d for d in _load().get("drivers", []) if d.get("rarity") == rarity]


def get_cars_by_rarity(rarity: str) -> List[Dict]:
    """Return custom car pool entries for the given rarity."""
    return [c for c in _load().get("cars", []) if c.get("rarity") == rarity]


def add_driver(name: str, code: str, skill: float, team: str, rarity: str) -> Dict:
    """Add (or replace) a custom driver.  Returns the saved entry."""
    data = _load()
    data["drivers"] = [d for d in data["drivers"] if d.get("code", "").upper() != code.upper()]
    entry = {
        "name": name,
        "code": code.upper(),
        "skill": round(float(skill), 1),
        "team": team,
        "rarity": rarity.lower(),
    }
    data["drivers"].append(entry)
    _save(data)
    return entry


def add_car(name: str, team: str, top_speed: int, handling: float, rarity: str) -> Dict:
    """Add (or replace) a custom car.  Returns the saved entry."""
    data = _load()
    data["cars"] = [c for c in data["cars"] if c.get("name", "").lower() != name.lower()]
    entry = {
        "name": name,
        "team": team,
        "top_speed": int(top_speed),
        "handling": round(float(handling), 1),
        "rarity": rarity.lower(),
    }
    data["cars"].append(entry)
    _save(data)
    return entry


def remove_driver(code: str) -> bool:
    """Remove a custom driver by code.  Returns True if found and removed."""
    data = _load()
    before = len(data["drivers"])
    data["drivers"] = [d for d in data["drivers"] if d.get("code", "").upper() != code.upper()]
    if len(data["drivers"]) < before:
        _save(data)
        return True
    return False


def remove_car(name: str) -> bool:
    """Remove a custom car by name.  Returns True if found and removed."""
    data = _load()
    before = len(data["cars"])
    data["cars"] = [c for c in data["cars"] if c.get("name", "").lower() != name.lower()]
    if len(data["cars"]) < before:
        _save(data)
        return True
    return False


def list_all() -> Dict:
    """Return the full custom_cards.json dict."""
    return _load()
