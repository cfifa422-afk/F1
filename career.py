"""
career.py — F1 Career Mode System
All career logic, embeds, views, and race engine.
"""

import discord
import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import cards as card_module

# ═══════════════════════════════════════════════════════════
#  CONSTANTS — SEASON / SCHEDULE
# ═══════════════════════════════════════════════════════════

CAREER_GIF_URL = "https://media.giphy.com/media/3oEjHI5PcHULCJkx0c/giphy.gif"
TOTAL_MATCHES  = 24
DAILY_LIMIT    = 2
COOLDOWN_HOURS = 14

CAREER_TRACKS: List[Dict] = [
    {"num": 1,  "name": "Bahrain GP",           "circuit": "Bahrain International Circuit",   "flag": "🇧🇭", "type": "High Speed",           "difficulty": "easy"},
    {"num": 2,  "name": "Italian GP",            "circuit": "Monza",                           "flag": "🇮🇹", "type": "Power Track",           "difficulty": "easy"},
    {"num": 3,  "name": "Belgian GP",            "circuit": "Spa-Francorchamps",               "flag": "🇧🇪", "type": "Mixed Layout",          "difficulty": "easy"},
    {"num": 4,  "name": "British GP",            "circuit": "Silverstone",                     "flag": "🇬🇧", "type": "High Speed",            "difficulty": "easy"},
    {"num": 5,  "name": "Canadian GP",           "circuit": "Circuit Gilles Villeneuve",       "flag": "🇨🇦", "type": "Street Circuit",        "difficulty": "easy"},
    {"num": 6,  "name": "Spanish GP",            "circuit": "Circuit de Barcelona-Catalunya",  "flag": "🇪🇸", "type": "Technical",             "difficulty": "medium"},
    {"num": 7,  "name": "Austrian GP",           "circuit": "Red Bull Ring",                   "flag": "🇦🇹", "type": "Short Circuit",         "difficulty": "medium"},
    {"num": 8,  "name": "Dutch GP",              "circuit": "Circuit Zandvoort",               "flag": "🇳🇱", "type": "Banked Corners",        "difficulty": "medium"},
    {"num": 9,  "name": "Hungarian GP",          "circuit": "Hungaroring",                     "flag": "🇭🇺", "type": "Tight & Twisty",        "difficulty": "medium"},
    {"num": 10, "name": "Australian GP",         "circuit": "Albert Park",                     "flag": "🇦🇺", "type": "Street Circuit",        "difficulty": "medium"},
    {"num": 11, "name": "Japanese GP",           "circuit": "Suzuka",                          "flag": "🇯🇵", "type": "Technical",             "difficulty": "hard"},
    {"num": 12, "name": "Singapore GP",          "circuit": "Marina Bay Street Circuit",       "flag": "🇸🇬", "type": "Night Street Race",     "difficulty": "hard"},
    {"num": 13, "name": "US GP",                 "circuit": "Circuit of the Americas",         "flag": "🇺🇸", "type": "High Speed",            "difficulty": "hard"},
    {"num": 14, "name": "Mexican GP",            "circuit": "Autódromo Hermanos Rodríguez",    "flag": "🇲🇽", "type": "Altitude Track",        "difficulty": "hard"},
    {"num": 15, "name": "Brazilian GP",          "circuit": "Interlagos",                      "flag": "🇧🇷", "type": "Undulating Layout",     "difficulty": "hard"},
    {"num": 16, "name": "Las Vegas GP",          "circuit": "Las Vegas Strip Circuit",         "flag": "🌃",  "type": "Night Street Race",     "difficulty": "hard"},
    {"num": 17, "name": "Qatar GP",              "circuit": "Lusail International Circuit",    "flag": "🇶🇦", "type": "High Speed",            "difficulty": "hard"},
    {"num": 18, "name": "Abu Dhabi GP",          "circuit": "Yas Marina Circuit",              "flag": "🇦🇪", "type": "Mixed Layout",          "difficulty": "peak"},
    {"num": 19, "name": "Saudi Arabian GP",      "circuit": "Jeddah Corniche Circuit",         "flag": "🇸🇦", "type": "Ultra High Speed",      "difficulty": "peak"},
    {"num": 20, "name": "Miami GP",              "circuit": "Miami International Autodrome",   "flag": "🇺🇸", "type": "Street Circuit",        "difficulty": "peak"},
    {"num": 21, "name": "Emilia Romagna GP",     "circuit": "Autodromo Enzo e Dino Ferrari",   "flag": "🇮🇹", "type": "Classic Circuit",       "difficulty": "peak"},
    {"num": 22, "name": "Monaco GP",             "circuit": "Circuit de Monaco",               "flag": "🇲🇨", "type": "Legendary Street Race", "difficulty": "peak"},
    {"num": 23, "name": "Azerbaijan GP",         "circuit": "Baku City Circuit",               "flag": "🇦🇿", "type": "Ultra High Speed",      "difficulty": "peak"},
    {"num": 24, "name": "F1 World Championship", "circuit": "Shanghai International Circuit",  "flag": "🏆",  "type": "Season Finale",         "difficulty": "peak"},
]

