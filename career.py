import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import discord
import asyncio
import time

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
    ],
    "medium": [
        {"name": "Yuki Tsunoda",      "team": "RB",           "skill": 7.2, "speed": 362},
        {"name": "Pierre Gasly",      "team": "Alpine",       "skill": 7.3, "speed": 364},
        {"name": "Sergio Perez",      "team": "Red Bull",     "skill": 7.6, "speed": 370},
    ],
    "hard": [
        {"name": "Oscar Piastri",    "team": "McLaren",      "skill": 7.8, "speed": 382},
        {"name": "Carlos Sainz",     "team": "Williams",     "skill": 7.9, "speed": 385},
        {"name": "George Russell",   "team": "Mercedes",     "skill": 8.1, "speed": 390},
    ],
    "peak": [
        {"name": "Lewis Hamilton",     "team": "Ferrari",      "skill": 8.8, "speed": 408},
        {"name": "Max Verstappen",     "team": "Red Bull",     "skill": 9.2, "speed": 412},
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

RACE_GIFS = [
    "https://media.giphy.com/media/3ohzdIuqJoo8QdKlnW/giphy.gif",
    "https://media.giphy.com/media/26gJAn0QqFWbqQUMw/giphy.gif",
    "https://media.giphy.com/media/l0MYyoYKBIRtjXJEQ/giphy.gif",
    "https://media.giphy.com/media/xT1Ra5h24Eliux3UVq/giphy.gif",
]

# ── Replace this URL with your own race GIF ──────────────────────
CAREER_RACE_GIF = "https://gifdb.com/images/thumbnail/f1-formula1-gif-qm0m61l3z6ydteoo.gif"

CAREER_LAPS   = 3
CAREER_TURNS  = 12

SCENARIO_TURNS  = {3, 6, 9, 11}
REACTION_TURNS  = [1, 2, 4, 5, 7, 8, 10]

# ─── Commentary pools ────────────────────────────────────────────
# Indexed by situation so we can pick context-aware lines every turn

_CMT_LEADING = [
    "🎙️ *\"He's pulling away lap by lap — an imperious drive!\"*",
    "🎙️ *\"The gap is growing. This is measured, clinical pace.\"*",
    "💨 Smooth through every sector — nothing wasted, nothing lost.",
    "📡 Gap holding strong. The rivals can't find an answer.",
    "🔵 Clean air up front. Every lap is a mini qualifying effort.",
    "🏁 The pit-wall body language says it all — controlled and composed.",
]

_CMT_CHASING = [
    "🎙️ *\"He's hunting them down — tenth by tenth, corner by corner!\"*",
    "🎙️ *\"The gap's coming down! Can he do it before the flag?\"*",
    "📡 DRS range within striking distance — just keep the pressure on.",
    "🔴 The car ahead is nervous. They know someone's coming.",
    "⚡ Every clean exit from a corner chips away at the deficit.",
    "🏎️ Closing the gap through traction zones — the tyres are alive.",
]

_CMT_MIDFIELD = [
    "🎙️ *\"Solid midfield pace — consistent, aggressive, tactical.\"*",
    "📻 A battle through the twisty middle sector — wheel to wheel.",
    "💨 Points are on the table. Every position matters in this season.",
    "🎯 Picking off rivals one by one — this could be huge for the standings.",
    "📡 The field is compressed here — one mistake and it unravels.",
]

_CMT_PRESSURE = [
    "🔴 *Incoming pressure* — the car behind is right in the DRS zone!",
    "⚠️ They're on your gearbox! Defend, defend, defend!",
    "🔥 Lap after lap of pressure — the tyres won't last forever.",
    "😰 Side by side through the braking zone — this is the real racing!",
    "📡 Radio: *\"He's right with you. Watch the mirrors through Turn 3.\"*",
    "🏎️ Defending hard — every apex must be perfect or the place is gone.",
]

_CMT_HIGH_WEAR = [
    "⚠️ Tyre degradation is becoming critical — be gentle on the rears.",
    "📡 Radio: *\"Tyres are going off. We need to manage these to the flag.\"*",
    "🌡️ Overheating rubber — the lap times are starting to suffer.",
    "🔴 Sliding on the exits — these tyres are done. Pit window is open.",
]

_CMT_LOW_FUEL = [
    "⛽ Radio: *\"Fuel is getting tight. We need to conserve from here.\"*",
    "📡 Fuel saving mode activated — every gear shift counts now.",
    "⚠️ Running on fumes in the final sector — this is going to be close.",
]

_CMT_RAIN = [
    "🌧️ Rain intensifying — visibility dropping, grip levels unpredictable.",
    "🌧️ Radio: *\"Track is still wet. Be careful through the fast stuff.\"*",
    "🌧️ Aquaplaning risk on the straights — lift and coast where possible.",
    "🌧️ *\"Whoever reads this weather best wins the race.\"* — commentator",
]

_CMT_FINAL_LAP = [
    "🏁 **WHITE FLAG!** This is it — one lap to go. Leave everything on track.",
    "🏁 *\"The chequered flag is within sight. Do NOT give this up now!\"*",
    "🏁 FINAL LAP. Every corner is worth a season's worth of pride.",
    "🏁 Radio: *\"Push, push, PUSH! This is what we came for!\"*",
]

_CMT_PIT = [
    "🔧 **PIT STOP!** Fresh rubber fitted — the team nailed it!",
    "🔧 In and out of the pits — track position traded for pace.",
    "🔧 Radio: *\"Good stop. Get your head down and make up the places.\"*",
]

def _pick_commentary(
    turn: int,
    fuel: float,
    tire_wear: float,
    weather: str,
    player_time: float,
    npc_avg_time: float,
    last_choice: Optional[str],
) -> str:
    """Return one context-aware commentary line for this turn."""
    if turn >= 9:
        return random.choice(_CMT_FINAL_LAP)
    if last_choice == "pit_stop":
        return random.choice(_CMT_PIT)
    if weather == "rain":
        return random.choice(_CMT_RAIN)
    if fuel < 20:
        return random.choice(_CMT_LOW_FUEL)
    if tire_wear > 70:
        return random.choice(_CMT_HIGH_WEAR)
    # position-based
    gap = player_time - npc_avg_time
    if gap < -2.0:
        return random.choice(_CMT_LEADING)
    if gap > 2.0:
        return random.choice(_CMT_CHASING)
    if abs(gap) < 0.5:
        return random.choice(_CMT_PRESSURE)
    return random.choice(_CMT_MIDFIELD)

def _fuel_bar(fuel: float) -> str:
    filled = max(0, min(5, int(fuel / 20)))
    icon = "🟢" if fuel > 50 else ("🟡" if fuel > 25 else "🔴")
    return f"{icon} `{'█' * filled}{'░' * (5 - filled)}` {fuel:.0f}%"

def _tyre_bar(wear: float) -> str:
    health = 100.0 - wear
    filled = max(0, min(5, int(health / 20)))
    icon = "🟢" if health > 60 else ("🟡" if health > 30 else "🔴")
    return f"{icon} `{'█' * filled}{'░' * (5 - filled)}` {health:.0f}%"

def get_track(match_num: int) -> Dict:
    return CAREER_TRACKS[match_num - 1]

def get_race_npcs(match_num: int, count: int = 15) -> List[Dict]:
    diff = get_track(match_num)["difficulty"]
    pool = NPC_POOLS[diff].copy()
    random.shuffle(pool)
    return pool[:count]

def can_play(career: Dict) -> Tuple[bool, str]:
    if career.get("matches_completed", 0) >= TOTAL_MATCHES:
        return False, "season_done"
    from datetime import date, datetime as dt, timedelta
    today = dt.now().date().isoformat()
    used  = career.get("daily_used", 0) if career.get("daily_reset_date") == today else 0
    if used >= DAILY_LIMIT:
        last_at = career.get("last_match_at")
        if last_at:
            unlock = dt.fromisoformat(last_at) + timedelta(hours=COOLDOWN_HOURS)
            if dt.now() < unlock:
                secs = int((unlock - dt.now()).total_seconds())
                return False, f"cooldown:{secs}"
    return True, "ok"

def next_unlock_timestamp(career: Dict) -> Optional[int]:
    last_at = career.get("last_match_at")
    if not last_at:
        return None
    from datetime import datetime as dt, timedelta
    dt_obj = dt.fromisoformat(last_at) + timedelta(hours=COOLDOWN_HOURS)
    return int(dt_obj.timestamp())

def fmt_secs(s: int) -> str:
    h, rem = divmod(s, 3600)
    m, s2  = divmod(rem, 60)
    return f"{h}h {m}m" if h else f"{m}m {s2}s"

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
            await interaction.response.send_message("This is not your contract!", ephemeral=True)
            return
        self.signed = True
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="✖  Decline", style=discord.ButtonStyle.danger, row=0)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("This is not your contract!", ephemeral=True)
            return
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
                await i.response.send_message("Not your selection!", ephemeral=True)
                return
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
                await i.response.send_message("Not your selection!", ephemeral=True)
                return
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
            await interaction.response.send_message("Not your contract!", ephemeral=True)
            return
        self.confirmed = True
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🔄  Change Selection", style=discord.ButtonStyle.secondary)
    async def change(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your contract!", ephemeral=True)
            return
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
            await interaction.response.send_message("Not your race!", ephemeral=True)
            return
        self.started = True
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="✖  Abort", style=discord.ButtonStyle.danger)
    async def abort(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your race!", ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(content="Race aborted.", embed=None, view=None)

class CareerRewardsView(discord.ui.View):
    def __init__(self, player_id: str, claimable: bool):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.claimed   = False
        btn = self.children[0] if self.children else None
        if btn:
            btn.disabled = not claimable

    def _owner(self, i):
        return str(i.user.id) == self.player_id

    @discord.ui.button(label="🎁  Claim Your Reward", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your reward!", ephemeral=True)
            return
        self.claimed = True
        self.stop()
        button.disabled = True
        await interaction.response.edit_message(view=self)

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
    pts_total = career.get("championship_points", 0)
    results = {r["match_num"]: r for r in career.get("match_results", [])}
    from datetime import datetime
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
            lines.append(f"✅  **R{n}** {t['flag']} {t['name']}  —  {pe} · **{pts} pts**")
        elif n == done + 1:
            if used < DAILY_LIMIT:
                lines.append(f"🟢  **R{n}** {t['flag']} {t['name']}  —  {meta['emoji']} {meta['label']}  ◄ **NEXT**")
            else:
                ts        = next_unlock_timestamp(career)
                unlock_str = f"<t:{ts}:R>" if ts else "soon"
                lines.append(f"⏰  **R{n}** {t['flag']} {t['name']}  —  unlocks {unlock_str}")
        else:
            lines.append(f"🔒  **R{n}** {t['flag']} {t['name']}  —  {meta['emoji']} {meta['label']}")

    chunk_size = 8
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
    labels = ["Races 1–8", "Races 9–16", "Races 17–24"]

    status = career.get("status", "active")
    color  = 0x00b894 if status == "active" else 0xf9ca24

    e = discord.Embed(
        title=f"📅  F1 Career — Season Schedule",
        color=color,
    )
    e.add_field(
        name="📊  Season Progress",
        value=(
            f"**Races completed:** {done} / {TOTAL_MATCHES}\n"
            f"**Championship Points:** {pts_total} pts\n"
            f"**Today's matches:** {used} / {DAILY_LIMIT} used"
        ),
        inline=False,
    )
    for i, chunk in enumerate(chunks):
        label = labels[i] if i < len(labels) else f"Races {i*8+1}–{i*8+8}"
        e.add_field(name=label, value="\n".join(chunk), inline=False)
    e.set_footer(text="🟢 Ready  ·  ✅ Done  ·  🔒 Locked  ·  ⏰ On cooldown  |  Use /career_match to race")
    return e

# ═══════════════════════════════════════════════════════════
#  CAREER RACE — SCENARIOS & REACTION SYSTEM
# ═══════════════════════════════════════════════════════════

CAREER_RACE_SCENARIOS: Dict[int, Dict] = {
    3: {
        "id": "pit_window",
        "title": "🛑  Pit Window Open!",
        "description": "**Lap 1 complete.** Fresh rubber could be decisive — but staying out preserves track position.",
        "question": "Do you pit for fresh tyres, or push on?",
        "options": [
            {"label": "⛽ Pit Now",   "value": "pit_stop",   "style": discord.ButtonStyle.danger},
            {"label": "🏎️ Stay Out", "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
    6: {
        "id": "drs_attack",
        "title": "💨  DRS Zone — Attack or Manage!",
        "description": "**Mid-race.** The DRS zone opens up. Go flat out and gain ground, or protect your tyres?",
        "question": "Go flat out through the DRS zone, or conserve tyres for the final laps?",
        "options": [
            {"label": "🔥 Maximum Attack",   "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Conserve & Cover", "value": "slow_down",  "style": discord.ButtonStyle.secondary},
        ],
    },
    9: {
        "id": "late_strategy",
        "title": "🚗  Late Race Strategy Call!",
        "description": "**Final third.** Tyre wear is critical and fuel loads are dropping fast. Every call is season-defining.",
        "question": "Push hard, manage tyres to the flag, or gamble on an emergency stop?",
        "options": [
            {"label": "🔥 Push Hard",      "value": "accelerate", "style": discord.ButtonStyle.success},
            {"label": "⏱️ Manage Tyres",  "value": "slow_down",  "style": discord.ButtonStyle.secondary},
            {"label": "⛽ Emergency Pit",  "value": "pit_stop",   "style": discord.ButtonStyle.danger},
        ],
    },
    11: {
        "id": "final_lap",
        "title": "🏁  FINAL LAP — Last Call!",
        "description": "**The white flag is out.** Everything comes down to the next few corners. Make it count.",
        "question": "Absolute maximum attack, or protect what you have?",
        "options": [
            {"label": "🔥 FLAT OUT!",        "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Protect the Gap", "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
}

REACTION_DIRECTIONS = ["left", "right", "up", "down"]
REACTION_LABELS = {
    "left":  "◀  LEFT",
    "right": "RIGHT  ▶",
    "up":    "▲  UP",
    "down":  "▼  DOWN",
}


class CareerReactionView(discord.ui.View):
    """Channel-only reaction challenge — disappears immediately on click or timeout."""

    def __init__(self, direction: str, player: discord.Member):
        super().__init__(timeout=5.0)
        self.direction = direction
        self.player    = player
        self.result: Optional[tuple] = None
        self.done      = asyncio.Event()
        self._start    = time.time()

    async def _handle(self, interaction: discord.Interaction, clicked: str):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ This isn't your race!", ephemeral=True)
            return
        if self.result is not None:
            await interaction.response.defer()
            return
        elapsed = time.time() - self._start
        correct = clicked == self.direction
        self.result = (correct, elapsed)
        self.done.set()
        self.stop()
        if correct:
            await interaction.response.edit_message(
                content=f"✅  **NAILED IT!**  `{elapsed:.2f}s` — speed boost incoming! 🚀",
                embed=None,
                view=None,
            )
        else:
            await interaction.response.edit_message(
                content=f"❌  **WRONG DIRECTION!**  Penalty applied… 💀",
                embed=None,
                view=None,
            )

    async def on_timeout(self):
        self.done.set()

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


class CareerScenarioView(discord.ui.View):
    """Single-player tactical decision shown in channel during a career race."""

    def __init__(self, player: discord.Member, scenario: Dict):
        super().__init__(timeout=30)
        self.player   = player
        self.choice: Optional[str] = None
        self.label:  Optional[str] = None
        self.chosen   = asyncio.Event()

        for opt in scenario["options"]:
            btn = discord.ui.Button(label=opt["label"], style=opt["style"], row=0)
            value = opt["value"]
            label = opt["label"]

            async def _cb(interaction: discord.Interaction, _v=value, _l=label):
                if interaction.user.id != self.player.id:
                    await interaction.response.send_message("This is not your race!", ephemeral=True)
                    return
                if self.choice:
                    await interaction.response.defer()
                    return
                self.choice = _v
                self.label  = _l
                self.chosen.set()
                self.stop()
                await interaction.response.edit_message(
                    content=f"✅  **{_l}** locked in! Decision made.",
                    embed=None,
                    view=None,
                )

            btn.callback = _cb
            self.add_item(btn)

    async def on_timeout(self):
        self.chosen.set()


# ═══════════════════════════════════════════════════════════
#  CAREER RACE — EMBEDS
# ═══════════════════════════════════════════════════════════

def match_preview_embed(
    match_num: int,
    npcs: List[Dict],
    car_snap: Dict,
    drv_snap: Dict,
    upgrades: Dict,
) -> discord.Embed:
    track = get_track(match_num)
    diff  = track["difficulty"]
    meta  = DIFF_META[diff]

    speed_boost = sum(upgrades.get(s, 0) for s in ["engine"]) * 3
    boosted_speed = car_snap.get("top_speed", 350) + speed_boost

    rival_lines = []
    for npc in npcs[:5]:
        rival_lines.append(f"• **{npc['name']}** ({npc['team']})  —  {npc['speed']} km/h · Skill {npc['skill']}/10")
    if len(npcs) > 5:
        rival_lines.append(f"*…and {len(npcs) - 5} more rivals*")

    e = discord.Embed(
        title=f"🏎️  Match {match_num} — {track['flag']} {track['name']}",
        description=(
            f"**Circuit:** {track['circuit']}\n"
            f"**Type:** {track['type']}\n"
            f"**Difficulty:** {meta['emoji']} {meta['label']}\n\n"
            f"Recommended speed: **{meta['rec_speed']} km/h** · Skill: **{meta['rec_skill']}/10**"
        ),
        color=meta["color"],
    )
    e.add_field(
        name="🏎️  Your Setup",
        value=(
            f"**Car:** {car_snap.get('name', '?')}  —  **{boosted_speed} km/h** (upgraded)\n"
            f"**Driver:** {drv_snap.get('name', '?')}  —  Skill {drv_snap.get('skill', '?')}/10"
        ),
        inline=False,
    )
    e.add_field(
        name=f"👥  Field Preview ({len(npcs)} rivals)",
        value="\n".join(rival_lines) or "*No rivals listed*",
        inline=False,
    )
    e.add_field(
        name="🎮  Race Format",
        value=(
            "**3 Laps · 12 Turns**\n"
            "⚡ Reaction challenges appear in **this channel** — click fast!\n"
            "🛑 Tactical decisions appear in **this channel** — choose wisely!"
        ),
        inline=False,
    )
    e.set_footer(text=f"Match {match_num} / {TOTAL_MATCHES}  ·  Press Start Race when ready")
    return e


def race_result_embed(
    standings: List[Dict],
    position: int,
    coins: int,
    points: int,
    track: Dict,
    qte_hits: int,
    qte_total: int,
    pit_hits: int,
    state: Dict,
) -> discord.Embed:
    diff  = track["difficulty"]
    meta  = DIFF_META[diff]
    pos_e = POS_EMOJIS.get(position, f"P{position}")

    color = 0x00b894 if position <= 3 else (0xfdcb6e if position <= 8 else 0xe17055)

    e = discord.Embed(
        title=f"🏁  Race Finished — {track['flag']} {track['name']}",
        color=color,
    )
    e.add_field(
        name="🏆  Your Result",
        value=(
            f"**Position:** {pos_e}  (P{position})\n"
            f"**Championship Points:** +{points} pts\n"
            f"**Coins Earned:** +{coins:,} 🪙"
        ),
        inline=False,
    )

    if standings:
        top_lines = []
        for s in standings[:8]:
            p    = s["position"]
            icon = POS_EMOJIS.get(p, f"P{p}")
            name = s["name"]
            gap  = s.get("gap_str", "")
            mark = "  ◄ **YOU**" if s.get("is_player") else ""
            top_lines.append(f"{icon}  **{name}**{f'  `{gap}`' if gap else ''}{mark}")
        e.add_field(name="📋  Race Standings", value="\n".join(top_lines), inline=False)

    react_str = f"{qte_hits}/{qte_total}" if qte_total else "—"
    e.add_field(
        name="📊  Performance",
        value=(
            f"⚡ Reactions: **{react_str}** hit\n"
            f"⛽ Pit decisions: **{pit_hits}**\n"
            f"🌤️ Conditions: {state.get('weather', 'Clear').title()}"
        ),
        inline=True,
    )
    e.add_field(
        name="🗺️  Track",
        value=(
            f"{track['flag']} {track['name']}\n"
            f"*{track['circuit']}*\n"
            f"{meta['emoji']} {meta['label']}"
        ),
        inline=True,
    )
    e.set_footer(text="Use /matches to see your season schedule · /career_match to race again")
    return e


# ═══════════════════════════════════════════════════════════
#  CAREER RACE — MAIN ENGINE
# ═══════════════════════════════════════════════════════════

async def run_career_race(
    channel,
    msg_obj,
    user: discord.Member,
    player_id: str,
    match_num: int,
    car_snap: Dict,
    drv_snap: Dict,
    upgrades: Dict,
) -> Dict:
    track = get_track(match_num)
    diff  = track["difficulty"]
    npcs  = get_race_npcs(match_num)

    speed_mult   = 1.0 + upgrades.get("engine", 0) * 0.03
    accel_mult   = 1.0 + upgrades.get("acceleration", 0) * 0.025
    brake_mult   = 1.0 + upgrades.get("brakes", 0) * 0.015
    player_speed = car_snap.get("top_speed", 350) * speed_mult
    player_skill = float(drv_snap.get("skill", 7.0))

    npc_speeds = [float(n["speed"]) for n in npcs]
    avg_npc    = sum(npc_speeds) / len(npc_speeds) if npc_speeds else 350.0

    fuel      = 100.0
    tire_wear = 0.0
    weather   = "clear"

    player_total_time = 0.0
    npc_times: List[float] = [0.0] * len(npcs)

    qte_hits  = 0
    qte_total = 0
    pit_hits  = 0
    commentary_lines: List[str] = []

    FUEL_BURN  = {"accelerate": 5.5, "same_speed": 3.5, "slow_down": 2.0, "pit_stop": 0.0}
    WEAR_RATE  = {"accelerate": 9.0, "same_speed": 5.5, "slow_down": 3.0, "pit_stop": 0.0}

    def _player_turn_time(choice: str) -> float:
        base = 90.0 * (avg_npc / max(player_speed, 1))
        skill_bonus = (player_skill - 7.0) * 0.08
        wear_pen    = tire_wear * 0.012
        fuel_pen    = max(0, (50 - fuel)) * 0.008
        choice_mod  = {"accelerate": -0.5, "same_speed": 0.0, "slow_down": 0.3, "pit_stop": 4.0}.get(choice, 0)
        brake_bonus = -brake_mult * 0.05
        jitter      = random.uniform(-0.3, 0.3)
        return base + choice_mod - skill_bonus + wear_pen + fuel_pen + brake_bonus + jitter

    def _npc_turn_time(npc: Dict) -> float:
        base = 90.0
        skill_bonus = (float(npc["skill"]) - 7.0) * 0.08
        speed_ratio = float(npc["speed"]) / max(avg_npc, 1)
        jitter = random.uniform(-0.25, 0.35)
        return base / speed_ratio - skill_bonus + jitter

    def _pos_color(pos: int) -> int:
        if pos <= 3:   return 0x00b894   # green  — podium
        if pos <= 8:   return 0xfdcb6e   # amber  — points
        return 0xe17055                   # red    — out of points

    def _fmt_gap(seconds: float) -> str:
        """Format a gap like real F1 timing — tenths/hundredths for tight gaps, lapped if huge."""
        if seconds < 0:
            return "LEADER"
        if seconds > 90:
            return "✖ LAPPED"
        if seconds < 10:
            return f"+{seconds:.3f}s"
        return f"+{seconds:.2f}s"

    def _live_timing_board() -> str:
        """F1-style timing tower — sorted by accumulated time, player highlighted."""
        field: List[Dict] = []
        for i, npc in enumerate(npcs):
            field.append({"name": npc["name"], "team": npc["team"], "time": npc_times[i], "is_player": False})
        field.append({"name": user.display_name, "team": "YOU", "time": player_total_time, "is_player": True})
        field.sort(key=lambda x: x["time"])

        leader_time = field[0]["time"]
        player_pos  = next((i + 1 for i, c in enumerate(field) if c["is_player"]), len(field))

        pos_icons = {1: "🥇", 2: "🥈", 3: "🥉"}

        # Determine which rows to show: always P1-P3, then player ± 2 context rows
        show_indices: List[int] = list(range(min(3, len(field))))  # P1–P3 (0-indexed)
        p_idx = player_pos - 1
        for offset in [-2, -1, 0, 1, 2]:
            idx = p_idx + offset
            if 3 <= idx < len(field):
                show_indices.append(idx)
        show_indices = sorted(set(show_indices))

        lines: List[str] = []
        prev_idx = -1
        for idx in show_indices:
            # Insert gap-row when there's a skip in positions
            if prev_idx != -1 and idx > prev_idx + 1:
                lines.append("` ·   ···················· `")
            prev_idx = idx

            car    = field[idx]
            pos    = idx + 1
            icon   = pos_icons.get(pos, f"P{pos:02d}")
            gap    = _fmt_gap(car["time"] - leader_time)
            name   = car["name"][:13].ljust(13)
            if car["is_player"]:
                lines.append(f"`{icon}` **{name}** ◄  `{gap}`")
            else:
                lines.append(f"`{icon}` {name}  `{gap}`")

        return "\n".join(lines)

    def _build_race_embed(turn_num: int, choice_made: Optional[str] = None) -> discord.Embed:
        lap = min(((turn_num - 1) // 4) + 1, 3)

        # Compute actual player position
        all_times   = npc_times + [player_total_time]
        sorted_times = sorted(all_times)
        est_pos      = sorted_times.index(player_total_time) + 1
        total_cars   = len(all_times)
        color        = _pos_color(est_pos)

        # Gap to leader (first car)
        leader_time = min(all_times)
        gap_to_lead = player_total_time - leader_time
        if gap_to_lead <= 0:
            pos_line = f"🏆 **P{est_pos} / {total_cars}**  —  **LEADER**"
        elif gap_to_lead > 90:
            pos_line = f"⚠️ **P{est_pos} / {total_cars}**  —  `✖ LAPPED`"
        else:
            pos_line = f"📍 **P{est_pos} / {total_cars}**  —  `{_fmt_gap(gap_to_lead)}` from leader"

        w_icon = "🌧️ Rain" if weather == "rain" else "☀️ Clear"
        choice_label = {
            "accelerate": "🔥 Pushed Hard",
            "same_speed": "➡️ Maintained",
            "slow_down":  "🛑 Lifted Off",
            "pit_stop":   "🔧 Pit Stop",
        }.get(choice_made or "", "")

        # Last 2 commentary lines
        cmt_block = "\n".join(commentary_lines[-2:]) if commentary_lines else "*Race underway…*"

        e = discord.Embed(
            title=f"🏎️  {track['flag']} {track['name']}",
            color=color,
        )
        e.description = (
            f"**Lap {lap} / 3  ·  Turn {turn_num} / {CAREER_TURNS}**  ·  {w_icon}\n"
            f"{_fuel_bar(fuel)}  ·  {_tyre_bar(tire_wear)}\n"
            f"{pos_line}\n\n"
            f"**📊 LIVE TIMING**\n"
            f"{_live_timing_board()}\n\n"
            f"{'─' * 30}\n"
            f"{cmt_block}"
        )
        footer_parts = [f"Match {match_num} / {TOTAL_MATCHES}"]
        if choice_label:
            footer_parts.append(choice_label)
        e.set_footer(text="  ·  ".join(footer_parts))
        e.set_thumbnail(url=CAREER_RACE_GIF)
        return e

    try:
        for turn_num in range(1, CAREER_TURNS + 1):
            lap = ((turn_num - 1) // 4) + 1
            player_choice: Optional[str] = None

            # ── Random weather event ───────────────────────────────────
            if random.random() < 0.05 and weather == "clear":
                weather = "rain"
                commentary_lines.append("🌧️ Rain begins to fall — conditions changing fast.")

            # ─────────────────────────────────────────────────────────
            # SCENARIO TURN  (turns 3, 6, 9, 11)
            # Show a clean decision embed — NO reaction on these turns
            # ─────────────────────────────────────────────────────────
            if turn_num in CAREER_RACE_SCENARIOS:
                scenario = CAREER_RACE_SCENARIOS[turn_num].copy()
                if weather == "rain" and turn_num in (6, 9):
                    scenario = {
                        "id": "rain_call",
                        "title": "🌧️  Weather Gamble!",
                        "description": (
                            "Rain is falling and slick tyres are becoming dangerous.\n"
                            "Box for wet tyres and lose track position, or gamble on the drying line?"
                        ),
                        "question": "Make the call — time is running out.",
                        "options": [
                            {"label": "🌧️ Box for Wets",   "value": "pit_stop",   "style": discord.ButtonStyle.primary},
                            {"label": "🎰 Stay on Slicks", "value": "same_speed", "style": discord.ButtonStyle.danger},
                        ],
                    }

                sv = CareerScenarioView(user, scenario)

                w_icon = "🌧️ Rain" if weather == "rain" else "☀️ Clear"
                scen_emb = discord.Embed(
                    title=scenario["title"],
                    color=0xF39C12,
                )
                scen_emb.description = (
                    f"{scenario['description']}\n\n"
                    f"*{scenario['question']}*\n\n"
                    f"{'─' * 30}\n"
                    f"{_fuel_bar(fuel)}  ·  {_tyre_bar(tire_wear)}  ·  {w_icon}  ·  Lap {lap}/3"
                )
                scen_emb.set_footer(text=f"⏱️  30 seconds to decide  ·  Turn {turn_num}/{CAREER_TURNS}")

                try:
                    await msg_obj.edit(embed=scen_emb, view=sv)
                except Exception:
                    pass

                try:
                    await asyncio.wait_for(sv.chosen.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass

                player_choice = sv.choice or "same_speed"
                if player_choice == "pit_stop":
                    pit_hits += 1

            # ─────────────────────────────────────────────────────────
            # AUTO TURN  (all other turns)
            # Smart choice based on car state
            # ─────────────────────────────────────────────────────────
            else:
                if tire_wear > 75 or fuel < 25:
                    player_choice = random.choices(
                        ["accelerate", "same_speed", "slow_down"],
                        weights=[0.15, 0.55, 0.30],
                    )[0]
                elif tire_wear > 50 or fuel < 50:
                    player_choice = random.choices(
                        ["accelerate", "same_speed", "slow_down"],
                        weights=[0.25, 0.55, 0.20],
                    )[0]
                else:
                    player_choice = random.choices(
                        ["accelerate", "same_speed", "slow_down"],
                        weights=[0.35, 0.50, 0.15],
                    )[0]

            # ── Apply consumables ──────────────────────────────────────
            if player_choice == "pit_stop":
                fuel      = 100.0
                tire_wear = 0.0
                commentary_lines.append("🔧 **Box, box!** Fresh tyres and full fuel — back out clean.")
            else:
                fuel      = max(0.0, fuel      - FUEL_BURN.get(player_choice, 3.5))
                tire_wear = min(100.0, tire_wear + WEAR_RATE.get(player_choice, 5.5))

            # ── Calculate turn times ───────────────────────────────────
            p_time = _player_turn_time(player_choice)
            player_total_time += p_time
            for i, npc in enumerate(npcs):
                npc_times[i] += _npc_turn_time(npc)

            # ── Add context-aware commentary ───────────────────────────
            npc_avg_now = sum(npc_times) / max(len(npc_times), 1)
            cmt = _pick_commentary(
                turn_num, fuel, tire_wear, weather,
                player_total_time, npc_avg_now, player_choice,
            )
            commentary_lines.append(cmt)

            # ── Update the main race embed ─────────────────────────────
            try:
                await msg_obj.edit(
                    embed=_build_race_embed(turn_num, player_choice),
                    view=None,
                )
            except Exception:
                pass

            # ─────────────────────────────────────────────────────────
            # REACTION CHALLENGE
            # Appears exactly 6 seconds after the turn update.
            # Nothing else is shown during the reaction window.
            # ─────────────────────────────────────────────────────────
            if turn_num in REACTION_TURNS:
                # 6-second breathing gap — tension builds
                await asyncio.sleep(6)

                qte_total += 1
                direction = random.choice(REACTION_DIRECTIONS)
                dir_label = REACTION_LABELS[direction]

                # Map direction to a large, clean visual
                dir_visual = {
                    "left":  "◀",
                    "right": "▶",
                    "up":    "▲",
                    "down":  "▼",
                }.get(direction, "?")

                react_emb = discord.Embed(
                    title="⚡  REACTION CHALLENGE!",
                    color=0xF1C40F,
                )
                react_emb.description = (
                    f"{user.mention} — **REACT NOW!**\n\n"
                    f"```\n"
                    f"   {dir_visual}  {dir_label}\n"
                    f"```\n"
                    f"*❌ Wrong direction = +2.0s penalty*\n"
                    f"*⏱️ No click = +0.3s penalty*"
                )
                react_emb.set_footer(text="⏱️  5 seconds — GO!")

                rv   = CareerReactionView(direction, user)
                rmsg = None
                try:
                    rmsg = await channel.send(embed=react_emb, view=rv)
                except Exception:
                    rv.done.set()

                try:
                    await asyncio.wait_for(rv.done.wait(), timeout=5.2)
                except asyncio.TimeoutError:
                    rv.stop()

                # Collapse the reaction message
                if rmsg:
                    try:
                        if rv.result:
                            correct, elapsed = rv.result
                            if correct:
                                await rmsg.edit(
                                    embed=discord.Embed(
                                        description=f"✅  **Nailed it!**  `{elapsed:.2f}s` — **+0.5s** speed boost! 🚀",
                                        color=0x00b894,
                                    ),
                                    view=None,
                                )
                            else:
                                await rmsg.edit(
                                    embed=discord.Embed(
                                        description=f"❌  **Wrong direction!**  **+2.0s** penalty. 💀",
                                        color=0xe17055,
                                    ),
                                    view=None,
                                )
                        else:
                            await rmsg.edit(
                                embed=discord.Embed(
                                    description=f"⏱️  **Too slow!**  **+0.3s** penalty.",
                                    color=0x636e72,
                                ),
                                view=None,
                            )
                    except Exception:
                        pass

                # Apply reaction result to race time + commentary
                if rv.result:
                    correct, elapsed = rv.result
                    if correct:
                        qte_hits += 1
                        player_total_time -= 0.5
                        commentary_lines.append(
                            f"⚡ Reaction in `{elapsed:.2f}s` — **speed boost applied!** 🚀"
                        )
                    else:
                        player_total_time += 2.0
                        commentary_lines.append(
                            "❌ Wrong direction — **+2.0s penalty!** That's going to hurt."
                        )
                else:
                    player_total_time += 0.3
                    commentary_lines.append(
                        "⏱️ Missed the reaction window — **+0.3s penalty** applied."
                    )

                # Update main embed with reaction result baked in
                try:
                    await msg_obj.edit(
                        embed=_build_race_embed(turn_num, player_choice),
                        view=None,
                    )
                except Exception:
                    pass

                await asyncio.sleep(2)

            else:
                # Non-reaction auto turns: brief pause before next
                await asyncio.sleep(3)

    except Exception as e:
        commentary_lines.append(f"⚠️ Race interrupted: {e}")

    # ── Calculate Final Position ────────────────────────────────────────
    field: List[Dict] = []
    for i, npc in enumerate(npcs):
        field.append({"name": npc["name"], "time": npc_times[i], "is_player": False})
    field.append({"name": user.display_name, "time": player_total_time, "is_player": True})
    field.sort(key=lambda x: x["time"])

    position = 1
    standings = []
    leader_time = field[0]["time"] if field else player_total_time
    for i, car in enumerate(field, 1):
        gap_secs = car["time"] - leader_time
        gap_str  = "LEADER" if i == 1 else f"+{gap_secs:.3f}s"
        if car["is_player"]:
            position = i
        standings.append({
            "position":  i,
            "name":      car["name"],
            "gap_str":   gap_str,
            "is_player": car["is_player"],
        })

    points = CAREER_PTS.get(position, 0)
    coins  = RACE_PAYOUT.get(position, 10)

    return {
        "match_num": match_num,
        "standings": standings,
        "position":  position,
        "coins":     coins,
        "points":    points,
        "track":     track,
        "qte_hits":  qte_hits,
        "qte_total": qte_total,
        "pit_hits":  pit_hits,
        "state":     {"weather": weather, "fuel": fuel, "tire_wear": tire_wear},
    }


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

    lines = []
    for pos, pack, coins, special in rows:
        mark = " ◄" if pos == player_pos else ""
        lines.append(f"**P{pos}** — {pack}  ·  {coins}{(f'  ·  {special}') if special != '—' else ''}{mark}")

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
