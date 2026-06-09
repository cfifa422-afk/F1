import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
import time
from datetime import datetime
from typing import Optional, Dict, List, Literal
import random

from database import Database, UPGRADE_STATS, UPGRADE_COSTS, UPGRADE_MAX_LEVEL, UPGRADE_INFO
import cards as card_module
import race_v2 as race_v2_mod
import f1_images
import commentary as commentary_engine
import card_manager as cm
import career as career_mod

# ==================== BOT SETUP ====================

intents = discord.Intents.default()
intents.dm_messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

db = Database()

# ==================== DATA MODELS ====================

class Car:
    def __init__(self, car_id: str, name: str, team: str, top_speed: int, rarity: str, handling: float = 7.0):
        self.car_id = car_id
        self.name = name
        self.team = team
        self.top_speed = top_speed
        self.rarity = rarity
        self.handling = handling
        self.stats = self._calculate_stats()

    def _calculate_stats(self) -> Dict:
        base_multiplier = self.top_speed / 350
        rarity_bonus = {"mythic": 1.25, "legendary": 1.15, "epic": 1.10, "rare": 1.05, "common": 1.00}.get(self.rarity, 1.0)
        multiplier = base_multiplier * rarity_bonus
        return {
            "top_speed": self.top_speed,
            "acceleration": min(10, 7.5 * multiplier),
            "handling": min(10, self.handling * multiplier),
            "tire_wear_rate": max(10, 20 - (self.top_speed / 350 * 5)),
            "fuel_efficiency": max(2.0, 3.0 - (self.top_speed / 350 * 0.5)),
            "rarity_multiplier": rarity_bonus,
        }


class Driver:
    def __init__(self, driver_id: str, name: str, code: str, skill: float, rarity: str, perks: List[str] = None):
        self.driver_id = driver_id
        self.name = name
        self.code = code
        self.skill = skill
        self.rarity = rarity
        self.perks = perks or []

    def get_skill_bonus(self) -> float:
        return 1.0 + (self.skill / 10) * 0.1


class PlayerDeck:
    def __init__(self, player_id: str):
        self.player_id = player_id
        self.cars: List[Car] = []
        self.drivers: List[Driver] = []

    def add_car(self, car: Car):
        self.cars.append(car)

    def add_driver(self, driver: Driver):
        self.drivers.append(driver)


class RaceState:
    def __init__(self, player1_id: str, player2_id: str, p1_car: Car, p1_driver: Driver,
                 p2_car: Car, p2_driver: Driver):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.turn = 0
        self.lap = 1
        self.total_laps = 3
        self.max_turns = 12
        self.p1_car = p1_car
        self.p1_driver = p1_driver
        self.p1_position = 1
        self.p1_fuel = 100.0
        self.p1_tire_wear = 0.0
        self.p1_tire_type = "soft"
        self.p1_pit_stops = 0
        self.p1_choice = None
        self.p2_car = p2_car
        self.p2_driver = p2_driver
        self.p2_position = 2
        self.p2_fuel = 100.0
        self.p2_tire_wear = 0.0
        self.p2_tire_type = "soft"
        self.p2_pit_stops = 0
        self.p2_choice = None
        self.weather = "clear"
        self.gap = 0.0
        self.events_log = []
        self.choice_history = {"p1": [], "p2": []}

    def get_lap_info(self) -> str:
        return f"Lap {self.lap}/{self.total_laps} | Turn {self.turn}/{self.max_turns}"


# ==================== RACE ENGINE ====================

class RaceEngine:
    def __init__(self):
        self.active_races: Dict[str, RaceState] = {}

    def create_race(self, p1_id: str, p2_id: str, p1_car: Car, p1_driver: Driver,
                    p2_car: Car, p2_driver: Driver):
        race_id = f"{p1_id}_{p2_id}_{int(datetime.now().timestamp())}"
        race = RaceState(p1_id, p2_id, p1_car, p1_driver, p2_car, p2_driver)
        self.active_races[race_id] = race
        return race, race_id

    def process_turn(self, race: RaceState, p1_choice: str, p2_choice: str) -> Dict:
        race.turn += 1
        race.choice_history["p1"].append(p1_choice)
        race.choice_history["p2"].append(p2_choice)

        if race.turn % 4 == 0 and race.turn > 0:
            race.lap += 1
            if race.lap > race.total_laps:
                return {"race_finished": True}

        event = self._generate_event(race)
        if event:
            race.events_log.append(event)

        p1_time = self._calculate_lap_time(race, "p1", p1_choice, event)
        p2_time = self._calculate_lap_time(race, "p2", p2_choice, event)

        self._update_consumables(race, "p1", p1_choice)
        self._update_consumables(race, "p2", p2_choice)

        if p1_choice == "pit_stop":
            race.p1_pit_stops += 1
            race.p1_fuel = 100.0
            race.p1_tire_wear = 0.0
            race.p1_tire_type = self._get_optimal_tire(race, event)
            pit_bonus_p1 = race.p1_car.stats.get("pit_time_bonus", 0.0)
            crew_chief_p1 = "pit_crew_chief" in race.p1_driver.perks
            p1_time = -3.2 + pit_bonus_p1 + (0.5 if crew_chief_p1 else 0.0)

        if p2_choice == "pit_stop":
            race.p2_pit_stops += 1
            race.p2_fuel = 100.0
            race.p2_tire_wear = 0.0
            race.p2_tire_type = self._get_optimal_tire(race, event)
            pit_bonus_p2 = race.p2_car.stats.get("pit_time_bonus", 0.0)
            crew_chief_p2 = "pit_crew_chief" in race.p2_driver.perks
            p2_time = -3.2 + pit_bonus_p2 + (0.5 if crew_chief_p2 else 0.0)

        race.gap += (p2_time - p1_time)

        race.p1_position = 2 if race.gap > 0.5 else 1
        race.p2_position = 1 if race.gap > 0.5 else 2

        if race.p1_fuel < 0:
            return {"dnf": "p1", "reason": "fuel_depleted"}
        if race.p2_fuel < 0:
            return {"dnf": "p2", "reason": "fuel_depleted"}
        if race.p1_tire_wear > 100:
            return {"dnf": "p1", "reason": "tire_failure"}
        if race.p2_tire_wear > 100:
            return {"dnf": "p2", "reason": "tire_failure"}

        return {
            "turn_complete": True,
            "p1_time": p1_time,
            "p2_time": p2_time,
            "event": event,
            "gap": race.gap,
        }

    def _generate_event(self, race: RaceState) -> Optional[str]:
        rand = random.random()
        if rand < 0.05:
            race.weather = "rain"
            return "🌧️ Rain incoming!"
        elif rand < 0.10:
            return "💨 DRS zone available!"
        elif rand < 0.12:
            return "🚗 Safety car deployed!"
        return None

    def _calculate_lap_time(self, race: RaceState, player: str, choice: str, event: Optional[str]) -> float:
        car = race.p1_car if player == "p1" else race.p2_car
        driver = race.p1_driver if player == "p1" else race.p2_driver
        tire_type = race.p1_tire_type if player == "p1" else race.p2_tire_type
        tire_wear = race.p1_tire_wear if player == "p1" else race.p2_tire_wear

        base_speed = car.stats["acceleration"]
        # Driver skill bonus: skill 5.0→10.0 gives +0.4→+0.8
        skill_bonus = (driver.skill / 10.0) * 0.8
        # Handling gives a cornering edge (aero + suspension upgrades feed into this)
        handling_bonus = (car.stats.get("handling", 7.0) / 10.0) * 0.3
        wear_penalty = (tire_wear / 100) * 2.0
        choice_impact = {"accelerate": 0.8, "same_speed": 0.0, "slow_down": -0.6, "pit_stop": -3.2}.get(choice, 0.0)
        tire_stats = {"soft": 1.05, "medium": 1.02, "hard": 1.0, "wet": 0.8}
        tire_bonus = tire_stats.get(tire_type, 1.0)

        event_modifier = 0.0
        if event and "DRS" in event and choice == "accelerate":
            event_modifier = 0.5
        if event and "Rain" in event and tire_type == "wet":
            event_modifier = 0.3

        weather_impact = 0.0
        if race.weather == "rain":
            weather_impact = 0.4 if tire_type == "wet" else -1.0

        # Perk bonuses
        perk_bonus = 0.0
        perks = driver.perks
        if "drs_specialist" in perks and event and "DRS" in event:
            perk_bonus += 0.8
        if "rain_master" in perks and race.weather == "rain":
            perk_bonus += 2.5
        if "consistency" in perks:
            perk_bonus += 0.3

        return base_speed * tire_bonus + choice_impact + event_modifier + weather_impact - wear_penalty + skill_bonus + handling_bonus + perk_bonus

    def _update_consumables(self, race: RaceState, player: str, choice: str):
        car = race.p1_car if player == "p1" else race.p2_car
        driver = race.p1_driver if player == "p1" else race.p2_driver
        fuel_burn = {"accelerate": 5.0, "same_speed": 3.0, "slow_down": 2.0, "pit_stop": 0.0}.get(choice, 3.0)
        fuel_eff = car.stats["fuel_efficiency"]

        # fuel_saver perk: -10% fuel consumption
        if "fuel_saver" in driver.perks:
            fuel_burn *= 0.9

        # Tire wear scaled by brakes upgrade (tire_wear_rate baseline ~15; lower = better brakes)
        base_tire_wear = {"accelerate": 8.0, "same_speed": 4.0, "slow_down": 2.0}.get(choice, 4.0)
        tire_wear_rate = car.stats.get("tire_wear_rate", 15.0)
        tire_wear_mult = tire_wear_rate / 15.0          # <1.0 with brakes upgrades = less wear
        if "tire_master" in driver.perks:
            tire_wear_mult *= 0.85                       # tire_master: -15% wear
        actual_tire_wear = base_tire_wear * tire_wear_mult

        if player == "p1":
            race.p1_fuel -= fuel_burn * fuel_eff
            if choice != "pit_stop":
                race.p1_tire_wear += actual_tire_wear
        else:
            race.p2_fuel -= fuel_burn * fuel_eff
            if choice != "pit_stop":
                race.p2_tire_wear += actual_tire_wear

    def _get_optimal_tire(self, race: RaceState, event: Optional[str]) -> str:
        if race.weather == "rain" or (event and "Rain" in event):
            return "wet"
        elif race.lap >= 2:
            return "hard"
        return "soft"


# ==================== GLOBAL INSTANCES ====================

race_engine = RaceEngine()
active_race_pairs: Dict = {}

# ==================== SLASH COMMAND GROUPS ====================

pack_group = app_commands.Group(name="pack", description="Open your F1 card packs")
f1_group = app_commands.Group(name="f1", description="F1 card collection commands")
config_group = app_commands.Group(name="config", description="Server configuration (admin only)")
channels_group = app_commands.Group(name="channels", description="Manage card spawn channels", parent=config_group)

# ==================== HELPER FUNCTIONS ====================

def format_cooldown(seconds: int) -> str:
    if seconds < 3600:
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s}s"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d {h}h"


def card_to_car(card: Dict) -> Car:
    return Car(
        car_id=card["id"],
        name=card["name"],
        team=card["team"],
        top_speed=card["top_speed"],
        rarity=card["rarity"],
        handling=card.get("handling", 7.0),
    )


def card_to_driver(card: Dict) -> Driver:
    return Driver(
        driver_id=card["id"],
        name=card["name"],
        code=card["code"],
        skill=card["skill"],
        rarity=card["rarity"],
        perks=card.get("perks", []),
    )


def make_card_art_file(card: Dict) -> Optional[discord.File]:
    """Return a discord.File for the card's local image, or None if not available."""
    return f1_images.get_card_file(card)


def give_starter_cards(player_id: str, username: str):
    """Give starter cards to brand new players."""
    cards = db.get_player_cards(player_id)
    if not cards["drivers"] and not cards["cars"]:
        import random as _r
        _now_iso = datetime.now().isoformat()
        starter_driver = {
            "id": f"starter_driver_{player_id}",
            "type": "driver",
            "name": "Alex Albon",
            "code": "ALB",
            "skill": 6.8,
            "team": "Williams",
            "rarity": "common",
            "perks": [],
            "obtained_at": _now_iso,
        }
        starter_car = {
            "id": f"starter_car_{player_id}",
            "type": "car",
            "name": "Williams FW45",
            "team": "Williams",
            "top_speed": 360,
            "handling": 7.3,
            "rarity": "common",
            "perks": [],
            "obtained_at": _now_iso,
        }
        db.add_card_to_player(player_id, starter_driver, "driver")
        db.add_card_to_player(player_id, starter_car, "car")
        db.set_equipped(player_id, "driver", starter_driver["id"])
        db.set_equipped(player_id, "car", starter_car["id"])


def get_player_race_cards(player_id: str):
    """Return (Car, Driver) objects to use in a race based on equipped + fallback.
    Applies upgrade multipliers and equipped team-asset bonuses to Car stats.
    """
    equipped = db.get_equipped(player_id)
    cards = db.get_player_cards(player_id)

    car_data = None
    if equipped.get("car_id"):
        car_data = db.get_card_by_id(player_id, equipped["car_id"])
    if not car_data and cards["cars"]:
        car_data = cards["cars"][0]

    driver_data = None
    if equipped.get("driver_id"):
        driver_data = db.get_card_by_id(player_id, equipped["driver_id"])
    if not driver_data and cards["drivers"]:
        driver_data = cards["drivers"][0]

    race_car    = card_to_car(car_data)       if car_data    else Car("default", "Unknown Car", "Unknown", 350, "common")
    race_driver = card_to_driver(driver_data) if driver_data else Driver("default", "Unknown Driver", "UNK", 5.0, "common")

    # Apply upgrade multipliers
    mults        = db.get_upgrade_multipliers(player_id)
    team_bonuses = db.get_team_bonuses(player_id)

    race_car.top_speed = int(race_car.top_speed * mults["engine"])

    stats = race_car.stats
    # Engine boosts both top speed (above) and base acceleration/power
    # Acceleration upgrade adds responsiveness on top of engine power
    stats["acceleration"] = stats.get("acceleration", 5.0) * mults["engine"] * mults["acceleration"] * (1.0 + team_bonuses.get("acceleration", 0.0))
    # Aero + Suspension both feed into handling (cornering stability)
    stats["handling"]     = stats.get("handling", 5.0)     * mults["aero"] * mults["suspension"]    * (1.0 + team_bonuses.get("aero", 0.0))
    # Brakes reduce tire_wear_rate (lower rate = less wear in _update_consumables)
    stats["tire_wear_rate"]   = stats.get("tire_wear_rate", 15.0) * mults["brakes"] * max(0.2, 1.0 - team_bonuses.get("tire_wear", 0.0))
    stats["fuel_efficiency"]  = stats.get("fuel_efficiency", 1.0) * max(0.2, 1.0 - team_bonuses.get("fuel_efficiency", 0.0))
    stats["pit_time_bonus"]   = team_bonuses.get("pit_time", 0.0)

    return race_car, race_driver


def format_card_footer(card: Dict) -> str:
    """Return a footer string showing the card's ID and caught date with relative time."""
    card_id = card.get("id", "?").upper()
    caught_raw = card.get("caught_at") or card.get("obtained_at")
    if caught_raw:
        try:
            caught_dt = datetime.fromisoformat(str(caught_raw))
            delta = datetime.now() - caught_dt
            if delta.days == 0:
                hours = delta.seconds // 3600
                rel = f"{hours} hour{'s' if hours != 1 else ''} ago" if hours > 0 else "just now"
            elif delta.days == 1:
                rel = "1 day ago"
            else:
                rel = f"{delta.days} days ago"
            caught_str = caught_dt.strftime("%b %d, %Y %I:%M %p")
            return f"ID: #{card_id}  ·  Caught on {caught_str} ({rel})"
        except Exception:
            pass
    return f"ID: #{card_id}"


def build_pack_embed(card: Dict, pack_type: str, user: discord.User, player_id: str) -> discord.Embed:
    """Build a rich single-card embed with full-size photo."""
    config = card_module.PACK_CONFIGS[pack_type]
    emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
    color = card_module.RARITY_COLORS.get(card["rarity"], 0x3498DB)
    is_new = not db.has_card_name(player_id, card["name"], card["type"])

    if card["type"] == "driver":
        title = f"👤 {card['name']} ({card['code']})"
    else:
        title = f"🏎️ {card['name']}"

    embed = discord.Embed(
        title=title,
        description=(
            f"{config['emoji']} **{config['name']}** — {user.display_name}\n"
            f"{emoji} **{card['rarity'].upper()}**"
            + ("  ✨ **NEW!**" if is_new else "  *(duplicate)*")
        ),
        color=color,
    )

    if card["type"] == "driver":
        embed.add_field(name="🏁 Team", value=card["team"], inline=True)
        embed.add_field(name="⭐ Skill", value=f"{card['skill']}/10", inline=True)
    else:
        embed.add_field(name="🏁 Team", value=card["team"], inline=True)
        embed.add_field(name="💨 Top Speed", value=f"{card['top_speed']} km/h", inline=True)
        embed.add_field(name="🎛️ Handling", value=f"{card.get('handling', '?')}/10", inline=True)

    if card.get("perks"):
        perk_key = card["perks"][0]
        perk_data = card_module.PERKS.get(perk_key, {})
        embed.add_field(
            name="✨ Special Perk",
            value=f"**{perk_data.get('name', perk_key)}** — {perk_data.get('description', '')}",
            inline=False,
        )

    embed.set_footer(text=format_card_footer(card))
    return embed


def build_spawn_embed(card: Dict, image_filename: Optional[str] = None) -> discord.Embed:
    """Rich embed for wild card spawns."""
    rarity = card["rarity"]
    rarity_emoji = card_module.RARITY_EMOJIS.get(rarity, "")
    color = card_module.RARITY_COLORS.get(rarity, 0x3498DB)

    if card["type"] == "driver":
        card_name = f"👤  {card['name']} ({card.get('code', '')})"
        team_line = card.get("team", "")
    elif card["type"] == "team_asset":
        card_name = f"🏗️  {card['name']}"
        team_line = card.get("team", "")
    else:
        card_name = f"🏎️  {card['name']}"
        team_line = card.get("team", "")

    description = f"{rarity_emoji}  **{rarity.upper()}**"
    if team_line:
        description += f"  ·  {team_line}"

    embed = discord.Embed(
        title="🏁  A wild F1 card appeared!",
        description=f"## {card_name}\n{description}",
        color=color,
    )
    embed.set_footer(text="Type the exact name to catch it!  ·  Expires in 5 minutes")
    if image_filename:
        embed.set_image(url=f"attachment://{image_filename}")
    return embed


# ==================== DYNAMIC PACK OPENING ====================

class PackOpeningView(discord.ui.View):
    """Reveals cards one by one with animated step-by-step interaction."""

    def __init__(self, player_id: str, cards: List[Dict], user: discord.User, pack_type: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.cards = cards
        self.user = user
        self.pack_type = pack_type
        self.index = 0
        for card in cards:
            db.add_card_to_player(player_id, card, card["type"])
        self._refresh_button()

    def _refresh_button(self):
        total = len(self.cards)
        if self.index < total:
            self.reveal_btn.label = f"✨  Reveal Card {self.index + 1} of {total}"
            self.reveal_btn.style = discord.ButtonStyle.primary
            self.reveal_btn.disabled = False
        else:
            self.reveal_btn.label = "📋  See Summary"
            self.reveal_btn.style = discord.ButtonStyle.secondary
            self.reveal_btn.disabled = False

    def sealed_embed(self) -> discord.Embed:
        config = card_module.PACK_CONFIGS[self.pack_type]
        total = len(self.cards)
        embed = discord.Embed(
            title=f"{config['emoji']}  {config['name']}",
            description=(
                f"**{total} card{'s' if total > 1 else ''}** sealed inside.\n\n"
                f"Click the button below to reveal your first card!"
            ),
            color=0x2C3E50,
        )
        embed.set_footer(text=f"Pack opened by {self.user.display_name}")
        return embed

    def card_embed(self, card: Dict, position: int, art_file=None) -> discord.Embed:
        total = len(self.cards)
        rarity = card["rarity"]
        color = card_module.RARITY_COLORS.get(rarity, 0x95A5A6)
        emoji = card_module.RARITY_EMOJIS.get(rarity, "")
        if card["type"] == "driver":
            headline = f"👤  {card['name']} ({card['code']})"
            stats = f"**Team:** {card['team']}  ·  **Skill:** {card['skill']}/10"
        elif card["type"] == "team_asset":
            effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(card.get("effect", ""), card.get("effect", ""))
            headline = f"🏗️  {card['name']}"
            bonus = card.get("bonus", 0)
            effect = card.get("effect", "")
            bonus_str = f"-{bonus:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{bonus:.0%}"
            stats = (
                f"**Team:** {card['team']}  ·  **Role:** {card.get('role', '?')}\n"
                f"{effect_label}: **{bonus_str}**  ·  {card.get('description', '')}"
            )
        else:
            headline = f"🏎️  {card['name']}"
            stats = f"**Team:** {card['team']}  ·  **Top Speed:** {card['top_speed']} km/h"
        if card.get("perks"):
            perk_key = card["perks"][0]
            perk = card_module.PERKS.get(perk_key, {})
            stats += f"\n✨ **{perk.get('name', perk_key)}** — {perk.get('description', '')}"
        remaining = total - position
        embed = discord.Embed(
            title=f"Card {position} of {total}",
            description=f"## {headline}\n{emoji}  **{rarity.upper()}**\n{stats}",
            color=color,
        )
        if art_file:
            embed.set_image(url=f"attachment://{art_file.filename}")
        if remaining > 0:
            embed.set_footer(text=f"{remaining} more card{'s' if remaining != 1 else ''} to go →")
        else:
            embed.set_footer(text="Last card! Click to see your full summary.")
        return embed

    def summary_embed(self) -> discord.Embed:
        config = card_module.PACK_CONFIGS[self.pack_type]
        lines = []
        for card in self.cards:
            emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
            if card["type"] == "driver":
                lines.append(f"{emoji}  **{card['name']}** ({card['code']})  —  {card['rarity'].title()}")
            elif card["type"] == "team_asset":
                lines.append(f"{emoji}  🏗️ **{card['name']}** ({card.get('role', '?')})  —  {card['rarity'].title()}")
            else:
                lines.append(f"{emoji}  **{card['name']}**  —  {card['rarity'].title()}")
        embed = discord.Embed(
            title=f"✅  {config['name']} Complete!",
            description="\n".join(lines),
            color=0x2ECC71,
        )
        embed.set_footer(text="All cards added to your collection!  Use /team to equip staff · /f1 equip for race loadout.")
        return embed

    @discord.ui.button(label="✨  Reveal Card 1", style=discord.ButtonStyle.primary)
    async def reveal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your pack!", ephemeral=True)
            return
        total = len(self.cards)
        if self.index >= total:
            button.disabled = True
            await interaction.response.edit_message(embed=self.summary_embed(), view=self, attachments=[])
            self.stop()
            return
        card = self.cards[self.index]
        self.index += 1
        self._refresh_button()
        art_file = make_card_art_file(card)
        embed = self.card_embed(card, self.index, art_file)
        if art_file:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[art_file])
        else:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])