NPC_POOLS: Dict[str, List[Dict]] = {
    "easy": [
        {"name": "Lance Stroll",     "team": "Aston Martin", "skill": 6.5, "speed": 340},
        {"name": "Alex Albon",       "team": "Williams",     "skill": 6.8, "speed": 345},
        {"name": "Logan Sargeant",   "team": "Williams",     "skill": 6.1, "speed": 338},
        {"name": "Nico Hulkenberg",  "team": "Kick Sauber",  "skill": 6.9, "speed": 348},
        {"name": "Jack Doohan",      "team": "Alpine",       "skill": 6.6, "speed": 342},
        {"name": "Zhou Guanyu",      "team": "Kick Sauber",  "skill": 6.4, "speed": 336},
        {"name": "Isack Hadjar",     "team": "RB",           "skill": 6.7, "speed": 346},
        {"name": "Franco Colapinto", "team": "Alpine",       "skill": 6.8, "speed": 344},
        {"name": "Test Driver A",    "team": "Williams",     "skill": 5.8, "speed": 330},
        {"name": "Test Driver B",    "team": "Haas",         "skill": 5.6, "speed": 328},
        {"name": "Reserve Driver",   "team": "Alpine",       "skill": 6.2, "speed": 338},
        {"name": "Academy Driver",   "team": "Mercedes",     "skill": 5.9, "speed": 332},
        {"name": "Kevin Magnussen",  "team": "Haas",         "skill": 7.0, "speed": 350},
        {"name": "Esteban Ocon",     "team": "Haas",         "skill": 7.1, "speed": 352},
        {"name": "Valtteri Bottas",  "team": "Kick Sauber",  "skill": 7.4, "speed": 355},
    ],
    "medium": [
        {"name": "Yuki Tsunoda",      "team": "RB",           "skill": 7.2, "speed": 362},
        {"name": "Pierre Gasly",      "team": "Alpine",       "skill": 7.3, "speed": 364},
        {"name": "Esteban Ocon",      "team": "Haas",         "skill": 7.1, "speed": 358},
        {"name": "Valtteri Bottas",   "team": "Kick Sauber",  "skill": 7.4, "speed": 366},
        {"name": "Kevin Magnussen",   "team": "Haas",         "skill": 7.0, "speed": 356},
        {"name": "Sergio Perez",      "team": "Red Bull",     "skill": 7.6, "speed": 370},
        {"name": "Mark Webber",       "team": "Red Bull",     "skill": 7.8, "speed": 374},
        {"name": "Kimi Antonelli",    "team": "Mercedes",     "skill": 7.4, "speed": 368},
        {"name": "Oliver Bearman",    "team": "Haas",         "skill": 7.3, "speed": 362},
        {"name": "Gabriel Bortoleto", "team": "Kick Sauber",  "skill": 7.5, "speed": 368},
        {"name": "Liam Lawson",       "team": "Red Bull",     "skill": 7.6, "speed": 370},
        {"name": "Felipe Drugovich",  "team": "Aston Martin", "skill": 6.9, "speed": 354},
        {"name": "Oscar Piastri",     "team": "McLaren",      "skill": 7.8, "speed": 375},
        {"name": "Carlos Sainz",      "team": "Williams",     "skill": 7.9, "speed": 378},
        {"name": "Fernando Alonso",   "team": "Aston Martin", "skill": 8.0, "speed": 380},
    ],
    "hard": [
        {"name": "Oscar Piastri",    "team": "McLaren",      "skill": 7.8, "speed": 382},
        {"name": "Carlos Sainz",     "team": "Williams",     "skill": 7.9, "speed": 385},
        {"name": "Fernando Alonso",  "team": "Aston Martin", "skill": 8.0, "speed": 388},
        {"name": "George Russell",   "team": "Mercedes",     "skill": 8.1, "speed": 390},
        {"name": "Nico Rosberg",     "team": "Mercedes",     "skill": 8.0, "speed": 386},
        {"name": "Jenson Button",    "team": "Brawn GP",     "skill": 7.9, "speed": 382},
        {"name": "Kimi Raikkonen",   "team": "Ferrari",      "skill": 8.3, "speed": 392},
        {"name": "Charles Leclerc",  "team": "Ferrari",      "skill": 8.3, "speed": 394},
        {"name": "Damon Hill",       "team": "Williams",     "skill": 8.2, "speed": 390},
        {"name": "Nigel Mansell",    "team": "Williams",     "skill": 8.4, "speed": 394},
        {"name": "Jim Clark",        "team": "Lotus",        "skill": 8.9, "speed": 400},
        {"name": "Lando Norris",     "team": "McLaren",      "skill": 8.7, "speed": 398},
        {"name": "Sebastian Vettel", "team": "Aston Martin", "skill": 9.0, "speed": 404},
        {"name": "Niki Lauda",       "team": "Ferrari",      "skill": 9.0, "speed": 402},
        {"name": "Alain Prost",      "team": "McLaren",      "skill": 9.1, "speed": 406},
    ],
    "peak": [
        {"name": "Lewis Hamilton",     "team": "Ferrari",      "skill": 8.8, "speed": 408},
        {"name": "Max Verstappen",     "team": "Red Bull",     "skill": 9.2, "speed": 412},
        {"name": "Ayrton Senna",       "team": "McLaren",      "skill": 9.5, "speed": 415},
        {"name": "Michael Schumacher", "team": "Ferrari",      "skill": 9.4, "speed": 414},
        {"name": "Alain Prost",        "team": "McLaren",      "skill": 9.1, "speed": 410},
        {"name": "Niki Lauda",         "team": "Ferrari",      "skill": 9.0, "speed": 408},
        {"name": "Juan Manuel Fangio", "team": "Mercedes",     "skill": 9.6, "speed": 416},
        {"name": "Sebastian Vettel",   "team": "Aston Martin", "skill": 9.0, "speed": 408},
        {"name": "Jim Clark",          "team": "Lotus",        "skill": 8.9, "speed": 406},
        {"name": "Lando Norris",       "team": "McLaren",      "skill": 8.7, "speed": 404},
        {"name": "Charles Leclerc",    "team": "Ferrari",      "skill": 8.3, "speed": 400},
        {"name": "George Russell",     "team": "Mercedes",     "skill": 8.1, "speed": 398},
        {"name": "Kimi Raikkonen",     "team": "Ferrari",      "skill": 8.3, "speed": 400},
        {"name": "Nigel Mansell",      "team": "Williams",     "skill": 8.4, "speed": 400},
        {"name": "Fernando Alonso",    "team": "Aston Martin", "skill": 8.0, "speed": 396},
    ],
}

DIFF_META = {
    "easy":   {"label": "Easy",      "emoji": "🟢", "color": 0x00b894, "rec_speed": 350, "rec_skill": 6.5},
    "medium": {"label": "Medium",    "emoji": "🟡", "color": 0xfdcb6e, "rec_speed": 375, "rec_skill": 7.5},
    "hard":   {"label": "Hard",      "emoji": "🔴", "color": 0xe17055, "rec_speed": 395, "rec_skill": 8.0},
    "peak":   {"label": "Elite ⚠️",  "emoji": "🔱", "color": 0x6c5ce7, "rec_speed": 410, "rec_skill": 9.0},
}

CAREER_PTS  = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
RACE_PAYOUT = {1: 500, 2: 420, 3: 350, 4: 280, 5: 220, 6: 160, 7: 110, 8: 70, 9: 40, 10: 20}
POS_EMOJIS  = {1: "🥇", 2: "🥈", 3: "🥉"}

CAREER_SPECIAL_CARDS = {
    1: {"id": "career_world_champion", "name": "World Champion", "code": "CHM",
        "skill": 10.0, "team": "F1 Career", "rarity": "mythic",
        "type": "driver", "perks": ["consistency", "drs_specialist"]},
    2: {"id": "career_contender",      "name": "Championship Contender", "code": "CTD",
        "skill": 9.7,  "team": "F1 Career", "rarity": "legendary",
        "type": "driver", "perks": ["rain_master"]},
    3: {"id": "career_podium_driver",  "name": "Grand Prix Podium", "code": "POD",
        "skill": 9.4,  "team": "F1 Career", "rarity": "legendary",
        "type": "driver", "perks": ["tire_master"]},
}

# ═══════════════════════════════════════════════════════════
#  RACE ENGINE CONSTANTS  (mirrors normal race)
# ═══════════════════════════════════════════════════════════

RACE_GIFS = [
    "https://media.giphy.com/media/3ohzdIuqJoo8QdKlnW/giphy.gif",
    "https://media.giphy.com/media/26gJAn0QqFWbqQUMw/giphy.gif",
    "https://media.giphy.com/media/l0MYyoYKBIRtjXJEQ/giphy.gif",
    "https://media.giphy.com/media/xT1Ra5h24Eliux3UVq/giphy.gif",
]

CAREER_LAPS   = 3
CAREER_TURNS  = 12   # 4 turns per lap

# Turns 3,6,9,11 → tactical decisions  |  1,2,4,5,7,8,10 → reaction challenges
SCENARIO_TURNS  = {3, 6, 9, 11}
REACTION_TURNS  = [1, 2, 4, 5, 7, 8, 10]

