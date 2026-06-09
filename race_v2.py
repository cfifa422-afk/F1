"""
/race engine — mirrors career match style.
Two-player head-to-head: reaction challenges, occasional sequence sprints, tactical decisions.
Wrong reaction/sequence = +3s penalty. Correct = no change. Tactical choices affect lap time.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import discord

# ─────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────

ARROWS       = ["up", "down", "left", "right"]
ARROW_LABELS = {"up": "▲  UP", "down": "▼  DOWN", "left": "◀  LEFT", "right": "RIGHT  ▶"}
ARROW_VISUAL = {"up": "▲", "down": "▼", "left": "◀", "right": "▶"}

TOTAL_LAPS   = 3
TOTAL_TURNS  = 12

SCENARIO_TURNS  = {3, 6, 9, 11}
SEQUENCE_CHANCE = 0.30          # 30 % of reaction turns become sequence sprints
WRONG_PENALTY   = 3.0           # seconds added for wrong/missed reaction

FUEL_BURN = {"accelerate": 5.5, "same_speed": 3.5, "slow_down": 2.0, "pit_stop": 0.0}
WEAR_RATE = {"accelerate": 9.0, "same_speed": 5.5, "slow_down": 3.0, "pit_stop": 0.0}

C_GREEN  = 0x00b894
C_AMBER  = 0xfdcb6e
C_RED    = 0xe17055
C_DARK   = 0x2d3436
C_PURPLE = 0x6c5ce7
C_YELLOW = 0xF1C40F

RACE_GIF = "https://gifdb.com/images/thumbnail/f1-formula1-gif-qm0m61l3z6ydteoo.gif"

RACE_SCENARIOS: Dict[int, Dict] = {
    3: {
        "title": "🛑  Pit Window Open!",
        "description": "**Lap 1 complete.** Fresh rubber could be decisive — but staying out preserves track position.",
        "question": "Do you pit for fresh tyres, or push on?",
        "options": [
            {"label": "⛽ Pit Now",    "value": "pit_stop",   "style": discord.ButtonStyle.danger},
            {"label": "🏎️ Stay Out",  "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
    6: {
        "title": "💨  DRS Zone — Attack or Manage!",
        "description": "**Mid-race.** The DRS zone opens up. Go flat out or protect your tyres?",
        "question": "Maximum attack or conserve?",
        "options": [
            {"label": "🔥 Max Attack",   "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Conserve",    "value": "slow_down",  "style": discord.ButtonStyle.secondary},
        ],
    },
    9: {
        "title": "🚗  Late Race Strategy!",
        "description": "**Final third.** Tyre wear is critical. Every call is race-defining.",
        "question": "Push hard, manage tyres, or emergency stop?",
        "options": [
            {"label": "🔥 Push Hard",     "value": "accelerate", "style": discord.ButtonStyle.success},
            {"label": "⏱️ Manage Tyres", "value": "slow_down",  "style": discord.ButtonStyle.secondary},
            {"label": "⛽ Emergency Pit", "value": "pit_stop",   "style": discord.ButtonStyle.danger},
        ],
    },
    11: {
        "title": "🏁  FINAL LAP!",
        "description": "**The white flag is out.** Make it count.",
        "question": "Flat out or protect the gap?",
        "options": [
            {"label": "🔥 FLAT OUT!",        "value": "accelerate", "style": discord.ButtonStyle.danger},
            {"label": "🛡️ Protect the Gap", "value": "same_speed", "style": discord.ButtonStyle.success},
        ],
    },
}

RAIN_SCENARIO = {
    "title": "🌧️  Weather Gamble!",
    "description": "Rain is falling — pit for wets or gamble on the drying line?",
    "question": "Make the call.",
    "options": [
        {"label": "🌧️ Box for Wets",   "value": "pit_stop",   "style": discord.ButtonStyle.primary},
        {"label": "🎰 Stay on Slicks", "value": "same_speed", "style": discord.ButtonStyle.danger},
    ],
}


# ─────────────────────────────────────────────────────────────
#  State
# ─────────────────────────────────────────────────────────────

@dataclass
class RaceV2State:
    p1_id:      str
    p2_id:      str
    p1_name:    str
    p2_name:    str
    p1_car:     object
    p1_driver:  object
    p2_car:     object
    p2_driver:  object
    p1_synergy: bool = False
    p2_synergy: bool = False

    lap:     int   = 1
    segment: int   = 0
    gap:     float = 0.0
    weather: str   = "clear"
    p1_fuel: float = 100.0
    p2_fuel: float = 100.0

    p1_wrong_streak: int = 0
    p2_wrong_streak: int = 0
    p1_total_correct: int = 0
    p2_total_correct: int = 0
    p1_total_wrong:   int = 0
    p2_total_wrong:   int = 0
    p1_drag_wins:     int = 0
    p2_drag_wins:     int = 0
    p1_battles_won:   int = 0
    p2_battles_won:   int = 0

    dnf:    Optional[str] = None
    winner: Optional[str] = None
    events: List[str]     = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _fuel_bar(fuel: float) -> str:
    filled = max(0, min(5, int(fuel / 20)))
    icon = "🟢" if fuel > 50 else ("🟡" if fuel > 25 else "🔴")
    return f"{icon} `{'█' * filled}{'░' * (5 - filled)}` {fuel:.0f}%"


def _tyre_bar(wear: float) -> str:
    health = 100.0 - wear
    filled = max(0, min(5, int(health / 20)))
    icon = "🟢" if health > 60 else ("🟡" if health > 30 else "🔴")
    return f"{icon} `{'█' * filled}{'░' * (5 - filled)}` {health:.0f}%"


def _gap_line(gap: float, p1_name: str, p2_name: str) -> str:
    """gap = p1_time - p2_time; negative means p1 leads."""
    ag = abs(gap)
    if ag < 0.05:
        return "🏎️ **DEAD HEAT** — anything can happen!"
    if gap < 0:
        return f"📍 **{p1_name}** leads by `+{ag:.3f}s`"
    return f"📍 **{p2_name}** leads by `+{ag:.3f}s`"


# ─────────────────────────────────────────────────────────────
#  Race Accept View
# ─────────────────────────────────────────────────────────────

class RaceAcceptView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent   = opponent
        self.accepted   = False
        self.done       = asyncio.Event()

    @discord.ui.button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.accepted = True
        self.done.set()
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.opponent.id, self.challenger.id):
            await interaction.response.send_message("Not your race!", ephemeral=True)
            return
        self.done.set()
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        self.done.set()


# ─────────────────────────────────────────────────────────────
#  Two-player Reaction View  (single direction)
# ─────────────────────────────────────────────────────────────

class TwoPlayerReactionView(discord.ui.View):
    """
    Shows 4 direction buttons. Both p1 and p2 click independently.
    Wrong direction → +3 s penalty. Correct → no change.
    """

    def __init__(self, direction: str, p1_id: str, p2_id: str):
        super().__init__(timeout=5.0)
        self.direction = direction
        self.p1_id     = p1_id
        self.p2_id     = p2_id

        self.p1_result: Optional[bool] = None   # True = correct, False = wrong, None = no click
        self.p2_result: Optional[bool] = None
        self._start     = time.time()
        self.both_done  = asyncio.Event()

        dirs = ARROWS.copy()
        random.shuffle(dirs)
        for d in dirs:
            btn = discord.ui.Button(label=ARROW_LABELS[d], style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(d)
            self.add_item(btn)

    def _make_cb(self, clicked: str):
        async def cb(interaction: discord.Interaction):
            uid = str(interaction.user.id)
            is_p1 = uid == self.p1_id
            is_p2 = uid == self.p2_id
            if not (is_p1 or is_p2):
                await interaction.response.send_message("You're not in this race!", ephemeral=True)
                return
            if (is_p1 and self.p1_result is not None) or (is_p2 and self.p2_result is not None):
                await interaction.response.defer()
                return

            elapsed = time.time() - self._start
            correct = (clicked == self.direction)

            if is_p1:
                self.p1_result = correct
            else:
                self.p2_result = correct

            if correct:
                await interaction.response.send_message(
                    f"✅ **Correct!**  `{elapsed:.2f}s` — no penalty.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **Wrong direction!**  `+{WRONG_PENALTY:.0f}s` penalty. 💀", ephemeral=True
                )

            if self.p1_result is not None and self.p2_result is not None:
                self.both_done.set()
                self.stop()
        return cb

    async def on_timeout(self):
        self.both_done.set()


# ─────────────────────────────────────────────────────────────
#  Two-player Sequence View  (4-arrow sprint)
# ─────────────────────────────────────────────────────────────

class TwoPlayerSequenceView(discord.ui.View):
    """
    Both players independently complete a 4-arrow sequence.
    Wrong arrow → immediate +3 s penalty for that player.
    Full correct sequence → no penalty.
    """

    SEQ_LEN = 4

    def __init__(self, sequence: List[str], p1_id: str, p2_id: str):
        super().__init__(timeout=8.0)
        self.sequence  = sequence
        self.p1_id     = p1_id
        self.p2_id     = p2_id

        self.p1_idx   = 0;  self.p2_idx   = 0
        self.p1_done  = False; self.p2_done  = False
        self.p1_wrong = False; self.p2_wrong = False
        self.both_done = asyncio.Event()

        dirs = ARROWS.copy()
        random.shuffle(dirs)
        for d in dirs:
            btn = discord.ui.Button(label=ARROW_LABELS[d], style=discord.ButtonStyle.primary)
            btn.callback = self._make_cb(d)
            self.add_item(btn)

    def _prog(self, idx: int) -> str:
        return "✅" * idx + "⬜" * (self.SEQ_LEN - idx)

    def _make_cb(self, clicked: str):
        async def cb(interaction: discord.Interaction):
            uid = str(interaction.user.id)
            is_p1 = uid == self.p1_id
            is_p2 = uid == self.p2_id
            if not (is_p1 or is_p2):
                await interaction.response.send_message("You're not in this race!", ephemeral=True)
                return

            if is_p1:
                if self.p1_done or self.p1_wrong:
                    await interaction.response.defer()
                    return
                if clicked == self.sequence[self.p1_idx]:
                    self.p1_idx += 1
                    if self.p1_idx == self.SEQ_LEN:
                        self.p1_done = True
                        await interaction.response.send_message(
                            "✅ **Sequence complete!** No penalty.", ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            f"{self._prog(self.p1_idx)}  `{self.p1_idx}/{self.SEQ_LEN}`", ephemeral=True
                        )
                else:
                    self.p1_wrong = True
                    await interaction.response.send_message(
                        f"❌ **Wrong arrow!**  `+{WRONG_PENALTY:.0f}s` penalty.", ephemeral=True
                    )
            else:
                if self.p2_done or self.p2_wrong:
                    await interaction.response.defer()
                    return
                if clicked == self.sequence[self.p2_idx]:
                    self.p2_idx += 1
                    if self.p2_idx == self.SEQ_LEN:
                        self.p2_done = True
                        await interaction.response.send_message(
                            "✅ **Sequence complete!** No penalty.", ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            f"{self._prog(self.p2_idx)}  `{self.p2_idx}/{self.SEQ_LEN}`", ephemeral=True
                        )
                else:
                    self.p2_wrong = True
                    await interaction.response.send_message(
                        f"❌ **Wrong arrow!**  `+{WRONG_PENALTY:.0f}s` penalty.", ephemeral=True
                    )

            both_resolved = (
                (self.p1_done or self.p1_wrong) and
                (self.p2_done or self.p2_wrong)
            )
            if both_resolved:
                self.both_done.set()
                self.stop()
        return cb

    async def on_timeout(self):
        self.both_done.set()


# ─────────────────────────────────────────────────────────────
#  Two-player Scenario View  (tactical decision)
# ─────────────────────────────────────────────────────────────

class TwoPlayerScenarioView(discord.ui.View):
    """Both players pick a tactical option independently. Wait for both or timeout."""

    def __init__(self, p1: discord.Member, p2: discord.Member, scenario: Dict):
        super().__init__(timeout=30)
        self.p1_id = str(p1.id)
        self.p2_id = str(p2.id)
        self.p1_choice: Optional[str] = None
        self.p2_choice: Optional[str] = None
        self.both_done = asyncio.Event()

        for opt in scenario["options"]:
            btn   = discord.ui.Button(label=opt["label"], style=opt["style"])
            value = opt["value"]
            label = opt["label"]

            async def _cb(interaction: discord.Interaction, _v=value, _l=label):
                uid = str(interaction.user.id)
                if uid == self.p1_id:
                    if self.p1_choice:
                        await interaction.response.defer()
                        return
                    self.p1_choice = _v
                    await interaction.response.send_message(f"✅ **{_l}** locked in!", ephemeral=True)
                elif uid == self.p2_id:
                    if self.p2_choice:
                        await interaction.response.defer()
                        return
                    self.p2_choice = _v
                    await interaction.response.send_message(f"✅ **{_l}** locked in!", ephemeral=True)
                else:
                    await interaction.response.send_message("This isn't your race!", ephemeral=True)
                    return

                if self.p1_choice and self.p2_choice:
                    self.both_done.set()
                    self.stop()

            btn.callback = _cb
            self.add_item(btn)

    async def on_timeout(self):
        self.both_done.set()


# ─────────────────────────────────────────────────────────────
#  Embeds
# ─────────────────────────────────────────────────────────────

def build_challenge_embed_v2(
    challenger: discord.Member,
    opponent:   discord.Member,
    p1_car,
    p1_driver,
    p2_car,
    p2_driver,
    synergy1,
    synergy2,
) -> discord.Embed:
    from cards import RARITY_EMOJIS
    d1_e = RARITY_EMOJIS.get(p1_driver.rarity, "")
    c1_e = RARITY_EMOJIS.get(p1_car.rarity,    "")
    d2_e = RARITY_EMOJIS.get(p2_driver.rarity,  "")
    c2_e = RARITY_EMOJIS.get(p2_car.rarity,     "")

    e = discord.Embed(
        title="⚡  Race Challenge!",
        description=(
            f"{challenger.mention} is challenging {opponent.mention}!\n"
            f"*{opponent.display_name} has 60 seconds to accept or decline.*"
        ),
        color=C_DARK,
    )
    p1_val = (
        f"{d1_e} **{p1_driver.name}** ({p1_driver.code})  ·  Skill {p1_driver.skill}/10\n"
        f"{c1_e} **{p1_car.name}**  ·  {p1_car.top_speed} km/h"
    )
    if synergy1:
        p1_val += f"\n✨ *{synergy1['name']}*"

    p2_val = (
        f"{d2_e} **{p2_driver.name}** ({p2_driver.code})  ·  Skill {p2_driver.skill}/10\n"
        f"{c2_e} **{p2_car.name}**  ·  {p2_car.top_speed} km/h"
    )
    if synergy2:
        p2_val += f"\n✨ *{synergy2['name']}*"

    e.add_field(name=f"🏎️  {challenger.display_name}", value=p1_val, inline=True)
    e.add_field(name=f"🏎️  {opponent.display_name}",   value=p2_val, inline=True)
    e.add_field(
        name="🎮  Race Format",
        value=(
            "**3 Laps · 12 Turns**\n"
            "⚡ Reaction challenges — click the right arrow fast!\n"
            "🔢 Sequence sprints — enter all 4 arrows in order!\n"
            "🛑 Tactical decisions — pit, push, or conserve!\n"
            f"❌ Wrong answer = **+{WRONG_PENALTY:.0f}s penalty**"
        ),
        inline=False,
    )
    e.set_image(url=RACE_GIF)
    e.set_footer(text="3 Laps · 12 Turns · May the best driver win!")
    return e


def build_result_embed(
    result:  Dict,
    p1:      discord.Member,
    p2:      discord.Member,
    state:   RaceV2State,
) -> discord.Embed:
    winner_id = result.get("winner")
    if winner_id == "p1":
        title = f"🏁  {p1.display_name} wins!"
        color = C_GREEN
    elif winner_id == "p2":
        title = f"🏁  {p2.display_name} wins!"
        color = C_RED
    else:
        title = "🏁  Dead heat — it's a draw!"
        color = C_AMBER

    e = discord.Embed(title=title, color=color)

    p1t = result["p1_time"]
    p2t = result["p2_time"]
    gap = abs(p1t - p2t)

    e.add_field(
        name=f"{'🥇' if winner_id == 'p1' else '🥈'} {p1.display_name}",
        value=(
            f"Reactions hit: **{result['p1_hits']}/{result['p1_challenges']}**\n"
            f"Penalties: **{result['p1_penalties']}×**  (+{result['p1_penalty_time']:.0f}s total)"
        ),
        inline=True,
    )
    e.add_field(
        name=f"{'🥇' if winner_id == 'p2' else '🥈'} {p2.display_name}",
        value=(
            f"Reactions hit: **{result['p2_hits']}/{result['p2_challenges']}**\n"
            f"Penalties: **{result['p2_penalties']}×**  (+{result['p2_penalty_time']:.0f}s total)"
        ),
        inline=True,
    )
    e.add_field(
        name="📊  Race Summary",
        value=(
            f"Winning margin: `{gap:.3f}s`  ·  Weather: {result.get('weather', 'clear').title()}\n"
            f"💰 {p1.display_name}: **+{result['p1_coins']:,}** coins\n"
            f"💰 {p2.display_name}: **+{result['p2_coins']:,}** coins"
        ),
        inline=False,
    )
    e.set_footer(text="Use /race to challenge again  ·  /garage to upgrade  ·  /career to join career mode")
    return e


# ─────────────────────────────────────────────────────────────
#  Main Race Engine
# ─────────────────────────────────────────────────────────────

async def run_race(
    channel,
    p1:    discord.Member,
    p2:    discord.Member,
    state: RaceV2State,
) -> Dict:

    p1_total_time = 0.0
    p2_total_time = 0.0
    p1_fuel = 100.0;  p2_fuel = 100.0
    p1_wear = 0.0;    p2_wear = 0.0
    weather = "clear"
    commentary: List[str] = []

    p1_hits = 0;         p2_hits = 0
    p1_penalties = 0;    p2_penalties = 0
    p1_penalty_time = 0.0; p2_penalty_time = 0.0
    challenge_count = 0

    # ── Lap time formula ─────────────────────────────────────
    def _turn_time(car, driver, fuel: float, wear: float, choice: str) -> float:
        base       = 90.0 * (350.0 / max(car.top_speed, 1))
        skill_b    = (float(driver.skill) - 7.0) * 0.08
        wear_pen   = wear * 0.012
        fuel_pen   = max(0.0, (50.0 - fuel)) * 0.008
        choice_mod = {"accelerate": -0.5, "same_speed": 0.0,
                      "slow_down": 0.3,   "pit_stop": 4.0}.get(choice, 0.0)
        jitter = random.uniform(-0.25, 0.25)
        return base + choice_mod - skill_b + wear_pen + fuel_pen + jitter

    # ── Live embed ────────────────────────────────────────────
    def _build_embed(turn: int, p1_choice=None, p2_choice=None) -> discord.Embed:
        lap   = min(((turn - 1) // 4) + 1, 3) if turn > 0 else 1
        w_ico = "🌧️ Rain" if weather == "rain" else "☀️ Clear"
        gap   = p1_total_time - p2_total_time   # negative = p1 leads

        ag = abs(gap)
        if ag < 0.5:
            color = C_AMBER
        elif gap < 0:
            color = C_GREEN   # p1 ahead
        else:
            color = C_RED     # p2 ahead

        choice_lbl = {
            "accelerate": "🔥 Pushed Hard",
            "same_speed": "➡️ Maintained Pace",
            "slow_down":  "🛑 Lifted Off",
            "pit_stop":   "🔧 Pit Stop",
        }
        p1_cl = choice_lbl.get(p1_choice or "", "")
        p2_cl = choice_lbl.get(p2_choice or "", "")

        cmt = "\n".join(commentary[-2:]) if commentary else "*Race underway…*"

        e = discord.Embed(
            title=f"🏎️  {p1.display_name} vs {p2.display_name}",
            color=color,
        )
        e.description = (
            f"**Lap {lap}/3  ·  Turn {turn}/{TOTAL_TURNS}**  ·  {w_ico}\n\n"
            f"**{p1.display_name}**\n"
            f"⛽ {_fuel_bar(p1_fuel)}  ·  🏎️ {_tyre_bar(p1_wear)}\n"
            + (f"*{p1_cl}*\n" if p1_cl else "")
            + f"\n**{p2.display_name}**\n"
            f"⛽ {_fuel_bar(p2_fuel)}  ·  🏎️ {_tyre_bar(p2_wear)}\n"
            + (f"*{p2_cl}*\n" if p2_cl else "")
            + f"\n{_gap_line(gap, p1.display_name, p2.display_name)}\n\n"
            f"{'─' * 28}\n"
            f"{cmt}"
        )
        e.set_thumbnail(url=RACE_GIF)
        e.set_footer(text=f"Turn {turn}/{TOTAL_TURNS}  ·  {p1.display_name} vs {p2.display_name}")
        return e

    # ── Initial embed ─────────────────────────────────────────
    msg = await channel.send(embed=_build_embed(0))

    try:
        for turn in range(1, TOTAL_TURNS + 1):
            lap       = ((turn - 1) // 4) + 1
            p1_choice = None
            p2_choice = None

            # ── Random weather ────────────────────────────────
            if random.random() < 0.05 and weather == "clear":
                weather = "rain"
                commentary.append("🌧️ *Rain begins to fall — conditions changing fast!*")

            # ══════════════════════════════════════════════════
            # SCENARIO TURN  (turns 3, 6, 9, 11)
            # ══════════════════════════════════════════════════
            if turn in RACE_SCENARIOS:
                scenario = (
                    RAIN_SCENARIO.copy()
                    if weather == "rain" and turn in (6, 9)
                    else RACE_SCENARIOS[turn].copy()
                )

                sv      = TwoPlayerScenarioView(p1, p2, scenario)
                w_ico   = "🌧️ Rain" if weather == "rain" else "☀️ Clear"

                scen_emb = discord.Embed(title=scenario["title"], color=0xF39C12)
                scen_emb.description = (
                    f"{scenario['description']}\n\n"
                    f"*{scenario['question']}*\n\n"
                    f"{'─' * 28}\n"
                    f"⛽ {_fuel_bar(p1_fuel)} · {_fuel_bar(p2_fuel)}\n"
                    f"{w_ico}  ·  Lap {lap}/3\n\n"
                    f"{p1.mention} & {p2.mention} — **both choose!**"
                )
                scen_emb.set_footer(text=f"⏱️  30 seconds to decide  ·  Turn {turn}/{TOTAL_TURNS}")

                try:
                    await msg.edit(embed=scen_emb, view=sv)
                except Exception:
                    pass

                try:
                    await asyncio.wait_for(sv.both_done.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass

                p1_choice = sv.p1_choice or "same_speed"
                p2_choice = sv.p2_choice or "same_speed"

                if p1_choice == "pit_stop":
                    p1_fuel = 100.0; p1_wear = 0.0
                    commentary.append(f"🔧 **{p1.display_name}** pits! Fresh rubber and full fuel.")
                if p2_choice == "pit_stop":
                    p2_fuel = 100.0; p2_wear = 0.0
                    commentary.append(f"🔧 **{p2.display_name}** pits! Fresh rubber and full fuel.")

            # ══════════════════════════════════════════════════
            # REACTION / SEQUENCE TURN
            # ══════════════════════════════════════════════════
            else:
                p1_choice = "same_speed"
                p2_choice = "same_speed"
                challenge_count += 1
                cmsg = None

                await asyncio.sleep(4)  # brief tension before challenge pops

                # ── Decide challenge type ─────────────────────
                if random.random() < SEQUENCE_CHANCE:
                    # ─── SEQUENCE SPRINT ─────────────────────
                    seq        = [random.choice(ARROWS) for _ in range(TwoPlayerSequenceView.SEQ_LEN)]
                    seq_visual = "  ".join(ARROW_VISUAL[a] for a in seq)

                    ch_emb = discord.Embed(title="🔢  SEQUENCE SPRINT!", color=C_PURPLE)
                    ch_emb.description = (
                        f"{p1.mention} & {p2.mention} — **enter the sequence!**\n\n"
                        f"```\n{seq_visual}\n```\n"
                        f"*Click the arrows in that exact order.*\n"
                        f"✅ Full sequence = no penalty\n"
                        f"❌ Wrong arrow = **+{WRONG_PENALTY:.0f}s** penalty"
                    )
                    ch_emb.set_footer(text="⏱️  8 seconds — GO!")

                    sv2 = TwoPlayerSequenceView(seq, state.p1_id, state.p2_id)
                    try:
                        cmsg = await channel.send(embed=ch_emb, view=sv2)
                    except Exception:
                        sv2.both_done.set()

                    try:
                        await asyncio.wait_for(sv2.both_done.wait(), timeout=8.2)
                    except asyncio.TimeoutError:
                        sv2.stop()

                    p1_pen = not sv2.p1_done
                    p2_pen = not sv2.p2_done

                    if p1_pen:
                        p1_total_time   += WRONG_PENALTY
                        p1_penalties    += 1
                        p1_penalty_time += WRONG_PENALTY
                    else:
                        p1_hits += 1

                    if p2_pen:
                        p2_total_time   += WRONG_PENALTY
                        p2_penalties    += 1
                        p2_penalty_time += WRONG_PENALTY
                    else:
                        p2_hits += 1

                    p1_tag = "✅ Nailed it" if not p1_pen else f"❌ +{WRONG_PENALTY:.0f}s"
                    p2_tag = "✅ Nailed it" if not p2_pen else f"❌ +{WRONG_PENALTY:.0f}s"

                    if cmsg:
                        try:
                            await cmsg.edit(
                                embed=discord.Embed(
                                    description=(
                                        f"🔢 Sequence result — "
                                        f"**{p1.display_name}**: {p1_tag}  ·  "
                                        f"**{p2.display_name}**: {p2_tag}"
                                    ),
                                    color=C_PURPLE,
                                ),
                                view=None,
                            )
                        except Exception:
                            pass

                    commentary.append(
                        f"🔢 Sequence: {p1.display_name} {p1_tag.lower()}, "
                        f"{p2.display_name} {p2_tag.lower()}."
                    )

                else:
                    # ─── SINGLE REACTION CHALLENGE ───────────
                    direction  = random.choice(ARROWS)
                    dir_visual = ARROW_VISUAL[direction]
                    dir_label  = ARROW_LABELS[direction]

                    ch_emb = discord.Embed(title="⚡  REACTION CHALLENGE!", color=C_YELLOW)
                    ch_emb.description = (
                        f"{p1.mention} & {p2.mention} — **REACT NOW!**\n\n"
                        f"```\n   {dir_visual}  {dir_label}\n```\n"
                        f"✅ Correct = no penalty\n"
                        f"❌ Wrong direction = **+{WRONG_PENALTY:.0f}s** penalty"
                    )
                    ch_emb.set_footer(text="⏱️  5 seconds — GO!")

                    rv = TwoPlayerReactionView(direction, state.p1_id, state.p2_id)
                    try:
                        cmsg = await channel.send(embed=ch_emb, view=rv)
                    except Exception:
                        rv.both_done.set()

                    try:
                        await asyncio.wait_for(rv.both_done.wait(), timeout=5.2)
                    except asyncio.TimeoutError:
                        rv.stop()

                    # Apply results
                    if rv.p1_result is True:
                        p1_hits += 1
                    else:
                        p1_total_time   += WRONG_PENALTY
                        p1_penalties    += 1
                        p1_penalty_time += WRONG_PENALTY

                    if rv.p2_result is True:
                        p2_hits += 1
                    else:
                        p2_total_time   += WRONG_PENALTY
                        p2_penalties    += 1
                        p2_penalty_time += WRONG_PENALTY

                    def _res_tag(res: Optional[bool]) -> str:
                        if res is True:   return "✅ Correct"
                        if res is False:  return f"❌ Wrong +{WRONG_PENALTY:.0f}s"
                        return f"⏱️ Too slow +{WRONG_PENALTY:.0f}s"

                    p1_tag = _res_tag(rv.p1_result)
                    p2_tag = _res_tag(rv.p2_result)

                    if cmsg:
                        try:
                            await cmsg.edit(
                                embed=discord.Embed(
                                    description=(
                                        f"⚡ Result — "
                                        f"**{p1.display_name}**: {p1_tag}  ·  "
                                        f"**{p2.display_name}**: {p2_tag}"
                                    ),
                                    color=C_YELLOW,
                                ),
                                view=None,
                            )
                        except Exception:
                            pass

                    commentary.append(
                        f"⚡ Reaction: {p1.display_name} {p1_tag.lower()}, "
                        f"{p2.display_name} {p2_tag.lower()}."
                    )

            # ── Consumables ───────────────────────────────────
            _p1c = p1_choice or "same_speed"
            _p2c = p2_choice or "same_speed"
            if _p1c != "pit_stop":
                p1_fuel = max(0.0, p1_fuel - FUEL_BURN.get(_p1c, 3.5))
                p1_wear = min(100.0, p1_wear + WEAR_RATE.get(_p1c, 5.5))
            if _p2c != "pit_stop":
                p2_fuel = max(0.0, p2_fuel - FUEL_BURN.get(_p2c, 3.5))
                p2_wear = min(100.0, p2_wear + WEAR_RATE.get(_p2c, 5.5))

            # ── Lap times ─────────────────────────────────────
            p1_total_time += _turn_time(state.p1_car, state.p1_driver, p1_fuel, p1_wear, _p1c)
            p2_total_time += _turn_time(state.p2_car, state.p2_driver, p2_fuel, p2_wear, _p2c)

            # ── Context commentary ────────────────────────────
            gap = p1_total_time - p2_total_time
            if abs(gap) < 0.5:
                commentary.append("🔥 *Neck and neck — every millisecond counts!*")
            elif gap < -3.0:
                commentary.append(f"💨 {p1.display_name} in full control — `{abs(gap):.2f}s` clear!")
            elif gap > 3.0:
                commentary.append(f"📡 {p2.display_name} pulling away — gap is `{gap:.2f}s`!")

            # ── Update main embed ─────────────────────────────
            try:
                await msg.edit(embed=_build_embed(turn, p1_choice, p2_choice), view=None)
            except Exception:
                pass

            await asyncio.sleep(2)

    except Exception as exc:
        commentary.append(f"⚠️ Race interrupted: {exc}")

    # ─────────────────────────────────────────────────────────
    #  Final result
    # ─────────────────────────────────────────────────────────
    gap = p1_total_time - p2_total_time  # negative = p1 wins
    if abs(gap) < 0.1:
        winner = "draw"
    elif gap < 0:
        winner = "p1"
    else:
        winner = "p2"

    p1_coins = 500 if winner == "p1" else (200 if winner == "draw" else 100)
    p2_coins = 500 if winner == "p2" else (200 if winner == "draw" else 100)

    return {
        "winner":          winner,
        "p1_time":         p1_total_time,
        "p2_time":         p2_total_time,
        "p1_coins":        p1_coins,
        "p2_coins":        p2_coins,
        "p1_hits":         p1_hits,
        "p2_hits":         p2_hits,
        "p1_challenges":   challenge_count,
        "p2_challenges":   challenge_count,
        "p1_penalties":    p1_penalties,
        "p2_penalties":    p2_penalties,
        "p1_penalty_time": p1_penalty_time,
        "p2_penalty_time": p2_penalty_time,
        "weather":         weather,
    }
