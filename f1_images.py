import os
from typing import Optional

# Anchor to the directory that contains this file so paths work correctly
# regardless of where the hosting service sets the working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))

CARD_IMAGES_DIR = os.path.join(_HERE, "card_images")
CARS_DIR = os.path.join(CARD_IMAGES_DIR, "cars")
SPAWN_DIR = os.path.join(CARD_IMAGES_DIR, "spawn")

_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp"]


def get_local_driver_path(code: str) -> Optional[str]:
    """Find a driver card-art image by code — scans card_images/ automatically."""
    if not code:
        return None
    code = code.strip().upper()
    for ext in _IMAGE_EXTS:
        path = os.path.join(CARD_IMAGES_DIR, f"{code}{ext}")
        if os.path.exists(path):
            return path
    return None


def get_local_spawn_driver_path(code: str) -> Optional[str]:
    """Find a driver spawn photo — checks card_images/spawn/ first, falls back to card art."""
    if not code:
        return None
    code = code.strip().upper()
    for ext in _IMAGE_EXTS:
        path = os.path.join(SPAWN_DIR, f"{code}{ext}")
        if os.path.exists(path):
            return path
    return get_local_driver_path(code)


def get_local_car_path(name: str) -> Optional[str]:
    """Find a car card-art image by name — checks cars/ subdirectory first, then root."""
    if not name:
        return None
    slug = (
        name.replace(" ", "_")
            .replace("-", "_")
            .replace("+", "plus")
    )
    for search_dir in [CARS_DIR, CARD_IMAGES_DIR]:
        for ext in _IMAGE_EXTS:
            path = os.path.join(search_dir, f"{slug}{ext}")
            if os.path.exists(path):
                return path

    name_lower = name.lower()
    for search_dir in [CARS_DIR, CARD_IMAGES_DIR]:
        if not os.path.isdir(search_dir):
            continue
        for fname in os.listdir(search_dir):
            stem = os.path.splitext(fname)[0].lower().replace("_", " ").replace("plus", "+")
            if stem in name_lower or name_lower in stem:
                path = os.path.join(search_dir, fname)
                if os.path.exists(path):
                    return path
    return None


def get_local_spawn_car_path(name: str) -> Optional[str]:
    """Find a car spawn photo — checks card_images/spawn/car_* first, falls back to card art."""
    if not name:
        return None
    slug = name.replace(" ", "_").replace("-", "_").replace("+", "plus")
    for ext in _IMAGE_EXTS:
        path = os.path.join(SPAWN_DIR, f"car_{slug}{ext}")
        if os.path.exists(path):
            return path
    return get_local_car_path(name)


def get_local_card_path(card: dict) -> Optional[str]:
    """Return the local card-art file path for any card type."""
    ctype = card.get("type")
    if ctype == "driver":
        return get_local_driver_path(card.get("code", ""))
    elif ctype == "car":
        return get_local_car_path(card.get("name", ""))
    return None


def get_local_spawn_path(card: dict) -> Optional[str]:
    """Return the local spawn-photo path (spawn/ folder first, falls back to card art)."""
    ctype = card.get("type")
    if ctype == "driver":
        return get_local_spawn_driver_path(card.get("code", ""))
    elif ctype == "car":
        return get_local_spawn_car_path(card.get("name", ""))
    return None


# Legacy aliases
def get_card_art_path(card: dict) -> Optional[str]:
    return get_local_card_path(card)

def get_card_image(card: dict) -> Optional[str]:
    return None  # All images served as local file attachments
