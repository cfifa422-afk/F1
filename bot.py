import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, List
import random

from database import Database, UPGRADE_STATS, UPGRADE_COSTS, UPGRADE_MAX_LEVEL, UPGRADE_INFO
import cards as card_module
import f1_images
import commentary as commentary_engine

# ==================== BOT SETUP ====================

intents = discord.Intents.default()
intents.message_content = True
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
        rarity_bonus = {"legendary": 1.15, "epic": 1.10, "rare": 1.05, "common": 1.00}.get(self.rarity, 1.0)
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
    def __init__(self, driver_id: str, name: str, code: str, skill: float, rarity: str):
        self.driver_id = driver_id
        self.name = name
        self.code = code
        self.skill = skill
        self.rarity = rarity

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
            p1_time = -3.2

        if p2_choice == "pit_stop":
            race.p2_pit_stops += 1
            race.p2_fuel = 100.0
            race.p2_tire_wear = 0.0
            race.p2_tire_type = self._get_optimal_tire(race, event)
            p2_time = -3.2

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
        tire_type = race.p1_tire_type if player == "p1" else race.p2_tire_type
        tire_wear = race.p1_tire_wear if player == "p1" else race.p2_tire_wear

        base_speed = car.stats["acceleration"]
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

        return base_speed * tire_bonus + choice_impact + event_modifier + weather_impact - wear_penalty

    def _update_consumables(self, race: RaceState, player: str, choice: str):
        fuel_burn = {"accelerate": 5.0, "same_speed": 3.0, "slow_down": 2.0, "pit_stop": 0.0}.get(choice, 3.0)
        car = race.p1_car if player == "p1" else race.p2_car
        fuel_eff = car.stats["fuel_efficiency"]

        if player == "p1":
            race.p1_fuel -= fuel_burn * fuel_eff
            if choice != "pit_stop":
                race.p1_tire_wear += {"accelerate": 8.0, "same_speed": 4.0, "slow_down": 2.0}.get(choice, 4.0)
        else:
            race.p2_fuel -= fuel_burn * fuel_eff
            if choice != "pit_stop":
                race.p2_tire_wear += {"accelerate": 8.0, "same_speed": 4.0, "slow_down": 2.0}.get(choice, 4.0)

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
    )


