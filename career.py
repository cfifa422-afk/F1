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

CAREER_LAPS   = 3
CAREER_TURNS  = 12

SCENARIO_TURNS  = {3, 6, 9, 11}
REACTION_TURNS  = [1, 2, 4, 5, 7, 8, 10]

COMMENTARY = [
    "The car is looking quick through the high-speed section.",
    "Tyre degradation starting to become visible.",
    "Gap holding steady — consistent pace from your side.",
    "The rivals are pushing hard — no room for mistakes.",
]

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

    e = discord.Embed(
        title=f"📅  Season Schedule — {done}/{TOTAL_MATCHES} Completed",
        color=0x0984e3,
    )
    for i, line in enumerate(lines[:15]):
        if i == 0:
            e.add_field(name="Races", value="\n".join(lines[:8]), inline=False)
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
