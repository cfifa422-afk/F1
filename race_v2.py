"""
Revamped /race system — fully interactive, skill-based, pressure-building.
Gap + position always visible inside every challenge embed.
No external APIs. Pure Discord.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import discord

# ─────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────

ARROWS = ["⬆️", "⬇️", "⬅️", "➡️"]
ARROW_LABEL = {"⬆️": "▲  UP", "⬇️": "▼  DOWN", "⬅️": "◀  LEFT", "➡️": "RIGHT  ▶"}

BATTLE_GAP   = 0.8   # gap (seconds) that triggers battle mode
NECK_GAP     = 0.2   # dead-heat threshold

C_BLUE   = 0x0984e3
C_ORANGE = 0xF39C12
C_PURPLE = 0x6c5ce7
C_RED    = 0xE10600
C_GREEN  = 0x00b894
C_DARK   = 0x2d3436

# 9 segments across 3 laps; battle overrides any segment when gap is close
BASE_SCHEDULE = [
    "arrow",    "drag",  "tactical",
    "arrow",    "drag",  "tactical",
    "arrow",    "drag",  "tactical",
]

FUEL_BURN = {"push": 9.0, "hold": 4.5, "box": 0.0}
DNF_WRONG_LIMIT = 4       # wrong arrows in one challenge → DNF risk


# ─────────────────────────────────────────────────────────────
#  Race State
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
    segment: int   = 0      # 0-indexed (0-8)
    gap:     float = 0.0    # positive = p1 leads, negative = p2 leads
    weather: str   = "clear"

    # Consumables (for tactical realism)
    p1_fuel: float = 100.0
    p2_fuel: float = 100.0

    # Streak tracking
    p1_wrong_streak: int = 0
    p2_wrong_streak: int = 0

    # Stats for results screen
    p1_total_correct: int = 0
    p2_total_correct: int = 0
    p1_total_wrong:   int = 0
    p2_total_wrong:   int = 0
    p1_drag_wins:     int = 0
    p2_drag_wins:     int = 0
    p1_battles_won:   int = 0
    p2_battles_won:   int = 0

    dnf:    Optional[str] = None    # "p1" or "p2"
    winner: Optional[str] = None    # "p1" | "p2" | "draw"
    events: List[str]     = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
#  Embed helpers — gap always baked in
# ─────────────────────────────────────────────────────────────

def _gap_bar(gap: float, p1: str, p2: str) -> str:
    """Compact single-line gap display for every embed."""
    p1s = p1[:9]
    p2s = p2[:9]
    ag = abs(gap)
    if ag < 0.05:
        return f"🏎️ **{p1s}** ══ **DEAD HEAT** ══ **{p2s}** 🏎️"
    filled = min(int(ag / 0.3), 7)
    bar    = "█" * filled + "░" * (7 - filled)
    if gap > 0:
        return f"🏎️ **{p1s}** `+{ag:.2f}s` [{bar}] **{p2s}** 🏎️"
    else:
        return f"🏎️ **{p1s}** [{bar}] `+{ag:.2f}s` **{p2s}** 🏎️"


def _pressure(gap: float) -> str:
    ag = abs(gap)
    if ag < NECK_GAP:
        return "🔴 **NECK AND NECK** — one mistake ends it!"
    if ag < BATTLE_GAP:
        return "🟠 **CLOSE RACE** — battle incoming!"
    if ag < 1.8:
        return "🟡 Tight — stay focused"
    return "🟢 Comfortable gap"


def _weather(w: str) -> str:
    return "🌧️ **RAIN**" if w == "rain" else "☀️ Clear"


def race_header(state: RaceV2State) -> str:
    """3-line block included in the description of EVERY challenge embed."""
    lap_s  = f"Lap {state.lap}/3  ·  Seg {(state.segment % 3) + 1}/3"
    fuel_s = f"⛽ {state.p1_fuel:.0f}% / {state.p2_fuel:.0f}%"
    return (
        f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n"
        f"{_pressure(state.gap)}  ·  {_weather(state.weather)}\n"
        f"🏁 {lap_s}  ·  {fuel_s}"
    )


def _prog(done: int, total: int) -> str:
    return "✅" * done + "⬜" * (total - done)


# ─────────────────────────────────────────────────────────────
#  Arrow Sprint View
# ─────────────────────────────────────────────────────────────

class ArrowSprintView(discord.ui.View):
    """
    4-arrow sequence challenge. Both players click in the correct order.
    Wrong arrow → resets their progress + penalty.
    First to complete wins the segment. 8s window (5s in battle mode).
    """
    SEQ_LEN = 4

    def __init__(self, state: RaceV2State, sequence: List[str], is_battle: bool = False):
        timeout = 5.0 if is_battle else 8.0
        super().__init__(timeout=timeout)
        self.state      = state
        self.sequence   = sequence
        self.is_battle  = is_battle
        self._timeout_s = timeout

        self.p1_idx   = 0;  self.p2_idx   = 0
        self.p1_done  = False; self.p2_done  = False
        self.p1_wrong = 0;  self.p2_wrong = 0
        self.p1_first = False  # did p1 finish first?

        self.resolved = asyncio.Event()
        self.msg: Optional[discord.Message] = None

        # Shuffle button layout so arrows aren't predictably placed
        shuffled = ARROWS.copy()
        random.shuffle(shuffled)
        style = discord.ButtonStyle.danger if is_battle else discord.ButtonStyle.primary
        for arrow in shuffled:
            btn = discord.ui.Button(
                label=ARROW_LABEL[arrow],
                style=style,
                custom_id=f"arw_{arrow}",
            )
            btn.callback = self._make_cb(arrow)
            self.add_item(btn)

    def _make_cb(self, arrow: str):
        async def cb(interaction: discord.Interaction):
            uid = str(interaction.user.id)
            is_p1 = uid == self.state.p1_id
            is_p2 = uid == self.state.p2_id
            if not (is_p1 or is_p2):
                await interaction.response.send_message(
                    "❌ You're not in this race!", ephemeral=True
                )
                return
            await interaction.response.defer()

            updated = False
            if is_p1 and not self.p1_done:
                if arrow == self.sequence[self.p1_idx]:
                    self.p1_idx += 1
                    if self.p1_idx == self.SEQ_LEN:
                        self.p1_done = True
                        self.p1_first = not self.p2_done
                        updated = True
                else:
                    self.p1_wrong += 1
                    self.p1_idx = 0
                    if self.p1_wrong >= DNF_WRONG_LIMIT:
                        self.state.dnf = "p1"
                    updated = True

            elif is_p2 and not self.p2_done:
                if arrow == self.sequence[self.p2_idx]:
                    self.p2_idx += 1
                    if self.p2_idx == self.SEQ_LEN:
                        self.p2_done = True
                        updated = True
                else:
                    self.p2_wrong += 1
                    self.p2_idx = 0
                    if self.p2_wrong >= DNF_WRONG_LIMIT:
                        self.state.dnf = "p2"
                    updated = True

            if updated and self.msg:
                await self._refresh_embed()

            if self.p1_done and self.p2_done:
                self.resolved.set()
            if self.state.dnf:
                self.resolved.set()

        return cb

    async def _refresh_embed(self):
        s    = self.state
        seq  = "  ".join(self.sequence)
        p1_p = _prog(self.p1_idx, self.SEQ_LEN)
        p2_p = _prog(self.p2_idx, self.SEQ_LEN)

        p1_note = "✅ **DONE!**" if self.p1_done else (f"❌ ×{self.p1_wrong}" if self.p1_wrong else "")
        p2_note = "✅ **DONE!**" if self.p2_done else (f"❌ ×{self.p2_wrong}" if self.p2_wrong else "")

        title = "⚡  BATTLE MODE — Arrow Duel!" if self.is_battle else "⬆️  Arrow Sprint!"
        color = C_RED if self.is_battle else C_BLUE

        emb = discord.Embed(title=title, color=color)
        emb.description = (
            f"{race_header(s)}\n\n"
            f"**Sequence:**  {seq}\n\n"
            f"🔵 **{s.p1_name}**: {p1_p}  {p1_note}\n"
            f"🔴 **{s.p2_name}**: {p2_p}  {p2_note}\n\n"
            f"*Wrong arrow = sequence resets · Click in order!*"
        )
        emb.set_footer(text=f"⏱️  {self._timeout_s:.0f}s window")
        try:
            await self.msg.edit(embed=emb, view=self)
        except Exception:
            pass

    async def on_timeout(self):
        self.resolved.set()

    def calc_delta(self) -> float:
        """gap_delta: positive = p1 gains."""
        BASE  = 1.4 if self.is_battle else 0.9
        WRONG = 0.3
        SPEED = 0.35

        p1_adv = (BASE if self.p1_done else 0.0) + (SPEED if self.p1_first else 0.0) - self.p1_wrong * WRONG
        p2_adv = (BASE if self.p2_done else 0.0) + (SPEED if (self.p2_done and not self.p1_first) else 0.0) - self.p2_wrong * WRONG

        # Card skill bonus
        p1_skill = float(getattr(self.state.p1_driver, "skill", 7.0))
        p2_skill = float(getattr(self.state.p2_driver, "skill", 7.0))
        p1_adv += (p1_skill - 7.0) * 0.06
        p2_adv += (p2_skill - 7.0) * 0.06

        # Synergy
        if self.state.p1_synergy: p1_adv += 0.12
        if self.state.p2_synergy: p2_adv += 0.12

        return p1_adv - p2_adv


# ─────────────────────────────────────────────────────────────
#  Drag Race View
# ─────────────────────────────────────────────────────────────

class DragRaceView(discord.ui.View):
    """
    Both players mash the same PUSH button. First to 3 clicks wins DRS.
    5-second window.
    """
    WIN_AT  = 3
    TIMEOUT = 5.0

    def __init__(self, state: RaceV2State):
        super().__init__(timeout=self.TIMEOUT)
        self.state     = state
        self.p1_clicks = 0
        self.p2_clicks = 0
        self.p1_won    = False
        self.p2_won    = False
        self.resolved  = asyncio.Event()
        self.msg: Optional[discord.Message] = None

    @discord.ui.button(label="⚡  PUSH IT!", style=discord.ButtonStyle.success, custom_id="drag_push")
    async def push_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        is_p1 = uid == self.state.p1_id
        is_p2 = uid == self.state.p2_id
        if not (is_p1 or is_p2):
            await interaction.response.send_message("❌ You're not in this race!", ephemeral=True)
            return
        await interaction.response.defer()

        if is_p1 and not self.p1_won:
            self.p1_clicks = min(self.p1_clicks + 1, self.WIN_AT)
            if self.p1_clicks >= self.WIN_AT and not self.p2_won:
                self.p1_won = True
                self.resolved.set()
        elif is_p2 and not self.p2_won:
            self.p2_clicks = min(self.p2_clicks + 1, self.WIN_AT)
            if self.p2_clicks >= self.WIN_AT and not self.p1_won:
                self.p2_won = True
                self.resolved.set()

        if self.msg:
            await self._refresh_embed()

    async def _refresh_embed(self):
        s    = self.state
        p1_b = "⚡" * self.p1_clicks + "⬜" * (self.WIN_AT - self.p1_clicks)
        p2_b = "⚡" * self.p2_clicks + "⬜" * (self.WIN_AT - self.p2_clicks)
        emb  = discord.Embed(title="⚡  Drag Race — PUSH IT!", color=C_ORANGE)
        emb.description = (
            f"{race_header(s)}\n\n"
            f"🔵 **{s.p1_name}**: {p1_b}  `{self.p1_clicks}/{self.WIN_AT}`\n"
            f"🔴 **{s.p2_name}**: {p2_b}  `{self.p2_clicks}/{self.WIN_AT}`\n\n"
            f"*First to {self.WIN_AT} clicks takes DRS!*"
        )
        emb.set_footer(text="⏱️  5s — CLICK FAST!")
        try:
            await self.msg.edit(embed=emb, view=self)
        except Exception:
            pass

    async def on_timeout(self):
        self.resolved.set()

    def calc_delta(self) -> float:
        BASE  = 0.75
        SMALL = 0.30

        # DRS specialist perk
        p1_perks = getattr(self.state.p1_driver, "perks", [])
        p2_perks = getattr(self.state.p2_driver, "perks", [])
        p1_drs = 0.25 if "drs_specialist" in p1_perks else 0.0
        p2_drs = 0.25 if "drs_specialist" in p2_perks else 0.0

        if self.p1_won:
            return BASE + p1_drs
        if self.p2_won:
            return -(BASE + p2_drs)
        # Partial — more clicks = small edge
        if self.p1_clicks > self.p2_clicks:
            return SMALL + p1_drs
        if self.p2_clicks > self.p1_clicks:
            return -(SMALL + p2_drs)
        return 0.0


# ─────────────────────────────────────────────────────────────
#  Tactical View
# ─────────────────────────────────────────────────────────────

class TacticalView(discord.ui.View):
    """
    Strategic call: Push / Hold / Box.
    Both players choose independently. Card stats + perks influence outcome.
    20-second window; auto-fills 'hold' on timeout.
    """
    TIMEOUT = 20.0

    def __init__(self, state: RaceV2State):
        super().__init__(timeout=self.TIMEOUT)
        self.state     = state
        self.p1_choice: Optional[str] = None
        self.p2_choice: Optional[str] = None
        self.resolved  = asyncio.Event()
        self.msg: Optional[discord.Message] = None

    async def _pick(self, interaction: discord.Interaction, choice: str):
        uid = str(interaction.user.id)
        is_p1 = uid == self.state.p1_id
        is_p2 = uid == self.state.p2_id
        if not (is_p1 or is_p2):
            await interaction.response.send_message("❌ You're not in this race!", ephemeral=True)
            return
        await interaction.response.defer()
        if is_p1 and not self.p1_choice:
            self.p1_choice = choice
        elif is_p2 and not self.p2_choice:
            self.p2_choice = choice
        if self.msg:
            await self._refresh_embed(reveal=bool(self.p1_choice and self.p2_choice))
        if self.p1_choice and self.p2_choice:
            self.resolved.set()

    @discord.ui.button(label="🔥 Push",  style=discord.ButtonStyle.danger,   custom_id="tac_push", row=0)
    async def push(self, i, b): await self._pick(i, "push")

    @discord.ui.button(label="🛞 Hold",  style=discord.ButtonStyle.primary,  custom_id="tac_hold", row=0)
    async def hold(self, i, b): await self._pick(i, "hold")

    @discord.ui.button(label="🔧 Box",   style=discord.ButtonStyle.secondary, custom_id="tac_box",  row=0)
    async def box(self, i, b):  await self._pick(i, "box")

    async def _refresh_embed(self, reveal: bool = False):
        s  = self.state
        def _status(choice, name):
            if choice:
                return f"✅ **{choice.title()}**" if reveal else "✅ Decided"
            return "⏳ Deciding…"

        emb = discord.Embed(title="🎯  Tactical Call", color=C_PURPLE)
        emb.description = (
            f"{race_header(s)}\n\n"
            f"🔵 **{s.p1_name}**: {_status(self.p1_choice, s.p1_name)}\n"
            f"🔴 **{s.p2_name}**: {_status(self.p2_choice, s.p2_name)}\n\n"
            f"**🔥 Push** — Attack! Burns fuel & tyres for pace\n"
            f"**🛞 Hold** — Safe and consistent, protect the gap\n"
            f"**🔧 Box** — Pit stop: lose time, reset fuel & tyres"
        )
        emb.set_footer(text="⏱️  20s to decide — driver perks & car stats shape the result!")
        try:
            await self.msg.edit(embed=emb, view=self)
        except Exception:
            pass

    async def on_timeout(self):
        if not self.p1_choice: self.p1_choice = "hold"
        if not self.p2_choice: self.p2_choice = "hold"
        self.resolved.set()

    def calc_delta(self) -> Tuple[float, str]:
        """Returns (gap_delta, commentary_line). Also mutates state fuel."""
        p1c = self.p1_choice or "hold"
        p2c = self.p2_choice or "hold"
        s   = self.state

        def _score(choice, car, driver, synergy, fuel):
            spd   = getattr(car,    "stats", {}).get("acceleration", 7.0)
            skill = float(getattr(driver, "skill", 7.0))
            perks = getattr(driver, "perks", [])

            if choice == "push":
                base = spd * 0.14 + skill * 0.07
                if fuel < 30: base -= 0.6
            elif choice == "hold":
                base = skill * 0.09 + 0.15
                if "consistency" in perks: base += 0.35
            else:  # box
                base = -2.0
                if "pit_crew_chief" in perks: base += 0.9
                base += getattr(car, "stats", {}).get("pit_time_bonus", 0.0) * 10

            if synergy: base += 0.18
            base += random.uniform(-0.25, 0.25)
            return base

        p1s = _score(p1c, s.p1_car, s.p1_driver, s.p1_synergy, s.p1_fuel)
        p2s = _score(p2c, s.p2_car, s.p2_driver, s.p2_synergy, s.p2_fuel)

        # Fuel burn
        s.p1_fuel = max(0.0, s.p1_fuel - FUEL_BURN.get(p1c, 4.5))
        s.p2_fuel = max(0.0, s.p2_fuel - FUEL_BURN.get(p2c, 4.5))
        if p1c == "box": s.p1_fuel = 100.0
        if p2c == "box": s.p2_fuel = 100.0

        # Rain: stay-on-slicks penalty unless "rain_master"
        if s.weather == "rain":
            p1_perks = getattr(s.p1_driver, "perks", [])
            p2_perks = getattr(s.p2_driver, "perks", [])
            if p1c != "box" and "rain_master" not in p1_perks: p1s -= 0.5
            if p2c != "box" and "rain_master" not in p2_perks: p2s -= 0.5

        comments = {
            ("push", "hold"):  "🔥 P1 pushed hard while P2 played it safe!",
            ("hold", "push"):  "🔥 P2 attacked while P1 managed the gap!",
            ("push", "push"):  "🔥🔥 Flat-out from both — pure pace decides!",
            ("hold", "hold"):  "🛞 Both holding position — strategy stalemate.",
            ("box",  "push"):  "🔧 P1 pits while P2 pushes — undercut attempt!",
            ("push", "box"):   "🔧 P2 pits while P1 pushes — overcut gamble!",
            ("box",  "hold"):  "🔧 P1 boxes for fresh rubber — back out soon.",
            ("hold", "box"):   "🔧 P2 boxes for fresh rubber — back out soon.",
            ("box",  "box"):   "🔧🔧 Both pit simultaneously — no net change.",
        }
        comment = comments.get((p1c, p2c), "Tactical battle continues…")
        return p1s - p2s, comment


# ─────────────────────────────────────────────────────────────
#  Race Accept View
# ─────────────────────────────────────────────────────────────

class RaceAcceptView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=30.0)
        self.challenger = challenger
        self.opponent   = opponent
        self.accepted   = False
        self.done       = asyncio.Event()

    @discord.ui.button(label="✅  Accept Race", style=discord.ButtonStyle.success, custom_id="race_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.accepted = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.done.set()
        self.stop()

    @discord.ui.button(label="❌  Decline",     style=discord.ButtonStyle.danger,   custom_id="race_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.opponent.id, self.challenger.id):
            await interaction.response.send_message("Not your race!", ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.done.set()
        self.stop()

    async def on_timeout(self):
        self.done.set()


# ─────────────────────────────────────────────────────────────
#  Challenge embed builders (initial state)
# ─────────────────────────────────────────────────────────────

def _arrow_embed(state: RaceV2State, sequence: List[str], is_battle: bool, seg_in_lap: int) -> discord.Embed:
    seq_str = "  ".join(sequence)
    title   = "⚡  BATTLE MODE — Arrow Duel!" if is_battle else f"⬆️  Arrow Sprint  ·  Segment {seg_in_lap}/3"
    color   = C_RED if is_battle else C_BLUE
    timeout = 5 if is_battle else 8
    emb = discord.Embed(title=title, color=color)
    emb.description = (
        f"{race_header(state)}\n\n"
        f"**Sequence:**  {seq_str}\n\n"
        f"🔵 **{state.p1_name}**: ⬜⬜⬜⬜\n"
        f"🔴 **{state.p2_name}**: ⬜⬜⬜⬜\n\n"
        f"*Wrong arrow = sequence resets · Click in order!*"
    )
    emb.set_footer(text=f"⏱️  {timeout}s window  ·  Both players clicking simultaneously")
    return emb


def _drag_embed(state: RaceV2State, seg_in_lap: int) -> discord.Embed:
    emb = discord.Embed(title=f"⚡  Drag Race — PUSH IT!  ·  Segment {seg_in_lap}/3", color=C_ORANGE)
    emb.description = (
        f"{race_header(state)}\n\n"
        f"🔵 **{state.p1_name}**: ⬜⬜⬜  `0/3`\n"
        f"🔴 **{state.p2_name}**: ⬜⬜⬜  `0/3`\n\n"
        f"*First player to click 3 times wins DRS advantage!*"
    )
    emb.set_footer(text="⏱️  5s — MASH THAT BUTTON!")
    return emb


def _tactical_embed(state: RaceV2State, seg_in_lap: int) -> discord.Embed:
    emb = discord.Embed(title=f"🎯  Tactical Call  ·  Segment {seg_in_lap}/3", color=C_PURPLE)
    emb.description = (
        f"{race_header(state)}\n\n"
        f"🔵 **{state.p1_name}**: ⏳ Deciding…\n"
        f"🔴 **{state.p2_name}**: ⏳ Deciding…\n\n"
        f"**🔥 Push** — Attack! Burns fuel & tyres for pace\n"
        f"**🛞 Hold** — Safe and consistent, protect the gap\n"
        f"**🔧 Box** — Pit stop: lose time, reset fuel & tyres"
    )
    emb.set_footer(text="⏱️  20s to decide — driver perks & card stats shape the result!")
    return emb


# ─────────────────────────────────────────────────────────────
#  Main race coroutine
# ─────────────────────────────────────────────────────────────

async def run_race(
    channel: discord.TextChannel,
    p1: discord.Member,
    p2: discord.Member,
    state: RaceV2State,
) -> Dict:
    """
    Runs the full 9-segment interactive race in the channel.
    Returns a result dict for coin rewards.
    """

    # ── LIGHTS OUT ────────────────────────────────────────────
    p1_car_name = getattr(state.p1_car, "name", "Unknown Car")
    p2_car_name = getattr(state.p2_car, "name", "Unknown Car")
    p1_drv_name = getattr(state.p1_driver, "name", "Unknown Driver")
    p2_drv_name = getattr(state.p2_driver, "name", "Unknown Driver")
    p1_skill    = float(getattr(state.p1_driver, "skill", 7.0))
    p2_skill    = float(getattr(state.p2_driver, "skill", 7.0))

    syn_line = ""
    if state.p1_synergy: syn_line += f"🔗 {p1.display_name} has driver/car **synergy bonus**!  "
    if state.p2_synergy: syn_line += f"🔗 {p2.display_name} has driver/car **synergy bonus**!"

    intro = discord.Embed(
        title="🚦  LIGHTS OUT — AND AWAY WE GO!",
        color=C_RED,
    )
    intro.description = (
        f"**3 Laps · 9 Challenges · Everything matters**\n\n"
        f"🔵 **{p1.display_name}**\n"
        f"└ {p1_drv_name} (Skill {p1_skill:.1f}/10)  ·  {p1_car_name}\n\n"
        f"🔴 **{p2.display_name}**\n"
        f"└ {p2_drv_name} (Skill {p2_skill:.1f}/10)  ·  {p2_car_name}\n\n"
        + (f"{syn_line}\n\n" if syn_line else "")
        + "🏎️ `⬆️ Arrow Sprint` → `⚡ Drag Race` → `🎯 Tactical` — repeat × 3\n"
        f"⚡ **Battle Mode** fires automatically when the gap drops below 0.8s!"
    )
    intro.set_footer(text="Gap and position shown in every challenge. Good luck!")
    await channel.send(content=f"{p1.mention} {p2.mention}", embed=intro)
    await asyncio.sleep(3)

    # ── SEGMENT LOOP ─────────────────────────────────────────
    for seg_idx in range(9):
        state.segment = seg_idx
        state.lap     = (seg_idx // 3) + 1
        seg_in_lap    = (seg_idx % 3) + 1

        # Lap announcement
        if seg_in_lap == 1 and seg_idx > 0:
            lap_col = C_RED if state.lap == 3 else C_BLUE
            lap_emb = discord.Embed(
                title=f"🏁  LAP {state.lap} / 3{'  ·  FINAL LAP!' if state.lap == 3 else ''}",
                color=lap_col,
            )
            lap_emb.description = (
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n"
                f"{_pressure(state.gap)}"
            )
            if state.lap == 3:
                lap_emb.set_footer(text="🔴 EVERYTHING ON THE LINE — no more chances after this!")
            await channel.send(embed=lap_emb)
            await asyncio.sleep(2)

        # Weather event (chance at lap transitions)
        if seg_in_lap == 1 and seg_idx > 0 and random.random() < 0.22:
            state.weather = "rain"
            rain_emb = discord.Embed(
                title="🌧️  RAIN BEGINS TO FALL",
                color=0x74b9ff,
            )
            rain_emb.description = (
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n\n"
                f"Conditions are changing! Box for wets or gamble on slicks?"
            )
            await channel.send(embed=rain_emb)
            await asyncio.sleep(2)

        # Determine challenge type — Battle overrides when gap is within threshold
        seg_type = BASE_SCHEDULE[seg_idx]
        is_battle = abs(state.gap) < BATTLE_GAP and seg_idx > 0
        if is_battle:
            seg_type = "battle"

        # ── ARROW / BATTLE ────────────────────────────────────
        if seg_type in ("arrow", "battle"):
            sequence = random.sample(ARROWS, 4)
            view     = ArrowSprintView(state, sequence, is_battle=is_battle)
            emb      = _arrow_embed(state, sequence, is_battle, seg_in_lap)
            mention  = f"{p1.mention} {p2.mention}" if is_battle else ""
            msg      = await channel.send(content=mention or None, embed=emb, view=view)
            view.msg = msg

            timeout_s = 5.5 if is_battle else 8.5
            try:
                await asyncio.wait_for(view.resolved.wait(), timeout=timeout_s)
            except asyncio.TimeoutError:
                pass

            delta = view.calc_delta()
            state.gap             += delta
            state.p1_total_correct += view.p1_idx
            state.p2_total_correct += view.p2_idx
            state.p1_total_wrong   += view.p1_wrong
            state.p2_total_wrong   += view.p2_wrong

            if is_battle:
                if delta > 0: state.p1_battles_won += 1
                elif delta < 0: state.p2_battles_won += 1

            # Result line
            if view.p1_done and view.p1_first:
                win_line = f"🔵 **{p1.display_name}** finished first! Gap shift: **{delta:+.2f}s**"
            elif view.p2_done and not view.p1_first:
                win_line = f"🔴 **{p2.display_name}** finished first! Gap shift: **{-delta:+.2f}s**"
            else:
                win_line = f"⏰ Time ran out — partial scores applied  ({delta:+.2f}s)"

            res_emb = discord.Embed(
                title=("⚡  Battle" if is_battle else "⬆️  Arrow Sprint") + " — Result",
                color=C_RED if is_battle else C_BLUE,
            )
            res_emb.description = (
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n\n"
                f"{win_line}"
            )
            await msg.edit(embed=res_emb, view=None)

        # ── DRAG RACE ─────────────────────────────────────────
        elif seg_type == "drag":
            view = DragRaceView(state)
            emb  = _drag_embed(state, seg_in_lap)
            msg  = await channel.send(embed=emb, view=view)
            view.msg = msg

            try:
                await asyncio.wait_for(view.resolved.wait(), timeout=5.5)
            except asyncio.TimeoutError:
                pass

            delta = view.calc_delta()
            state.gap += delta
            if view.p1_won: state.p1_drag_wins += 1
            elif view.p2_won: state.p2_drag_wins += 1

            if view.p1_won:
                win_line = f"🔵 **{p1.display_name}** smashed it — DRS engaged! ({delta:+.2f}s)"
            elif view.p2_won:
                win_line = f"🔴 **{p2.display_name}** smashed it — DRS engaged! ({delta:+.2f}s)"
            else:
                win_line = f"⏰ Neither hit 3 — minor shift ({delta:+.2f}s)"

            res_emb = discord.Embed(title="⚡  Drag Race — Result", color=C_ORANGE)
            res_emb.description = (
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n\n{win_line}"
            )
            await msg.edit(embed=res_emb, view=None)

        # ── TACTICAL ──────────────────────────────────────────
        elif seg_type == "tactical":
            view = TacticalView(state)
            emb  = _tactical_embed(state, seg_in_lap)
            msg  = await channel.send(embed=emb, view=view)
            view.msg = msg

            try:
                await asyncio.wait_for(view.resolved.wait(), timeout=21.0)
            except asyncio.TimeoutError:
                view.p1_choice = view.p1_choice or "hold"
                view.p2_choice = view.p2_choice or "hold"

            delta, comment = view.calc_delta()
            state.gap += delta

            await view._refresh_embed(reveal=True)
            await asyncio.sleep(1)

            res_emb = discord.Embed(title="🎯  Tactical Call — Result", color=C_PURPLE)
            res_emb.description = (
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}\n\n"
                f"{comment}\n\n"
                f"⛽ Fuel — 🔵 {state.p1_fuel:.0f}%  ·  🔴 {state.p2_fuel:.0f}%"
            )
            await msg.edit(embed=res_emb, view=None)

        # ── DNF CHECK ─────────────────────────────────────────
        if state.dnf:
            dnf_name = p1.display_name if state.dnf == "p1" else p2.display_name
            survivor  = p2.display_name if state.dnf == "p1" else p1.display_name
            dnf_emb = discord.Embed(
                title="💥  TYRE BLOWOUT — DNF!",
                color=C_DARK,
            )
            dnf_emb.description = (
                f"❌ **{dnf_name}** hit {DNF_WRONG_LIMIT} wrong arrows — catastrophic tyre failure!\n\n"
                f"🏆 **{survivor}** wins by retirement!\n\n"
                f"{_gap_bar(state.gap, state.p1_name, state.p2_name)}"
            )
            await channel.send(embed=dnf_emb)
            state.winner = "p2" if state.dnf == "p1" else "p1"
            break

        # Fuel DNF (only on last lap)
        if state.lap == 3:
            if state.p1_fuel <= 0 and state.p2_fuel > 0:
                state.dnf    = "p1"
                state.winner = "p2"
                fuel_emb = discord.Embed(
                    title="⛽  OUT OF FUEL — DNF!",
                    color=C_DARK,
                )
                fuel_emb.description = (
                    f"🔵 **{p1.display_name}** ran out of fuel on the final lap!\n"
                    f"🏆 **{p2.display_name}** wins!"
                )
                await channel.send(embed=fuel_emb)
                break
            elif state.p2_fuel <= 0 and state.p1_fuel > 0:
                state.dnf    = "p2"
                state.winner = "p1"
                fuel_emb = discord.Embed(title="⛽  OUT OF FUEL — DNF!", color=C_DARK)
                fuel_emb.description = (
                    f"🔴 **{p2.display_name}** ran out of fuel on the final lap!\n"
                    f"🏆 **{p1.display_name}** wins!"
                )
                await channel.send(embed=fuel_emb)
                break

        await asyncio.sleep(1.8)

    # ── DETERMINE WINNER ──────────────────────────────────────
    if not state.winner:
        if abs(state.gap) < 0.05:
            state.winner = "draw"
        elif state.gap > 0:
            state.winner = "p1"
        else:
            state.winner = "p2"

    return _build_result(state)


# ─────────────────────────────────────────────────────────────
#  Result helpers
# ─────────────────────────────────────────────────────────────

def _build_result(state: RaceV2State) -> Dict:
    margin     = abs(state.gap)
    close_race = margin < 0.6 and not state.dnf

    p1_perfect = state.p1_total_wrong == 0 and (state.p1_total_correct + state.p1_drag_wins) > 0
    p2_perfect = state.p2_total_wrong == 0 and (state.p2_total_correct + state.p2_drag_wins) > 0

    base_win  = 110
    base_lose = 20
    close_win_bonus  = 45
    close_lose_bonus = 30
    perfect_bonus    = 30

    p1_coins = (base_win  if state.winner == "p1" else base_lose)
    p2_coins = (base_win  if state.winner == "p2" else base_lose)
    if state.winner == "draw":
        p1_coins = p2_coins = 60

    if close_race:
        p1_coins += close_win_bonus if state.winner == "p1" else close_lose_bonus
        p2_coins += close_win_bonus if state.winner == "p2" else close_lose_bonus

    if p1_perfect: p1_coins += perfect_bonus
    if p2_perfect: p2_coins += perfect_bonus

    return {
        "winner":        state.winner,
        "winner_id":     state.p1_id if state.winner == "p1" else (state.p2_id if state.winner == "p2" else None),
        "loser_id":      state.p2_id if state.winner == "p1" else (state.p1_id if state.winner == "p2" else None),
        "gap":           state.gap,
        "margin":        margin,
        "close_race":    close_race,
        "dnf":           state.dnf,
        "p1_coins":      p1_coins,
        "p2_coins":      p2_coins,
        "p1_correct":    state.p1_total_correct,
        "p2_correct":    state.p2_total_correct,
        "p1_wrong":      state.p1_total_wrong,
        "p2_wrong":      state.p2_total_wrong,
        "p1_drag_wins":  state.p1_drag_wins,
        "p2_drag_wins":  state.p2_drag_wins,
        "p1_battles":    state.p1_battles_won,
        "p2_battles":    state.p2_battles_won,
        "p1_perfect":    p1_perfect,
        "p2_perfect":    p2_perfect,
    }


def build_result_embed(
    result: Dict,
    p1: discord.Member,
    p2: discord.Member,
    state: RaceV2State,
) -> discord.Embed:
    winner_m = p1 if result["winner"] == "p1" else (p2 if result["winner"] == "p2" else None)
    loser_m  = p2 if result["winner"] == "p1" else (p1 if result["winner"] == "p2" else None)

    if result["winner"] == "draw":
        title = "🏁  Race Over — DEAD HEAT!"
        desc  = f"**{state.margin:.3f}s** separates them — almost impossible to call!"
        color = C_BLUE
    elif result["dnf"]:
        title = f"🏆  {winner_m.display_name} Wins by Retirement!"
        desc  = f"💥 **{loser_m.display_name}** suffered a catastrophic failure.\n**{winner_m.display_name}** takes the chequered flag!"
        color = C_DARK
    elif result["close_race"]:
        title = f"🏆  Photo Finish — {winner_m.display_name} Wins!"
        desc  = f"Margin: **+{result['margin']:.3f}s** — an absolute thriller!"
        color = C_GREEN
    else:
        title = f"🏆  {winner_m.display_name} Wins!"
        desc  = f"Margin of victory: **+{result['margin']:.2f}s**"
        color = C_GREEN

    emb = discord.Embed(title=title, description=desc, color=color)

    def _perf(correct, wrong, drag, battles, coins, perfect):
        lines = [
            f"🎯 Arrow hits: **{correct}**",
            f"❌ Mistakes: **{wrong}**",
            f"⚡ Drag wins: **{drag}**",
            f"⚔️ Battles won: **{battles}**",
            f"💰 +**{coins}** coins" + (" *(+perfect bonus!)*" if perfect else ""),
        ]
        return "\n".join(lines)

    emb.add_field(
        name=f"🔵 {p1.display_name}",
        value=_perf(result["p1_correct"], result["p1_wrong"], result["p1_drag_wins"],
                    result["p1_battles"], result["p1_coins"], result["p1_perfect"]),
        inline=True,
    )
    emb.add_field(
        name=f"🔴 {p2.display_name}",
        value=_perf(result["p2_correct"], result["p2_wrong"], result["p2_drag_wins"],
                    result["p2_battles"], result["p2_coins"], result["p2_perfect"]),
        inline=True,
    )

    footer_parts = []
    if result["close_race"]:
        footer_parts.append("🔥 Close race bonus applied!")
    if result["p1_perfect"] or result["p2_perfect"]:
        footer_parts.append("⭐ Perfect run bonus awarded!")
    footer_parts.append("Use /race to challenge again!")
    emb.set_footer(text="  ·  ".join(footer_parts))

    return emb


def build_challenge_embed_v2(
    challenger: discord.Member,
    opponent: discord.Member,
    p1_car, p1_driver,
    p2_car, p2_driver,
    synergy1: bool,
    synergy2: bool,
) -> discord.Embed:
    """The initial challenge / accept embed."""
    p1_speed = getattr(p1_car, "stats", {}).get("top_speed", "?")
    p2_speed = getattr(p2_car, "stats", {}).get("top_speed", "?")
    p1_skill = float(getattr(p1_driver, "skill", 7.0))
    p2_skill = float(getattr(p2_driver, "skill", 7.0))

    emb = discord.Embed(
        title=f"🏁  Race Challenge!",
        description=(
            f"**{challenger.display_name}** has challenged **{opponent.display_name}** to a race!\n\n"
            f"🔵 **{challenger.display_name}** — {getattr(p1_driver,'name','?')} · Skill {p1_skill:.1f}/10\n"
            f"└ {getattr(p1_car,'name','?')}  ·  {p1_speed} km/h"
            + ("  🔗 Synergy!" if synergy1 else "") + "\n\n"
            f"🔴 **{opponent.display_name}** — {getattr(p2_driver,'name','?')} · Skill {p2_skill:.1f}/10\n"
            f"└ {getattr(p2_car,'name','?')}  ·  {p2_speed} km/h"
            + ("  🔗 Synergy!" if synergy2 else "") + "\n\n"
            f"**3 Laps · 9 Interactive Challenges**\n"
            f"Arrow sprints · Drag races · Tactical calls · Battle mode"
        ),
        color=C_RED,
    )
    emb.set_footer(text=f"{opponent.display_name} has 30 seconds to accept!")
    return emb