# ==================== RACE VISUAL HELPERS ====================

RACE_GIFS = [
    "https://media.giphy.com/media/3ohzdIuqJoo8QdKlnW/giphy.gif",
    "https://media.giphy.com/media/26gJAn0QqFWbqQUMw/giphy.gif",
    "https://media.giphy.com/media/l0MYyoYKBIRtjXJEQ/giphy.gif",
    "https://media.giphy.com/media/xT1Ra5h24Eliux3UVq/giphy.gif",
]

# Per-event GIF files — place your GIFs in the race_gifs/ folder with these exact names.
# Any missing file is silently skipped (no crash).
EVENT_GIFS = {
    "pit_window":    "race_gifs/pit_stop.gif",      # Turn 3: pit window opens
    "drs_attack":    "race_gifs/overtake.gif",       # Turn 6: DRS overtake attack
    "late_strategy": "race_gifs/speed_boost.gif",    # Turn 9: late push
    "final_lap":     "race_gifs/final_lap.gif",      # Turn 11: white flag
    "rain_call":     "race_gifs/rain.gif",            # Rain scenario override
    "reaction":      "race_gifs/reaction.gif",        # Reaction challenge flash
    "safety_car":    "race_gifs/safety_car.gif",      # Safety car random event
}


async def _send_event_gif(channel, gif_key: str, delete_after: float = 8.0):
    """Send a local GIF file for the given event key. Silently skips if file missing."""
    path = EVENT_GIFS.get(gif_key)
    if path and os.path.exists(path):
        try:
            await channel.send(file=discord.File(path), delete_after=delete_after)
        except Exception:
            pass

CHOICE_LABELS = {
    "accelerate": ("🚀", "Push Hard"),
    "same_speed":  ("➡️", "Maintain"),
    "slow_down":   ("🛑", "Lift Off"),
    "pit_stop":    ("⛽", "Pit Stop"),
}

def _bar(value: float, max_val: float = 100.0, length: int = 8) -> str:
    ratio = max(0.0, min(1.0, value / max_val))
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)

def _fuel_str(fuel: float) -> str:
    icon = "🟢" if fuel > 50 else ("🟡" if fuel > 25 else "🔴")
    return f"{icon} `{_bar(fuel)}` **{fuel:.0f}%**"

def _tire_str(wear: float, tire_type: str) -> str:
    health = 100.0 - wear
    icon = "🟢" if health > 60 else ("🟡" if health > 30 else "🔴")
    t = {"soft": "Soft", "medium": "Med", "hard": "Hard", "wet": "Wet"}.get(tire_type, tire_type.title())
    return f"{icon} `{_bar(health)}` **{t}** ({health:.0f}%)"

def build_live_embed(
    race: RaceState,
    p1_user: discord.Member,
    p2_user: discord.Member,
    gif_url: str,
    p1_locked: bool = False,
    p2_locked: bool = False,
    last_event: Optional[str] = None,
    commentary_lines: Optional[List[str]] = None,
) -> discord.Embed:
    weather_icon = "🌧️" if race.weather == "rain" else "☀️"
    p1_pos_icon = "🥇" if race.p1_position == 1 else "🥈"
    p2_pos_icon = "🥇" if race.p2_position == 1 else "🥈"

    title = f"🏁  F1 Race  ·  Lap {race.lap}/{race.total_laps}  ·  Turn {race.turn + 1}/{race.max_turns}"

    desc_parts = []
    if commentary_lines:
        desc_parts.append(commentary_engine.format_commentary(commentary_lines[-3:]))
    elif last_event:
        desc_parts.append(f"📡 **{last_event}**")
    if race.weather == "rain":
        desc_parts.append("🌧️ *WET CONDITIONS — pit for wets!*")

    embed = discord.Embed(
        title=title,
        description="\n".join(desc_parts) if desc_parts else None,
        color=0xE74C3C,
    )
    embed.set_image(url=gif_url)

    gap = race.gap
    if abs(gap) < 0.3:
        gap_str = "**⚡ SIDE BY SIDE!**"
    elif gap < 0:
        gap_str = f"🏎️ **{p1_user.display_name}** leads by **{abs(gap):.2f}s**"
    else:
        gap_str = f"🏎️ **{p2_user.display_name}** leads by **{abs(gap):.2f}s**"

    embed.add_field(name=f"{weather_icon}  Race Gap", value=gap_str, inline=False)

    p1_val = (
        f"👤 **{race.p1_driver.name}** ({race.p1_driver.code})  ·  🏎️ **{race.p1_car.name}**\n"
        f"⛽ {_fuel_str(race.p1_fuel)}\n"
        f"🔧 {_tire_str(race.p1_tire_wear, race.p1_tire_type)}"
    )
    embed.add_field(name=f"{p1_pos_icon}  {p1_user.display_name}", value=p1_val, inline=True)

    p2_val = (
        f"👤 **{race.p2_driver.name}** ({race.p2_driver.code})  ·  🏎️ **{race.p2_car.name}**\n"
        f"⛽ {_fuel_str(race.p2_fuel)}\n"
        f"🔧 {_tire_str(race.p2_tire_wear, race.p2_tire_type)}"
    )
    embed.add_field(name=f"{p2_pos_icon}  {p2_user.display_name}", value=p2_val, inline=True)

    p1_status = f"✅ **{p1_user.display_name}** locked in" if p1_locked else f"⏳ Waiting for **{p1_user.display_name}**…"
    p2_status = f"✅ **{p2_user.display_name}** locked in" if p2_locked else f"⏳ Waiting for **{p2_user.display_name}**…"
    embed.add_field(name="​", value=f"{p1_status}\n{p2_status}", inline=False)
    embed.set_footer(text="Both drivers choose · Auto-resolves in 45s if idle")
    return embed


def build_auto_embed(
    race: RaceState,
    p1_user: discord.Member,
    p2_user: discord.Member,
    gif_url: str,
    commentary_log: List[str],
    next_scenario_turn: Optional[int] = None,
) -> discord.Embed:
    """Embed shown during auto-simulation turns — pure commentary, no buttons."""
    weather_icon = "🌧️" if race.weather == "rain" else "☀️"
    p1_pos_icon = "🥇" if race.p1_position == 1 else "🥈"
    p2_pos_icon = "🥇" if race.p2_position == 1 else "🥈"

    title = f"🏎️  F1 Race  ·  Lap {race.lap} / {race.total_laps}  ·  Turn {race.turn} / {race.max_turns}"

    lines = []
    if race.weather == "rain":
        lines.append("🌧️  **WET CONDITIONS**\n")
    if commentary_log:
        lines.append(commentary_engine.format_commentary(commentary_log[-3:]))
    else:
        lines.append("> *Race underway…*")

    embed = discord.Embed(title=title, description="\n".join(lines), color=0xE74C3C)
    embed.set_image(url=gif_url)

    gap = race.gap
    if abs(gap) < 0.3:
        gap_str = "⚡ **SIDE BY SIDE — WHEEL TO WHEEL!**"
    elif gap < 0:
        gap_str = f"**{p1_user.display_name}** leads by **{abs(gap):.2f}s**"
    else:
        gap_str = f"**{p2_user.display_name}** leads by **{abs(gap):.2f}s**"

    embed.add_field(name=f"{weather_icon}  Gap", value=gap_str, inline=False)
    embed.set_footer(text="⚡ Auto-simulation in progress…")
    return embed


def build_scenario_embed(
    scenario: Dict,
    race: RaceState,
    p1_user: discord.Member,
    p2_user: discord.Member,
    gif_url: str,
    p1_locked: bool = False,
    p2_locked: bool = False,
    p1_label: Optional[str] = None,
    p2_label: Optional[str] = None,
) -> discord.Embed:
    """Embed shown during a scenario pause — shows the tactical choice."""
    embed = discord.Embed(
        title=scenario["title"],
        description=(
            f"{scenario['description']}\n\n"
            f"*{scenario['question']}*"
        ),
        color=0xF39C12,
    )
    embed.set_image(url=gif_url)

    embed.add_field(
        name="📊  Current Status",
        value=(
            f"**{p1_user.display_name}:** ⛽ {race.p1_fuel:.0f}%  ·  {_tire_str(race.p1_tire_wear, race.p1_tire_type)}\n"
            f"**{p2_user.display_name}:** ⛽ {race.p2_fuel:.0f}%  ·  {_tire_str(race.p2_tire_wear, race.p2_tire_type)}"
        ),
        inline=False,
    )

    gap = race.gap
    if abs(gap) < 0.3:
        gap_str = "⚡ **Side by side!**"
    elif gap < 0:
        gap_str = f"**{p1_user.display_name}** leads by **{abs(gap):.2f}s**"
    else:
        gap_str = f"**{p2_user.display_name}** leads by **{abs(gap):.2f}s**"
    embed.add_field(name="🏎️  Gap", value=gap_str, inline=True)
    embed.add_field(name="🔄  Lap", value=f"{race.lap}/{race.total_laps}", inline=True)

    p1_status = (
        f"✅  **{p1_user.display_name}** → {p1_label}" if p1_locked
        else f"⏳  Waiting for **{p1_user.display_name}**…"
    )
    p2_status = (
        f"✅  **{p2_user.display_name}** → {p2_label}" if p2_locked
        else f"⏳  Waiting for **{p2_user.display_name}**…"
    )
    embed.add_field(name="📡  Driver Status", value=f"{p1_status}\n{p2_status}", inline=False)
    embed.set_footer(text="Both drivers must choose · Auto-resolves in 30 seconds")
    return embed


def build_challenge_embed(
    challenger: discord.Member, opponent: discord.Member,
    p1_car: Car, p1_driver: Driver,
    p2_car: Car, p2_driver: Driver,
    gif_url: str,
    synergy1: Optional[Dict], synergy2: Optional[Dict],
) -> discord.Embed:
    d1_e = card_module.RARITY_EMOJIS.get(p1_driver.rarity, "")
    c1_e = card_module.RARITY_EMOJIS.get(p1_car.rarity, "")
    d2_e = card_module.RARITY_EMOJIS.get(p2_driver.rarity, "")
    c2_e = card_module.RARITY_EMOJIS.get(p2_car.rarity, "")

    embed = discord.Embed(
        title="⚡  Race Challenge!",
        description=(
            f"{challenger.mention} is challenging {opponent.mention} to a race!\n"
            f"*{opponent.display_name} has 60 seconds to accept or decline.*"
        ),
        color=0x3498DB,
    )
    embed.set_image(url=gif_url)

    p1_val = f"{d1_e} **{p1_driver.name}** ({p1_driver.code})\n{c1_e} **{p1_car.name}** · {p1_car.top_speed} km/h"
    if synergy1:
        p1_val += f"\n✨ *{synergy1['name']}*"
    embed.add_field(name=f"🏎️  {challenger.display_name}", value=p1_val, inline=True)

    p2_val = f"{d2_e} **{p2_driver.name}** ({p2_driver.code})\n{c2_e} **{p2_car.name}** · {p2_car.top_speed} km/h"
    if synergy2:
        p2_val += f"\n✨ *{synergy2['name']}*"
    embed.add_field(name=f"🏎️  {opponent.display_name}", value=p2_val, inline=True)

    embed.set_footer(text="3 Laps · 12 Turns · Manage fuel, tyres & strategy to win")
    return embed


# ==================== ACTIVITY TRACKING ====================

# channel_id (int) → timestamp of last human message seen in that channel
_channel_last_message: Dict[int, float] = {}
# guild_id → timestamp of last wild card spawn
_guild_last_spawn: Dict[str, float] = {}

SPAWN_INTERVAL  = 15 * 60   # seconds between spawns (per guild)
ACTIVITY_WINDOW = 20 * 60   # seconds — channel is "alive" if a message arrived within this window


# ==================== BOT EVENTS ====================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if message.guild:
        _channel_last_message[message.channel.id] = message.created_at.timestamp()
    await bot.process_commands(message)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")
    print(f"✅ Bot logged in as {bot.user}")
    print(f"🏁 F1 Card Racing Bot is ready!")
    if not spawn_wild_card.is_running():
        spawn_wild_card.start()
        print("🃏 Wild card spawn loop started (20 min idle / 15 min active)")
    if not daily_promo_dm.is_running():
        daily_promo_dm.start()
        print("📨 Daily promo DM loop started")


# ==================== WILD CARD SPAWN SYSTEM ====================

class CatchModal(discord.ui.Modal, title="Catch the Card!"):
    """Modal that asks the player to type the card name."""

    answer = discord.ui.TextInput(
        label="Type the name to claim this card",
        placeholder="e.g. Lando Norris  or  McLaren MCL60",
        style=discord.TextStyle.short,
        max_length=60,
    )

    def __init__(self, card: Dict, spawn_view: "SpawnView"):
        super().__init__()
        self.card = card
        self.spawn_view = spawn_view

    async def on_submit(self, interaction: discord.Interaction):
        if self.spawn_view.caught:
            await interaction.response.send_message(
                "Too slow — someone already caught this card!", ephemeral=True
            )
            return

        entered = self.answer.value.strip().lower()
        correct_name = self.card["name"].lower()
        correct_code = self.card.get("code", "").lower()

        if entered == correct_name or (correct_code and entered == correct_code):
            self.spawn_view.caught = True
            for child in self.spawn_view.children:
                child.disabled = True

            player_id = str(interaction.user.id)
            is_returning = db.player_exists(player_id)
            db.ensure_player(player_id, interaction.user.name)
            give_starter_cards(player_id, interaction.user.name)
            db.add_card_to_player(player_id, self.card, self.card["type"])

            rarity_label = self.card["rarity"].upper()
            display = (
                f"{self.card['name']} ({self.card['code']})"
                if self.card["type"] == "driver"
                else self.card["name"]
            )
            card_display_id = f"#{self.card.get('id', '?').upper()}"
            await interaction.response.edit_message(view=self.spawn_view)
            if self.card["type"] == "car":
                extra = "🔧 You caught a mechanic card! Use `/team` to equip it to your team."
            else:
                extra = "Added to your collection. Use `/f1 equip` to race with it."
            returning_note = "\n🏅 Welcome back, veteran racer!" if is_returning else "\n👋 Welcome to F1 Racing! Use `/garage` to see your collection."
            await interaction.followup.send(
                f"{interaction.user.mention} You caught **{display}**! ``({card_display_id},  {rarity_label})``\n"
                f"{extra}{returning_note}"
            )

            # Prompt players who haven't joined career mode yet
            if not db.get_career(player_id):
                await interaction.followup.send(
                    f"🏆 {interaction.user.mention} You don't have a career yet! "
                    f"Use `/career` to sign up and race through 24 circuits to earn championship points and exclusive cards.",
                    ephemeral=True,
                )

            self.spawn_view.stop()
        else:
            await interaction.response.send_message(
                f'Wrong name — try again!', ephemeral=True
            )


class SpawnView(discord.ui.View):
    """Catch button for wild spawns — opens a name-entry modal."""

    def __init__(self, card: Dict):
        super().__init__(timeout=300)
        self.card = card
        self.caught = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Catch me!", style=discord.ButtonStyle.success)
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message(
                "This card was already caught!", ephemeral=True
            )
            return
        await interaction.response.send_modal(CatchModal(self.card, self))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                rarity_emoji = card_module.RARITY_EMOJIS.get(self.card["rarity"], "")
                name = self.card["name"]
                embed = discord.Embed(
                    title="⏰  This card has fled!",
                    description=f"~~**{name}**~~  {rarity_emoji}  **{self.card['rarity'].upper()}**\n*Nobody caught it in time. Better luck next time!*",
                    color=0x95A5A6,
                )
                await self.message.edit(content=None, embed=embed, view=self, attachments=[])
            except Exception:
                pass


@tasks.loop(minutes=1)
async def spawn_wild_card():
    """Spawn a wild card only in channels that have had recent activity.

    A channel is considered alive if a human message was sent there within
    the last ACTIVITY_WINDOW seconds. Dead channels are skipped entirely.
    Spawns happen at most once every SPAWN_INTERVAL seconds per guild.
    """
    now = __import__("time").time()
    for guild in bot.guilds:
        gid = str(guild.id)
        channel_ids = db.get_spawn_channels(gid)
        if not channel_ids:
            continue

        # Only consider channels that have seen recent human activity
        active_channels = [
            guild.get_channel(int(cid))
            for cid in channel_ids
            if (now - _channel_last_message.get(int(cid), 0)) < ACTIVITY_WINDOW
            and guild.get_channel(int(cid)) is not None
        ]
        if not active_channels:
            continue  # All channels are dead — skip this guild entirely

        last_spawn = _guild_last_spawn.get(gid, 0)
        if (now - last_spawn) < SPAWN_INTERVAL:
            continue

        channel = random.choice(active_channels)
        try:
            card = card_module.generate_spawn_card()
            spawn_file = f1_images.get_spawn_file(card)
            spawn_embed = build_spawn_embed(card, image_filename=spawn_file.filename if spawn_file else None)
            view = SpawnView(card)
            if spawn_file:
                msg = await channel.send(content=None, embed=spawn_embed, view=view, file=spawn_file)
            else:
                msg = await channel.send(content=None, embed=spawn_embed, view=view)
            view.message = msg
            _guild_last_spawn[gid] = now
            print(f"🃏 Spawned {card['rarity']} {card['name']} in #{channel.name} ({guild.name}) [active — {SPAWN_INTERVAL//60}min interval]")
        except Exception as e:
            print(f"⚠️ Failed to spawn card in guild {guild.id}: {e}")


@spawn_wild_card.before_loop
async def before_spawn():
    await bot.wait_until_ready()


# ==================== DAILY PROMO DM ====================

@tasks.loop(hours=120)
async def daily_promo_dm():
    """DM every registered player once per day with the server-invite promo."""
    player_ids = db.get_all_player_ids()
    sent = 0
    skipped = 0
    for pid in player_ids:
        if not db.should_send_promo_dm(pid):
            skipped += 1
            continue
        try:
            user = await bot.fetch_user(int(pid))
            await user.send(
                "🏎️ **F1 Card Bot** — your cards are waiting! "
                "Use `/race` to challenge someone or `/daily` to claim your pack. GL HF! 🏁"
            )
            db.set_promo_dm_sent(pid)
            sent += 1
            await asyncio.sleep(1)
        except discord.Forbidden:
            db.set_promo_dm_sent(pid)
            skipped += 1
        except discord.NotFound:
            skipped += 1
        except Exception as e:
            print(f"⚠️ Failed to send promo DM to {pid}: {e}")
    print(f"📨 Daily promo DM: sent={sent}, skipped={skipped}")


@daily_promo_dm.before_loop
async def before_promo_dm():
    await bot.wait_until_ready()


# ==================== CONFIG COMMANDS ====================

def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return (
        interaction.user.guild_permissions.manage_guild
        or interaction.user.guild_permissions.administrator
    )


