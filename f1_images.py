"""
f1_images.py
============
Loads every card image into memory at startup so there are no file-path
issues at runtime, regardless of how or where the host launches the bot.

Images are stored as raw bytes keyed by their stem (upper-case for drivers,
slugified name for cars).  discord.File objects are built on-demand from
io.BytesIO so no file-system access is needed after startup.
"""

import os
import io
import logging
from typing import Optional, Dict, Tuple

import discord

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal store:  key -> (original_filename, raw_bytes)
# ---------------------------------------------------------------------------
# Driver card art:   key = "ALB", "VER", …
# Driver spawn art:  key = "spawn:ALB", "spawn:VER", …
# Car card art:      key = "car:Williams_FW45", …  (slugified name)
# Car spawn art:     key = "spawn_car:Williams_FW45", …
# ---------------------------------------------------------------------------

_store: Dict[str, Tuple[str, bytes]] = {}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_HERE = os.path.dirname(os.path.abspath(__file__))


def _slugify(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_").replace("+", "plus")


def _load_dir(directory: str, key_prefix: str, stem_transform=str.upper) -> int:
    """Load all images in *directory* into _store.  Returns count loaded."""
    if not os.path.isdir(directory):
        return 0
    count = 0
    for fname in os.listdir(directory):
        stem, ext = os.path.splitext(fname)
        if ext.lower() not in _IMAGE_EXTS:
            continue
        path = os.path.join(directory, fname)
        try:
            with open(path, "rb") as f:
                raw = f.read()
            key = key_prefix + stem_transform(stem)
            _store[key] = (fname, raw)
            count += 1
        except Exception as e:
            log.warning("Could not load image %s: %s", path, e)
    return count


def _load_all():
    """Called once at import time to fill _store."""
    base = os.path.join(_HERE, "card_images")

    print(f"[f1_images] Looking for card_images at: {base}")
    print(f"[f1_images] card_images/ exists: {os.path.isdir(base)}")

    if os.path.isdir(base):
        contents = os.listdir(base)
        print(f"[f1_images] card_images/ contents: {contents}")
        cars_dir = os.path.join(base, "cars")
        print(f"[f1_images] card_images/cars/ exists: {os.path.isdir(cars_dir)}")
        if os.path.isdir(cars_dir):
            print(f"[f1_images] card_images/cars/ contents: {os.listdir(cars_dir)}")

    # Driver card art  (key = "ALB", "VER", …)
    n = _load_dir(base, "", str.upper)
    print(f"[f1_images] Driver images loaded: {n}")

    # Car card art  (key = "car:Williams_FW45", …)
    # Primary: card_images/cars/ subdirectory
    cars_subdir = os.path.join(base, "cars")
    car_count = _load_dir(cars_subdir, "car:", _slugify)
    # Fallback: some hosting setups extract zips flat — also scan card_images/ root
    # for files whose names look like car names (contain underscore patterns of known cars)
    if car_count == 0:
        print("[f1_images] No cars/ subfolder found — scanning card_images/ root for car images")
        _CAR_PREFIXES = (
            "Alfa", "Alpha", "Alpine", "Aston", "Ferrari", "Haas",
            "McLaren", "Mercedes", "Red_Bull", "Williams", "Red Bull",
        )
        for fname in os.listdir(base) if os.path.isdir(base) else []:
            stem, ext = os.path.splitext(fname)
            if ext.lower() not in _IMAGE_EXTS:
                continue
            if any(stem.startswith(p) or stem.replace("_", " ").startswith(p) for p in _CAR_PREFIXES):
                path = os.path.join(base, fname)
                try:
                    with open(path, "rb") as f:
                        raw = f.read()
                    key = "car:" + _slugify(stem)
                    _store[key] = (fname, raw)
                    car_count += 1
                except Exception as e:
                    log.warning("Could not load car image %s: %s", path, e)
    n += car_count
    print(f"[f1_images] Car images loaded: {car_count}")

    # Spawn driver art  (key = "spawn:ALB", …)
    spawn_count = _load_dir(os.path.join(base, "spawn"), "spawn:", str.upper)
    n += spawn_count
    print(f"[f1_images] Spawn images loaded: {spawn_count}")

    # Spawn car art  (key = "spawn_car:car_Williams_FW45", …)
    # Saved by addcar as  card_images/spawn/car_{slug}.ext
    # We re-map those to  "spawn_car:{slug}"
    spawn_dir = os.path.join(base, "spawn")
    if os.path.isdir(spawn_dir):
        for fname in os.listdir(spawn_dir):
            stem, ext = os.path.splitext(fname)
            if ext.lower() not in _IMAGE_EXTS:
                continue
            if not stem.startswith("car_"):
                continue
            slug = stem[4:]   # strip leading "car_"
            path = os.path.join(spawn_dir, fname)
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                key = "spawn_car:" + slug
                _store[key] = (fname, raw)
            except Exception as e:
                log.warning("Could not load spawn car image %s: %s", path, e)

    print(f"[f1_images] ✅ Total images in memory: {len(_store)}")
    log.info("f1_images: loaded %d card images into memory", len(_store))
    if n == 0:
        print(f"[f1_images] ❌ NO images loaded — card_images/ not found or empty at {base}")
        log.warning(
            "f1_images: NO images loaded — card_images/ not found at %s", base
        )


_load_all()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _make_file(key: str, filename_override: Optional[str] = None) -> Optional[discord.File]:
    entry = _store.get(key)
    if not entry:
        return None
    fname, raw = entry
    return discord.File(io.BytesIO(raw), filename=filename_override or fname)


def get_driver_card_file(code: str) -> Optional[discord.File]:
    """Card-art file for a driver (shown in collection / packs)."""
    if not code:
        return None
    return _make_file(code.strip().upper())


def get_driver_spawn_file(code: str) -> Optional[discord.File]:
    """Spawn-photo file for a driver; falls back to card art."""
    if not code:
        return None
    code = code.strip().upper()
    f = _make_file("spawn:" + code, filename_override=f"spawn_{code}.png")
    return f or _make_file(code)


def get_car_card_file(name: str) -> Optional[discord.File]:
    """Card-art file for a car."""
    if not name:
        return None
    slug = _slugify(name)
    # Try exact slug first, then fuzzy match
    key = "car:" + slug
    if key in _store:
        return _make_file(key)
    name_lower = name.lower()
    for k, (fname, _) in _store.items():
        if not k.startswith("car:"):
            continue
        k_name = k[4:].replace("_", " ").lower()
        if k_name in name_lower or name_lower in k_name:
            return _make_file(k)
    return None


def get_car_spawn_file(name: str) -> Optional[discord.File]:
    """Spawn-photo file for a car; falls back to card art."""
    if not name:
        return None
    slug = _slugify(name)
    key = "spawn_car:" + slug
    f = _make_file(key, filename_override=f"spawn_car_{slug}.png")
    return f or get_car_card_file(name)


def get_card_file(card: dict) -> Optional[discord.File]:
    """Card-art file for any card type."""
    ctype = card.get("type")
    if ctype == "driver":
        return get_driver_card_file(card.get("code", ""))
    elif ctype == "car":
        return get_car_card_file(card.get("name", ""))
    return None


def get_spawn_file(card: dict) -> Optional[discord.File]:
    """Spawn-photo file for any card type (spawn folder first, card art fallback)."""
    ctype = card.get("type")
    if ctype == "driver":
        return get_driver_spawn_file(card.get("code", ""))
    elif ctype == "car":
        return get_car_spawn_file(card.get("name", ""))
    return None


def reload():
    """Re-scan card_images/ at runtime (e.g. after uploading new images via /config)."""
    _store.clear()
    _load_all()


# Legacy aliases kept so existing bot.py calls still work
def get_local_card_path(card: dict):
    return None  # no longer used — use get_card_file() instead

def get_local_spawn_path(card: dict):
    return None

def get_card_art_path(card: dict):
    return None

def get_card_image(card: dict):
    return None