def give_starter_cards(player_id: str, username: str):
    """Give starter cards to brand new players."""
    cards = db.get_player_cards(player_id)
    if not cards["drivers"] and not cards["cars"]:
        import random as _r
        starter_driver = {
            "id": f"starter_driver_{player_id}",
            "type": "driver",
            "name": "Alex Albon",
            "code": "ALB",
            "skill": 6.8,
            "team": "Williams",
            "rarity": "common",
            "perks": [],
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
    stats["acceleration"] = stats.get("acceleration", 5.0) * mults["acceleration"] * (1.0 + team_bonuses.get("acceleration", 0.0))
    stats["handling"]     = stats.get("handling", 5.0)     * mults["aero"]         * (1.0 + team_bonuses.get("aero", 0.0))
    stats["tire_wear_rate"]   = stats.get("tire_wear_rate", 1.0) * mults["brakes"]  * max(0.2, 1.0 - team_bonuses.get("tire_wear", 0.0))
    stats["fuel_efficiency"]  = stats.get("fuel_efficiency", 1.0) * max(0.2, 1.0 - team_bonuses.get("fuel_efficiency", 0.0))
    stats["pit_time_bonus"]   = team_bonuses.get("pit_time", 0.0)

    return race_car, race_driver


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

    img = f1_images.get_card_image(card)
    if img:
        embed.set_image(url=img)

    embed.set_footer(text="Added to collection! Use /f1 equip to race with it.")
    return embed


def build_spawn_embed(card: Dict) -> discord.Embed:
    """Professional spawn embed — bold rarity color, large image, clean layout."""
    rarity = card["rarity"]
    color = card_module.RARITY_COLORS.get(rarity, 0x95A5A6)
    rarity_emoji = card_module.RARITY_EMOJIS.get(rarity, "")
    rarity_label = rarity.upper()

    if card["type"] == "driver":
        card_name = f"{card['name']} ({card.get('code', '')})"
        card_icon = "👤"
        team_line = card.get("team", "")
    elif card["type"] == "team_asset":
        card_name = card["name"]
        card_icon = "🏗️"
        team_line = card.get("team", "")
    else:
        card_name = card["name"]
        card_icon = "🏎️"
        team_line = card.get("team", "")

    embed = discord.Embed(
        title="🏁  A wild F1 card appeared!",
        description=(
            f"## {card_icon}  {card_name}\n"
            f"{rarity_emoji}  **{rarity_label}**" +
            (f"  ·  {team_line}" if team_line else "")
        ),
        color=color,
    )

    img = f1_images.get_card_image(card)
    if img:
        embed.set_image(url=img)

    embed.set_footer(text="Click Catch me! and type the exact name to claim this card  ·  Expires in 5 minutes")
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

    def card_embed(self, card: Dict, position: int) -> discord.Embed:
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
        img = f1_images.get_card_image(card)
        if img:
            embed.set_image(url=img)
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
            await interaction.response.edit_message(embed=self.summary_embed(), view=self)
            self.stop()
            return
        card = self.cards[self.index]
        self.index += 1
        self._refresh_button()
        await interaction.response.edit_message(embed=self.card_embed(card, self.index), view=self)


# ==================== RACE VISUAL HELPERS ====================

RACE_GIFS = [
    "https://media.giphy.com/media/3ohzdIuqJoo8QdKlnW/giphy.gif",
    "https://media.giphy.com/media/26gJAn0QqFWbqQUMw/giphy.gif",
    "https://media.giphy.com/media/l0MYyoYKBIRtjXJEQ/giphy.gif",
    "https://media.giphy.com/media/xT1Ra5h24Eliux3UVq/giphy.gif",
]

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

    # Lap progress bar
    laps_done = race.lap - 1
    lap_bar = "🟥" * laps_done + "⬜" * (race.total_laps - laps_done)
    turn_in_lap = ((race.turn - 1) % 4) + 1 if race.turn > 0 else 1
    turn_bar = "🟧" * turn_in_lap + "⬜" * (4 - turn_in_lap)

    title = f"🏎️  F1 Race  ·  Lap {race.lap}/{race.total_laps}  ·  Turn {race.turn}/{race.max_turns}"

    weather_line = "🌧️  **WET CONDITIONS — Intermediates recommended!**\n\n" if race.weather == "rain" else ""
    commentary_block = commentary_engine.format_commentary(commentary_log[-3:]) if commentary_log else "> *Race underway…*"
    desc = f"{weather_line}{commentary_block}"

    embed = discord.Embed(title=title, description=desc, color=0xE74C3C)
    embed.set_image(url=gif_url)

    # Race progress
    embed.add_field(
        name="📊  Race Progress",
        value=f"**Laps:** {lap_bar}  `{race.lap}/{race.total_laps}`\n**Turn:** {turn_bar}  `{turn_in_lap}/4`",
        inline=False,
    )

    # Gap
    gap = race.gap
    if abs(gap) < 0.3:
        gap_str = "**⚡ SIDE BY SIDE — WHEEL TO WHEEL!**"
    elif gap < 0:
        gap_str = f"🏎️ **{p1_user.display_name}** leads by **{abs(gap):.2f}s**"
    else:
        gap_str = f"🏎️ **{p2_user.display_name}** leads by **{abs(gap):.2f}s**"

    embed.add_field(name=f"{weather_icon}  Live Gap", value=gap_str, inline=False)

    # Player 1 status
    p1_val = (
        f"👤 **{race.p1_driver.name}** `{race.p1_driver.code}`\n"
        f"🏎️ {race.p1_car.name}\n\n"
        f"⛽ {_fuel_str(race.p1_fuel)}\n"
        f"🔧 {_tire_str(race.p1_tire_wear, race.p1_tire_type)}\n"
        f"🔩 Pit stops: **{race.p1_pit_stops}**"
    )
    embed.add_field(name=f"{p1_pos_icon}  {p1_user.display_name}", value=p1_val, inline=True)

    # Player 2 status
    p2_val = (
        f"👤 **{race.p2_driver.name}** `{race.p2_driver.code}`\n"
        f"🏎️ {race.p2_car.name}\n\n"
        f"⛽ {_fuel_str(race.p2_fuel)}\n"
        f"🔧 {_tire_str(race.p2_tire_wear, race.p2_tire_type)}\n"
        f"🔩 Pit stops: **{race.p2_pit_stops}**"
    )
    embed.add_field(name=f"{p2_pos_icon}  {p2_user.display_name}", value=p2_val, inline=True)

    if next_scenario_turn and race.turn < next_scenario_turn:
        turns_away = next_scenario_turn - race.turn
        embed.set_footer(text=f"⚡ Auto-simulation  ·  Next decision point in {turns_away} turn{'s' if turns_away != 1 else ''}")
    else:
        embed.set_footer(text="⚡ Auto-simulation — strategic decision incoming!")
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


# ==================== BOT EVENTS ====================

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
        print("🃏 Wild card spawn loop started (30 min interval)")


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
            db.ensure_player(player_id, interaction.user.name)
            give_starter_cards(player_id, interaction.user.name)
            db.add_card_to_player(player_id, self.card, self.card["type"])

            rarity_label = self.card["rarity"].upper()
            display = (
                f"{self.card['name']} ({self.card['code']})"
                if self.card["type"] == "driver"
                else self.card["name"]
            )
            await interaction.response.edit_message(view=self.spawn_view)
            await interaction.followup.send(
                f"{interaction.user.mention} caught **{display}**!  ·  {rarity_label}\n"
                f"Added to your collection. Use `/f1 equip` to race with it."
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
                rarity = self.card["rarity"]
                rarity_emoji = card_module.RARITY_EMOJIS.get(rarity, "")
                color = card_module.RARITY_COLORS.get(rarity, 0x95A5A6)
                name = self.card["name"]
                expired_embed = discord.Embed(
                    title="⏰  This card has fled!",
                    description=(
                        f"~~**{name}**~~\n"
                        f"{rarity_emoji}  **{rarity.upper()}**\n\n"
                        f"*Nobody caught it in time.*"
                    ),
                    color=0x5C5C5C,
                )
                img = f1_images.get_card_image(self.card)
                if img:
                    expired_embed.set_image(url=img)
                expired_embed.set_footer(text="Better luck next time!")
                await self.message.edit(embed=expired_embed, view=self)
            except Exception:
                pass


@tasks.loop(minutes=30)
async def spawn_wild_card():
    """Spawn a wild card in all configured channels across all guilds."""
    for guild in bot.guilds:
        channel_ids = db.get_spawn_channels(str(guild.id))
        if not channel_ids:
            continue
        channel_id = random.choice(channel_ids)
        channel = guild.get_channel(int(channel_id))
        if not channel:
            continue
        try:
            card = card_module.generate_spawn_card()
            embed = build_spawn_embed(card)
            view = SpawnView(card)
            msg = await channel.send(embed=embed, view=view)
            view.message = msg
            print(f"🃏 Spawned {card['rarity']} {card['name']} in #{channel.name} ({guild.name})")
        except Exception as e:
            print(f"⚠️ Failed to spawn card in guild {guild.id}: {e}")


@spawn_wild_card.before_loop
async def before_spawn():
    await bot.wait_until_ready()


# ==================== CONFIG COMMANDS ====================

def _is_admin(interaction: discord.Interaction) -> bool:
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


@f1_group.command(name="profile", description="View your F1 racing profile and stats")
async def f1_profile(interaction: discord.Interaction):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    player = db.get_player(player_id)
    stats = player["stats"]
    equipped = db.get_equipped(player_id)
    cards = db.get_player_cards(player_id)

    equipped_driver = db.get_card_by_id(player_id, equipped["driver_id"]) if equipped.get("driver_id") else None
    equipped_car = db.get_card_by_id(player_id, equipped["car_id"]) if equipped.get("car_id") else None

    rank_colors = {
        "Diamond": 0x00FFFF,
        "Platinum": 0xE5E4E2,
        "Gold": 0xFFD700,
        "Silver": 0xC0C0C0,
        "Bronze": 0xCD7F32,
    }

    rank_emojis = {
        "Diamond": "💎",
        "Platinum": "🪙",
        "Gold": "🏆",
        "Silver": "🥈",
        "Bronze": "🥉",
    }

    rank = stats.get("rank", "Bronze")
    embed = discord.Embed(
        title=f"🏁 {interaction.user.display_name}'s Profile",
        color=rank_colors.get(rank, 0xCD7F32),
    )

    embed.add_field(
        name=f"{rank_emojis.get(rank, '')} Rank",
        value=f"**{rank}** — {stats['ranking_points']} pts",
        inline=True,
    )
    embed.add_field(name="💰 Race Credits", value=f"**{player.get('coins', 0)}** 💰", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.add_field(
        name="📊 Race Stats",
        value=(
            f"🏆 Wins: **{stats['wins']}**\n"
            f"❌ Losses: **{stats['losses']}**\n"
            f"🔥 Win Rate: **{stats['win_rate']:.0%}**\n"
            f"🏎️ Total Races: **{stats['total_races']}**"
        ),
        inline=True,
    )

    d_emoji = card_module.RARITY_EMOJIS.get(equipped_driver["rarity"], "") if equipped_driver else ""
    c_emoji = card_module.RARITY_EMOJIS.get(equipped_car["rarity"], "") if equipped_car else ""

    embed.add_field(
        name="⚙️ Active Loadout",
        value=(
            f"👤 {d_emoji} {equipped_driver['name']} ({equipped_driver['code']})\n"
            if equipped_driver else "👤 *No driver equipped*\n"
        ) + (
            f"🏎️ {c_emoji} {equipped_car['name']}"
            if equipped_car else "🏎️ *No car equipped*"
        ),
        inline=True,
    )

    total_cards = len(cards["drivers"]) + len(cards["cars"])
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name="🎴 Collection",
        value=f"**{total_cards}** cards\n({len(cards['drivers'])} drivers, {len(cards['cars'])} cars)",
        inline=False,
    )

    # Pack cooldowns
    can_daily, daily_rem = db.can_claim_daily(player_id)
    can_weekly, weekly_rem = db.can_claim_weekly(player_id)
    daily_status = "✅ Ready!" if can_daily else f"⏳ {format_cooldown(daily_rem)}"
    weekly_status = "✅ Ready!" if can_weekly else f"⏳ {format_cooldown(weekly_rem)}"
    embed.add_field(
        name="📦 Pack Status",
        value=f"🗓️ Daily Pack: {daily_status}\n🏆 Weekly Pack: {weekly_status}",
        inline=False,
    )

    embed.set_footer(text="Use /f1 collection to browse cards | /f1 equip to change loadout")
    await interaction.response.send_message(embed=embed)


@f1_group.command(name="collection", description="Browse your full card collection")
@app_commands.describe(filter="Filter cards by type")
@app_commands.choices(filter=[
    app_commands.Choice(name="All Cards", value="all"),
    app_commands.Choice(name="Drivers Only", value="driver"),
    app_commands.Choice(name="Cars Only", value="car"),
])
async def f1_collection(interaction: discord.Interaction, filter: str = "all"):
    player_id = str(interaction.user.id)
    db.ensure_player(player_id, interaction.user.name)
    give_starter_cards(player_id, interaction.user.name)

    all_cards = db.get_all_cards_sorted(player_id)
    if filter == "driver":
        filtered = [c for c in all_cards if c["type"] == "driver"]
    elif filter == "car":
        filtered = [c for c in all_cards if c["type"] == "car"]
    else:
        filtered = all_cards

    if not filtered:
        embed = discord.Embed(
            title="🎴 Your Collection",
            description="You have no cards yet! Open packs with `/pack daily` or `/pack weekly`.",
            color=0x95A5A6,
        )
        await interaction.response.send_message(embed=embed)
        return

    view = CollectionView(player_id, filtered, interaction.user.display_name)
    embed = view.build_embed()
    await interaction.response.send_message(embed=embed, view=view)


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
        db.spend_coins(self.player_id, cost)
        new_balance = db.get_coins(self.player_id)
        pack_cards = card_module.generate_pack(pack_key)
        open_view = PackOpeningView(self.player_id, pack_cards, interaction.user, pack_key)
        await interaction.response.edit_message(
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
        # Sort: common first (most likely to sell), then by rarity ascending
        RARITY_ORDER = {"common": 0, "rare": 1, "epic": 2, "legendary": 3}
        self.all_cards = sorted(all_cards, key=lambda c: RARITY_ORDER.get(c["rarity"], 0))
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
        equipped = db.get_equipped(self.player_id)
        eq_ids = {equipped.get("driver_id"), equipped.get("car_id")} | set(equipped.get("team_assets", []))
        equipped_selected = [c for c in self.all_cards if c["id"] in self.selected_ids and c["id"] in eq_ids]
        if equipped_selected:
            embed.add_field(
                name="⚠️ Warning",
                value=f"**{len(equipped_selected)}** selected card(s) are currently equipped — selling them will unequip.",
                inline=False,
            )
        embed.set_footer(text=f"{len(self.all_cards)} cards total · Page {self.page+1}/{self.total_pages}")
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
        for rarity in ("legendary", "epic", "rare", "common"):
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
                sv = ScenarioView(p1_user, p2_user, scenario, race, message, gif_url)
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

            if turn_num < race.max_turns:
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
    player_id  = str(interaction.user.id)
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

    race, race_id = race_engine.create_race(player_id, opponent_id, p1_car, p1_driver, p2_car, p2_driver)
    active_race_pairs[player_id]  = race_id
    active_race_pairs[opponent_id] = race_id

    gif_url = random.choice(RACE_GIFS)
    challenge_embed = build_challenge_embed(
        interaction.user, opponent,
        p1_car, p1_driver, p2_car, p2_driver,
        gif_url, synergy1, synergy2,
    )
    challenge_view = ChallengeView(interaction.user, opponent, race, gif_url)
    await interaction.response.send_message(embed=challenge_embed, view=challenge_view)


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

            embed = discord.Embed(
                title=f"✅ {self.card_type.title()} Equipped!",
                description=f"{icon} {emoji} **{display_name}** is now your active {self.card_type}!",
                color=0x2ECC71,
            )
            embed.add_field(name="Stats", value=stats, inline=False)
            embed.add_field(name="Rarity", value=f"{emoji} {card['rarity'].title()}", inline=True)
            if card.get("perks"):
                embed.add_field(name="✨ Perk", value=card["perks"][0].replace("_", " ").title(), inline=True)
            img = f1_images.get_card_image(card)
            if img:
                embed.set_image(url=img)
            embed.set_footer(text="Your equipped card will be used in your next !race")
        else:
            embed = discord.Embed(title="❌ Error", description="Could not equip that card.", color=0xE74C3C)

        await interaction.response.edit_message(embed=embed, view=None)

    async def _on_quit(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Menu closed.", embed=None, view=None)


class CollectionView(discord.ui.View):
    def __init__(self, player_id: str, cards: List[Dict], display_name: str, per_page: int = 8):
        super().__init__(timeout=120)
        self.player_id = player_id
        self.cards = cards
        self.display_name = display_name
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(cards) + per_page - 1) // per_page)
        self._rebuild()

    def _get_page_cards(self) -> List[Dict]:
        start = self.page * self.per_page
        return self.cards[start:start + self.per_page]

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
                    desc = f"{card['rarity'].title()} | Skill: {card['skill']}/10"
                else:
                    label = f"{emoji} {card['name']}"
                    desc = f"{card['rarity'].title()} | {card['top_speed']}km/h"
                obtained = card.get("obtained_at", "")
                if obtained:
                    try:
                        dt = datetime.fromisoformat(obtained)
                        desc += f" | {dt.strftime('%Y/%m/%d')}"
                    except Exception:
                        pass
                options.append(discord.SelectOption(label=label[:100], description=desc[:100], value=card["id"]))

            select = discord.ui.Select(placeholder="Select a card to view details...", options=options, row=1)
            select.callback = self._on_select
            self.add_item(select)

        quit_btn = discord.ui.Button(label="✖ Close", style=discord.ButtonStyle.danger, row=2)
        quit_btn.callback = self._on_quit
        self.add_item(quit_btn)

    def build_embed(self) -> discord.Embed:
        page_cards = self._get_page_cards()
        equipped = db.get_equipped(self.player_id)
        embed = discord.Embed(
            title=f"{self.display_name}'s Collection",
            description=f"{len(self.cards)} cards  ·  Page {self.page + 1} of {self.total_pages}",
            color=0x2C3E50,
        )
        for card in page_cards:
            rarity = card["rarity"].title()
            is_equipped = card["id"] in (equipped.get("driver_id"), equipped.get("car_id"))
            eq = "  [Equipped]" if is_equipped else ""

            if card["type"] == "driver":
                field_name = f"{card['name']} ({card['code']}){eq}"
                field_val = f"{card['team']}  ·  Skill {card['skill']}/10  ·  {rarity}"
            else:
                field_name = f"{card['name']}{eq}"
                field_val = f"{card['team']}  ·  {card['top_speed']} km/h  ·  {rarity}"

            if card.get("perks"):
                perk_name = card["perks"][0].replace("_", " ").title()
                field_val += f"  ·  {perk_name}"

            embed.add_field(name=field_name, value=field_val, inline=False)

        embed.set_footer(text="[Equipped] = active card  ·  /f1 equip to change loadout")
        return embed

    async def _check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your collection!", ephemeral=True)
            return False
        return True

    async def _go_first(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = 0
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _go_prev(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = max(0, self.page - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = min(self.total_pages - 1, self.page + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _go_last(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        self.page = self.total_pages - 1
        self._rebuild()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_select(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        card_id = interaction.data["values"][0]
        card = db.get_card_by_id(self.player_id, card_id)
        if not card:
            await interaction.response.send_message("Card not found.", ephemeral=True)
            return

        color = card_module.RARITY_COLORS.get(card["rarity"], 0x95A5A6)
        equipped = db.get_equipped(self.player_id)
        is_equipped = card["id"] in (equipped.get("driver_id"), equipped.get("car_id"))

        if card["type"] == "driver":
            title = f"{card['name']} ({card['code']})"
            stats = f"{card['team']}  ·  Skill {card['skill']}/10  ·  {card['rarity'].title()}"
        else:
            title = card["name"]
            stats = f"{card['team']}  ·  {card['top_speed']} km/h  ·  Handling {card.get('handling', '?')}/10  ·  {card['rarity'].title()}"

        if is_equipped:
            stats += "  ·  Equipped"

        if card.get("perks"):
            perk_key = card["perks"][0]
            perk_data = card_module.PERKS.get(perk_key, {})
            stats += f"\n{perk_data.get('name', perk_key)} — {perk_data.get('description', '')}"

        detail = discord.Embed(title=title, description=stats, color=color)

        img = f1_images.get_card_image(card)
        if img:
            detail.set_image(url=img)

        await interaction.response.send_message(embed=detail)

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
    embed.add_field(name="🏗️ Team Staff",   value="\n".join(ta_lines),   inline=True)
    embed.add_field(name="💰 Race Credits", value=f"**{coins:,}** coins", inline=False)
    embed.set_footer(text="/f1 equip · /upgrade · /team to change loadout")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="profile", description="View your F1 racing profile and full stats")
@app_commands.describe(member="Player to view (leave blank for yourself)")
async def profile_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    target   = member or interaction.user
    player_id = str(target.id)
    db.ensure_player(player_id, target.name)

    player   = db.get_player(player_id)
    stats    = player.get("stats", {})
    coins    = db.get_coins(player_id)
    cards    = db.get_player_cards(player_id)
    upgrades = db.get_upgrades(player_id)
    equipped = db.get_equipped(player_id)

    wins     = stats.get("wins", 0)
    losses   = stats.get("losses", 0)
    dnf      = stats.get("dnf", 0)
    total    = stats.get("total_races", 0)
    win_rate = (wins / total * 100) if total > 0 else 0.0
    rank     = stats.get("rank", "Bronze")
    rp       = stats.get("ranking_points", 0)

    RANK_EMOJIS = {"Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Platinum": "💎", "Diamond": "💠"}
    rank_emoji = RANK_EMOJIS.get(rank, "🏁")

    # Collection counts
    n_drivers = len(cards.get("drivers", []))
    n_cars    = len(cards.get("cars", []))
    n_team    = len(cards.get("team_assets", []))

    # Equipped loadout quick view
    driver_name = "None"
    car_name    = "None"
    if equipped.get("driver_id"):
        d = db.get_card_by_id(player_id, equipped["driver_id"])
        if d:
            driver_name = f"{d['name']} ({d['code']})"
    if equipped.get("car_id"):
        c = db.get_card_by_id(player_id, equipped["car_id"])
        if c:
            car_name = c["name"]

    # Total upgrade levels
    total_upgrades = sum(upgrades.get(s, 0) for s in UPGRADE_STATS)
    upgrade_str = " · ".join(
        f"{UPGRADE_INFO[s]['emoji']}Lv.{upgrades.get(s,0)}" for s in UPGRADE_STATS
    )

    created = player.get("created_at", "")
    try:
        joined = datetime.fromisoformat(created).strftime("%b %d %Y")
    except Exception:
        joined = "Unknown"

    embed = discord.Embed(
        title=f"{rank_emoji}  {target.display_name}",
        description=f"*F1 Card Racing Profile*",
        color=0x1ABC9C,
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    embed.add_field(
        name="🏆 Race Record",
        value=(
            f"🥇 Wins: **{wins}**  ·  🥈 Losses: **{losses}**  ·  ⚠️ DNF: **{dnf}**\n"
            f"📊 Total Races: **{total}**  ·  Win Rate: **{win_rate:.1f}%**"
        ),
        inline=False,
    )
    embed.add_field(name=f"{rank_emoji} Rank", value=f"**{rank}**  ·  {rp} RP", inline=True)
    embed.add_field(name="💰 Coins",           value=f"**{coins:,}**",              inline=True)

    embed.add_field(
        name="🎴 Collection",
        value=(
            f"👤 Drivers: **{n_drivers}**  ·  🏎️ Cars: **{n_cars}**  ·  🏗️ Staff: **{n_team}**\n"
            f"Total: **{n_drivers + n_cars + n_team}** cards"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏎️ Equipped",
        value=f"👤 {driver_name}\n🏎️ {car_name}",
        inline=True,
    )
    embed.add_field(
        name=f"🔧 Upgrades ({total_upgrades}/{UPGRADE_MAX_LEVEL * len(UPGRADE_STATS)})",
        value=upgrade_str,
        inline=False,
    )
    embed.set_footer(text=f"Joined: {joined}  ·  Use /garage for full loadout")
    await interaction.response.send_message(embed=embed)


# ==================== MAIN ====================

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable not set!")
        exit(1)
    bot.run(TOKEN)