@channels_group.command(name="add", description="Add a channel where F1 cards will spawn")
@app_commands.describe(channel="The channel to add")
async def config_channels_add(interaction: discord.Interaction, channel: discord.TextChannel):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ You need **Manage Server** permission to do this.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    added = db.add_spawn_channel(guild_id, channel.id)
    if added:
        embed = discord.Embed(
            title="✅ Spawn Channel Added",
            description=f"{channel.mention} will now receive wild F1 card spawns every 30 minutes.",
            color=0x2ECC71,
        )
        embed.add_field(
            name="Drop Rates",
            value="⚪ Common: 55%  |  💙 Rare: 30%  |  💜 Epic: 12%  |  👑 Legendary: 3%",
            inline=False,
        )
    else:
        embed = discord.Embed(
            title="ℹ️ Already Added",
            description=f"{channel.mention} is already a spawn channel.",
            color=0x3498DB,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@channels_group.command(name="remove", description="Remove a card spawn channel")
@app_commands.describe(channel="The channel to remove")
async def config_channels_remove(interaction: discord.Interaction, channel: discord.TextChannel):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ You need **Manage Server** permission to do this.", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    removed = db.remove_spawn_channel(guild_id, channel.id)
    if removed:
        embed = discord.Embed(
            title="✅ Spawn Channel Removed",
            description=f"{channel.mention} will no longer receive wild card spawns.",
            color=0xE74C3C,
        )
    else:
        embed = discord.Embed(
            title="ℹ️ Not Found",
            description=f"{channel.mention} was not a spawn channel.",
            color=0x95A5A6,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@channels_group.command(name="list", description="List all configured card spawn channels")
async def config_channels_list(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    channel_ids = db.get_spawn_channels(guild_id)
    if not channel_ids:
        embed = discord.Embed(
            title="📋 Spawn Channels",
            description="No spawn channels configured yet.\nUse `/config channels add #channel` to set one up.",
            color=0x95A5A6,
        )
    else:
        mentions = []
        for cid in channel_ids:
            ch = interaction.guild.get_channel(int(cid))
            mentions.append(ch.mention if ch else f"<deleted channel {cid}>")
        embed = discord.Embed(
            title="📋 Spawn Channels",
            description="\n".join(mentions),
            color=0x3498DB,
        )
        embed.set_footer(text="Cards spawn every 30 minutes in one of these channels.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== CARD MANAGEMENT (ADMIN) ====================

async def _save_attachment(attachment: discord.Attachment, path: str):
    """Download a Discord attachment and save it to path."""
    import aiohttp
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(attachment.url) as resp:
            if resp.status == 200:
                with open(path, "wb") as f:
                    f.write(await resp.read())


@config_group.command(name="adddriver", description="Add a custom driver card to the spawn/pack pool")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    name="Full driver name (e.g. Kimi Antonelli)",
    code="3-letter code used for image lookup (e.g. ANT)",
    skill="Skill rating 1.0 – 10.0",
    team="Team name (e.g. Mercedes)",
    rarity="Card rarity tier",
    card_image="Card art shown in collection & packs (full designed card PNG)",
    spawn_image="Photo shown when the card spawns in chat (clean driver photo)",
)
async def config_adddriver(
    interaction: discord.Interaction,
    name: str,
    code: str,
    skill: float,
    team: str,
    rarity: Literal["common", "rare", "epic", "legendary", "mythic"],
    card_image: Optional[discord.Attachment] = None,
    spawn_image: Optional[discord.Attachment] = None,
):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    saved = []
    if card_image:
        ext = os.path.splitext(card_image.filename)[1] or ".png"
        await _save_attachment(card_image, f"card_images/{code.upper()}{ext}")
        saved.append(f"Card art → `card_images/{code.upper()}{ext}`")
    if spawn_image:
        ext2 = os.path.splitext(spawn_image.filename)[1] or ".png"
        await _save_attachment(spawn_image, f"card_images/spawn/{code.upper()}{ext2}")
        saved.append(f"Spawn photo → `card_images/spawn/{code.upper()}{ext2}`")
    entry = cm.add_driver(name, code, skill, team, rarity)
    color = card_module.RARITY_COLORS.get(rarity, 0x95A5A6)
    emoji = card_module.RARITY_EMOJIS.get(rarity, "")
    embed = discord.Embed(
        title="✅ Driver Card Added",
        description=f"{emoji} **{entry['name']}** (`{entry['code']}`) — {rarity.title()}\n"
                    f"Team: {team}  ·  Skill: {skill}/10",
        color=color,
    )
    embed.set_footer(text="\n".join(saved) if saved else "No images provided — upload later via this command.")
    await interaction.followup.send(embed=embed, ephemeral=True)


@config_group.command(name="addcar", description="Add a custom car card to the spawn/pack pool")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    name="Full car name (e.g. Williams FW47)",
    team="Team name (e.g. Williams)",
    top_speed="Top speed in km/h (e.g. 355)",
    handling="Handling rating 1.0 – 10.0",
    rarity="Card rarity tier",
    card_image="Card art shown in collection & packs (full designed card PNG)",
    spawn_image="Photo shown when the card spawns in chat",
)
async def config_addcar(
    interaction: discord.Interaction,
    name: str,
    team: str,
    top_speed: int,
    handling: float,
    rarity: Literal["common", "rare", "epic", "legendary", "mythic"],
    card_image: Optional[discord.Attachment] = None,
    spawn_image: Optional[discord.Attachment] = None,
):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    slug = name.replace(" ", "_").replace("+", "plus")
    saved = []
    if card_image:
        ext = os.path.splitext(card_image.filename)[1] or ".png"
        await _save_attachment(card_image, f"card_images/cars/{slug}{ext}")
        saved.append(f"Card art → `card_images/cars/{slug}{ext}`")
    if spawn_image:
        ext2 = os.path.splitext(spawn_image.filename)[1] or ".png"
        await _save_attachment(spawn_image, f"card_images/spawn/car_{slug}{ext2}")
        saved.append(f"Spawn photo → `card_images/spawn/car_{slug}{ext2}`")
    entry = cm.add_car(name, team, top_speed, handling, rarity)
    color = card_module.RARITY_COLORS.get(rarity, 0x95A5A6)
    emoji = card_module.RARITY_EMOJIS.get(rarity, "")
    embed = discord.Embed(
        title="✅ Car Card Added",
        description=f"{emoji} **{entry['name']}** — {rarity.title()}\n"
                    f"Team: {team}  ·  Top Speed: {top_speed} km/h  ·  Handling: {handling}/10",
        color=color,
    )
    embed.set_footer(text="\n".join(saved) if saved else "No images provided — upload later via this command.")
    await interaction.followup.send(embed=embed, ephemeral=True)


@config_group.command(name="listcards", description="List all custom cards in the pool")
@app_commands.default_permissions(administrator=True)
async def config_listcards(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    data = cm.list_all()
    drivers = data.get("drivers", [])
    cars = data.get("cars", [])
    embed = discord.Embed(title="📋 Custom Cards", color=0x5865F2)
    if drivers:
        lines = []
        for d in drivers:
            emoji = card_module.RARITY_EMOJIS.get(d["rarity"], "")
            lines.append(f"{emoji} **{d['name']}** (`{d['code']}`) — {d['rarity'].title()} | {d['team']} | Skill {d['skill']}")
        embed.add_field(name="👤 Drivers", value="\n".join(lines), inline=False)
    if cars:
        lines = []
        for c in cars:
            emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
            lines.append(f"{emoji} **{c['name']}** — {c['rarity'].title()} | {c['team']} | {c['top_speed']} km/h")
        embed.add_field(name="🏎️ Cars", value="\n".join(lines), inline=False)
    if not drivers and not cars:
        embed.description = "No custom cards yet.\nUse `/config adddriver` or `/config addcar` to add some!"
    await interaction.response.send_message(embed=embed, ephemeral=True)


@config_group.command(name="removedriver", description="Remove a custom driver card by code")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(code="3-letter driver code (e.g. ANT)")
async def config_removedriver(interaction: discord.Interaction, code: str):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    removed = cm.remove_driver(code)
    if removed:
        await interaction.response.send_message(f"✅ Driver `{code.upper()}` removed from custom pool.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No custom driver with code `{code.upper()}` found.", ephemeral=True)


@config_group.command(name="removecar", description="Remove a custom car card by name")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(name="Exact car name (e.g. Williams FW47)")
async def config_removecar(interaction: discord.Interaction, name: str):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    removed = cm.remove_car(name)
    if removed:
        await interaction.response.send_message(f"✅ Car **{name}** removed from custom pool.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No custom car named **{name}** found.", ephemeral=True)


# ==================== PACK SLASH COMMANDS ====================

@pack_group.command(name="daily", description="Open your daily pack — 1 card, resets every 24 hours")
async def pack_daily(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    can_claim, remaining = db.can_claim_daily(player_id)
    if not can_claim:
        embed = discord.Embed(
            title="⏳ Daily Pack Not Ready",
            description=f"Your daily pack resets in **{format_cooldown(remaining)}**.",
            color=0xE74C3C,
        )
        embed.set_footer(text="Try /pack weekly for another free pack!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    pack_cards = card_module.generate_pack("daily")
    db.mark_daily_claimed(player_id)
    view = PackOpeningView(player_id, pack_cards, interaction.user, "daily")
    await interaction.followup.send(embed=view.sealed_embed(), view=view)


@pack_group.command(name="weekly", description="Open your weekly pack — guaranteed Rare+, resets every 7 days")
async def pack_weekly(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    can_claim, remaining = db.can_claim_weekly(player_id)
    if not can_claim:
        embed = discord.Embed(
            title="⏳ Weekly Pack Not Ready",
            description=f"Your weekly pack resets in **{format_cooldown(remaining)}**.",
            color=0xE74C3C,
        )
        embed.set_footer(text="Try /pack daily for a free daily pack!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    await interaction.response.defer()

    pack_cards = card_module.generate_pack("weekly")
    db.mark_weekly_claimed(player_id)
    view = PackOpeningView(player_id, pack_cards, interaction.user, "weekly")
    await interaction.followup.send(embed=view.sealed_embed(), view=view)


# ==================== F1 SLASH COMMANDS ====================

@f1_group.command(name="equip", description="Equip a driver or car card for racing")
async def f1_equip(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    equipped = db.get_equipped(player_id)
    equipped_driver = db.get_card_by_id(player_id, equipped["driver_id"]) if equipped.get("driver_id") else None
    equipped_car = db.get_card_by_id(player_id, equipped["car_id"]) if equipped.get("car_id") else None

    d_emoji = card_module.RARITY_EMOJIS.get(equipped_driver["rarity"], "") if equipped_driver else ""
    c_emoji = card_module.RARITY_EMOJIS.get(equipped_car["rarity"], "") if equipped_car else ""

    embed = discord.Embed(
        title="⚙️ Equip Cards",
        description="Choose what you want to equip for your next race.",
        color=0x2C3E50,
    )
    embed.add_field(
        name="👤 Active Driver",
        value=f"{d_emoji} **{equipped_driver['name']}** ({equipped_driver['code']})" if equipped_driver else "*None equipped*",
        inline=True,
    )
    embed.add_field(
        name="🏎️ Active Car",
        value=f"{c_emoji} **{equipped_car['name']}**" if equipped_car else "*None equipped*",
        inline=True,
    )
    embed.set_footer(text="Select a card type below to change your loadout.")

    view = EquipTypeView(player_id)
    await interaction.response.send_message(embed=embed, view=view)


RANK_EMOJIS_MAP = {
    "Diamond": "💠",
    "Platinum": "💎",
    "Gold": "🥇",
    "Silver": "🥈",
    "Bronze": "🥉",
}

UPGRADE_BAR_MAP = {s: UPGRADE_INFO[s]["emoji"] for s in UPGRADE_STATS}


def _upgrade_progress(level: int, max_level: int = 5) -> str:
    filled = "█" * level
    empty = "░" * (max_level - level)
    return f"`{filled}{empty}`  Lv.{level}/{max_level}"


def build_profile_embeds(player_id: str, display_name: str) -> List[discord.Embed]:
    player = db.get_player(player_id)
    if not player:
        return []
    stats = player.get("stats", {})
    cards = db.get_player_cards(player_id)
    upgrades = db.get_upgrades(player_id)
    equipped = db.get_equipped(player_id)
    coins = db.get_coins(player_id)

    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    dnf = stats.get("dnf", 0)
    total = stats.get("total_races", 0)
    win_rate = (wins / total * 100) if total > 0 else 0.0
    rank = stats.get("rank", "Bronze")
    rp = stats.get("ranking_points", 0)
    rank_emoji = RANK_EMOJIS_MAP.get(rank, "🏁")

    n_drivers = len(cards.get("drivers", []))
    n_cars = len(cards.get("cars", []))
    n_team = len(cards.get("team_assets", []))
    total_cards = n_drivers + n_cars + n_team

    driver_name = "*None equipped*"
    car_name = "*None equipped*"
    if equipped.get("driver_id"):
        d = db.get_card_by_id(player_id, equipped["driver_id"])
        if d:
            driver_name = f"{d['name']} ({d['code']})"
    if equipped.get("car_id"):
        c = db.get_card_by_id(player_id, equipped["car_id"])
        if c:
            car_name = c["name"]

    total_upgrades = sum(upgrades.get(s, 0) for s in UPGRADE_STATS)
    max_upgrades = UPGRADE_MAX_LEVEL * len(UPGRADE_STATS)

    created = player.get("created_at", "")
    try:
        joined = datetime.fromisoformat(created).strftime("%b %d %Y")
    except Exception:
        joined = "Unknown"

    # Embed 1 — Main profile
    e1 = discord.Embed(title=f"{rank_emoji}  {display_name}", color=0x00FF88)
    e1.add_field(
        name="🏆 Race Record",
        value=(
            f"🥇 Wins: **{wins}**\n"
            f"🥈 Losses: **{losses}**\n"
            f"⚠️ DNF: **{dnf}**"
        ),
        inline=True,
    )
    e1.add_field(
        name=f"{rank_emoji} Rank",
        value=f"**{rank}**\n{rp} Ranking Points",
        inline=True,
    )
    e1.add_field(
        name="💰 Coins",
        value=f"**{coins:,}**",
        inline=True,
    )
    e1.add_field(
        name="📊 Statistics",
        value=f"📊 Total Races: **{total}**\n📈 Win Rate: **{win_rate:.1f}%**",
        inline=False,
    )
    e1.set_footer(text=f"Joined: {joined}")

    # Embed 2 — Collection
    e2 = discord.Embed(title="🎴 Collection", color=0x64C8FF)
    e2.add_field(name="👤 Drivers", value=f"**{n_drivers}**", inline=True)
    e2.add_field(name="🏎️ Cars", value=f"**{n_cars}**", inline=True)
    e2.add_field(name="🏗️ Staff", value=f"**{n_team}**", inline=True)
    e2.add_field(name="✨ Total Cards", value=f"**{total_cards}**", inline=False)

    # Embed 3 — Equipped
    e3 = discord.Embed(title="🏎️ Currently Equipped", color=0xFF6B9D)
    e3.add_field(name="👤 Driver", value=driver_name, inline=False)
    e3.add_field(name="🏎️ Car", value=car_name, inline=False)

    # Embed 4 — Upgrades
    e4 = discord.Embed(title=f"🔧 Upgrades ({total_upgrades}/{max_upgrades})", color=0xFFC800)
    for stat in UPGRADE_STATS:
        info = UPGRADE_INFO[stat]
        level = upgrades.get(stat, 0)
        e4.add_field(
            name=f"{info['emoji']} {info['label']}",
            value=_upgrade_progress(level),
            inline=True,
        )

    return [e1, e2, e3, e4]


@f1_group.command(name="profile", description="View your F1 racing profile and stats")
async def f1_profile(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)
    embeds = build_profile_embeds(player_id, interaction.user.display_name)
    await interaction.response.send_message(embeds=embeds)


@f1_group.command(name="collection", description="Browse a card collection — yours or another player's")
@discord.app_commands.describe(user="The player whose collection to view (leave blank for your own)")
async def f1_collection(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    viewing_other = user is not None and user.id != interaction.user.id

    if viewing_other:
        target         = user
        target_id      = str(target.id)
        display_name   = target.display_name
        if not db.player_exists(target_id):
            await interaction.response.send_message(
                f"**{target.display_name}** hasn't started playing yet.", ephemeral=True
            )
            return
        all_cards = db.get_all_cards_sorted(target_id)
        if not all_cards:
            await interaction.response.send_message(
                f"**{target.display_name}** has no cards yet!", ephemeral=True
            )
            return
        view = CollectionView(target_id, all_cards, display_name)
        await interaction.response.send_message(
            content=f"📖 {target.mention}'s card collection:",
            embed=view.build_embed(),
            view=view,
        )
        return

    # Viewing own collection
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    all_cards = db.get_all_cards_sorted(player_id)
    if not all_cards:
        embed = discord.Embed(
            title="🎴 Your Collection",
            description="You have no cards yet! Open packs with `/pack daily` or `/pack weekly`.",
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed)
        return

    view = CollectionView(player_id, all_cards, interaction.user.display_name)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


# ==================== SHOP ====================

BUYABLE_PACKS = ["bronze", "silver", "gold", "platinum"]

PACK_CONTENTS = {
    "bronze":   "Common & Rare F1 Cards",
    "silver":   "Rare, Epic & occasional Legendary Cards",
    "gold":     "Epic & Legendary F1 Cards",
    "platinum": "Legendary F1 Cards — Guaranteed!",
}


def build_shop_embed(player_id: str) -> discord.Embed:
    balance = db.get_coins(player_id)
    embed = discord.Embed(
        title="📦  Pack Shop",
        description=(
            "Purchase mystery packs to unlock exclusive F1 Cards!\n"
            "✨ Each pack contains random cards based on rarity!"
        ),
        color=0xF39C12,
    )
    embed.add_field(name="💰 Your Coins", value=str(balance), inline=True)

    pack_lines = []
    for pack_key in BUYABLE_PACKS:
        cfg = card_module.PACK_CONFIGS[pack_key]
        guar = cfg.get("guaranteed")
        guar_str = f" (Guaranteed {guar.title()}+)" if guar else ""
        contents = PACK_CONTENTS.get(pack_key, "")
        affordable = "" if balance >= cfg["cost"] else "  ❌"
        pack_lines.append(
            f"**{cfg['emoji']} {cfg['name']}**{affordable}\n"
            f"└ Price: **{cfg['cost']:,} coins**\n"
            f"└ {contents}{guar_str}\n"
            f"└ {cfg['card_count']} card{'s' if cfg['card_count'] > 1 else ''} per pack"
        )

    embed.add_field(
        name="Available Packs",
        value="\n\n".join(pack_lines),
        inline=False,
    )
    embed.set_footer(text="Purchase packs here, then reveal cards one by one!  Win races to earn more coins.")
    return embed


class ShopView(discord.ui.View):
    """Select-dropdown shop matching the clean reference design."""

    def __init__(self, player_id: str, user: discord.User):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.user = user

        balance = db.get_coins(player_id)
        options = []
        for pack_key in BUYABLE_PACKS:
            cfg = card_module.PACK_CONFIGS[pack_key]
            affordable = balance >= cfg["cost"]
            label = f"{cfg['name']}  —  {cfg['cost']:,} coins"
            desc = PACK_CONTENTS.get(pack_key, "")[:100]
            options.append(discord.SelectOption(
                label=label[:100],
                value=pack_key,
                description=desc,
                emoji=cfg["emoji"],
            ))

        self.select = discord.ui.Select(
            placeholder="Choose a pack to purchase…",
            options=options,
            min_values=1,
            max_values=1,
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your shop menu!", ephemeral=True)
            return
        pack_key = self.select.values[0]
        cfg = card_module.PACK_CONFIGS[pack_key]
        cost = cfg["cost"]
        balance = db.get_coins(self.player_id)
        if balance < cost:
            short = cost - balance
            await interaction.response.send_message(
                f"❌ Not enough coins!  You have **{balance:,}** but need **{cost:,}**  *(short by {short:,})*.",
                ephemeral=True,
            )
            return
        # Defer immediately to prevent the 3-second interaction timeout expiring
        # while the blocking Replit DB backup runs.
        await interaction.response.defer()
        db.spend_coins(self.player_id, cost)
        new_balance = db.get_coins(self.player_id)
        pack_cards = card_module.generate_pack(pack_key)
        open_view = PackOpeningView(self.player_id, pack_cards, interaction.user, pack_key)
        await interaction.edit_original_response(
            content=f"✅  Bought **{cfg['emoji']} {cfg['name']}** for **{cost:,} coins**  ·  Remaining: **{new_balance:,} coins**",
            embed=open_view.sealed_embed(),
            view=open_view,
        )


@bot.tree.command(name="shop", description="Buy packs with your race credits")
async def shop_command(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    embed = build_shop_embed(player_id)
    view = ShopView(player_id, interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


# ==================== SELL CARDS ====================

class MultiSellView(discord.ui.View):
    """Multi-card sell — select 1-25 cards per page and sell them all at once."""

    PER_PAGE = 20

    def __init__(self, player_id: str, all_cards: List[Dict], user: discord.User):
        super().__init__(timeout=180)
        self.player_id = player_id
        self.user = user
        # Starter cards are protected — cannot be sold
        RARITY_ORDER = {"common": 0, "rare": 1, "epic": 2, "legendary": 3, "mythic": 4}
        self.starter_count = sum(
            1 for c in all_cards
            if c["id"].startswith("starter_driver_") or c["id"].startswith("starter_car_")
        )
        sellable = [
            c for c in all_cards
            if not c["id"].startswith("starter_driver_") and not c["id"].startswith("starter_car_")
        ]
        self.all_cards = sorted(sellable, key=lambda c: RARITY_ORDER.get(c["rarity"], 0))
        self.page = 0
        self.total_pages = max(1, (len(self.all_cards) + self.PER_PAGE - 1) // self.PER_PAGE)
        self.selected_ids: set = set()
        self._rebuild()

    def _page_cards(self) -> List[Dict]:
        start = self.page * self.PER_PAGE
        return self.all_cards[start:start + self.PER_PAGE]

    def _total_value(self) -> int:
        return sum(
            card_module.SELL_VALUES.get(c["rarity"], 0)
            for c in self.all_cards if c["id"] in self.selected_ids
        )

    def _rebuild(self):
        self.clear_items()
        page_cards = self._page_cards()

        if page_cards:
            options = []
            for card in page_cards:
                emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
                price = card_module.SELL_VALUES.get(card["rarity"], 0)
                if card["type"] == "driver":
                    label = f"{card['name']} ({card['code']})"
                elif card["type"] == "team_asset":
                    label = f"🏗️ {card['name']} ({card.get('role','?')})"
                else:
                    label = card["name"]
                label = label[:95]
                desc = f"{card['rarity'].title()} · {price:,} 💰"
                options.append(discord.SelectOption(
                    label=label,
                    value=card["id"],
                    description=desc[:100],
                    emoji=emoji,
                    default=(card["id"] in self.selected_ids),
                ))

            select = discord.ui.Select(
                placeholder=f"Pick cards to sell (pg {self.page+1}/{self.total_pages}) · {len(self.selected_ids)} selected",
                options=options,
                min_values=0,
                max_values=len(options),
                row=0,
            )
            select.callback = self._on_select
            self.add_item(select)

        # Page nav
        if self.total_pages > 1:
            prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=(self.page == 0), row=1)
            prev_btn.callback = self._go_prev
            self.add_item(prev_btn)

            page_lbl = discord.ui.Button(label=f"{self.page+1}/{self.total_pages}", style=discord.ButtonStyle.primary, disabled=True, row=1)
            self.add_item(page_lbl)

            next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=(self.page >= self.total_pages - 1), row=1)
            next_btn.callback = self._go_next
            self.add_item(next_btn)

        # Sell / Clear / Close
        total_val = self._total_value()
        sell_label = (f"💰 Sell {len(self.selected_ids)} cards · +{total_val:,} coins" if self.selected_ids else "Select cards to sell")[:80]
        sell_btn = discord.ui.Button(
            label=sell_label,
            style=discord.ButtonStyle.success if self.selected_ids else discord.ButtonStyle.secondary,
            disabled=not self.selected_ids,
            row=2,
        )
        sell_btn.callback = self._on_sell
        self.add_item(sell_btn)

        clear_btn = discord.ui.Button(label="✖ Clear All", style=discord.ButtonStyle.danger, disabled=not self.selected_ids, row=2)
        clear_btn.callback = self._on_clear
        self.add_item(clear_btn)

        close_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.secondary, row=2)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _build_embed(self) -> discord.Embed:
        balance   = db.get_coins(self.player_id)
        n_sel     = len(self.selected_ids)
        total_val = self._total_value()

        lines = [
            f"💰 **Balance:** {balance:,} coins",
            "",
            "**Sell Prices:**",
            "⚪ Common **75**  ·  💙 Rare **200**  ·  💜 Epic **600**  ·  👑 Legendary **1,500**",
        ]
        if n_sel:
            lines.append(f"\n✅ **{n_sel} card{'s' if n_sel != 1 else ''} selected** — earns **+{total_val:,} coins**")
        else:
            lines.append("\n*Select cards from the dropdown, then hit Sell.*")

        embed = discord.Embed(
            title="💸  Sell Cards",
            description="\n".join(lines),
            color=0xF39C12,
        )
        if self.starter_count:
            embed.add_field(
                name="🔒 Starter Cards Protected",
                value=f"Your **{self.starter_count}** starter card(s) cannot be sold — they are your base equipment.",
                inline=False,
            )
        equipped = db.get_equipped(self.player_id)
        eq_ids = {equipped.get("driver_id"), equipped.get("car_id")} | set(equipped.get("team_assets", []))
        equipped_selected = [c for c in self.all_cards if c["id"] in self.selected_ids and c["id"] in eq_ids]
        if equipped_selected:
            embed.add_field(
                name="⚠️ Warning",
                value=f"**{len(equipped_selected)}** selected card(s) are currently equipped — selling them will unequip.",
                inline=False,
            )
        embed.set_footer(text=f"{len(self.all_cards)} sellable cards · Page {self.page+1}/{self.total_pages}")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        page_ids = {c["id"] for c in self._page_cards()}
        self.selected_ids -= page_ids
        self.selected_ids.update(interaction.data["values"])
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _go_prev(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = min(self.total_pages - 1, self.page + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_sell(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        if not self.selected_ids:
            await interaction.response.send_message("No cards selected!", ephemeral=True)
            return

        total_coins = 0
        sold_cards  = []
        for card in list(self.all_cards):
            if card["id"] in self.selected_ids:
                if db.remove_card(self.player_id, card["id"]):
                    total_coins += card_module.SELL_VALUES.get(card["rarity"], 0)
                    sold_cards.append(card)

        new_balance = db.add_coins(self.player_id, total_coins)

        rarity_counts: Dict[str, int] = {}
        for c in sold_cards:
            rarity_counts[c["rarity"]] = rarity_counts.get(c["rarity"], 0) + 1

        summary = []
        for rarity in ("mythic", "legendary", "epic", "rare", "common"):
            cnt = rarity_counts.get(rarity, 0)
            if cnt:
                emoji = card_module.RARITY_EMOJIS.get(rarity, "")
                val   = card_module.SELL_VALUES.get(rarity, 0) * cnt
                summary.append(f"{emoji} **{rarity.title()}** × {cnt}  —  +**{val:,} coins**")

        embed = discord.Embed(
            title="✅  Cards Sold!",
            description=(
                "\n".join(summary) + "\n\n"
                f"**Total earned:** +**{total_coins:,} coins**\n"
                f"**New balance: {new_balance:,} coins**"
            ),
            color=0x2ECC71,
        )
        embed.set_footer(text=f"Sold {len(sold_cards)} card{'s' if len(sold_cards) != 1 else ''}")
        await interaction.response.edit_message(embed=embed, view=None)

    async def _on_clear(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.selected_ids.clear()
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_close(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Sell menu closed.", embed=None, view=None)


@f1_group.command(name="sell", description="Sell cards from your collection for race credits — pick multiple at once")
async def f1_sell(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    all_cards = db.get_all_cards_sorted(player_id)
    if not all_cards:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ No Cards to Sell",
                description="You have no cards yet! Open packs with `/pack daily` or `/pack weekly`.",
                color=0xE74C3C,
            ),
            ephemeral=True,
        )
        return

    view = MultiSellView(player_id, all_cards, interaction.user)
    await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)


# ==================== TRADING SYSTEM ====================

# ── Multi-card trade state ────────────────────────────────────────────────────
# trade_id → {"offerer_id", "target_id", "offerer_cards", "target_cards",
#              "offerer_confirmed", "target_confirmed"}
_active_multi_trades: Dict[str, Dict] = {}


def _is_starter(card_id: str) -> bool:
    return card_id.startswith("starter_driver_") or card_id.startswith("starter_car_")


def _card_label(card: Dict) -> str:
    rarity = card.get("rarity", "common").title()
    emoji  = card_module.RARITY_EMOJIS.get(card.get("rarity", "common"), "")
    if card.get("type") == "driver":
        return f"{emoji} {card['name']} ({card.get('code','?')}) — {rarity}"
    elif card.get("type") == "team_asset":
        return f"🏗️ {card['name']} ({card.get('role','?')}) — {rarity}"
    return f"{emoji} {card['name']} — {rarity}"


def _trade_cards_str(cards: List[Dict], confirmed: bool) -> str:
    if not cards:
        return "*No cards added yet*"
    lines = []
    for c in cards:
        re = card_module.RARITY_EMOJIS.get(c.get("rarity", "common"), "")
        lines.append(f"{re} **{c['name']}**")
    if confirmed:
        lines.append("✅ **CONFIRMED**")
    return "\n".join(lines)


class TradeCardPickerView(discord.ui.View):
    """Ephemeral dropdown — player picks one card to add to their trade side."""

    def __init__(self, trade_view: "MultiTradeView", player: discord.Member,
                 is_offerer: bool, cards: List[Dict]):
        super().__init__(timeout=60)
        self.trade_view = trade_view
        self.player     = player
        self.is_offerer = is_offerer
        self._cards: Dict[str, Dict] = {}

        options = []
        for c in cards[:25]:
            price = card_module.SELL_VALUES.get(c.get("rarity", "common"), 0)
            options.append(discord.SelectOption(
                label=f"{c['name']}"[:100],
                value=c["id"],
                description=f"{c.get('rarity','').title()} · worth {price:,} coins"[:100],
                emoji=card_module.RARITY_EMOJIS.get(c.get("rarity", "common"), None),
            ))
            self._cards[c["id"]] = c

        sel = discord.ui.Select(placeholder="Pick a card to add to your offer…", options=options)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your picker!", ephemeral=True)
            return
        card_id = interaction.data["values"][0]
        card    = self._cards.get(card_id)
        trade   = _active_multi_trades.get(self.trade_view.trade_id)
        if not card or not trade:
            await interaction.response.edit_message(content="Trade expired.", view=None)
            return

        async with self.trade_view.lock:
            side = trade["offerer_cards"] if self.is_offerer else trade["target_cards"]
            if len(side) >= 5:
                await interaction.response.edit_message(content="Maximum 5 cards per side reached.", view=None)
                return
            if any(c["id"] == card_id for c in side):
                await interaction.response.edit_message(content="That card is already in your offer.", view=None)
                return
            side.append(card)
            # reset this player's confirmation when they change their offer
            if self.is_offerer:
                trade["offerer_confirmed"] = False
            else:
                trade["target_confirmed"] = False

        self.stop()
        await interaction.response.edit_message(
            content=f"✅  Added **{card['name']}** to your offer!", view=None
        )
        if self.trade_view.message:
            try:
                await self.trade_view.message.edit(
                    embed=self.trade_view.build_embed(), view=self.trade_view
                )
            except Exception:
                pass


class MultiTradeView(discord.ui.View):
    """
    Live trade room — both players add / remove cards, then both confirm.
    Supports up to 5 cards per side.
    """

    def __init__(self, trade_id: str, offerer: discord.Member, target: discord.Member):
        super().__init__(timeout=300)
        self.trade_id = trade_id
        self.offerer  = offerer
        self.target   = target
        self.lock     = asyncio.Lock()
        self.message: Optional[discord.Message] = None

    def _is_participant(self, user_id: int) -> bool:
        return user_id in (self.offerer.id, self.target.id)

    def build_embed(self) -> discord.Embed:
        trade = _active_multi_trades.get(self.trade_id)
        if not trade:
            return discord.Embed(title="Trade expired", color=0xE74C3C)

        oc = trade["offerer_cards"]
        tc = trade["target_cards"]
        e  = discord.Embed(
            title="🔄  Multi-Card Trade",
            description=(
                f"{self.offerer.mention}  ↔️  {self.target.mention}\n\n"
                f"Both players add cards (up to **5 each**), then both press "
                f"**✅ Confirm Trade** to complete the swap.\n"
                f"Either player can press **❌ Cancel** at any time."
            ),
            color=0xF39C12,
        )
        e.add_field(
            name=f"{'✅ ' if trade['offerer_confirmed'] else '🔴 '}{self.offerer.display_name}",
            value=_trade_cards_str(oc, trade["offerer_confirmed"]),
            inline=True,
        )
        e.add_field(name="↔️", value="\u200b", inline=True)
        e.add_field(
            name=f"{'✅ ' if trade['target_confirmed'] else '🔵 '}{self.target.display_name}",
            value=_trade_cards_str(tc, trade["target_confirmed"]),
            inline=True,
        )
        e.set_footer(text=f"Cards: {len(oc)}/5 ↔ {len(tc)}/5  ·  Trade expires in 5 minutes")
        return e

    # ── Add Card ──────────────────────────────────────────────────────────────
    @discord.ui.button(label="➕ Add Card", style=discord.ButtonStyle.success, row=0)
    async def add_card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user.id):
            await interaction.response.send_message("You're not part of this trade!", ephemeral=True)
            return
        trade = _active_multi_trades.get(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade has expired.", ephemeral=True)
            return

        is_offerer = interaction.user.id == self.offerer.id
        side       = trade["offerer_cards"] if is_offerer else trade["target_cards"]
        confirmed  = trade["offerer_confirmed"] if is_offerer else trade["target_confirmed"]

        if confirmed:
            await interaction.response.send_message(
                "You've already confirmed — press **❌ Cancel** to restart, or wait for the other player.",
                ephemeral=True,
            )
            return
        if len(side) >= 5:
            await interaction.response.send_message("Maximum 5 cards per side reached.", ephemeral=True)
            return

        player_id       = str(interaction.user.id)
        already_ids     = {c["id"] for c in side}
        all_p           = db.get_all_cards_sorted(player_id)
        tradeable       = [c for c in all_p if not _is_starter(c["id"]) and c["id"] not in already_ids]

        if not tradeable:
            await interaction.response.send_message(
                "No more tradeable cards to add (starter cards are protected).", ephemeral=True
            )
            return

        picker = TradeCardPickerView(self, interaction.user, is_offerer, tradeable[:25])
        await interaction.response.send_message(
            "Select a card to add to your offer:", view=picker, ephemeral=True
        )

    # ── Remove Card ───────────────────────────────────────────────────────────
    @discord.ui.button(label="➖ Remove Card", style=discord.ButtonStyle.secondary, row=0)
    async def remove_card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user.id):
            await interaction.response.send_message("You're not part of this trade!", ephemeral=True)
            return
        trade = _active_multi_trades.get(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade has expired.", ephemeral=True)
            return

        is_offerer = interaction.user.id == self.offerer.id
        confirmed  = trade["offerer_confirmed"] if is_offerer else trade["target_confirmed"]
        if confirmed:
            await interaction.response.send_message(
                "You've already confirmed. Use **❌ Cancel** to start over.", ephemeral=True
            )
            return

        removed_name = None
        async with self.lock:
            side = trade["offerer_cards"] if is_offerer else trade["target_cards"]
            if not side:
                await interaction.response.send_message("No cards to remove.", ephemeral=True)
                return
            removed      = side.pop()
            removed_name = removed["name"]
            if is_offerer:
                trade["offerer_confirmed"] = False
            else:
                trade["target_confirmed"] = False

        await interaction.response.send_message(
            f"Removed **{removed_name}** from your offer.", ephemeral=True
        )
        if self.message:
            try:
                await self.message.edit(embed=self.build_embed(), view=self)
            except Exception:
                pass

    # ── Confirm Trade ─────────────────────────────────────────────────────────
    @discord.ui.button(label="✅ Confirm Trade", style=discord.ButtonStyle.primary, row=1)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user.id):
            await interaction.response.send_message("You're not part of this trade!", ephemeral=True)
            return
        trade = _active_multi_trades.get(self.trade_id)
        if not trade:
            await interaction.response.send_message("Trade has expired.", ephemeral=True)
            return

        is_offerer  = interaction.user.id == self.offerer.id
        my_cards    = trade["offerer_cards"]    if is_offerer else trade["target_cards"]
        their_cards = trade["target_cards"]     if is_offerer else trade["offerer_cards"]

        if not my_cards:
            await interaction.response.send_message("Add at least 1 card before confirming.", ephemeral=True)
            return
        if not their_cards:
            await interaction.response.send_message(
                "Waiting for the other player to add their cards.", ephemeral=True
            )
            return

        execute_trade = False
        async with self.lock:
            if is_offerer:
                trade["offerer_confirmed"] = True
            else:
                trade["target_confirmed"] = True
            execute_trade = trade["offerer_confirmed"] and trade["target_confirmed"]

        if not execute_trade:
            await interaction.response.send_message(
                "✅ Your side is confirmed! Waiting for the other player to confirm.", ephemeral=True
            )
            if self.message:
                try:
                    await self.message.edit(embed=self.build_embed(), view=self)
                except Exception:
                    pass
            return

        # ── Both confirmed — execute the swap ────────────────────────────────
        _active_multi_trades.pop(self.trade_id, None)
        self.stop()

        offerer_id = str(self.offerer.id)
        target_id  = str(self.target.id)

        # Verify all cards still exist before swapping
        for c in trade["offerer_cards"]:
            if not db.get_card_by_id(offerer_id, c["id"]):
                await interaction.response.send_message(
                    f"❌ Trade failed — {self.offerer.display_name}'s card **{c['name']}** was already traded or sold.",
                    ephemeral=False,
                )
                return
        for c in trade["target_cards"]:
            if not db.get_card_by_id(target_id, c["id"]):
                await interaction.response.send_message(
                    f"❌ Trade failed — {self.target.display_name}'s card **{c['name']}** was already traded or sold.",
                    ephemeral=False,
                )
                return

        # Remove from original owners
        for c in trade["offerer_cards"]:
            db.remove_card(offerer_id, c["id"])
        for c in trade["target_cards"]:
            db.remove_card(target_id, c["id"])

        # Add to new owners (strip timestamps)
        for c in trade["offerer_cards"]:
            copy = {k: v for k, v in c.items() if k not in ("obtained_at", "caught_at")}
            db.add_card_to_player(target_id, copy, c.get("type", "driver"))
        for c in trade["target_cards"]:
            copy = {k: v for k, v in c.items() if k not in ("obtained_at", "caught_at")}
            db.add_card_to_player(offerer_id, copy, c.get("type", "driver"))

        def _received_str(cards: List[Dict]) -> str:
            return "\n".join(
                f"{card_module.RARITY_EMOJIS.get(c.get('rarity','common'),'')} **{c['name']}**"
                for c in cards
            )

        result_embed = discord.Embed(
            title="✅  Trade Complete!",
            description=f"{self.offerer.mention} and {self.target.mention} exchanged cards!",
            color=0x2ECC71,
        )
        result_embed.add_field(
            name=f"📬  {self.offerer.display_name} received",
            value=_received_str(trade["target_cards"]),
            inline=True,
        )
        result_embed.add_field(
            name=f"📬  {self.target.display_name} received",
            value=_received_str(trade["offerer_cards"]),
            inline=True,
        )
        await interaction.response.edit_message(embed=result_embed, view=None)

    # ── Cancel ────────────────────────────────────────────────────────────────
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_participant(interaction.user.id):
            await interaction.response.send_message("You're not part of this trade!", ephemeral=True)
            return
        _active_multi_trades.pop(self.trade_id, None)
        self.stop()
        embed = discord.Embed(
            title="❌  Trade Cancelled",
            description=f"{interaction.user.display_name} cancelled the trade.",
            color=0xE74C3C,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        _active_multi_trades.pop(self.trade_id, None)
        if self.message:
            try:
                embed = discord.Embed(
                    title="⏰  Trade Expired",
                    description="This trade offer has expired (5-minute timeout).",
                    color=0x95a5a6,
                )
                await self.message.edit(embed=embed, view=None)
            except Exception:
                pass


@f1_group.command(name="trade", description="Trade cards with another player — add multiple cards to your offer")
@discord.app_commands.describe(player="The player you want to trade with")
async def f1_trade(interaction: discord.Interaction, player: discord.Member):
    if player.id == interaction.user.id:
        await interaction.response.send_message("You can't trade with yourself!", ephemeral=True)
        return
    if player.bot:
        await interaction.response.send_message("You can't trade with a bot!", ephemeral=True)
        return

    offerer_id = str(interaction.user.id)
    target_id  = str(player.id)
    db.ensure_player(offerer_id, interaction.user.name)
    give_starter_cards(offerer_id, interaction.user.name)

    if not db.player_exists(target_id):
        await interaction.response.send_message(
            f"{player.display_name} hasn't started playing yet — they need to use `/f1 profile` first.",
            ephemeral=True,
        )
        return

    trade_id = f"mt_{offerer_id}_{target_id}"
    reverse  = f"mt_{target_id}_{offerer_id}"
    if trade_id in _active_multi_trades or reverse in _active_multi_trades:
        await interaction.response.send_message(
            "There's already an active trade between you two. Finish or cancel it first.",
            ephemeral=True,
        )
        return

    all_cards = db.get_all_cards_sorted(offerer_id)
    tradeable  = [c for c in all_cards if not _is_starter(c["id"])]
    if not tradeable:
        await interaction.response.send_message(
            "You have no tradeable cards. Starter cards are protected.\n"
            "Open packs with `/pack daily` or `/pack weekly` to get more!",
            ephemeral=True,
        )
        return

    _active_multi_trades[trade_id] = {
        "offerer_id":        offerer_id,
        "target_id":         target_id,
        "offerer_cards":     [],
        "target_cards":      [],
        "offerer_confirmed": False,
        "target_confirmed":  False,
    }

    view = MultiTradeView(trade_id, interaction.user, player)
    await interaction.response.send_message(
        content=f"{interaction.user.mention} wants to trade with {player.mention}!",
        embed=view.build_embed(),
        view=view,
    )
    msg = await interaction.original_response()
    view.message = msg


# ==================== REGISTER COMMAND GROUPS ====================

bot.tree.add_command(pack_group)
bot.tree.add_command(f1_group)
bot.tree.add_command(config_group)


# ==================== AUTO-SIMULATION RACE SYSTEM ====================

RACE_SCENARIOS: Dict[int, Dict] = {
    3: {
        "id": "pit_window",
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
        "id": "drs_attack",
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
        "id": "late_strategy",
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
        "id": "final_lap",
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
    "id": "rain_call",
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

SCENARIO_TURNS = sorted(RACE_SCENARIOS.keys())

# Turns where the reaction challenge fires (must not overlap with SCENARIO_TURNS: 3,6,9,11)
REACTION_TURNS = [1, 2, 4, 5, 7, 8, 10]


REACTION_DIRECTIONS = ["left", "right", "up", "down"]
REACTION_LABELS = {
    "left":  "◀  LEFT",
    "right": "RIGHT  ▶",
    "up":    "▲  UP",
    "down":  "▼  DOWN",
}


class ReactionChallengeView(discord.ui.View):
    """A timed 4-direction button challenge that appears mid-race."""

    def __init__(self, direction: str, p1_user: discord.Member, p2_user: discord.Member):
        super().__init__(timeout=5.0)
        self.direction = direction
        self.p1_user   = p1_user
        self.p2_user   = p2_user
        self.clicks: Dict[str, tuple] = {}
        self.done      = asyncio.Event()
        self._start    = time.time()   # set when challenge appears, not on first click

    async def _handle(self, interaction: discord.Interaction, clicked: str):
        if interaction.user.id not in (self.p1_user.id, self.p2_user.id):
            await interaction.response.send_message("❌ You're not in this race!", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid in self.clicks:
            await interaction.response.defer()
            return
        elapsed = time.time() - self._start
        correct = clicked == self.direction
        self.clicks[uid] = (correct, elapsed)
        if correct:
            await interaction.response.send_message(
                f"✅ **{interaction.user.display_name}** — correct! `{elapsed:.2f}s`", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ **{interaction.user.display_name}** — wrong direction! Penalty incoming!", ephemeral=True
            )
        if len(self.clicks) >= 2:
            self.done.set()
            self.stop()

    @discord.ui.button(label="◀  LEFT", style=discord.ButtonStyle.primary, row=0)
    async def btn_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "left")

    @discord.ui.button(label="RIGHT  ▶", style=discord.ButtonStyle.primary, row=0)
    async def btn_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "right")

    @discord.ui.button(label="▲  UP", style=discord.ButtonStyle.primary, row=0)
    async def btn_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "up")

    @discord.ui.button(label="▼  DOWN", style=discord.ButtonStyle.primary, row=0)
    async def btn_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "down")


class SinglePlayerReactionView(discord.ui.View):
    """Reaction challenge for one player only — staggered per-player in channel."""

    def __init__(self, direction: str, player: discord.Member):
        super().__init__(timeout=5.0)
        self.direction = direction
        self.player    = player
        self.result: Optional[tuple] = None   # (correct: bool, elapsed: float)
        self.done      = asyncio.Event()
        self._start    = time.time()

    async def _handle(self, interaction: discord.Interaction, clicked: str):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("❌ This challenge isn't for you!", ephemeral=True)
            return
        if self.result is not None:
            await interaction.response.defer()
            return
        elapsed = time.time() - self._start
        correct = clicked == self.direction
        self.result = (correct, elapsed)
        if correct:
            await interaction.response.send_message(
                f"✅ **{interaction.user.display_name}** — nailed it! `{elapsed:.2f}s`", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ **{interaction.user.display_name}** — wrong direction! Penalty incoming.", ephemeral=True
            )
        self.done.set()
        self.stop()

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


class ScenarioView(discord.ui.View):
    """Shown at key race moments — both players pick a tactic then simulation continues."""

    def __init__(
        self,
        p1_user: discord.Member,
        p2_user: discord.Member,
        scenario: Dict,
        race: RaceState,
        message: discord.Message,
        gif_url: str,
    ):
        super().__init__(timeout=30)
        self.p1_user   = p1_user
        self.p2_user   = p2_user
        self.scenario  = scenario
        self.race      = race
        self.message   = message
        self.gif_url   = gif_url
        self.p1_choice: Optional[str] = None
        self.p2_choice: Optional[str] = None
        self.p1_label:  Optional[str] = None
        self.p2_label:  Optional[str] = None
        self.lock        = asyncio.Lock()
        self.both_chosen = asyncio.Event()

        for opt in scenario["options"]:
            btn = discord.ui.Button(label=opt["label"], style=opt["style"], row=0)
            value = opt["value"]
            label = opt["label"]

            async def _cb(interaction: discord.Interaction, _v=value, _l=label):
                await self._handle(interaction, _v, _l)

            btn.callback = _cb
            self.add_item(btn)

    async def _handle(self, interaction: discord.Interaction, value: str, label: str):
        is_p1 = interaction.user.id == self.p1_user.id
        is_p2 = interaction.user.id == self.p2_user.id
        if not (is_p1 or is_p2):
            await interaction.response.send_message("You're not in this race!", ephemeral=True)
            return

        async with self.lock:
            if is_p1:
                if self.p1_choice:
                    await interaction.response.send_message("Already locked in!", ephemeral=True)
                    return
                self.p1_choice = value
                self.p1_label  = label
            else:
                if self.p2_choice:
                    await interaction.response.send_message("Already locked in!", ephemeral=True)
                    return
                self.p2_choice = value
                self.p2_label  = label

            await interaction.response.send_message(
                f"✅  **{label}** locked in!  Waiting for your opponent…", ephemeral=True
            )

            # Update embed live as players lock in
            if self.message:
                try:
                    await self.message.edit(
                        embed=build_scenario_embed(
                            self.scenario, self.race,
                            self.p1_user, self.p2_user, self.gif_url,
                            p1_locked=bool(self.p1_choice),
                            p2_locked=bool(self.p2_choice),
                            p1_label=self.p1_label,
                            p2_label=self.p2_label,
                        ),
                        view=self,
                    )
                except Exception:
                    pass

            if self.p1_choice and self.p2_choice:
                self.both_chosen.set()


class ChallengeView(discord.ui.View):
    """Accept/decline embed before the race starts."""

    def __init__(
        self,
        challenger: discord.Member,
        opponent: discord.Member,
        race: RaceState,
        gif_url: str,
    ):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.race = race
        self.gif_url = gif_url

    @discord.ui.button(label="✅  Accept Challenge", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.stop()

        embed = build_auto_embed(self.race, self.challenger, self.opponent, self.gif_url, [])
        await interaction.response.edit_message(embed=embed, view=None)
        msg = await interaction.original_response()
        asyncio.create_task(run_auto_race(self.race, self.challenger, self.opponent, msg, self.gif_url, interaction.channel))

    @discord.ui.button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't for you!", ephemeral=True)
            return
        self.stop()
        active_race_pairs.pop(str(self.challenger.id), None)
        active_race_pairs.pop(str(self.opponent.id), None)
        embed = discord.Embed(
            title="❌  Challenge Declined",
            description=f"{self.opponent.display_name} declined the race.",
            color=0xE74C3C,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        active_race_pairs.pop(str(self.challenger.id), None)
        active_race_pairs.pop(str(self.opponent.id), None)


def _auto_choice(race: RaceState, player: str) -> str:
    """Smart auto-choice for non-scenario turns based on car state."""
    fuel = race.p1_fuel if player == "p1" else race.p2_fuel
    wear = race.p1_tire_wear if player == "p1" else race.p2_tire_wear
    if wear > 75 or fuel < 25:
        weights = [0.15, 0.55, 0.30]  # accelerate / same / slow
    elif wear > 50 or fuel < 50:
        weights = [0.25, 0.55, 0.20]
    else:
        weights = [0.30, 0.50, 0.20]
    return random.choices(["accelerate", "same_speed", "slow_down"], weights=weights)[0]


async def run_auto_race(
    race: RaceState,
    p1_user: discord.Member,
    p2_user: discord.Member,
    message: discord.Message,
    gif_url: str,
    channel,
):
    """Fully auto-simulated race — plays itself with commentary, pauses 4× for player decisions."""
    AUTO_DELAY    = 2.8   # seconds between auto turns
    SCENARIO_WAIT = 30    # seconds before scenario auto-resolves
    commentary_log: List[str] = []

    # Find next scenario turn for footer hint
    def _next_scenario(current_turn: int) -> Optional[int]:
        return next((t for t in SCENARIO_TURNS if t > current_turn), None)

    try:
        for turn_num in range(1, race.max_turns + 1):
            scenario = None
            if turn_num in RACE_SCENARIOS:
                scenario = RACE_SCENARIOS[turn_num].copy()
                if race.weather == "rain" and turn_num in (6, 9):
                    scenario = RAIN_SCENARIO_OVERRIDE.copy()

            if scenario:
                # ── SCENARIO PAUSE ──────────────────────────────────
                # Send scenario-specific GIF if available
                await _send_event_gif(channel, scenario.get("id", ""), delete_after=10.0)

                sv = ScenarioView(p1_user, p2_user, scenario, race, message, gif_url)

                # Notify both players so they don't miss the decision
                scenario_title = scenario.get("title", "Race Decision")
                is_pit = any(
                    opt.get("value") == "pit_stop"
                    for opt in scenario.get("options", [])
                )
                pit_note = "  🔧 Pit stop available!" if is_pit else ""
                try:
                    await channel.send(
                        f"⚠️ {p1_user.mention} {p2_user.mention} — "
                        f"**{scenario_title}** — make your choice now!{pit_note}",
                        delete_after=SCENARIO_WAIT,
                    )
                except Exception:
                    pass

                try:
                    await message.edit(
                        embed=build_scenario_embed(scenario, race, p1_user, p2_user, gif_url),
                        view=sv,
                    )
                except Exception:
                    pass

                try:
                    await asyncio.wait_for(sv.both_chosen.wait(), timeout=SCENARIO_WAIT)
                except asyncio.TimeoutError:
                    pass

                p1_choice = sv.p1_choice or "same_speed"
                p2_choice = sv.p2_choice or "same_speed"
                p1_label  = sv.p1_label  or "Auto (timed out)"
                p2_label  = sv.p2_label  or "Auto (timed out)"

                # Show both choices resolved briefly
                try:
                    await message.edit(
                        embed=build_scenario_embed(
                            scenario, race, p1_user, p2_user, gif_url,
                            p1_locked=True, p2_locked=True,
                            p1_label=p1_label, p2_label=p2_label,
                        ),
                        view=None,
                    )
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            else:
                # ── AUTO TURN ────────────────────────────────────────
                p1_choice = _auto_choice(race, "p1")
                p2_choice = _auto_choice(race, "p2")

            # Process the turn
            result = race_engine.process_turn(race, p1_choice, p2_choice)
            event  = result.get("event")

            # Generate commentary
            try:
                new_lines = commentary_engine.generate_turn_commentary(
                    turn=race.turn,
                    lap=race.lap,
                    total_laps=race.total_laps,
                    p1_name=p1_user.display_name,
                    p2_name=p2_user.display_name,
                    p1_choice=p1_choice,
                    p2_choice=p2_choice,
                    gap=race.gap,
                    event=event,
                    p1_fuel=race.p1_fuel,
                    p2_fuel=race.p2_fuel,
                    p1_tire_wear=race.p1_tire_wear,
                    p2_tire_wear=race.p2_tire_wear,
                    p1_tire_type=race.p1_tire_type,
                    p2_tire_type=race.p2_tire_type,
                    p1_leading=(race.p1_position == 1),
                    weather=race.weather,
                )
                commentary_log.extend(new_lines)
            except Exception:
                pass

            # Check for early end
            if result.get("dnf") or result.get("race_finished") or race.lap > race.total_laps:
                await finish_auto_race(race, p1_user, p2_user, message, result, channel)
                return

            # Update live embed
            try:
                next_s = _next_scenario(race.turn)
                await message.edit(
                    embed=build_auto_embed(race, p1_user, p2_user, gif_url, commentary_log, next_s),
                    view=None,
                )
            except Exception:
                pass

            # ── REACTION CHALLENGE (staggered per-player) ─────────
            if turn_num in REACTION_TURNS and channel:
                await asyncio.sleep(1.2)
                direction = random.choice(REACTION_DIRECTIONS)
                dir_label = REACTION_LABELS[direction]

                await _send_event_gif(channel, "reaction", delete_after=5.0)

                def _reaction_embed(player: discord.Member) -> discord.Embed:
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

                # ── Send P1's challenge first ──
                rv1 = SinglePlayerReactionView(direction, p1_user)
                msg1 = None
                try:
                    await channel.send(
                        f"⚡ {p1_user.mention} — **YOUR REACTION!** Hit  **{dir_label}**  NOW!",
                        delete_after=6,
                    )
                    msg1 = await channel.send(embed=_reaction_embed(p1_user), view=rv1)
                except Exception:
                    pass

                # Start waiting for P1 in background while we stagger
                p1_task = asyncio.create_task(
                    asyncio.wait_for(rv1.done.wait(), timeout=4.0)
                )

                # ── Stagger: 2–3 s before P2 gets their challenge ──
                stagger = random.uniform(2.0, 3.0)
                await asyncio.sleep(stagger)

                # ── Send P2's challenge ──
                rv2 = SinglePlayerReactionView(direction, p2_user)
                msg2 = None
                try:
                    await channel.send(
                        f"⚡ {p2_user.mention} — **YOUR REACTION!** Hit  **{dir_label}**  NOW!",
                        delete_after=6,
                    )
                    msg2 = await channel.send(embed=_reaction_embed(p2_user), view=rv2)
                except Exception:
                    pass

                # Wait for P2's full 4 s window
                try:
                    await asyncio.wait_for(rv2.done.wait(), timeout=4.0)
                except asyncio.TimeoutError:
                    rv2.stop()

                # Clean up P1's background task
                if not rv1.done.is_set():
                    rv1.stop()
                p1_task.cancel()
                try:
                    await p1_task
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass

                # ── Evaluate results ──
                p1_result = rv1.result   # (correct, elapsed) or None
                p2_result = rv2.result

                result_lines = []

                correct_clicks = []
                if p1_result and p1_result[0]:
                    correct_clicks.append((p1_user, p1_result[1], "p1"))
                if p2_result and p2_result[0]:
                    correct_clicks.append((p2_user, p2_result[1], "p2"))
                correct_clicks.sort(key=lambda x: x[1])

                for i, (user, elapsed, side) in enumerate(correct_clicks):
                    if i == 0:       # fastest correct gets the gap bonus
                        if side == "p1":
                            race.gap -= 0.5
                        else:
                            race.gap += 0.5
                    medal = "🥇" if i == 0 else "🥈"
                    line = f"{medal} **{user.display_name}** reacted in `{elapsed:.2f}s`"
                    if i == 0:
                        line += " — **+0.5s advantage!** 🚀"
                    result_lines.append(line)

                if p1_result and not p1_result[0]:
                    race.gap += 2.0
                    result_lines.append(f"❌ **{p1_user.display_name}** wrong direction — **+2.0s penalty!**")
                if p2_result and not p2_result[0]:
                    race.gap -= 2.0
                    result_lines.append(f"❌ **{p2_user.display_name}** wrong direction — **+2.0s penalty!**")

                if not p1_result:
                    race.gap += 0.3
                    result_lines.append(f"⏱️ **{p1_user.display_name}** didn't react — **+0.3s penalty!**")
                if not p2_result:
                    race.gap -= 0.3
                    result_lines.append(f"⏱️ **{p2_user.display_name}** didn't react — **+0.3s penalty!**")

                if not result_lines:
                    result_lines.append("⏱️  Neither player reacted — no gap change.")

                result_embed = discord.Embed(
                    title="✅  Reaction Results",
                    description="\n".join(result_lines),
                    color=0x2ECC71,
                )
                for m in (msg1, msg2):
                    if m:
                        try:
                            await m.edit(embed=result_embed, view=None)
                        except Exception:
                            pass
                await asyncio.sleep(2.0)

            elif turn_num < race.max_turns:
                await asyncio.sleep(AUTO_DELAY)

        # All turns done
        await finish_auto_race(race, p1_user, p2_user, message, {"race_finished": True}, channel)

    except Exception as e:
        print(f"Auto race error: {e}")
        active_race_pairs.pop(str(race.player1_id), None)
        active_race_pairs.pop(str(race.player2_id), None)


async def finish_auto_race(
    race: RaceState,
    p1_user: discord.Member,
    p2_user: discord.Member,
    message: discord.Message,
    result: Dict,
    channel,
):
    """Award coins and post results at the end of an auto-simulated race."""
    active_race_pairs.pop(str(race.player1_id), None)
    active_race_pairs.pop(str(race.player2_id), None)

    if result.get("dnf"):
        dnf_side = result["dnf"]
        winner_id   = race.player2_id if dnf_side == "p1" else race.player1_id
        loser_id    = race.player1_id if dnf_side == "p1" else race.player2_id
        winner_user = p2_user if dnf_side == "p1" else p1_user
        loser_user  = p1_user if dnf_side == "p1" else p2_user
        reason = result.get("reason", "unknown").replace("_", " ").title()

        winner_coins = db.add_coins(winner_id, 100)
        loser_coins  = db.add_coins(loser_id, 10)
        db.update_player_stats(winner_id, {"status": "win"})
        db.update_player_stats(loser_id,  {"status": "dnf"})

        embed = discord.Embed(
            title="⚠️  Race Ended — DNF!",
            description=f"{loser_user.mention} retired from the race — **{reason}**",
            color=0xE74C3C,
        )
        embed.add_field(name="🏆 Winner", value=winner_user.mention, inline=True)
        embed.add_field(
            name="💰 Rewards",
            value=(
                f"🥇 {winner_user.mention}: **+100 coins** ({winner_coins:,} total)\n"
                f"🔧 {loser_user.mention}: **+10 coins** ({loser_coins:,} total)"
            ),
            inline=False,
        )
    else:
        winner_pos_1 = race.p1_position == 1
        winner_id   = race.player1_id if winner_pos_1 else race.player2_id
        loser_id    = race.player2_id if winner_pos_1 else race.player1_id
        winner_user = p1_user if winner_pos_1 else p2_user
        loser_user  = p2_user if winner_pos_1 else p1_user

        winner_coins = db.add_coins(winner_id, 100)
        loser_coins  = db.add_coins(loser_id, 25)
        db.update_player_stats(winner_id, {"status": "win"})
        db.update_player_stats(loser_id,  {"status": "loss"})

        gap_text = f"{abs(race.gap):.3f}s"

        # Determine dominant strategy for each player
        def _strategy_label(history: list) -> str:
            if not history:
                return "Balanced"
            pits   = history.count("pit_stop")
            pushs  = history.count("accelerate")
            lifts  = history.count("slow_down")
            if pits >= 2:
                return f"Aggressive Pit ({pits}x)"
            if pushs > lifts:
                return "Attacking"
            if lifts > pushs:
                return "Conservative"
            return "Balanced"

        p1_strategy = _strategy_label(race.choice_history.get("p1", []))
        p2_strategy = _strategy_label(race.choice_history.get("p2", []))

        # Tyre label at finish
        def _tire_label(tire_type: str, wear: float) -> str:
            t = {"soft": "Soft", "medium": "Medium", "hard": "Hard", "wet": "Wet"}.get(tire_type, tire_type.title())
            health = 100 - wear
            return f"{t} ({health:.0f}% left)"

        # Weather summary
        weather_events = [e for e in race.events_log if "Rain" in e or "Safety" in e or "DRS" in e]
        weather_summary = ""
        if any("Rain" in e for e in race.events_log):
            weather_summary = "🌧️ Wet conditions hit mid-race"
        if any("Safety" in e for e in race.events_log):
            weather_summary += ("\n" if weather_summary else "") + "🚨 Safety car deployed"

        embed = discord.Embed(
            title="🏁  Race Complete!",
            description=(
                f"## 🥇  {winner_user.mention} takes the chequered flag!\n"
                f"🥈  {loser_user.mention} finishes P2\n\n"
                f"⏱️  Final gap: **{gap_text}**"
            ),
            color=0xFFD700,
        )

        # Driver & car recap
        embed.add_field(
            name=f"🏎️  {p1_user.display_name}",
            value=(
                f"👤 {race.p1_driver.name} `{race.p1_driver.code}`\n"
                f"🚗 {race.p1_car.name}\n"
                f"🔩 Pit stops: **{race.p1_pit_stops}**\n"
                f"🏁 Tyres: {_tire_label(race.p1_tire_type, race.p1_tire_wear)}\n"
                f"⛽ Fuel left: **{race.p1_fuel:.0f}%**\n"
                f"📋 Style: *{p1_strategy}*"
            ),
            inline=True,
        )
        embed.add_field(
            name=f"🏎️  {p2_user.display_name}",
            value=(
                f"👤 {race.p2_driver.name} `{race.p2_driver.code}`\n"
                f"🚗 {race.p2_car.name}\n"
                f"🔩 Pit stops: **{race.p2_pit_stops}**\n"
                f"🏁 Tyres: {_tire_label(race.p2_tire_type, race.p2_tire_wear)}\n"
                f"⛽ Fuel left: **{race.p2_fuel:.0f}%**\n"
                f"📋 Style: *{p2_strategy}*"
            ),
            inline=True,
        )

        # Race key points
        key_points = []
        if abs(race.gap) < 0.5:
            key_points.append("⚡ Incredibly close finish — decided by less than half a second!")
        if race.p1_pit_stops == 0 or race.p2_pit_stops == 0:
            no_pit = p1_user.display_name if race.p1_pit_stops == 0 else p2_user.display_name
            key_points.append(f"🔥 {no_pit} completed the race on a single set of tyres!")
        if race.p1_pit_stops >= 2 or race.p2_pit_stops >= 2:
            multi = p1_user.display_name if race.p1_pit_stops >= 2 else p2_user.display_name
            stops = race.p1_pit_stops if race.p1_pit_stops >= 2 else race.p2_pit_stops
            key_points.append(f"🔧 {multi} ran an aggressive {stops}-stop strategy!")
        if weather_summary:
            key_points.append(weather_summary)
        if race.p1_fuel < 15 or race.p2_fuel < 15:
            low_fuel = p1_user.display_name if race.p1_fuel < race.p2_fuel else p2_user.display_name
            key_points.append(f"⛽ {low_fuel} crossed the line on fumes — fuel management was critical!")
        if not key_points:
            key_points.append("🎯 A clean, controlled race from lights to flag.")

        embed.add_field(
            name="📰  Race Highlights",
            value="\n".join(f"• {kp}" for kp in key_points),
            inline=False,
        )

        embed.add_field(
            name="💰  Rewards",
            value=(
                f"🥇 {winner_user.mention}: **+100 coins** ({winner_coins:,} total)\n"
                f"🥈 {loser_user.mention}: **+25 coins** ({loser_coins:,} total)"
            ),
            inline=False,
        )
        embed.set_footer(text="Open a pack with /pack  ·  Upgrade your setup with /shop")

    try:
        await message.edit(embed=embed, view=None)
    except Exception:
        if channel:
            try:
                await channel.send(embed=embed)
            except Exception:
                pass


@bot.tree.command(name="race", description="Challenge another player to an F1 race!")
@app_commands.describe(opponent="The player you want to race against")
async def race_slash_command(interaction: discord.Interaction, opponent: discord.Member):
    player_id   = str(interaction.user.id)
    opponent_id = str(opponent.id)

    if interaction.user.id == opponent.id:
        await interaction.response.send_message("❌ You can't race yourself!", ephemeral=True)
        return
    if opponent.bot:
        await interaction.response.send_message("❌ You can't race a bot!", ephemeral=True)
        return
    if player_id in active_race_pairs or opponent_id in active_race_pairs:
        await interaction.response.send_message("❌ One of you is already in a race!", ephemeral=True)
        return

    db.ensure_player(player_id, interaction.user.name)
    db.ensure_player(opponent_id, opponent.name)
    give_starter_cards(player_id, interaction.user.name)
    give_starter_cards(opponent_id, opponent.name)

    p1_car, p1_driver = get_player_race_cards(player_id)
    p2_car, p2_driver = get_player_race_cards(opponent_id)
    synergy1 = card_module.check_synergy(p1_driver.code, p1_car.team)
    synergy2 = card_module.check_synergy(p2_driver.code, p2_car.team)

    # ── Show challenge / accept embed ─────────────────────────
    accept_view = race_v2_mod.RaceAcceptView(interaction.user, opponent)
    challenge_emb = race_v2_mod.build_challenge_embed_v2(
        interaction.user, opponent,
        p1_car, p1_driver,
        p2_car, p2_driver,
        synergy1, synergy2,
    )
    await interaction.response.send_message(
        content=f"{opponent.mention} — you've been challenged!",
        embed=challenge_emb,
        view=accept_view,
    )

    await accept_view.done.wait()
    if not accept_view.accepted:
        declined_emb = discord.Embed(
            title="❌  Challenge Declined",
            description=f"**{opponent.display_name}** declined the race (or it timed out).",
            color=0x636e72,
        )
        await interaction.edit_original_response(embed=declined_emb, view=None, content=None)
        return

    # ── Lock both players in ──────────────────────────────────
    race_id = f"{player_id}_{opponent_id}_{int(__import__('time').time())}"
    active_race_pairs[player_id]   = race_id
    active_race_pairs[opponent_id] = race_id

    state = race_v2_mod.RaceV2State(
        p1_id      = player_id,
        p2_id      = opponent_id,
        p1_name    = interaction.user.display_name,
        p2_name    = opponent.display_name,
        p1_car     = p1_car,
        p1_driver  = p1_driver,
        p2_car     = p2_car,
        p2_driver  = p2_driver,
        p1_synergy = synergy1,
        p2_synergy = synergy2,
    )

    channel = interaction.channel
    try:
        result = await race_v2_mod.run_race(channel, interaction.user, opponent, state)
    finally:
        active_race_pairs.pop(player_id, None)
        active_race_pairs.pop(opponent_id, None)

    # ── Award coins ───────────────────────────────────────────
    db.add_coins(player_id, result["p1_coins"])
    db.add_coins(opponent_id, result["p2_coins"])

    # ── Post result embed ─────────────────────────────────────
    result_emb = race_v2_mod.build_result_embed(result, interaction.user, opponent, state)
    await channel.send(embed=result_emb)


@bot.command(name="deck")
async def show_deck(ctx):
    """Show your card collection summary: !deck"""
    player_id = str(ctx.author.id)
    db.ensure_player(player_id, ctx.author.name)
    give_starter_cards(player_id, ctx.author.name)

    cards = db.get_player_cards(player_id)
    equipped = db.get_equipped(player_id)
    coins = db.get_coins(player_id)

    embed = discord.Embed(title=f"🎴 {ctx.author.display_name}'s Deck", color=discord.Color.blue())
    embed.add_field(name="💰 Race Credits", value=f"**{coins}** 💰", inline=False)

    if cards["drivers"]:
        lines = []
        for d in cards["drivers"][:10]:
            emoji = card_module.RARITY_EMOJIS.get(d["rarity"], "")
            active = " ← **equipped**" if d["id"] == equipped.get("driver_id") else ""
            lines.append(f"{emoji} **{d['name']}** ({d['code']}) — {d['rarity'].title()}{active}")
        embed.add_field(name=f"👤 Drivers ({len(cards['drivers'])})", value="\n".join(lines) + ("\n*...and more*" if len(cards["drivers"]) > 10 else ""), inline=False)
    else:
        embed.add_field(name="👤 Drivers", value="*None — open a pack!*", inline=False)

    if cards["cars"]:
        lines = []
        for c in cards["cars"][:10]:
            emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
            active = " ← **equipped**" if c["id"] == equipped.get("car_id") else ""
            lines.append(f"{emoji} **{c['name']}** — {c['top_speed']}km/h — {c['rarity'].title()}{active}")
        embed.add_field(name=f"🏎️ Cars ({len(cards['cars'])})", value="\n".join(lines) + ("\n*...and more*" if len(cards["cars"]) > 10 else ""), inline=False)
    else:
        embed.add_field(name="🏎️ Cars", value="*None — open a pack!*", inline=False)

    embed.set_footer(text="Use /pack daily | /pack weekly | /f1 equip | /f1 collection")
    await ctx.send(embed=embed)


# ==================== UI COMPONENTS ====================

class EquipTypeView(discord.ui.View):
    def __init__(self, player_id: str):
        super().__init__(timeout=90)
        self.player_id = player_id

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="👤 Equip Driver", style=discord.ButtonStyle.primary, row=0)
    async def equip_driver(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        cards = db.get_player_cards(self.player_id)
        if not cards["drivers"]:
            embed = discord.Embed(title="❌ No Drivers", description="You have no driver cards yet! Open `/pack daily` or `/pack weekly` to get some.", color=0xE74C3C)
            await interaction.response.edit_message(embed=embed, view=None)
            return
        view = CardSelectView(cards["drivers"], "driver", self.player_id)
        await interaction.response.edit_message(embed=view.build_embed("👤 Select Driver to Equip"), view=view)

    @discord.ui.button(label="🏎️ Equip Car", style=discord.ButtonStyle.primary, row=0)
    async def equip_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        cards = db.get_player_cards(self.player_id)
        if not cards["cars"]:
            embed = discord.Embed(title="❌ No Cars", description="You have no car cards yet! Open `/pack daily` or `/pack weekly` to get some.", color=0xE74C3C)
            await interaction.response.edit_message(embed=embed, view=None)
            return
        view = CardSelectView(cards["cars"], "car", self.player_id)
        await interaction.response.edit_message(embed=view.build_embed("🏎️ Select Car to Equip"), view=view)

    @discord.ui.button(label="✖ Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        await interaction.response.edit_message(content="Equip menu closed.", embed=None, view=None)


class CardSelectView(discord.ui.View):
    def __init__(self, cards: List[Dict], card_type: str, player_id: str, per_page: int = 10):
        super().__init__(timeout=120)
        self.all_cards = cards
        self.card_type = card_type
        self.player_id = player_id
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(cards) + per_page - 1) // per_page)
        self._rebuild()

    def _get_page_cards(self) -> List[Dict]:
        start = self.page * self.per_page
        return self.all_cards[start:start + self.per_page]

    def _rebuild(self):
        self.clear_items()
        is_first = self.page == 0
        is_last = self.page >= self.total_pages - 1

        first_btn = discord.ui.Button(label="⏮", style=discord.ButtonStyle.secondary, disabled=is_first, row=0)
        first_btn.callback = self._go_first
        self.add_item(first_btn)

        prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=is_first, row=0)
        prev_btn.callback = self._go_prev
        self.add_item(prev_btn)

        page_btn = discord.ui.Button(label=f"{self.page + 1} / {self.total_pages}", style=discord.ButtonStyle.primary, disabled=True, row=0)
        self.add_item(page_btn)

        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=is_last, row=0)
        next_btn.callback = self._go_next
        self.add_item(next_btn)

        last_btn = discord.ui.Button(label="⏭", style=discord.ButtonStyle.secondary, disabled=is_last, row=0)
        last_btn.callback = self._go_last
        self.add_item(last_btn)

        page_cards = self._get_page_cards()
        if page_cards:
            options = []
            for card in page_cards:
                emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
                if card["type"] == "driver":
                    label = f"{emoji} {card['name']} ({card['code']})"
                    desc = f"{card['rarity'].title()} | Skill: {card['skill']}/10 | {card['team']}"
                else:
                    label = f"{emoji} {card['name']}"
                    desc = f"{card['rarity'].title()} | {card['top_speed']}km/h | {card['team']}"
                options.append(discord.SelectOption(label=label[:100], description=desc[:100], value=card["id"]))

            select = discord.ui.Select(placeholder="Make a selection...", options=options, row=1)
            select.callback = self._on_select
            self.add_item(select)

        quit_btn = discord.ui.Button(label="✖ Quit", style=discord.ButtonStyle.danger, row=2)
        quit_btn.callback = self._on_quit
        self.add_item(quit_btn)

    def build_embed(self, title: str) -> discord.Embed:
        page_cards = self._get_page_cards()
        embed = discord.Embed(
            title=title,
            description=f"Page **{self.page + 1}** of **{self.total_pages}** — {len(self.all_cards)} total",
            color=0x2C3E50,
        )
        for card in page_cards:
            emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
            if card["type"] == "driver":
                field_name = f"{emoji} {card['name']} ({card['code']}) — {card['rarity'].title()}"
                field_val = f"Team: {card['team']} | Skill: **{card['skill']}/10**"
            else:
                field_name = f"{emoji} {card['name']} — {card['rarity'].title()}"
                field_val = f"Team: {card['team']} | **{card['top_speed']}km/h** | Handling: {card.get('handling', '?')}"
            if card.get("perks"):
                field_val += f"\n✨ Perk: *{card['perks'][0].replace('_', ' ').title()}*"
            embed.add_field(name=field_name, value=field_val, inline=False)
        embed.set_footer(text="Select a card from the dropdown below to equip it.")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return False
        return True

    async def _go_first(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(f"{'👤' if self.card_type == 'driver' else '🏎️'} Select {self.card_type.title()} to Equip"), view=self)

    async def _go_prev(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(f"{'👤' if self.card_type == 'driver' else '🏎️'} Select {self.card_type.title()} to Equip"), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = min(self.total_pages - 1, self.page + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(f"{'👤' if self.card_type == 'driver' else '🏎️'} Select {self.card_type.title()} to Equip"), view=self)

    async def _go_last(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = self.total_pages - 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(f"{'👤' if self.card_type == 'driver' else '🏎️'} Select {self.card_type.title()} to Equip"), view=self)

    async def _on_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        card_id = interaction.data["values"][0]
        success = db.set_equipped(self.player_id, self.card_type, card_id)
        card = db.get_card_by_id(self.player_id, card_id)

        if success and card:
            emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
            icon = "👤" if self.card_type == "driver" else "🏎️"
            display_name = f"{card['name']} ({card['code']})" if self.card_type == "driver" else card["name"]
            stats = f"Skill: {card['skill']}/10 | Team: {card['team']}" if self.card_type == "driver" else f"{card['top_speed']}km/h | Handling: {card.get('handling', '?')} | Team: {card['team']}"

            art_file = make_card_art_file(card)
            embed = discord.Embed(
                title=f"✅ {self.card_type.title()} Equipped!",
                description=f"{icon} {emoji} **{display_name}** is now your active {self.card_type}!",
                color=0x2ECC71,
            )
            embed.add_field(name="Stats", value=stats, inline=False)
            embed.add_field(name="Rarity", value=f"{emoji} {card['rarity'].title()}", inline=True)
            if card.get("perks"):
                embed.add_field(name="✨ Perk", value=card["perks"][0].replace("_", " ").title(), inline=True)
            if art_file:
                embed.set_image(url=f"attachment://{art_file.filename}")
            embed.set_footer(text="Your equipped card will be used in your next race")
        else:
            art_file = None
            embed = discord.Embed(title="❌ Error", description="Could not equip that card.", color=0xE74C3C)

        if art_file:
            await interaction.response.edit_message(embed=embed, view=None, attachments=[art_file])
        else:
            await interaction.response.edit_message(embed=embed, view=None)

    async def _on_quit(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Menu closed.", embed=None, view=None)


class CardDetailView(discord.ui.View):
    """Shown after selecting a card in the collection — has a back button."""

    def __init__(self, collection_view: "CollectionView"):
        super().__init__(timeout=120)
        self.collection_view = collection_view

    @discord.ui.button(label="◀ Back to Collection", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.collection_view.player_id:
            await interaction.response.send_message("This isn't your collection!", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=None,
            embed=self.collection_view.build_embed(),
            view=self.collection_view,
            attachments=[],
        )


class CollectionView(discord.ui.View):
    def __init__(self, player_id: str, all_cards: List[Dict], display_name: str, per_page: int = 5):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.all_cards = all_cards
        self.display_name = display_name
        self.per_page = per_page
        self.filter_type = "all"
        self.page = 0
        self._update_filtered()
        self._rebuild()

    def _update_filtered(self):
        if self.filter_type == "all":
            self.cards = self.all_cards
        else:
            self.cards = [c for c in self.all_cards if c["type"] == self.filter_type]
        self.total_pages = max(1, (len(self.cards) + self.per_page - 1) // self.per_page)
        self.page = min(self.page, max(0, self.total_pages - 1))

    def _get_page_cards(self) -> List[Dict]:
        start = self.page * self.per_page
        return self.cards[start:start + self.per_page]

    def _rebuild(self):
        self.clear_items()
        is_first = self.page == 0
        is_last = self.page >= self.total_pages - 1

        all_btn = discord.ui.Button(
            label="📋 All",
            style=discord.ButtonStyle.primary if self.filter_type == "all" else discord.ButtonStyle.secondary,
            row=0,
        )
        all_btn.callback = self._filter_all
        self.add_item(all_btn)

        drivers_btn = discord.ui.Button(
            label="👤 Drivers",
            style=discord.ButtonStyle.primary if self.filter_type == "driver" else discord.ButtonStyle.secondary,
            row=0,
        )
        drivers_btn.callback = self._filter_drivers
        self.add_item(drivers_btn)

        cars_btn = discord.ui.Button(
            label="🏎️ Cars",
            style=discord.ButtonStyle.primary if self.filter_type == "car" else discord.ButtonStyle.secondary,
            row=0,
        )
        cars_btn.callback = self._filter_cars
        self.add_item(cars_btn)

        assets_btn = discord.ui.Button(
            label="🏗️ Staff",
            style=discord.ButtonStyle.primary if self.filter_type == "team_asset" else discord.ButtonStyle.secondary,
            row=0,
        )
        assets_btn.callback = self._filter_assets
        self.add_item(assets_btn)

        prev_btn = discord.ui.Button(label="◀️", style=discord.ButtonStyle.secondary, disabled=is_first, row=1)
        prev_btn.callback = self._go_prev
        self.add_item(prev_btn)

        page_btn = discord.ui.Button(
            label=f"{self.page + 1} / {self.total_pages}",
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=1,
        )
        self.add_item(page_btn)

        next_btn = discord.ui.Button(label="▶️", style=discord.ButtonStyle.secondary, disabled=is_last, row=1)
        next_btn.callback = self._go_next
        self.add_item(next_btn)

        quit_btn = discord.ui.Button(label="✖ Close", style=discord.ButtonStyle.danger, row=1)
        quit_btn.callback = self._on_quit
        self.add_item(quit_btn)

        page_cards = self._get_page_cards()
        if page_cards:
            options = []
            for card in page_cards:
                emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
                if card["type"] == "driver":
                    label = f"{emoji} {card['name']} ({card['code']})"
                    desc = f"{card['rarity'].title()} | Skill: {card['skill']}/10"
                elif card["type"] == "car":
                    label = f"{emoji} {card['name']}"
                    desc = f"{card['rarity'].title()} | {card['top_speed']}km/h"
                else:
                    label = f"{emoji} {card['name']}"
                    desc = f"{card['rarity'].title()} | {card.get('role', 'Team Asset')}"
                options.append(discord.SelectOption(label=label[:100], description=desc[:100], value=card["id"]))

            select = discord.ui.Select(placeholder="Select a card to view details...", options=options, row=2)
            select.callback = self._on_select
            self.add_item(select)

    def build_embed(self) -> discord.Embed:
        page_cards = self._get_page_cards()
        equipped = db.get_equipped(self.player_id)
        filter_label = {
            "all": "All Cards",
            "driver": "Drivers",
            "car": "Cars",
            "team_asset": "Team Assets",
        }.get(self.filter_type, "All Cards")

        embed = discord.Embed(
            title=f"🎴  {self.display_name}'s Collection",
            color=0x5865F2,
        )

        lines = []
        for card in page_cards:
            rarity_emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
            rarity_label = card["rarity"].title()
            is_equipped = card["id"] in (equipped.get("driver_id"), equipped.get("car_id"))
            eq = "  ✅" if is_equipped else ""

            if card["type"] == "driver":
                name_line = f"**{card['name']} ({card['code']})**{eq}"
                detail = f"{card['team']}  ·  Skill {card['skill']}/10  ·  {rarity_emoji} {rarity_label}"
            elif card["type"] == "car":
                name_line = f"**{card['name']}**{eq}"
                detail = f"{card['team']}  ·  {card['top_speed']} km/h  ·  {rarity_emoji} {rarity_label}"
            else:
                name_line = f"**{card['name']}**{eq}"
                detail = f"{card['team']}  ·  {card.get('role', 'Team Asset')}  ·  {rarity_emoji} {rarity_label}"

            if card.get("perks"):
                perk_name = card["perks"][0].replace("_", " ").title()
                detail += f"  ·  ✨ {perk_name}"

            lines.append(f"{name_line}\n{detail}")

        embed.description = "\n".join(lines) if lines else "*No cards in this category.*"
        embed.set_footer(text=f"{len(self.cards)} cards  ·  Page {self.page + 1} of {self.total_pages}  ·  {filter_label}  ·  ✅ = Equipped")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your collection!", ephemeral=True)
            return False
        return True

    async def _filter_all(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.filter_type = "all"
        self.page = 0
        self._update_filtered()
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _filter_drivers(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.filter_type = "driver"
        self.page = 0
        self._update_filtered()
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _filter_cars(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.filter_type = "car"
        self.page = 0
        self._update_filtered()
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _filter_assets(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.filter_type = "team_asset"
        self.page = 0
        self._update_filtered()
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _go_prev(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = min(self.total_pages - 1, self.page + 1)
        self._rebuild()
        await interaction.response.edit_message(content=None, embed=self.build_embed(), view=self)

    async def _on_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        card_id = interaction.data["values"][0]
        card = db.get_card_by_id(self.player_id, card_id)
        if not card:
            await interaction.response.send_message("Card not found.", ephemeral=True)
            return

        # Build plain-text header (no embed)
        card_display_id = card.get("id", "?").upper()
        caught_raw = card.get("caught_at") or card.get("obtained_at")
        caught_line = ""
        if caught_raw:
            try:
                caught_dt = datetime.fromisoformat(str(caught_raw))
                ts = int(caught_dt.timestamp())
                caught_line = f"Caught on <t:{ts}> (<t:{ts}:R>)"
            except Exception:
                caught_line = ""

        player_data = db.get_player(self.player_id)
        total_races = player_data.get("stats", {}).get("total_races", 0) if player_data else 0

        lines = [f"ID: ``#{card_display_id}``"]
        if caught_line:
            lines.append(caught_line)
        lines.append(f"__Matches played__: {total_races}")
        content = "\n".join(lines)

        art_file = make_card_art_file(card)
        back_view = CardDetailView(self)
        if art_file:
            await interaction.response.edit_message(
                content=content, embed=None, view=back_view, attachments=[art_file]
            )
        else:
            await interaction.response.edit_message(
                content=content, embed=None, view=back_view, attachments=[]
            )

    async def _on_quit(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Collection closed.", embed=None, view=None)


# ==================== UPGRADE SYSTEM ====================

def _upgrade_bar(level: int, max_level: int = 5) -> str:
    filled = "█" * level
    empty  = "░" * (max_level - level)
    return f"`{filled}{empty}`"


class UpgradeView(discord.ui.View):
    def __init__(self, player_id: str):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.selected_stat: Optional[str] = None
        self._build()

    def _build(self):
        self.clear_items()
        upgrades = db.get_upgrades(self.player_id)
        options = []
        for stat in UPGRADE_STATS:
            info   = UPGRADE_INFO[stat]
            level  = upgrades.get(stat, 0)
            if level < UPGRADE_MAX_LEVEL:
                cost   = UPGRADE_COSTS[level]
                label  = f"{info['emoji']} {info['label']}  Lv.{level}→{level+1}  · {cost:,} coins"
                desc   = info["description"]
            else:
                label  = f"{info['emoji']} {info['label']}  MAX LEVEL"
                desc   = "Already at peak performance!"
                cost   = 0
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description=desc[:100],
                    value=stat,
                    default=(stat == self.selected_stat),
                )
            )
        select = discord.ui.Select(
            placeholder="Select a system to upgrade…",
            options=options,
            row=0,
        )
        select.callback = self._on_select
        self.add_item(select)

        if self.selected_stat:
            level = db.get_upgrades(self.player_id).get(self.selected_stat, 0)
            can_upgrade = level < UPGRADE_MAX_LEVEL
            confirm_btn = discord.ui.Button(
                label="✅ Confirm Upgrade",
                style=discord.ButtonStyle.success if can_upgrade else discord.ButtonStyle.secondary,
                disabled=not can_upgrade,
                row=1,
            )
            confirm_btn.callback = self._on_confirm
            self.add_item(confirm_btn)

        close_btn = discord.ui.Button(label="✖ Close", style=discord.ButtonStyle.danger, row=1)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _build_embed(self) -> discord.Embed:
        upgrades  = db.get_upgrades(self.player_id)
        coins     = db.get_coins(self.player_id)
        player    = db.get_player(self.player_id)
        car_name  = "No car equipped"
        equipped  = db.get_equipped(self.player_id)
        if equipped.get("car_id"):
            car = db.get_card_by_id(self.player_id, equipped["car_id"])
            if car:
                car_name = f"{card_module.RARITY_EMOJIS.get(car['rarity'], '')} {car['name']} · {car['top_speed']} km/h"

        lines = [f"**🏎️ {car_name}**\n"]
        for stat in UPGRADE_STATS:
            info  = UPGRADE_INFO[stat]
            level = upgrades.get(stat, 0)
            bar   = _upgrade_bar(level)
            if level < UPGRADE_MAX_LEVEL:
                cost_str = f"Next: **{UPGRADE_COSTS[level]:,}** coins"
            else:
                cost_str = "**MAX ✅**"
            lines.append(f"{info['emoji']} **{info['label']}**  {bar}  Lv.{level}/5  ·  {cost_str}")

        if self.selected_stat:
            info  = UPGRADE_INFO[self.selected_stat]
            level = upgrades.get(self.selected_stat, 0)
            if level < UPGRADE_MAX_LEVEL:
                cost = UPGRADE_COSTS[level]
                lines.append(f"\n📦 *Selected:* **{info['label']}** Lv.{level}→{level+1} for **{cost:,} coins**")
                if coins < cost:
                    lines.append(f"⚠️ *Insufficient funds — you need **{cost - coins:,}** more coins.*")

        embed = discord.Embed(
            title="🔧  Car Upgrade Station",
            description="\n".join(lines),
            color=0xE67E22,
        )
        embed.add_field(name="💰 Your Balance", value=f"**{coins:,} coins**", inline=True)
        total_levels = sum(upgrades.get(s, 0) for s in UPGRADE_STATS)
        embed.add_field(name="📊 Total Upgrades", value=f"**{total_levels}** / {UPGRADE_MAX_LEVEL * len(UPGRADE_STATS)}", inline=True)
        embed.set_footer(text="Upgrades persist permanently · Earn coins by racing")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your upgrade menu!", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.selected_stat = interaction.data["values"][0]
        self._build()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_confirm(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        if not self.selected_stat:
            await interaction.response.send_message("Select an upgrade first.", ephemeral=True)
            return
        success, result = db.upgrade_stat(self.player_id, self.selected_stat)
        if success:
            info  = UPGRADE_INFO[self.selected_stat]
            level = result
            embed = discord.Embed(
                title="✅  Upgrade Complete!",
                description=(
                    f"{info['emoji']} **{info['label']}** upgraded to **Level {level}**!\n"
                    f"{_upgrade_bar(level)}  ·  {info['description']}"
                ),
                color=0x2ECC71,
            )
            embed.set_footer(text="Your car will be stronger in your next race!")
            self.selected_stat = None
            self._build()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(title="❌ Upgrade Failed", description=result, color=0xE74C3C)
            await interaction.response.edit_message(embed=embed, view=self)

    async def _on_close(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Upgrade menu closed.", embed=None, view=None)


@bot.tree.command(name="upgrade", description="Upgrade your car's systems: engine, aero, brakes, acceleration, suspension")
async def upgrade_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)
    view = UpgradeView(player_id)
    await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)


# ==================== TEAM MANAGEMENT ====================

class TeamView(discord.ui.View):
    """View/manage equipped team assets (staff cards)."""

    MAX_EQUIPPED = 3

    def __init__(self, player_id: str):
        super().__init__(timeout=120)
        self.player_id  = player_id
        self.mode       = "view"
        self._build()

    def _build(self):
        self.clear_items()
        cards    = db.get_player_cards(self.player_id)
        ta_cards = cards.get("team_assets", [])
        equipped = db.get_equipped(self.player_id)
        eq_ids   = equipped.get("team_assets", [])

        unequipped = [c for c in ta_cards if c["id"] not in eq_ids]
        equipped_cards = [c for c in ta_cards if c["id"] in eq_ids]

        if self.mode == "equip" and unequipped:
            options = []
            for c in unequipped[:25]:
                emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
                effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(c.get("effect", ""), c.get("effect", ""))
                bonus = c.get("bonus", 0)
                effect = c.get("effect", "")
                bonus_str = f"-{bonus:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{bonus:.0%}"
                options.append(discord.SelectOption(
                    label=f"{emoji} {c['name']} ({c.get('role','?')}) — {c['rarity'].title()}"[:100],
                    description=f"{effect_label}: {bonus_str}"[:100],
                    value=c["id"],
                ))
            select = discord.ui.Select(placeholder="Choose a team asset to equip…", options=options, row=0)
            select.callback = self._on_equip_select
            self.add_item(select)

        elif self.mode == "unequip" and equipped_cards:
            options = []
            for c in equipped_cards:
                emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
                effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(c.get("effect", ""), c.get("effect", ""))
                bonus = c.get("bonus", 0)
                effect = c.get("effect", "")
                bonus_str = f"-{bonus:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{bonus:.0%}"
                options.append(discord.SelectOption(
                    label=f"{emoji} {c['name']} ({c.get('role','?')}) — {c['rarity'].title()}"[:100],
                    description=f"{effect_label}: {bonus_str}"[:100],
                    value=c["id"],
                ))
            select = discord.ui.Select(placeholder="Choose a team asset to unequip…", options=options, row=0)
            select.callback = self._on_unequip_select
            self.add_item(select)

        if len(eq_ids) < self.MAX_EQUIPPED and unequipped:
            equip_btn = discord.ui.Button(label="➕ Equip Staff", style=discord.ButtonStyle.success, row=1)
            equip_btn.callback = self._set_equip_mode
            self.add_item(equip_btn)

        if equipped_cards:
            uneq_btn = discord.ui.Button(label="➖ Unequip Staff", style=discord.ButtonStyle.secondary, row=1)
            uneq_btn.callback = self._set_unequip_mode
            self.add_item(uneq_btn)

        close_btn = discord.ui.Button(label="✖ Close", style=discord.ButtonStyle.danger, row=1)
        close_btn.callback = self._on_close
        self.add_item(close_btn)

    def _build_embed(self) -> discord.Embed:
        cards    = db.get_player_cards(self.player_id)
        ta_cards = cards.get("team_assets", [])
        equipped = db.get_equipped(self.player_id)
        eq_ids   = equipped.get("team_assets", [])
        bonuses  = db.get_team_bonuses(self.player_id)

        eq_lines = []
        for i in range(self.MAX_EQUIPPED):
            if i < len(eq_ids):
                card = next((c for c in ta_cards if c["id"] == eq_ids[i]), None)
                if card:
                    emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
                    effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(card.get("effect", ""), card.get("effect", ""))
                    bonus = card.get("bonus", 0)
                    effect = card.get("effect", "")
                    bonus_str = f"-{bonus:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{bonus:.0%}"
                    eq_lines.append(f"**[{i+1}]** {emoji} **{card['name']}** — {effect_label} {bonus_str}")
                else:
                    eq_lines.append(f"**[{i+1}]** *Slot available*")
            else:
                eq_lines.append(f"**[{i+1}]** *Slot available*")

        bonus_parts = []
        for effect, val in bonuses.items():
            if val > 0:
                label = card_module.TEAM_ASSET_EFFECT_LABELS.get(effect, effect)
                bonus_str = f"-{val:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{val:.0%}"
                bonus_parts.append(f"{label}: **{bonus_str}**")

        desc = "**Active Slots**\n" + "\n".join(eq_lines)
        if bonus_parts:
            desc += "\n\n**Combined Race Bonuses**\n" + "\n".join(bonus_parts)

        unequipped = [c for c in ta_cards if c["id"] not in eq_ids]

        embed = discord.Embed(
            title="🏗️  Team Management",
            description=desc,
            color=0x3498DB,
        )
        embed.add_field(name="📦 Total Staff Cards", value=f"**{len(ta_cards)}**  ·  {len(eq_ids)}/{self.MAX_EQUIPPED} equipped", inline=True)
        embed.add_field(name="🔓 Available to Equip", value=f"**{len(unequipped)}**", inline=True)

        if unequipped[:8]:
            inv_lines = []
            for c in unequipped[:8]:
                emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
                effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(c.get("effect", ""), "")
                inv_lines.append(f"{emoji} **{c['name']}**  —  {effect_label}")
            if len(unequipped) > 8:
                inv_lines.append(f"*…and {len(unequipped) - 8} more*")
            embed.add_field(name="🗂️ Your Bench", value="\n".join(inv_lines), inline=False)

        embed.set_footer(text="Up to 3 team assets can be equipped · Bonuses apply in every race")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your team menu!", ephemeral=True)
            return False
        return True

    async def _set_equip_mode(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.mode = "equip"
        self._build()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _set_unequip_mode(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.mode = "unequip"
        self._build()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _on_equip_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        card_id = interaction.data["values"][0]
        success, msg = db.equip_team_asset(self.player_id, card_id)
        self.mode = "view"
        self._build()
        if success:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def _on_unequip_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        card_id = interaction.data["values"][0]
        success, msg = db.unequip_team_asset(self.player_id, card_id)
        self.mode = "view"
        self._build()
        if success:
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        else:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)

    async def _on_close(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Team menu closed.", embed=None, view=None)


@bot.tree.command(name="team", description="Manage your team staff — equip pit crew, engineers, and strategists")
async def team_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)
    view = TeamView(player_id)
    await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)


# ==================== GARAGE (SLASH) & PROFILE ====================

@bot.tree.command(name="garage", description="View your full racing loadout — driver, car, team staff, and upgrades")
async def garage_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    cards    = db.get_player_cards(player_id)
    equipped = db.get_equipped(player_id)
    upgrades = db.get_upgrades(player_id)
    bonuses  = db.get_team_bonuses(player_id)
    coins    = db.get_coins(player_id)

    # Equipped driver
    driver_line = "*None equipped*"
    if equipped.get("driver_id"):
        d = db.get_card_by_id(player_id, equipped["driver_id"])
        if d:
            emoji = card_module.RARITY_EMOJIS.get(d["rarity"], "")
            driver_line = f"{emoji} **{d['name']}** ({d['code']}) · Skill {d['skill']}/10 · {d['team']}"

    # Equipped car
    car_line = "*None equipped*"
    if equipped.get("car_id"):
        c = db.get_card_by_id(player_id, equipped["car_id"])
        if c:
            emoji = card_module.RARITY_EMOJIS.get(c["rarity"], "")
            mults = db.get_upgrade_multipliers(player_id)
            boosted_speed = int(c["top_speed"] * mults["engine"])
            car_line = (
                f"{emoji} **{c['name']}** · {c['team']}\n"
                f"Top Speed: **{c['top_speed']}** → **{boosted_speed} km/h** (with upgrades)"
            )

    # Upgrades summary
    upgrade_lines = []
    for stat in UPGRADE_STATS:
        info  = UPGRADE_INFO[stat]
        level = upgrades.get(stat, 0)
        upgrade_lines.append(f"{info['emoji']} {info['label']}  {_upgrade_bar(level)}  Lv.{level}/5")

    # Team assets
    ta_ids = equipped.get("team_assets", [])
    ta_cards = cards.get("team_assets", [])
    ta_lines = []
    for i in range(3):
        if i < len(ta_ids):
            card = next((c for c in ta_cards if c["id"] == ta_ids[i]), None)
            if card:
                emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
                effect_label = card_module.TEAM_ASSET_EFFECT_LABELS.get(card.get("effect", ""), "")
                bonus = card.get("bonus", 0)
                effect = card.get("effect", "")
                bonus_str = f"-{bonus:.0%}" if effect in ("tire_wear", "fuel_efficiency", "pit_time") else f"+{bonus:.0%}"
                ta_lines.append(f"{emoji} **{card['name']}** — {effect_label} {bonus_str}")
            else:
                ta_lines.append("*Empty slot*")
        else:
            ta_lines.append("*Empty slot*")

    embed = discord.Embed(
        title=f"🏎️  {interaction.user.display_name}'s Garage",
        color=0x2C3E50,
    )
    embed.add_field(name="👤 Driver",       value=driver_line,           inline=False)
    embed.add_field(name="🏎️ Car",          value=car_line,              inline=False)
    embed.add_field(name="🔧 Upgrades",     value="\n".join(upgrade_lines), inline=True)
    embed.add_field(name="🏗️ Team Staff",   value="\n".join(ta_lines), inline=True)
    embed.add_field(name="💰 Race Credits", value=f"**{coins:,}** coins", inline=False)
    embed.set_footer(text="/f1 equip · /upgrade · /team to change loadout")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="profile", description="View your F1 racing profile and full stats")
@app_commands.describe(member="Player to view (leave blank for yourself)")
async def profile_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    target = member or interaction.user
    player_id = str(target.id)
    db.ensure_player(player_id, target.name)
    embeds = build_profile_embeds(player_id, target.display_name)
    await interaction.response.send_message(embeds=embeds)


# ==================== MAIN ====================

# ==================== CARD FUSION ====================

FUSION_COST = 3  # duplicates required per fusion
_FUSION_RARITY_RANK = {"mythic": 0, "legendary": 1, "epic": 2, "rare": 3, "common": 4}
_DRIVER_SKILL_BOOSTS = [0.1, 0.2, 0.3]
_CAR_SPEED_BOOSTS    = [2, 3, 5]


def _get_fuseable_groups(player_id: str) -> List[Dict]:
    """Return groups of 3+ identical cards eligible for fusion, sorted by rarity desc."""
    cards = db.get_player_cards(player_id)
    groups = []
    for card_type, card_list in [("driver", cards["drivers"]), ("car", cards["cars"])]:
        by_name: Dict[str, List] = {}
        for card in card_list:
            by_name.setdefault(card["name"], []).append(card)
        for name, dupes in by_name.items():
            rarity = dupes[0]["rarity"]
            if len(dupes) >= FUSION_COST:
                groups.append({
                    "name":   name,
                    "type":   card_type,
                    "rarity": rarity,
                    "count":  len(dupes),
                    "cards":  dupes,
                })
    groups.sort(key=lambda g: (_FUSION_RARITY_RANK.get(g["rarity"], 9), g["name"]))
    return groups


def _build_fused_card(source: Dict):
    """Return (fused_card_dict, card_type, stat_boost) ready to give to the player."""
    card_type = source.get("type", "driver")
    new_id    = f"fused_{int(time.time())}_{random.randint(10000, 99999)}"
    fused     = dict(source)
    fused["id"]    = new_id
    # Rarity stays the same
    fused["rarity"] = source.get("rarity", "common")
    # Always grant a perk on fusion
    fused["perks"]  = [random.choice(list(card_module.PERKS.keys()))]

    # Luck-based stat boost — rarity never changes
    if card_type == "driver":
        boost = random.choice(_DRIVER_SKILL_BOOSTS)
        old_skill = float(source.get("skill", 5.0))
        fused["skill"] = round(min(10.0, old_skill + boost), 1)
        stat_boost = f"+{boost} Skill  ({old_skill}/10 → {fused['skill']}/10)"
    else:
        boost = random.choice(_CAR_SPEED_BOOSTS)
        old_speed = int(source.get("top_speed", 200))
        fused["top_speed"] = old_speed + boost
        stat_boost = f"+{boost} km/h  ({old_speed} → {fused['top_speed']} km/h)"

    return fused, card_type, stat_boost


# ── Embed builders ──────────────────────────────────────────────────────────

def _fusion_lab_embed(groups: List[Dict], user: discord.Member) -> discord.Embed:
    driver_n = sum(1 for g in groups if g["type"] == "driver")
    car_n    = sum(1 for g in groups if g["type"] == "car")
    embed = discord.Embed(
        title="🔬  CARD FUSION LAB",
        description=(
            "Sacrifice **3 identical cards** to boost a single card's stats.\n"
            "Every fused card receives a **guaranteed bonus perk**.\n\n"
            "**🎲 Luck-based boosts**\n"
            "👤 Driver → Skill +0.1 / +0.2 / +0.3\n"
            "🏎️  Car    → Speed +2 / +3 / +5 km/h\n\n"
            f"**Available Fusions**\n"
            f"👤 Driver groups: **{driver_n}**\n"
            f"🏎️  Car groups:    **{car_n}**"
        ),
        color=0x5865F2,
    )
    embed.set_footer(text=f"{user.display_name}  ·  /fusion")
    return embed


def _fusion_select_embed(groups: List[Dict], filter_type: Optional[str], user: discord.Member) -> discord.Embed:
    shown = [g for g in groups if filter_type is None or g["type"] == filter_type]
    label = {"driver": "👤 Drivers", "car": "🏎️ Cars"}.get(filter_type, "All Cards")
    embed = discord.Embed(
        title=f"⚗️  FUSION — {label}",
        description=(
            f"Pick a card group from the dropdown to preview the fusion.\n"
            f"**{FUSION_COST}×** identical cards are consumed per fusion.\n\u200b"
        ),
        color=0x5865F2,
    )
    if not shown:
        embed.add_field(name="\u200b", value="❌  No eligible cards in this category.", inline=False)
    else:
        lines = [
            f"{card_module.RARITY_EMOJIS.get(g['rarity'], '')} **{g['name']}**"
            f"  [{g['rarity'].upper()}]  ×{g['count']}"
            f"  →  📈 Stat Boost + Perk"
            for g in shown[:10]
        ]
        embed.add_field(name="Eligible Fusions", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"{user.display_name}  ·  /fusion")
    return embed


def _fusion_confirm_embed(group: Dict) -> discord.Embed:
    emoji = card_module.RARITY_EMOJIS.get(group["rarity"], "")
    color = card_module.RARITY_COLORS.get(group["rarity"], 0x5865F2)
    if group["type"] == "driver":
        boost_hint = "🎲 Luck-based **Skill boost** (+0.1 / +0.2 / +0.3)"
    else:
        boost_hint = "🎲 Luck-based **Speed boost** (+2 / +3 / +5 km/h)"
    desc = (
        f"**CONSUMING**  *(3 copies destroyed)*\n"
        f"```\n❌  {group['name']}  [{group['rarity'].upper()}]  ×{FUSION_COST}\n```\n"
        f"⬇️  ⬇️  ⬇️\n\n"
        f"**FORGED RESULT**\n"
        f"```\n✨  {group['name']}  [{group['rarity'].upper()}]  + Bonus Perk\n```\n"
        f"{boost_hint}\n\n"
        f"⚠️  This action **cannot be undone**."
    )
    return discord.Embed(title=f"🔥  FUSION PREVIEW  —  {emoji} {group['rarity'].upper()}", description=desc, color=color)


def _fusion_result_embed(fused: Dict, user: discord.Member, stat_boost: str = "") -> discord.Embed:
    emoji    = card_module.RARITY_EMOJIS.get(fused["rarity"], "")
    color    = card_module.RARITY_COLORS.get(fused["rarity"], 0x5865F2)
    perk_key = (fused.get("perks") or [None])[0]
    perk     = card_module.PERKS.get(perk_key, {}) if perk_key else {}
    type_tag = "👤 Driver" if fused.get("type") == "driver" else "🏎️ Car"

    if fused.get("type") == "driver":
        stats = f"Skill **{fused['skill']}/10**  ·  Team **{fused['team']}**"
    else:
        stats = f"**{fused['top_speed']} km/h**  ·  Handling **{fused.get('handling', '?')}/10**  ·  Team **{fused['team']}**"

    boost_line = f"📈  **Stat Boost:**  {stat_boost}\n\n" if stat_boost else ""
    desc = (
        f"## {emoji}  {fused['name'].upper()}\n"
        f"**{fused['rarity'].upper()}**  ·  {type_tag}\n\n"
        f"{stats}\n\n"
        f"{boost_line}"
        f"🎁  **Bonus Perk Unlocked**\n"
        f"**{perk.get('name', perk_key or '—')}** — {perk.get('description', '')}"
    )
    embed = discord.Embed(title="✨  FUSION COMPLETE!", description=desc, color=color)
    embed.set_footer(text=f"{user.display_name}  ·  3 cards consumed")
    return embed


# ── UI Views ────────────────────────────────────────────────────────────────

class FusionSelectView(discord.ui.View):
    def __init__(self, player_id: str, user: discord.Member, filter_type: Optional[str] = None):
        super().__init__(timeout=120)
        self.player_id   = player_id
        self.user        = user
        self.filter_type = filter_type
        self.groups      = _get_fuseable_groups(player_id)
        self._rebuild()

    def _owner(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.player_id

    def _rebuild(self):
        self.clear_items()
        ft = self.filter_type

        # ── Row 0: filter + cancel ──
        for label, ftype in [("🔀 All", None), ("👤 Drivers", "driver"), ("🏎️ Cars", "car")]:
            active = ft == ftype
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
                row=0,
            )
            _ft = ftype
            async def _filter_cb(i: discord.Interaction, _t=_ft):
                if not self._owner(i):
                    await i.response.send_message("Not your menu!", ephemeral=True); return
                self.filter_type = _t
                self._rebuild()
                await i.response.edit_message(embed=_fusion_select_embed(self.groups, self.filter_type, self.user), view=self)
            btn.callback = _filter_cb
            self.add_item(btn)

        cancel = discord.ui.Button(label="✖ Cancel", style=discord.ButtonStyle.danger, row=0)
        async def _cancel(i: discord.Interaction):
            if not self._owner(i):
                await i.response.send_message("Not your menu!", ephemeral=True); return
            await i.response.edit_message(content="Fusion cancelled.", embed=None, view=None)
        cancel.callback = _cancel
        self.add_item(cancel)

        # ── Row 1: card group dropdown ──
        shown = [g for g in self.groups if ft is None or g["type"] == ft]
        if shown:
            options = []
            for g in shown[:25]:
                e = card_module.RARITY_EMOJIS.get(g["rarity"], "")
                options.append(discord.SelectOption(
                    label=f"{g['name']}  ×{g['count']}"[:100],
                    description=f"{g['rarity'].title()}  ·  📈 Stat Boost + Perk"[:100],
                    value=f"{g['type']}::{g['name']}::{g['rarity']}",
                    emoji=e or None,
                ))
            sel = discord.ui.Select(placeholder="Choose a card group to fuse…", options=options, row=1)
            async def _on_sel(i: discord.Interaction):
                if not self._owner(i):
                    await i.response.send_message("Not your menu!", ephemeral=True); return
                val   = i.data["values"][0]
                ctype, cname, crarity = val.split("::")
                grp = next((g for g in self.groups if g["type"] == ctype and g["name"] == cname and g["rarity"] == crarity), None)
                if not grp:
                    await i.response.send_message("❌ Card group not found.", ephemeral=True); return
                await i.response.edit_message(embed=_fusion_confirm_embed(grp), view=FusionConfirmView(self.player_id, self.user, grp))
            sel.callback = _on_sel
            self.add_item(sel)


class FusionConfirmView(discord.ui.View):
    def __init__(self, player_id: str, user: discord.Member, group: Dict):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.user      = user
        self.group     = group

    def _owner(self, interaction: discord.Interaction) -> bool:
        return str(interaction.user.id) == self.player_id

    @discord.ui.button(label="🔥  FUSE IT", style=discord.ButtonStyle.success, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your menu!", ephemeral=True); return
        await interaction.response.defer()

        # Re-validate — make sure copies still exist
        current = _get_fuseable_groups(self.player_id)
        grp = next(
            (g for g in current
             if g["type"] == self.group["type"]
             and g["name"] == self.group["name"]
             and g["rarity"] == self.group["rarity"]),
            None,
        )
        if not grp:
            await interaction.followup.edit_message(
                interaction.message.id,
                content="❌ You no longer have enough copies for this fusion.",
                embed=None, view=None,
            )
            return

        # Remove exactly 3 copies
        removed = 0
        for card in grp["cards"][:FUSION_COST]:
            if db.remove_card(self.player_id, card["id"]):
                removed += 1

        if removed < FUSION_COST:
            await interaction.followup.edit_message(
                interaction.message.id,
                content=f"❌ Only removed {removed}/{FUSION_COST} cards — fusion failed.",
                embed=None, view=None,
            )
            return

        fused, card_type, stat_boost = _build_fused_card(grp["cards"][0])
        db.add_card_to_player(self.player_id, fused, card_type)
        await interaction.followup.edit_message(
            interaction.message.id,
            embed=_fusion_result_embed(fused, self.user, stat_boost),
            view=None,
        )

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your menu!", ephemeral=True); return
        view = FusionSelectView(self.player_id, self.user)
        await interaction.response.edit_message(
            embed=_fusion_select_embed(view.groups, view.filter_type, self.user), view=view
        )

    @discord.ui.button(label="✖ Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._owner(interaction):
            await interaction.response.send_message("Not your menu!", ephemeral=True); return
        await interaction.response.edit_message(content="Fusion cancelled.", embed=None, view=None)


# ── Slash command ────────────────────────────────────────────────────────────

@bot.tree.command(name="fusion", description="Fuse 3 identical cards into a single higher-rarity card")
async def fusion_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer()

    groups = _get_fuseable_groups(player_id)

    if not groups:
        embed = discord.Embed(
            title="🔬  CARD FUSION LAB",
            description=(
                "Sacrifice **3 identical cards** to forge a higher-rarity version.\n"
                "Every fused card receives a **guaranteed bonus perk**.\n\n"
                "**— Rarity Chain —**\n"
                "⚪ Common  →  💙 Rare  →  💜 Epic  →  👑 Legendary  →  🔱 Mythic\n\n"
                "❌  **No eligible cards yet.**\n"
                "Collect 3 duplicates of the same card to unlock fusion."
            ),
            color=0x5865F2,
        )
        embed.set_footer(text=f"{interaction.user.display_name}  ·  /fusion")
        await interaction.followup.send(embed=embed)
        return

    view = FusionSelectView(player_id, interaction.user)
    embed = discord.Embed(
        title="🔬  CARD FUSION LAB",
        description=(
            "Sacrifice **3 identical cards** to forge a single higher-rarity version.\n"
            "Every fused card receives a **guaranteed bonus perk**.\n\n"
            "**— Rarity Chain —**\n"
            "⚪ Common  →  💙 Rare  →  💜 Epic  →  👑 Legendary  →  🔱 Mythic\n\n"
            f"**{len(groups)} fusion{'s' if len(groups) != 1 else ''}** available — select a group below."
        ),
        color=0x5865F2,
    )
    embed.set_footer(text=f"{interaction.user.display_name}  ·  /fusion")
    await interaction.followup.send(embed=_fusion_select_embed(groups, None, interaction.user), view=view)


# ==================== VOTE COMMAND ====================

TOPGG_VOTE_URL = "https://top.gg/bot/1228631433501999124/vote"
VOTE_COINS_REWARD = 150

class VoteClaimView(discord.ui.View):
    def __init__(self, player_id: str, can_claim: bool):
        super().__init__(timeout=60)
        self.player_id = player_id

        self.add_item(discord.ui.Button(
            label="Vote on Top.gg",
            url=TOPGG_VOTE_URL,
            style=discord.ButtonStyle.link,
            emoji="🗳️",
            row=0,
        ))

        claim_btn = discord.ui.Button(
            label="Claim Reward" if can_claim else "Already Claimed",
            style=discord.ButtonStyle.success if can_claim else discord.ButtonStyle.secondary,
            emoji="🎁",
            disabled=not can_claim,
            custom_id="vote_claim",
            row=0,
        )
        claim_btn.callback = self._claim_callback
        self.add_item(claim_btn)

    async def _claim_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your reward!", ephemeral=True)
            return

        if not db.can_claim_vote(self.player_id):
            await interaction.response.send_message(
                "⏰ You've already claimed your vote reward. Vote again in 12 hours!", ephemeral=True
            )
            return

        db.add_coins(self.player_id, VOTE_COINS_REWARD)
        db.add_vote_bonus_match(self.player_id)
        db.set_vote_claimed(self.player_id)

        for item in self.children:
            item.disabled = True

        reward_embed = discord.Embed(
            title="✅  Vote Reward Claimed!",
            description=(
                f"Thanks for voting! You received:\n\n"
                f"💰 **{VOTE_COINS_REWARD} Race Credits**\n"
                f"🏁 **+1 Bonus Career Match**\n\n"
                f"Vote again in **12 hours** for another reward!"
            ),
            color=0x00b894,
        )
        reward_embed.set_footer(text="Use /career_match to play your bonus race!")
        await interaction.response.edit_message(embed=reward_embed, view=self)
        self.stop()


@bot.tree.command(name="vote", description="Vote for the bot on Top.gg and claim your reward!")
async def vote_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer(ephemeral=True)

    can_claim = db.can_claim_vote(player_id)
    bonus = db.get_vote_bonus_matches(player_id)

    if can_claim:
        desc = (
            "**Voting is free and takes 5 seconds!**\n\n"
            "Click **Vote on Top.gg**, then come back and hit **Claim Reward** to get:\n\n"
            f"💰 **{VOTE_COINS_REWARD} Race Credits**\n"
            f"🏁 **+1 Bonus Career Match**\n\n"
            f"You can vote every **12 hours**."
        )
        color = 0xE10600
    else:
        import re as _re
        player = db.get_player(player_id)
        last_str = player.get("last_vote_claimed") if player else None
        if last_str:
            from datetime import datetime as _dt
            elapsed = (_dt.now() - _dt.fromisoformat(last_str)).total_seconds()
            remaining = max(0, int(12 * 3600 - elapsed))
            h, m = divmod(remaining // 60, 60)
            time_str = f"{h}h {m}m" if h else f"{m}m"
        else:
            time_str = "soon"
        desc = (
            f"You've already voted — thank you! 🎉\n\n"
            f"Next claim available in **{time_str}**.\n\n"
            f"Current bonus matches saved: **{bonus}**"
        )
        color = 0x636e72

    embed = discord.Embed(
        title="🗳️  Vote for F1 Card Collection!",
        description=desc,
        color=color,
    )
    embed.set_footer(text="Your votes help the bot grow — thank you!")

    view = VoteClaimView(player_id, can_claim)
    await interaction.followup.send(embed=embed, view=view)


# ==================== CAREER VOTE VIEW ====================

class CareerVoteView(discord.ui.View):
    """Shown when career daily limit is reached — lets player use a bonus match or vote."""

    def __init__(self, player_id: str, has_bonus: bool):
        super().__init__(timeout=120)
        self.player_id  = player_id
        self.used_bonus = False

        vote_url = "https://top.gg/bot/1228631433501999124/vote"
        self.add_item(discord.ui.Button(
            label="Vote on Top.gg for +1 Match",
            url=vote_url,
            style=discord.ButtonStyle.link,
            emoji="🗳️",
            row=0,
        ))

        use_btn = discord.ui.Button(
            label="Use Bonus Match" if has_bonus else "No Bonus Matches",
            style=discord.ButtonStyle.success if has_bonus else discord.ButtonStyle.secondary,
            emoji="🏁",
            disabled=not has_bonus,
            row=0,
        )
        use_btn.callback = self._use_bonus_callback
        self.add_item(use_btn)

    async def _use_bonus_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your career!", ephemeral=True)
            return
        if not db.use_vote_bonus_match(self.player_id):
            await interaction.response.send_message(
                "❌ No bonus matches left. Vote on Top.gg to earn one!", ephemeral=True
            )
            return
        self.used_bonus = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✅  Bonus Match Used!",
                description="Your bonus match has been applied.\nRun `/career_match` now to play your extra race!",
                color=0x00b894,
            ),
            view=self,
        )
        self.stop()


# ==================== CAREER MODE ====================

@bot.tree.command(name="career", description="Start or view your F1 Career Mode season")
async def career_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer()

    career = db.get_career(player_id)

    # Already has an active / completed career → show status
    if career and career.get("status") in ("active", "completed"):
        if career["status"] == "completed":
            await interaction.followup.send(
                "🏁 You have completed all your career matches! Stay tuned for next season.",
                embed=career_mod.career_status_embed(career, interaction.user.display_name),
            )
        else:
            await interaction.followup.send(
                embed=career_mod.career_status_embed(career, interaction.user.display_name)
            )
        return

    # Fresh sign-up flow — show landing embed
    signup_view = career_mod.CareerSignupView(player_id)
    await interaction.followup.send(embed=career_mod.career_landing_embed(), view=signup_view)
    await signup_view.wait()
    if not signup_view.signed:
        return

    # --- Car selection ---
    cards = db.get_player_cards(player_id)
    cars  = cards.get("cars", [])
    if not cars:
        await interaction.followup.send("❌ You need at least one car in your collection to start career mode!", ephemeral=True)
        return
    car_view = career_mod.CareerCarSelectView(player_id, cars)
    await interaction.followup.send("**Step 1 of 2 — Choose your career car:**", view=car_view, ephemeral=True)
    await car_view.wait()
    chosen_car = car_view.selected
    if not chosen_car:
        await interaction.followup.send("❌ No car selected. Use `/career` to try again.", ephemeral=True)
        return

    # --- Driver selection ---
    drivers = cards.get("drivers", [])
    if not drivers:
        await interaction.followup.send("❌ You need at least one driver to start career mode!", ephemeral=True)
        return
    drv_view = career_mod.CareerDriverSelectView(player_id, drivers)
    await interaction.followup.send("**Step 2 of 2 — Choose your career driver:**", view=drv_view, ephemeral=True)
    await drv_view.wait()
    chosen_drv = drv_view.selected
    if not chosen_drv:
        await interaction.followup.send("❌ No driver selected. Use `/career` to try again.", ephemeral=True)
        return

    # --- Confirmation ---
    rarity_e_car = card_module.RARITY_EMOJIS.get(chosen_car.get("rarity", "common"), "")
    rarity_e_drv = card_module.RARITY_EMOJIS.get(chosen_drv.get("rarity", "common"), "")
    confirm_embed = discord.Embed(
        title="📝  Confirm Your Career Contract",
        description=(
            f"You are about to lock in your career setup for the **entire season**.\n"
            f"You cannot change these mid-season.\n\u200b\n"
            f"🏎️  **Car:** {rarity_e_car} {chosen_car['name']}  ·  {chosen_car.get('top_speed','?')} km/h\n"
            f"👤  **Driver:** {rarity_e_drv} {chosen_drv['name']}  ·  Skill {chosen_drv.get('skill','?')}/10\n\n"
            f"⚙️  Your **garage upgrades** will still apply each race."
        ),
        color=0x2d3436,
    )
    confirm_view = career_mod.CareerConfirmView(player_id)
    await interaction.followup.send(embed=confirm_embed, view=confirm_view, ephemeral=True)
    await confirm_view.wait()
    if not confirm_view.confirmed:
        await interaction.followup.send("Selection changed. Use `/career` to start again.", ephemeral=True)
        return

    # --- Create career record ---
    car_snap = {k: chosen_car.get(k) for k in ("id", "name", "team", "top_speed", "handling", "rarity")}
    drv_snap = {k: chosen_drv.get(k) for k in ("id", "name", "code", "skill", "team", "rarity")}
    db.create_career(player_id, car_snap, drv_snap)

    # Public announcement
    await interaction.channel.send(
        f"🏎️  {interaction.user.mention} has **signed their F1 Career contract!**\n"
        f"The career matches will become very hard. We request you to play the matches "
        f"at the recommended speed or above it to have a good chance of winning the match! 🏎️"
    )
    await interaction.followup.send(
        "✅ **Contract signed!** Your career has begun. Use `/matches` to see your schedule and `/career_match` to race!",
        ephemeral=True,
    )


@bot.tree.command(name="matches", description="View your F1 Career season schedule")
async def matches_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer()
    career = db.get_career(player_id)
    if not career:
        await interaction.followup.send("❌ You haven't started career mode yet. Use `/career` to sign up!")
        return
    await interaction.followup.send(embed=career_mod.matches_embed(career))


@bot.tree.command(name="career_match", description="Play your next F1 Career race")
async def career_match_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer()

    career = db.get_career(player_id)
    if not career:
        await interaction.followup.send("❌ You haven't started career mode yet. Use `/career` to sign up!")
        return
    if career.get("status") == "completed":
        await interaction.followup.send("🏁 You have completed all your career matches! Stay tuned for next season.")
        return

    ok, reason = career_mod.can_play(career)
    if not ok:
        if reason == "season_done":
            await interaction.followup.send("🏁 You have completed all your career matches! Stay tuned for next season.")
        elif reason.startswith("cooldown:"):
            secs = int(reason.split(":")[1])
            ts   = career_mod.next_unlock_timestamp(career)
            cooldown_str = (
                f"⏰ Daily limit reached. Next match unlocks <t:{ts}:R> ({career_mod.fmt_secs(secs)})."
                if ts else f"⏰ Cooldown: {career_mod.fmt_secs(secs)} remaining."
            )
            bonus = db.get_vote_bonus_matches(player_id)
            limit_embed = discord.Embed(
                title="🏁  Daily Limit Reached",
                description=(
                    f"{cooldown_str}\n\n"
                    + (
                        f"You have **{bonus} bonus {'match' if bonus == 1 else 'matches'}** saved up! Click below to use one."
                        if bonus > 0
                        else "**Vote for the bot on Top.gg** to earn an extra match right now!"
                    )
                ),
                color=0xE10600,
            )
            limit_embed.set_footer(text="Use /vote to claim voting rewards including bonus career matches.")
            view = CareerVoteView(player_id, has_bonus=bonus > 0)
            await interaction.followup.send(embed=limit_embed, view=view)
        return

    match_num = career.get("matches_completed", 0) + 1
    car_snap  = career["car_snapshot"]
    drv_snap  = career["driver_snapshot"]
    upgrades  = db.get_upgrades(player_id)
    npcs      = career_mod.get_race_npcs(match_num)

    # Show preview embed with Start button
    preview    = career_mod.match_preview_embed(match_num, npcs, car_snap, drv_snap, upgrades)
    start_view = career_mod.CareerMatchStartView(player_id)
    msg        = await interaction.followup.send(embed=preview, view=start_view)
    await start_view.wait()
    if not start_view.started:
        return

    # Fetch the actual message object for in-place editing during the race
    try:
        msg_obj = await interaction.channel.fetch_message(msg.id)
    except Exception:
        msg_obj = msg

    # Run full race (3 laps / 12 turns — mirrors normal race)
    result = await career_mod.run_career_race(
        interaction.channel,
        msg_obj,
        interaction.user,
        player_id,
        match_num,
        car_snap,
        drv_snap,
        upgrades,
    )

    # Save to DB
    db.record_career_match(player_id, result)

    # Show result embed
    await msg_obj.edit(
        embed=career_mod.race_result_embed(
            result["standings"],
            result["position"],
            result["coins"],
            result["points"],
            result["track"],
            result["qte_hits"],
            result["qte_total"],
            result["pit_hits"],
            result["state"],
        ),
        view=None,
    )

    # Check if season just completed
    updated_career = db.get_career(player_id)
    if updated_career and updated_career.get("status") == "completed":
        await interaction.channel.send(
            f"🏆 {interaction.user.mention} has **completed their career season!** "
            f"Use `/career_standings` to see the final standings and `/career_rewards` to claim your prize!"
        )


@bot.tree.command(name="career_standings", description="View the F1 Career championship standings")
async def career_standings_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    all_standings = db.get_career_standings()
    await interaction.followup.send(embed=career_mod.career_standings_embed(all_standings))


@bot.tree.command(name="career_rewards", description="View and claim your F1 Career season rewards")
async def career_rewards_slash(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    await interaction.response.defer()

    career = db.get_career(player_id)
    if not career:
        await interaction.followup.send("❌ You haven't started career mode yet. Use `/career` to sign up!")
        return

    player_pos  = db.get_career_player_position(player_id)
    completed   = career.get("matches_completed", 0) >= career_mod.TOTAL_MATCHES
    claimable   = completed and not career.get("reward_claimed", False)
    rewards_view = career_mod.CareerRewardsView(player_id, claimable)

    await interaction.followup.send(
        embed=career_mod.career_rewards_embed(player_pos or 99, career),
        view=rewards_view,
    )
    if not claimable:
        return

    await rewards_view.wait()
    if not rewards_view.claimed:
        return

    # ── Grant rewards ──
    career = db.get_career(player_id)
    career["reward_claimed"] = True
    db.set_career(player_id, career)

    lines = ["✅  **Season rewards granted!**\n"]

    # Coins
    coin_rewards = {1: 8000, 2: 8000, 3: 8000, 4: 6000, 5: 5000,
                    6: 4000, 7: 3000, 8: 2000}
    coins = coin_rewards.get(player_pos, 1000)
    db.add_coins(player_id, coins)
    lines.append(f"💰  **+{coins:,} Coins** awarded")

    # Special career card (top 3)
    if player_pos in career_mod.CAREER_SPECIAL_CARDS:
        spec = career_mod.CAREER_SPECIAL_CARDS[player_pos].copy()
        spec["id"] = f"{spec['id']}_{player_id}"
        spec["obtained_at"] = datetime.now().isoformat()
        db.add_card_to_player(player_id, spec, "driver")
        rarity_e = card_module.RARITY_EMOJIS.get(spec["rarity"], "")
        lines.append(f"{rarity_e}  **Special Card:** {spec['name']} added to your collection!")

    # Pack rewards (simulate by giving bonus coins for simplicity — packs can be added via existing pack system)
    pack_bonus = {1: 5000, 2: 4000, 3: 3000, 4: 2000, 5: 1000}
    if player_pos in pack_bonus:
        extra = pack_bonus[player_pos]
        db.add_coins(player_id, extra)
        lines.append(f"📦  **Pack value:** +{extra:,} coins (use to open packs)")

    await interaction.followup.send("\n".join(lines))


if __name__ == "__main__":
    # LOAD .ENV FIRST - before getting the token!
    from dotenv import load_dotenv
    load_dotenv()  # This must come FIRST
    
    # THEN get the token
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    bot.run(TOKEN)