CAREER_SCENARIOS: Dict[int, Dict] = {
    3: {
        "id":    "pit_window",
        "title": "🛑  Pit Window Open!",
        "description": (
            "**Lap 1 complete.** The optimal pit window has arrived — fresh rubber could be decisive, "
            "but staying out preserves precious track position."
        ),
        "question": "Do you pit for fresh tyres, or push on?",
        "options": [
            {"label": "⛽ Pit Now",   "value": "pit_stop",   "style": discord.ButtonStyle.danger},
            {"label": "🏎️ Stay Out", "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
    6: {
        "id":    "drs_attack",
        "title": "💨  DRS Zone — Attack or Manage!",
        "description": (
            "**Mid-race.** Both cars enter the longest DRS activation zone on the circuit. "
            "The gap is close enough for a real overtaking move — but pushing flat out burns rubber."
        ),
        "question": "Go flat out through the DRS zone, or conserve tyres for the final laps?",
        "options": [
            {"label": "🔥 Maximum Attack",   "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Conserve & Cover", "value": "slow_down",  "style": discord.ButtonStyle.secondary},
        ],
    },
    9: {
        "id":    "late_strategy",
        "title": "🚗  Late Race Strategy Call!",
        "description": (
            "**Final third.** Tyre wear is becoming critical and fuel loads are dropping fast. "
            "The race is still in the balance — every call from here is season-defining."
        ),
        "question": "Push hard for the gap, manage to the flag, or gamble on an emergency stop?",
        "options": [
            {"label": "🔥 Push Hard",      "value": "accelerate", "style": discord.ButtonStyle.success},
            {"label": "⏱️ Manage Tyres",  "value": "slow_down",  "style": discord.ButtonStyle.secondary},
            {"label": "⛽ Emergency Pit",  "value": "pit_stop",   "style": discord.ButtonStyle.danger},
        ],
    },
    11: {
        "id":    "final_lap",
        "title": "🏁  FINAL LAP — Last Call!",
        "description": (
            "**The white flag is out.** This is it — the last lap of the race. "
            "Everything you've built throughout this race comes down to the next few corners."
        ),
        "question": "Absolute maximum attack, or protect what you have?",
        "options": [
            {"label": "🔥 FLAT OUT!",        "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Protect the Gap", "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
}

RAIN_SCENARIO_OVERRIDE = {
    "id":    "rain_call",
    "title": "🌧️  RAIN! Weather Gamble!",
    "description": (
        "**Rain is falling on the circuit!** Slick tyres are becoming dangerously unpredictable "
        "lap by lap. Box for wet tyres and surrender track position, or gamble on the drying line?"
    ),
    "question": "Make the call — box for wets or stay on slicks?",
    "options": [
        {"label": "🌧️ Box for Wets",   "value": "pit_stop",   "style": discord.ButtonStyle.primary},
        {"label": "🎰 Stay on Slicks", "value": "same_speed", "style": discord.ButtonStyle.danger},
    ],
}

REACTION_DIRECTIONS = ["left", "right", "up", "down"]
REACTION_LABELS = {
    "left":  "◀  LEFT",
    "right": "RIGHT  ▶",
    "up":    "▲  UP",
    "down":  "▼  DOWN",
}

# ═══════════════════════════════════════════════════════════
#  RACE STATE
# ═══════════════════════════════════════════════════════════

class CareerRaceState:
    def __init__(self):
        self.lap:            int   = 1
        self.turn:           int   = 0
        self.total_laps:     int   = CAREER_LAPS
        self.max_turns:      int   = CAREER_TURNS
        self.fuel:           float = 100.0
        self.tire_wear:      float = 0.0
        self.tire_type:      str   = "medium"
        self.pit_stops:      int   = 0
        self.weather:        str   = "dry"
        self.choice_history: List[str] = []
        self.score_adj:      float = 0.0  # accumulated score bonus/penalty

# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def get_track(match_num: int) -> Dict:
    return CAREER_TRACKS[match_num - 1]

def get_race_npcs(match_num: int, count: int = 15) -> List[Dict]:
    diff = get_track(match_num)["difficulty"]
    pool = NPC_POOLS[diff].copy()
    random.shuffle(pool)
    return pool[:count]

def calc_upgrade_bonus(upgrades: Dict) -> float:
    return (
        upgrades.get("engine", 0) * 2.0 +
        upgrades.get("acceleration", 0) * 2.0 +
        upgrades.get("aero", 0) * 1.0 +
        upgrades.get("brakes", 0) * 0.5 +
        upgrades.get("suspension", 0) * 0.5
    )

def calc_player_score(car_speed: int, driver_skill: float,
                      upgrades: Dict, qte_hits: int, pit_hits: int) -> float:
    base    = car_speed + driver_skill * 10
    bonuses = calc_upgrade_bonus(upgrades) + qte_hits * 3.0 + pit_hits * 3.0
    return base + bonuses + random.uniform(-12, 12)

def calc_npc_score(npc: Dict) -> float:
    return npc["speed"] + npc["skill"] * 10 + random.uniform(-15, 15)

def build_standings(player_score: float, player_label: str, npcs: List[Dict]) -> List[Dict]:
    entries = [{"label": player_label, "score": player_score, "is_player": True, "team": "You"}]
    for npc in npcs:
        entries.append({
            "label":     npc["name"],
            "score":     calc_npc_score(npc),
            "is_player": False,
            "team":      npc["team"],
        })
    entries.sort(key=lambda x: x["score"], reverse=True)
    leader = entries[0]["score"]
    for i, e in enumerate(entries):
        e["position"] = i + 1
        e["gap_s"]    = (leader - e["score"]) * 0.15
    return entries

def can_play(career: Dict) -> Tuple[bool, str]:
    if career.get("matches_completed", 0) >= TOTAL_MATCHES:
        return False, "season_done"
    today = datetime.now().date().isoformat()
    used  = career.get("daily_used", 0) if career.get("daily_reset_date") == today else 0
    if used >= DAILY_LIMIT:
        last_at = career.get("last_match_at")
        if last_at:
            unlock = datetime.fromisoformat(last_at) + timedelta(hours=COOLDOWN_HOURS)
            if datetime.now() < unlock:
                secs = int((unlock - datetime.now()).total_seconds())
                return False, f"cooldown:{secs}"
    return True, "ok"

def next_unlock_timestamp(career: Dict) -> Optional[int]:
    last_at = career.get("last_match_at")
    if not last_at:
        return None
    dt = datetime.fromisoformat(last_at) + timedelta(hours=COOLDOWN_HOURS)
    return int(dt.timestamp())

def fmt_secs(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, s2  = divmod(rem, 60)
    return f"{h}h {m}m" if h else f"{m}m {s2}s"

def _bar(value: float, max_val: float = 100.0, length: int = 10) -> str:
    ratio  = max(0.0, min(1.0, value / max_val))
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)

def _fuel_str(fuel: float) -> str:
    icon = "🟢" if fuel > 50 else ("🟡" if fuel > 25 else "🔴")
    return f"{icon} `{_bar(fuel)}` **{fuel:.0f}%**"

def _tire_str(wear: float, tire_type: str) -> str:
    health = 100.0 - wear
    icon   = "🟢" if health > 60 else ("🟡" if health > 30 else "🔴")
    label  = {"soft": "Soft", "medium": "Med", "hard": "Hard", "wet": "Wet"}.get(tire_type, tire_type.title())
    return f"{icon} `{_bar(health)}` **{label}** ({health:.0f}%)"

def _strategy_label(history: List[str]) -> str:
    if not history:
        return "Balanced"
    pits  = history.count("pit_stop")
    pushs = history.count("accelerate")
    lifts = history.count("slow_down")
    if pits >= 2:
        return f"Aggressive Pit ({pits}x)"
    if pushs > lifts:
        return "Attacking"
    if lifts > pushs:
        return "Conservative"
    return "Balanced"

# ═══════════════════════════════════════════════════════════
#  TRACK STRIP VISUAL
# ═══════════════════════════════════════════════════════════

def build_track_strip(live_timing: List[Dict]) -> str:
    """
    Build a text-art strip showing all cars' positions on a 34-char track.
    Leader at the right, backmarkers at the left.
    Player = [ME], NPCs = [P#].
    """
    W       = 34
    MAX_GAP = 15.0

    # Map each car to a strip index
    placed: List[Tuple[int, str]] = []
    for entry in live_timing:
        gap   = min(entry.get("gap_s", 0.0), MAX_GAP)
        idx   = round((1.0 - gap / MAX_GAP) * (W - 1))
        idx   = max(0, min(W - 1, idx))
        label = "[ME]" if entry["is_player"] else f"[{entry['position']:02}]"
        placed.append((idx, label, entry["is_player"]))

    # Build rows — group overlapping positions
    # One char per slot, use single chars (collisions handled by priority)
    row = ["-"] * W
    for idx, label, is_player in sorted(placed, key=lambda x: not x[2]):
        sym = ">" if is_player else "*"
        if 0 <= idx < W:
            row[idx] = sym

    # Build a readable two-line: symbol row + position labels
    # Just show the symbol row; label below for player only
    sym_row   = "S" + "".join(row) + "F"

    # Find player index for annotation
    player_entry = next((p for p in placed if p[2]), None)
    annotation   = ""
    if player_entry:
        p_idx = player_entry[0] + 1  # +1 for the leading "S"
        annotation = " " * p_idx + "↑YOU"

    return sym_row + ("\n" + annotation if annotation.strip() else "")

# ═══════════════════════════════════════════════════════════
#  EMBED BUILDERS — SEASON
# ═══════════════════════════════════════════════════════════

def career_landing_embed() -> discord.Embed:
    e = discord.Embed(
        title="🏎️  F1 Bot Career Mode 💪",
        description=(
            "Welcome to **F1 Career Mode** — 24 gruelling races across the world's greatest circuits.\n\n"
            "🏆  Earn **Championship Points** each race and climb the season standings.\n"
            "🎯  Your locked **car & driver** stay fixed for the entire season.\n"
            "⚙️  **Garage upgrades** still apply — invest wisely.\n"
            "⚡  React to live **Reaction Challenges** — same as real races.\n"
            "🚦  **4 Tactical Decisions** per race — pit windows, DRS zones, final laps.\n"
            "⛽  Manage **fuel & tyres** across 3 laps / 12 turns.\n\n"
            "> ⚠️  Difficulty **scales hard** — the final 7 races are Elite tier.\n"
            "> You may play **2 matches per day** with a 14-hour cooldown.\n\n"
            "**Ready to sign your contract?**"
        ),
        color=0x2d3436,
    )
    e.set_image(url=CAREER_GIF_URL)
    e.set_footer(text="F1 Career Mode — Season 1")
    return e


def career_status_embed(career: Dict, username: str) -> discord.Embed:
    done   = career.get("matches_completed", 0)
    pts    = career.get("championship_points", 0)
    car_s  = career.get("car_snapshot", {})
    drv_s  = career.get("driver_snapshot", {})
    status = career.get("status", "active")
    color  = 0x00cec9 if status == "active" else 0xdfe6e9

    desc = (
        f"**Season Progress:** `{done}/{TOTAL_MATCHES}` races completed\n"
        f"**Championship Points:** `{pts} pts`\n\n"
        f"🏎️  **Career Car:**  {car_s.get('name','—')} · {car_s.get('top_speed','?')} km/h\n"
        f"👤  **Career Driver:**  {drv_s.get('name','—')} · Skill {drv_s.get('skill','?')}/10\n"
    )
    if done < TOTAL_MATCHES:
        next_num = done + 1
        track    = get_track(next_num)
        diff     = track["difficulty"]
        meta     = DIFF_META[diff]
        desc += (
            f"\n**Next Race:** {track['flag']} {track['name']} "
            f"({meta['emoji']} {meta['label']})\n"
            f"Circuit: *{track['circuit']}*"
        )
    title = "✅  Career Complete!" if status == "completed" else "📋  Career Status"
    return discord.Embed(title=title, description=desc, color=color)


def matches_embed(career: Dict) -> discord.Embed:
    done    = career.get("matches_completed", 0)
    results = {r["match_num"]: r for r in career.get("match_results", [])}
    today   = datetime.now().date().isoformat()
    used    = career.get("daily_used", 0) if career.get("daily_reset_date") == today else 0
    lines   = []
    for t in CAREER_TRACKS:
        n    = t["num"]
        diff = t["difficulty"]
        meta = DIFF_META[diff]
        if n <= done:
            r   = results.get(n, {})
            pos = r.get("position", "?")
            pe  = POS_EMOJIS.get(pos, f"P{pos}")
            pts = r.get("points", 0)
            lines.append(f"✅  **Match {n}** — {t['flag']} {t['name']} — {pe} · {pts} pts")
        elif n == done + 1:
            if used < DAILY_LIMIT:
                lines.append(f"🟢  **Match {n}** — {t['flag']} {t['name']} — {meta['emoji']} {meta['label']} ← **NEXT**")
            else:
                ts        = next_unlock_timestamp(career)
                unlock_str = f"<t:{ts}:R>" if ts else "soon"
                lines.append(f"⏰  **Match {n}** — {t['flag']} {t['name']} — unlocks {unlock_str}")
        else:
            lines.append(f"🔒  **Match {n}** — {t['flag']} {t['name']} — {meta['emoji']} {meta['label']}")

    chunks, chunk = [], []
    for line in lines:
        chunk.append(line)
        if len(chunk) == 8:
            chunks.append("\n".join(chunk)); chunk = []
    if chunk:
        chunks.append("\n".join(chunk))

    e = discord.Embed(
        title=f"📅  Season Schedule — {done}/{TOTAL_MATCHES} Completed",
        color=0x0984e3,
    )
    for i, text in enumerate(chunks):
        e.add_field(name="\u200b" if i else "Races", value=text, inline=False)
    e.set_footer(text=f"Daily limit: {used}/{DAILY_LIMIT} matches used today")
    return e


def match_preview_embed(match_num: int, npcs: List[Dict],
                        car_snap: Dict, drv_snap: Dict,
                        upgrades: Dict) -> discord.Embed:
    track    = get_track(match_num)
    diff     = track["difficulty"]
    meta     = DIFF_META[diff]
    up_bonus = calc_upgrade_bonus(upgrades)
    eff_speed = car_snap.get("top_speed", 0) + int(up_bonus)

    rec_speed = meta["rec_speed"]
    rec_skill = meta["rec_skill"]
    spd_ok    = "✅" if eff_speed >= rec_speed else "⚠️"
    skl_ok    = "✅" if drv_snap.get("skill", 0) >= rec_skill else "⚠️"

    field_lines = []
    for i, npc in enumerate(npcs[:10], 1):
        bar = "█" * int(npc["skill"])
        field_lines.append(f"`P{i:02}`  **{npc['name']}** · {npc['team']}  |  {npc['speed']} km/h  ·  {npc['skill']}/10  `{bar}`")
    if len(npcs) > 10:
        field_lines.append(f"*…and {len(npcs)-10} more competitors*")

    e = discord.Embed(
        title=f"{track['flag']}  Match {match_num}/24 — {track['name']}",
        description=(
            f"🏟️  *{track['circuit']}*  ·  {track['type']}\n"
            f"**Difficulty:** {meta['emoji']} {meta['label']}\n\u200b"
        ),
        color=meta["color"],
    )
    e.add_field(
        name="🏎️  Your Setup",
        value=(
            f"Car: **{car_snap.get('name','?')}** · {eff_speed} km/h {spd_ok}\n"
            f"Driver: **{drv_snap.get('name','?')}** · Skill {drv_snap.get('skill','?')}/10 {skl_ok}\n"
            f"Upgrades Bonus: +{up_bonus:.1f}"
        ),
        inline=True,
    )
    e.add_field(
        name="📊  Recommended",
        value=(
            f"Speed ≥ **{rec_speed} km/h**\n"
            f"Skill ≥ **{rec_skill}/10**\n"
            f"React fast · pit at the right moment!"
        ),
        inline=True,
    )
    e.add_field(
        name=f"🏁  Starting Grid ({len(npcs)+1} Cars)",
        value="\n".join(field_lines),
        inline=False,
    )
    e.add_field(
        name="🏎️  Race Format",
        value=(
            "**3 Laps · 12 Turns**\n"
            "⚡ Reaction challenges on turns 1, 2, 4, 5, 7, 8, 10\n"
            "🚦 Tactical decisions on turns 3 (pit), 6 (DRS), 9 (strategy), 11 (final lap)\n"
            "⛽ Fuel & tyre wear tracked — manage them well!"
        ),
        inline=False,
    )
    e.set_footer(text=f"Match {match_num} · 3 laps · 12 turns · weather possible")
    return e


# ═══════════════════════════════════════════════════════════
#  EMBED BUILDERS — LIVE RACE
# ═══════════════════════════════════════════════════════════

def build_career_live_embed(
    state:       "CareerRaceState",
    live_timing: List[Dict],
    track:       Dict,
    match_num:   int,
    gif_url:     str,
    commentary:  List[str],
) -> discord.Embed:
    """Main live timing embed shown between turns."""
    diff         = track["difficulty"]
    meta         = DIFF_META[diff]
    weather_icon = "🌧️" if state.weather == "rain" else "☀️"

    title = (
        f"🏎️  {track['flag']} {track['name']}  ·  "
        f"Lap {state.lap}/{state.total_laps}  ·  Turn {state.turn}/{state.max_turns}"
    )

    # Description: circuit + last commentary line
    desc_parts = [f"{weather_icon}  *{track['circuit']}*"]
    if state.weather == "rain":
        desc_parts.append("🌧️  **WET CONDITIONS — pit for wets!**")
    if commentary:
        desc_parts.append(f"\n> *{commentary[-1]}*")

    embed = discord.Embed(
        title=title,
        description="\n".join(desc_parts),
        color=meta["color"],
    )
    embed.set_image(url=gif_url)

    # ── Live timing board ──────────────────────────────────
    player_entry = next((e for e in live_timing if e["is_player"]), None)
    player_pos   = player_entry["position"] if player_entry else 99

    timing_lines = []
    for entry in live_timing[:8]:
        pos     = entry["position"]
        medal   = POS_EMOJIS.get(pos, f"**P{pos:02}**")
        gap_txt = "LEADER" if pos == 1 else f"+{entry['gap_s']:.3f}s"
        car_sym = "🏎️" if entry["is_player"] else "⬛"
        you_tag = "  **◄ YOU**" if entry["is_player"] else ""
        name_s  = f"{entry['label'][:20]:<20}"
        timing_lines.append(f"{medal}  {car_sym} {name_s} `{gap_txt}`{you_tag}")

    if player_pos > 8:
        timing_lines.append("　　　　…")
        pe     = player_entry
        gap_t  = f"+{pe['gap_s']:.3f}s"
        timing_lines.append(
            f"**P{player_pos:02}**  🏎️ {pe['label'][:20]:<20} `{gap_t}`  **◄ YOU**"
        )

    embed.add_field(
        name=f"🏁  Live Timing — {len(live_timing)} Cars",
        value="\n".join(timing_lines),
        inline=False,
    )

    # ── Track strip ────────────────────────────────────────
    strip = build_track_strip(live_timing)
    embed.add_field(
        name="🛣️  Track Position",
        value=f"```\n{strip}\n```",
        inline=False,
    )

    # ── Player status ──────────────────────────────────────
    embed.add_field(
        name="🏎️  Your Car Status",
        value=(
            f"⛽ Fuel:  {_fuel_str(state.fuel)}\n"
            f"🔧 Tyres: {_tire_str(state.tire_wear, state.tire_type)}\n"
            f"🔩 Pit stops: **{state.pit_stops}**"
        ),
        inline=False,
    )
    embed.set_footer(text=f"Match {match_num}/24  ·  {meta['emoji']} {meta['label']}  ·  ⚡ Race in progress…")
    return embed


def build_career_scenario_embed(
    scenario:    Dict,
    state:       "CareerRaceState",
    live_timing: List[Dict],
    track:       Dict,
    match_num:   int,
    gif_url:     str,
    locked:      bool = False,
    choice_label: Optional[str] = None,
) -> discord.Embed:
    """Embed for a tactical decision pause — single-player version."""
    diff = track["difficulty"]
    meta = DIFF_META[diff]

    embed = discord.Embed(
        title=scenario["title"],
        description=f"{scenario['description']}\n\n*{scenario['question']}*",
        color=0xF39C12,
    )
    embed.set_image(url=gif_url)

    # Current car status
    embed.add_field(
        name="📊  Your Status",
        value=(
            f"⛽ {_fuel_str(state.fuel)}\n"
            f"🔧 {_tire_str(state.tire_wear, state.tire_type)}\n"
            f"🔩 Pit stops so far: **{state.pit_stops}**"
        ),
        inline=True,
    )

    # Live position
    player_entry = next((e for e in live_timing if e["is_player"]), None)
    if player_entry:
        pos_txt = (
            "LEADER" if player_entry["position"] == 1
            else f"P{player_entry['position']}  (+{player_entry['gap_s']:.3f}s)"
        )
        embed.add_field(
            name="🏎️  Live Position",
            value=f"**{pos_txt}**\nLap {state.lap}/{state.total_laps}",
            inline=True,
        )

    # Decision status
    if locked and choice_label:
        embed.add_field(
            name="📡  Your Decision",
            value=f"✅  **{choice_label}** — locked in!",
            inline=False,
        )
    else:
        embed.add_field(
            name="📡  Awaiting Decision",
            value="⏳  Make your call — auto-resolves in 30 seconds.",
            inline=False,
        )

    embed.set_footer(text=f"Match {match_num}  ·  {meta['emoji']} {meta['label']}")
    return embed


def build_career_reaction_embed(player: discord.Member, dir_label: str) -> discord.Embed:
    e = discord.Embed(
        title="⚡  REACTION CHALLENGE!",
        description=(
            f"{player.mention} — Hit  **{dir_label}**  as fast as you can!\n\n"
            f"4 directions · only YOU can click this one\n"
            f"❌ Wrong = penalty  |  ⏱️ Miss = penalty"
        ),
        color=0xF1C40F,
    )
    e.set_footer(text="⏱️  4 seconds — GO!")
    return e


def race_result_embed(standings: List[Dict], player_pos: int,
                      coins: int, pts: int, track: Dict,
                      qte_hits: int, qte_total: int,
                      pit_stops: int, state: "CareerRaceState") -> discord.Embed:
    diff  = track["difficulty"]
    meta  = DIFF_META[diff]
    lines = []
    for entry in standings[:12]:
        pos   = entry["position"]
        medal = POS_EMOJIS.get(pos, f"P{pos:02}")
        gap   = "LEADER" if pos == 1 else f"+{entry['gap_s']:.3f}s"
        mark  = "  ◄ **YOU**" if entry["is_player"] else ""
        lines.append(f"{medal}  **{entry['label']}** · {entry['team']:<14}  `{gap}`{mark}")
    if player_pos > 12:
        p = next(e for e in standings if e["is_player"])
        lines.append("—")
        lines.append(f"P{player_pos:02}  **{p['label']}**  `+{p['gap_s']:.3f}s`  ◄ **YOU**")

    # Race highlights
    highlights = []
    if player_pos == 1:
        highlights.append("🏆 Race winner! Lights to flag domination!")
    if player_pos <= 3:
        highlights.append(f"🥇 Podium finish — P{player_pos}!")
    if pit_stops == 0:
        highlights.append("🔥 One-stop warrior — completed the race on a single tyre set!")
    if pit_stops >= 2:
        highlights.append(f"🔧 Aggressive {pit_stops}-stop strategy!")
    if state.fuel < 15:
        highlights.append("⛽ Crossed the line on fumes — fuel management was critical!")
    qte_pct = int(qte_hits / qte_total * 100) if qte_total else 0
    if qte_pct == 100:
        highlights.append(f"⚡ Perfect reactions — {qte_hits}/{qte_total} hits!")
    elif qte_pct >= 70:
        highlights.append(f"⚡ Sharp reactions — {qte_hits}/{qte_total} hits ({qte_pct}%)")
    if state.weather == "rain":
        highlights.append("🌧️ Navigated wet conditions!")
    if not highlights:
        highlights.append("🎯 A clean, controlled race from lights to flag.")

    strategy = _strategy_label(state.choice_history)

    e = discord.Embed(
        title=f"🏁  {track['flag']} {track['name']} — Race Result",
        description="\n".join(lines),
        color=meta["color"],
    )
    e.add_field(
        name="🏆  Your Result",
        value=f"**P{player_pos}**  ·  +{pts} Championship Points  ·  +{coins} Coins",
        inline=False,
    )
    e.add_field(
        name="⚡  Performance",
        value=(
            f"Reactions: **{qte_hits}/{qte_total}**  ·  Pit Stops: **{pit_stops}**\n"
            f"Strategy: *{strategy}*  ·  Fuel left: **{state.fuel:.0f}%**\n"
            f"Tyres: {_tire_str(state.tire_wear, state.tire_type)}"
        ),
        inline=False,
    )
    e.add_field(
        name="📰  Race Highlights",
        value="\n".join(f"• {h}" for h in highlights),
        inline=False,
    )
    e.set_footer(text="Use /career_standings to view the championship table")
    return e


def career_standings_embed(all_standings: List[Dict]) -> discord.Embed:
    lines = []
    for i, s in enumerate(all_standings[:15], 1):
        medal  = POS_EMOJIS.get(i, f"P{i:02}")
        status = "✅" if s["status"] == "completed" else "🔄"
        lines.append(
            f"{medal}  **{s['username']}**  ·  "
            f"`{s['championship_points']} pts`  ·  "
            f"{s['matches_completed']}/{TOTAL_MATCHES} races {status}"
        )
    if not lines:
        lines = ["No career players yet — be the first with `/career`!"]
    e = discord.Embed(
        title="🏆  F1 Career Championship Standings",
        description="\n".join(lines),
        color=0xf9ca24,
    )
    e.set_footer(text="Top 5 receive special season rewards at completion")
    return e


def career_rewards_embed(player_pos: int, career: Dict) -> discord.Embed:
    done = career.get("matches_completed", 0)
    pts  = career.get("championship_points", 0)
    rows = [
        (1, "🔱 Mythic Pack (1 Mythic card)",      "8,000 coins", "🌟 World Champion card"),
        (2, "👑 Legendary Pack (5 cards, 2 Leg.)", "8,000 coins", "🌟 Contender card"),
        (3, "👑 Legendary Pack (5 cards, 1 Leg.)", "8,000 coins", "🌟 Podium card"),
        (4, "👑 Legendary Pack (2 cards, 1 Leg.)", "6,000 coins", "—"),
        (5, "👑 Guaranteed Legendary (1 card)",    "5,000 coins", "—"),
    ]
    coin_rows = [(6, "4,000"), (7, "3,000"), (8, "2,000"), (9, "1,000")]

    lines = []
    for pos, pack, coins, special in rows:
        mark = " ◄" if pos == player_pos else ""
        lines.append(f"**P{pos}** — {pack}  ·  {coins}{(f'  ·  {special}') if special != '—' else ''}{mark}")
    lines.append("—")
    for pos, coins in coin_rows:
        mark  = " ◄" if pos == player_pos else ""
        label = f"P{pos}" if pos < 9 else "P9+"
        lines.append(f"**{label}** — {coins} coins{mark}")

    completed = done >= TOTAL_MATCHES
    claimed   = career.get("reward_claimed", False)
    if completed and not claimed and player_pos:
        footer = f"Your position: P{player_pos} · Click the button below to claim!"
    elif claimed:
        footer = "Rewards already claimed. Thank you for playing Season 1!"
    else:
        footer = f"Complete all {TOTAL_MATCHES} matches to claim your reward."

    e = discord.Embed(
        title="🎁  Season End Rewards",
        description="\n".join(lines),
        color=0xf9ca24,
    )
    e.add_field(
        name="Your Standing",
        value=f"**P{player_pos}**  ·  {pts} pts  ·  {done}/{TOTAL_MATCHES} matches",
        inline=False,
    )
    e.set_footer(text=footer)
    return e


# ═══════════════════════════════════════════════════════════
#  VIEWS — SEASON MANAGEMENT
# ═══════════════════════════════════════════════════════════

class CareerSignupView(discord.ui.View):
    def __init__(self, player_id: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.signed    = False

    def _owner(self, i: discord.Interaction) -> bool:
        return str(i.user.id) == self.player_id

    @discord.ui.button(label="✍️  Sign Contract", style=discord.ButtonStyle.success, row=0)
    async def sign(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("This is not your contract!", ephemeral=True); return
        self.signed = True
        self.stop()
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="✖  Decline", style=discord.ButtonStyle.danger, row=0)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("This is not your contract!", ephemeral=True); return
        self.stop()
        await interaction.response.edit_message(
            content="Contract declined. Use `/career` any time to sign up.", embed=None, view=None)


class CareerCarSelectView(discord.ui.View):
    def __init__(self, player_id: str, cars: List[Dict]):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.selected  = None

        options = []
        for car in cars[:25]:
            rarity_e = card_module.RARITY_EMOJIS.get(car.get("rarity", "common"), "")
            options.append(discord.SelectOption(
                label=f"{car['name']}"[:100],
                description=f"{car.get('top_speed','?')} km/h · {car.get('rarity','').upper()}"[:100],
                value=car["id"],
                emoji=rarity_e or None,
            ))
        sel = discord.ui.Select(placeholder="Choose your career car…", options=options)
        async def _on_sel(i: discord.Interaction):
            if str(i.user.id) != player_id:
                await i.response.send_message("Not your selection!", ephemeral=True); return
            self.selected = next((c for c in cars if c["id"] == i.data["values"][0]), None)
            self.stop()
            await i.response.defer()
        sel.callback = _on_sel
        self.add_item(sel)


class CareerDriverSelectView(discord.ui.View):
    def __init__(self, player_id: str, drivers: List[Dict]):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.selected  = None

        options = []
        for drv in drivers[:25]:
            rarity_e = card_module.RARITY_EMOJIS.get(drv.get("rarity", "common"), "")
            options.append(discord.SelectOption(
                label=f"{drv['name']}"[:100],
                description=f"Skill {drv.get('skill','?')}/10 · {drv.get('rarity','').upper()}"[:100],
                value=drv["id"],
                emoji=rarity_e or None,
            ))
        sel = discord.ui.Select(placeholder="Choose your career driver…", options=options)
        async def _on_sel(i: discord.Interaction):
            if str(i.user.id) != player_id:
                await i.response.send_message("Not your selection!", ephemeral=True); return
            self.selected = next((d for d in drivers if d["id"] == i.data["values"][0]), None)
            self.stop()
            await i.response.defer()
        sel.callback = _on_sel
        self.add_item(sel)


class CareerConfirmView(discord.ui.View):
    def __init__(self, player_id: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.confirmed = False

    def _owner(self, i):
        return str(i.user.id) == self.player_id

    @discord.ui.button(label="✅  Confirm & Sign", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your contract!", ephemeral=True); return
        self.confirmed = True
        self.stop()
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🔄  Change Selection", style=discord.ButtonStyle.secondary)
    async def change(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your contract!", ephemeral=True); return
        self.stop()
        await interaction.response.defer()


class CareerMatchStartView(discord.ui.View):
    def __init__(self, player_id: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.started   = False

    def _owner(self, i):
        return str(i.user.id) == self.player_id

    @discord.ui.button(label="🏁  Start Race", style=discord.ButtonStyle.success)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your race!", ephemeral=True); return
        self.started = True
        self.stop()
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="✖  Abort", style=discord.ButtonStyle.danger)
    async def abort(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your race!", ephemeral=True); return
        self.stop()
        await interaction.response.edit_message(content="Race aborted.", embed=None, view=None)


class CareerRewardsView(discord.ui.View):
    def __init__(self, player_id: str, claimable: bool):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.claimed   = False
        btn = self.children[0]
        btn.disabled = not claimable

    def _owner(self, i):
        return str(i.user.id) == self.player_id

    @discord.ui.button(label="🎁  Claim Your Reward", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your reward!", ephemeral=True); return
        self.claimed = True
        self.stop()
        button.disabled = True
        await interaction.response.edit_message(view=self)


# ═══════════════════════════════════════════════════════════
#  VIEWS — RACE ENGINE
# ═══════════════════════════════════════════════════════════

class CareerScenarioView(discord.ui.View):
    """Single-player scenario decision — mirrors ScenarioView from normal race."""

    def __init__(self, player_id: str, scenario: Dict, state: CareerRaceState,
                 live_timing: List[Dict], track: Dict, match_num: int,
                 message: discord.Message, gif_url: str):
        super().__init__(timeout=30)
        self.player_id    = player_id
        self.scenario     = scenario
        self.state        = state
        self.live_timing  = live_timing
        self.track        = track
        self.match_num    = match_num
        self.message      = message
        self.gif_url      = gif_url
        self.choice:       Optional[str] = None
        self.choice_label: Optional[str] = None
        self.chosen       = asyncio.Event()
        self.lock         = asyncio.Lock()

        for opt in scenario["options"]:
            btn   = discord.ui.Button(label=opt["label"], style=opt["style"], row=0)
            value = opt["value"]
            label = opt["label"]
            async def _cb(interaction: discord.Interaction, _v=value, _l=label):
                await self._handle(interaction, _v, _l)
            btn.callback = _cb
            self.add_item(btn)

    async def _handle(self, interaction: discord.Interaction, value: str, label: str):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("Not your race!", ephemeral=True)
            return
        async with self.lock:
            if self.choice:
                await interaction.response.send_message("Already locked in!", ephemeral=True)
                return
            self.choice       = value
            self.choice_label = label
        self.chosen.set()
        # Remove buttons immediately when player clicks
        await interaction.response.edit_message(
            embed=build_career_scenario_embed(
                self.scenario, self.state, self.live_timing,
                self.track, self.match_num, self.gif_url,
                locked=True, choice_label=label,
            ),
            view=None,
        )


class CareerReactionView(discord.ui.View):
    """Single-player reaction challenge — mirrors SinglePlayerReactionView from normal race."""

    def __init__(self, direction: str, player: discord.Member):
        super().__init__(timeout=4.0)
        self.direction = direction
        self.player    = player
        self.result:   Optional[Tuple[bool, float]] = None
        self.done      = asyncio.Event()
        self._start    = time.time()

    async def _handle(self, interaction: discord.Interaction, clicked: str):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ This challenge isn't for you!", ephemeral=True)
            return
        if self.result is not None:
            await interaction.response.defer()
            return
        elapsed     = time.time() - self._start
        correct     = (clicked == self.direction)
        self.result = (correct, elapsed)
        self.done.set()
        self.stop()
        if correct:
            await interaction.response.edit_message(
                content=f"✅ **CORRECT!** You hit it in `{elapsed:.2f}s`! 🚀",
                embed=None,
                view=None,
            )
        else:
            await interaction.response.edit_message(
                content=f"❌ **WRONG DIRECTION!** Penalty incoming… 💀",
                embed=None,
                view=None,
            )

    @discord.ui.button(label="◀  LEFT",  style=discord.ButtonStyle.primary, row=0)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "left")

    @discord.ui.button(label="RIGHT  ▶", style=discord.ButtonStyle.primary, row=0)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "right")

    @discord.ui.button(label="▲  UP",    style=discord.ButtonStyle.primary, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "up")

    @discord.ui.button(label="▼  DOWN",  style=discord.ButtonStyle.primary, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "down")


# ═══════════════════════════════════════════════════════════
#  RACE COROUTINE — full 3-lap / 12-turn career race
# ═══════════════════════════════════════════════════════════

CAREER_COMMENTARY = [
    "The car is looking quick through the high-speed section.",
    "Tyre degradation starting to become visible.",
    "Gap holding steady — consistent pace from your side.",
    "The rivals are pushing hard — no room for mistakes.",
    "Clean sector — gaining a tenth here and there.",
    "Engineers report the car balance is improving.",
    "Track evolution working in your favour.",
    "A brief lock-up at Turn 1 — tyres still okay.",
    "The safety car board is out in the pits — not for you.",
    "Fuel load dropping — the car coming alive!",
    "Splitting through backmarkers with precision.",
    "The crowd is on their feet for this battle!",
    "Radio: 'Pace looks good, stay focused.'",
    "Radio: 'Mind the gap to P2 — they're closing!'",
    "Radio: 'Fuel saving — lift and coast in T7.'",
    "Radio: 'Tyres are at the limit — one more lap.'",
    "A rival locks up ahead — opportunity incoming!",
    "Smooth through the chicane — time gained.",
]


async def run_career_race(
    channel,
    msg:       discord.Message,
    player:    discord.Member,
    player_id: str,
    match_num: int,
    car_snap:  Dict,
    drv_snap:  Dict,
    upgrades:  Dict,
) -> Dict:
    """
    Full 3-lap / 12-turn career race mirroring run_auto_race from the normal race.
    Scenarios at turns 3/6/9/11, reaction challenges at turns 1/2/4/5/7/8/10.
    Tracks fuel, tyre wear, weather, pit stops.
    Returns a result dict compatible with db.record_career_match().
    """
    track   = get_track(match_num)
    npcs    = get_race_npcs(match_num)
    diff    = track["difficulty"]
    meta    = DIFF_META[diff]
    gif_url = random.choice(RACE_GIFS)

    # Pre-roll NPC scores (fixed for the whole race)
    npc_scores = [calc_npc_score(npc) for npc in npcs]

    # Player base score (without reaction/scenario bonuses)
    car_speed  = car_snap.get("top_speed", 340)
    drv_skill  = drv_snap.get("skill", 6.0)
    up_bonus   = calc_upgrade_bonus(upgrades)
    base_noise = random.uniform(-12, 12)  # fixed random element
    player_base = car_speed + drv_skill * 10 + up_bonus + base_noise

    state = CareerRaceState()
    state.weather  = "rain" if random.random() < 0.12 else "dry"
    state.fuel     = 100.0
    state.tire_wear = 0.0
    state.tire_type = "medium"

    qte_hits     = 0
    qte_total    = 0
    commentary   = []

    def _live_timing() -> List[Dict]:
        """Compute live timing from current player score."""
        p_score = player_base + state.score_adj
        drv_n   = drv_snap.get("name", "?")
        car_n   = car_snap.get("name", "?")
        label   = f"{drv_n} / {car_n}"
        entries = [{"label": label, "score": p_score, "is_player": True, "team": "You"}]
        for i, npc in enumerate(npcs):
            entries.append({
                "label":     npc["name"],
                "score":     npc_scores[i],
                "is_player": False,
                "team":      npc["team"],
            })
        entries.sort(key=lambda x: x["score"], reverse=True)
        leader = entries[0]["score"]
        for j, e in enumerate(entries):
            e["position"] = j + 1
            e["gap_s"]    = (leader - e["score"]) * 0.15
        return entries

    AUTO_DELAY    = 2.8
    SCENARIO_WAIT = 30

    try:
        for turn_num in range(1, CAREER_TURNS + 1):
            state.turn = turn_num
            state.lap  = ((turn_num - 1) // 4) + 1

            # ── Fuel & tyre degradation each turn ──
            fuel_burn   = random.uniform(6.5, 8.5)
            wear_rate   = random.uniform(5.0, 8.0)
            state.fuel      = max(0.0, state.fuel - fuel_burn)
            state.tire_wear = min(100.0, state.tire_wear + wear_rate)

            # Random commentary line
            commentary.append(random.choice(CAREER_COMMENTARY))

            timing = _live_timing()

            # ══ SCENARIO TURN ══════════════════════════════
            if turn_num in SCENARIO_TURNS:
                scenario = CAREER_SCENARIOS[turn_num].copy()
                if state.weather == "rain" and turn_num in (6, 9):
                    scenario = RAIN_SCENARIO_OVERRIDE.copy()

                sv = CareerScenarioView(
                    player_id, scenario, state, timing, track, match_num, msg, gif_url
                )
                try:
                    await msg.edit(
                        embed=build_career_scenario_embed(
                            scenario, state, timing, track, match_num, gif_url
                        ),
                        view=sv,
                    )
                except Exception:
                    pass

                try:
                    await asyncio.wait_for(sv.chosen.wait(), timeout=SCENARIO_WAIT)
                except asyncio.TimeoutError:
                    pass

                choice       = sv.choice or "same_speed"
                choice_label = sv.choice_label or "Auto (timed out)"

                # Apply effects to state
                if choice == "pit_stop":
                    state.pit_stops += 1
                    state.fuel       = 100.0
                    state.tire_wear  = 0.0
                    state.tire_type  = "wet" if state.weather == "rain" else random.choice(["soft", "medium"])
                    state.score_adj -= 6.0  # pit lane time loss
                elif choice == "accelerate":
                    state.fuel      = max(0.0, state.fuel - 6.0)
                    state.tire_wear = min(100.0, state.tire_wear + 6.0)
                    state.score_adj += 4.5
                else:  # same_speed / slow_down
                    state.score_adj += 1.0

                state.choice_history.append(choice)

                # Show resolved embed briefly
                try:
                    await msg.edit(
                        embed=build_career_scenario_embed(
                            scenario, state, timing, track, match_num, gif_url,
                            locked=True, choice_label=choice_label,
                        ),
                        view=None,
                    )
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            # ── Refresh timing + update live embed ─────────
            timing = _live_timing()
            try:
                await msg.edit(
                    embed=build_career_live_embed(state, timing, track, match_num, gif_url, commentary),
                    view=None,
                )
            except Exception:
                pass

            # ══ REACTION CHALLENGE — embed sent to player DM ══
            if turn_num in REACTION_TURNS and channel:
                await asyncio.sleep(1.2)
                direction = random.choice(REACTION_DIRECTIONS)
                dir_label = REACTION_LABELS[direction]

                rv = CareerReactionView(direction, player)
                try:
                    await player.send(
                        embed=build_career_reaction_embed(player, dir_label),
                        view=rv,
                    )
                except Exception:
                    rv.done.set()

                try:
                    await asyncio.wait_for(rv.done.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    rv.stop()

                # Evaluate reaction
                qte_total += 1
                if rv.result is not None:
                    correct, elapsed = rv.result
                    if correct:
                        qte_hits        += 1
                        state.score_adj += 2.0
                    else:
                        state.score_adj -= 3.0
                else:
                    state.score_adj -= 1.0

                await asyncio.sleep(2.0)

            elif turn_num < CAREER_TURNS:
                await asyncio.sleep(AUTO_DELAY)

    except Exception as ex:
        print(f"Career race error (turn {state.turn}): {ex}")

    # ── Final standings ────────────────────────────────────
    final_timing = _live_timing()
    player_entry = next((e for e in final_timing if e["is_player"]), None)
    player_pos   = player_entry["position"] if player_entry else 16

    pts   = CAREER_PTS.get(player_pos, 0)
    coins = RACE_PAYOUT.get(player_pos, 10)

    return {
        "match_num":   match_num,
        "position":    player_pos,
        "points":      pts,
        "coins":       coins,
        "standings":   final_timing,
        "qte_hits":    qte_hits,
        "qte_total":   qte_total,
        "pit_hits":    state.pit_stops,
        "state":       state,
        "track":       track,
    }
