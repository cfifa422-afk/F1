import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, List
import random

from database import Database
import cards as card_module
import f1_images

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
    """Return (Car, Driver) objects to use in a race based on equipped + fallback."""
    equipped = db.get_equipped(player_id)
    cards = db.get_player_cards(player_id)

    # Car
    car_data = None
    if equipped.get("car_id"):
        car_data = db.get_card_by_id(player_id, equipped["car_id"])
    if not car_data and cards["cars"]:
        car_data = cards["cars"][0]

    # Driver
    driver_data = None
    if equipped.get("driver_id"):
        driver_data = db.get_card_by_id(player_id, equipped["driver_id"])
    if not driver_data and cards["drivers"]:
        driver_data = cards["drivers"][0]

    race_car = card_to_car(car_data) if car_data else Car("default", "Unknown Car", "Unknown", 350, "common")
    race_driver = card_to_driver(driver_data) if driver_data else Driver("default", "Unknown Driver", "UNK", 5.0, "common")
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
    """Build the wild-spawn embed shown in the channel."""
    emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
    color = card_module.RARITY_COLORS.get(card["rarity"], 0x95A5A6)
    rarity_label = card["rarity"].upper()

    if card["type"] == "driver":
        name_str = f"{card['name']} ({card['code']})"
        stats = f"🏁 {card['team']}  |  ⭐ Skill {card['skill']}/10"
    else:
        name_str = card["name"]
        stats = f"🏁 {card['team']}  |  💨 {card['top_speed']} km/h"

    embed = discord.Embed(
        title=f"🏎️ A wild F1 card appeared!",
        description=f"{emoji} **{name_str}**\n{rarity_label}\n{stats}",
        color=color,
    )

    if card.get("perks"):
        perk_key = card["perks"][0]
        perk_data = card_module.PERKS.get(perk_key, {})
        embed.add_field(name="✨ Perk", value=perk_data.get("name", perk_key), inline=True)

    img = f1_images.get_card_image(card)
    if img:
        embed.set_image(url=img)

    embed.set_footer(text="Click 'Catch me!' to add this card to your collection!")
    return embed


def create_race_embed(race: RaceState, title: str) -> discord.Embed:
    embed = discord.Embed(title=f"🏎️ {title}", description=race.get_lap_info(), color=discord.Color.blue())
    p1_pos = "🥇 P1" if race.p1_position == 1 else "🥈 P2"
    p2_pos = "🥇 P1" if race.p2_position == 1 else "🥈 P2"
    embed.add_field(name="Positions", value=f"{p1_pos} | Gap: {abs(race.gap):.1f}s | {p2_pos}", inline=False)
    embed.add_field(
        name="Player 1",
        value=f"{race.p1_driver.name} ({race.p1_driver.code}) in {race.p1_car.name}\nFuel: {race.p1_fuel:.0f}% | Tires: {race.p1_tire_type.upper()} ({race.p1_tire_wear:.0f}%)",
        inline=True,
    )
    embed.add_field(
        name="Player 2",
        value=f"{race.p2_driver.name} ({race.p2_driver.code}) in {race.p2_car.name}\nFuel: {race.p2_fuel:.0f}% | Tires: {race.p2_tire_type.upper()} ({race.p2_tire_wear:.0f}%)",
        inline=True,
    )
    if race.events_log:
        embed.add_field(name="📡 Events", value="\n".join(race.events_log[-3:]), inline=False)
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

class SpawnView(discord.ui.View):
    """One-click catch button for wild spawns."""

    def __init__(self, card: Dict):
        super().__init__(timeout=1800)
        self.card = card
        self.caught = False

    @discord.ui.button(label="🏎️ Catch me!", style=discord.ButtonStyle.success)
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message(
                "❌ This card was already caught by someone else!", ephemeral=True
            )
            return

        self.caught = True
        button.disabled = True
        button.label = "✅ Caught!"
        button.style = discord.ButtonStyle.secondary

        player_id = str(interaction.user.id)
        db.ensure_player(player_id, interaction.user.name)
        give_starter_cards(player_id, interaction.user.name)
        db.add_card_to_player(player_id, self.card, self.card["type"])

        emoji = card_module.RARITY_EMOJIS.get(self.card["rarity"], "")
        if self.card["type"] == "driver":
            name_str = f"{self.card['name']} ({self.card['code']})"
        else:
            name_str = self.card["name"]

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"🎉 {interaction.user.mention} caught **{name_str}**!\n"
            f"Rarity: {emoji} **{self.card['rarity'].title()}**\n"
            f"Added to your collection! Use `/f1 equip` to race with it."
        )
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


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
            await channel.send(embed=embed, view=view)
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
    card = pack_cards[0]
    db.add_card_to_player(player_id, card, card["type"])
    db.mark_daily_claimed(player_id)

    embed = build_pack_embed(card, "daily", interaction.user, player_id)
    await interaction.followup.send(embed=embed)


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
    card = pack_cards[0]
    db.add_card_to_player(player_id, card, card["type"])
    db.mark_weekly_claimed(player_id)

    embed = build_pack_embed(card, "weekly", interaction.user, player_id)
    await interaction.followup.send(embed=embed)


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


# ==================== REGISTER COMMAND GROUPS ====================

bot.tree.add_command(pack_group)
bot.tree.add_command(f1_group)
bot.tree.add_command(config_group)


# ==================== PREFIX RACE COMMANDS ====================

@bot.command(name="race")
async def start_race(ctx, opponent: discord.Member):
    """Start a 1v1 race: !race @opponent"""
    player_id = str(ctx.author.id)
    opponent_id = str(opponent.id)

    if player_id == opponent_id:
        await ctx.send("❌ You can't race yourself!")
        return

    if player_id in active_race_pairs or opponent_id in active_race_pairs:
        await ctx.send("❌ One of you is already in a race!")
        return

    db.ensure_player(player_id, ctx.author.name)
    db.ensure_player(opponent_id, opponent.name)
    give_starter_cards(player_id, ctx.author.name)
    give_starter_cards(opponent_id, opponent.name)

    p1_car, p1_driver = get_player_race_cards(player_id)
    p2_car, p2_driver = get_player_race_cards(opponent_id)

    synergy1 = card_module.check_synergy(p1_driver.code, p1_car.team)
    synergy2 = card_module.check_synergy(p2_driver.code, p2_car.team)

    race, race_id = race_engine.create_race(player_id, opponent_id, p1_car, p1_driver, p2_car, p2_driver)
    active_race_pairs[player_id] = race_id
    active_race_pairs[opponent_id] = race_id

    d1_emoji = card_module.RARITY_EMOJIS.get(p1_driver.rarity, "")
    c1_emoji = card_module.RARITY_EMOJIS.get(p1_car.rarity, "")
    d2_emoji = card_module.RARITY_EMOJIS.get(p2_driver.rarity, "")
    c2_emoji = card_module.RARITY_EMOJIS.get(p2_car.rarity, "")

    embed = discord.Embed(title="🏁 Race Starting!", description=f"{ctx.author.mention} vs {opponent.mention}", color=discord.Color.green())
    p1_val = f"{d1_emoji} {p1_driver.name} ({p1_driver.code})\n{c1_emoji} {p1_car.name} — {p1_car.top_speed}km/h"
    p2_val = f"{d2_emoji} {p2_driver.name} ({p2_driver.code})\n{c2_emoji} {p2_car.name} — {p2_car.top_speed}km/h"
    if synergy1:
        p1_val += f"\n✨ *{synergy1['name']}* bonus!"
    if synergy2:
        p2_val += f"\n✨ *{synergy2['name']}* bonus!"
    embed.add_field(name=f"Player 1 — {ctx.author.display_name}", value=p1_val, inline=True)
    embed.add_field(name=f"Player 2 — {opponent.display_name}", value=p2_val, inline=True)
    embed.add_field(name="📬 Status", value="Check your DMs for race controls!", inline=False)
    await ctx.send(embed=embed)

    asyncio.create_task(run_race(race, ctx.author, opponent, race_id))


async def run_race(race: RaceState, p1_user: discord.Member, p2_user: discord.Member, race_id: str):
    """Main race loop."""
    try:
        while race.lap <= race.total_laps and race.turn < race.max_turns:
            race.p1_choice = None
            race.p2_choice = None

            embed = create_race_embed(race, f"Turn {race.turn + 1}")
            p1_view = RaceChoiceView(race, "p1")
            p2_view = RaceChoiceView(race, "p2")

            try:
                p1_dm = await p1_user.create_dm()
                p2_dm = await p2_user.create_dm()
                await p1_dm.send(embed=embed, view=p1_view)
                await p2_dm.send(embed=embed, view=p2_view)
            except discord.Forbidden:
                pass

            await asyncio.sleep(30)

            p1_choice = race.p1_choice or "same_speed"
            p2_choice = race.p2_choice or "same_speed"

            result = race_engine.process_turn(race, p1_choice, p2_choice)

            if result.get("race_finished") or result.get("dnf"):
                await end_race(race, p1_user, p2_user, race_id, result)
                return

        await end_race(race, p1_user, p2_user, race_id, {"race_finished": True})
    except Exception as e:
        print(f"Race error: {e}")
        active_race_pairs.pop(race.player1_id, None)
        active_race_pairs.pop(race.player2_id, None)


async def end_race(race: RaceState, p1_user: discord.Member, p2_user: discord.Member, race_id: str, result: Dict):
    """Handle race end, award coins, update stats."""
    active_race_pairs.pop(race.player1_id, None)
    active_race_pairs.pop(race.player2_id, None)

    if result.get("dnf"):
        dnf_side = result["dnf"]
        dnf_id = race.player1_id if dnf_side == "p1" else race.player2_id
        winner_id = race.player2_id if dnf_side == "p1" else race.player1_id
        winner_user = p2_user if dnf_side == "p1" else p1_user
        reason = result.get("reason", "unknown").replace("_", " ").title()

        embed = discord.Embed(title="❌ Race DNF!", color=discord.Color.red())
        dnf_user = p1_user if dnf_side == "p1" else p2_user
        embed.add_field(name="DNF", value=f"{dnf_user.mention} — {reason}", inline=False)
        embed.add_field(name="🏆 Winner", value=winner_user.mention, inline=False)

        winner_coins = db.add_coins(winner_id, 100)
        loser_coins = db.add_coins(dnf_id, 10)
        embed.add_field(name="💰 Rewards", value=f"🏆 Winner: **+100** credits ({winner_coins} total)\nDNF: **+10** credits ({loser_coins} total)", inline=False)

        db.update_player_stats(winner_id, {"status": "win"})
        db.update_player_stats(dnf_id, {"status": "dnf"})
    else:
        winner_pos_1 = race.p1_position == 1
        winner_id = race.player1_id if winner_pos_1 else race.player2_id
        loser_id = race.player2_id if winner_pos_1 else race.player1_id
        winner_user = p1_user if winner_pos_1 else p2_user
        loser_user = p2_user if winner_pos_1 else p1_user

        embed = discord.Embed(title="🏁 Race Finished!", color=discord.Color.gold())
        embed.add_field(name="🥇 Winner", value=winner_user.mention, inline=True)
        embed.add_field(name="🥈 Runner-up", value=loser_user.mention, inline=True)
        embed.add_field(name="Gap", value=f"{abs(race.gap):.2f}s", inline=False)
        embed.add_field(name="Pit Stops", value=f"P1: {race.p1_pit_stops} | P2: {race.p2_pit_stops}", inline=False)

        winner_coins = db.add_coins(winner_id, 100)
        loser_coins = db.add_coins(loser_id, 25)
        embed.add_field(name="💰 Race Credits", value=f"🏆 Winner: **+100** credits ({winner_coins} total)\n🥈 Runner-up: **+25** credits ({loser_coins} total)", inline=False)

        db.update_player_stats(winner_id, {"status": "win"})
        db.update_player_stats(loser_id, {"status": "loss"})

    try:
        p1_dm = await p1_user.create_dm()
        p2_dm = await p2_user.create_dm()
        await p1_dm.send(embed=embed)
        await p2_dm.send(embed=embed)
    except discord.Forbidden:
        pass


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

class RaceChoiceView(discord.ui.View):
    def __init__(self, race: RaceState, player: str):
        super().__init__(timeout=30)
        self.race = race
        self.player = player

    @discord.ui.button(label="🛑 Slow Down", style=discord.ButtonStyle.danger)
    async def slow_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "slow_down"
        else:
            self.race.p2_choice = "slow_down"
        await interaction.response.send_message("✅ Slowing down...", ephemeral=True)
        self.stop()

    @discord.ui.button(label="➡️ Same Speed", style=discord.ButtonStyle.secondary)
    async def same_speed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "same_speed"
        else:
            self.race.p2_choice = "same_speed"
        await interaction.response.send_message("✅ Maintaining pace...", ephemeral=True)
        self.stop()

    @discord.ui.button(label="🚀 Accelerate", style=discord.ButtonStyle.success)
    async def accelerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "accelerate"
        else:
            self.race.p2_choice = "accelerate"
        await interaction.response.send_message("✅ Flooring it!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="⛽ Pit Stop", style=discord.ButtonStyle.primary)
    async def pit_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "pit_stop"
        else:
            self.race.p2_choice = "pit_stop"
        await interaction.response.send_message("✅ Pitting in!", ephemeral=True)
        self.stop()


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
            title=f"🎴 {self.display_name}'s Collection",
            description=f"**{len(self.cards)}** cards total — Page **{self.page + 1}/{self.total_pages}**",
            color=0x2C3E50,
        )
        for card in page_cards:
            emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
            is_equipped = card["id"] in (equipped.get("driver_id"), equipped.get("car_id"))
            equipped_tag = " ⚙️" if is_equipped else ""

            if card["type"] == "driver":
                field_name = f"{emoji} {card['name']} ({card['code']}){equipped_tag}"
                field_val = f"🏎️ {card['team']} | Skill: **{card['skill']}/10** | {card['rarity'].title()}"
            else:
                field_name = f"{emoji} {card['name']}{equipped_tag}"
                field_val = f"🏎️ {card['team']} | **{card['top_speed']}km/h** | {card['rarity'].title()}"

            obtained = card.get("obtained_at", "")
            if obtained:
                try:
                    dt = datetime.fromisoformat(obtained)
                    field_val += f"\n📅 {dt.strftime('%Y/%m/%d')}"
                except Exception:
                    pass

            if card.get("perks"):
                field_val += f"\n✨ *{card['perks'][0].replace('_', ' ').title()}*"

            embed.add_field(name=field_name, value=field_val, inline=True)

        embed.set_footer(text="⚙️ = Equipped | Use /f1 equip to change loadout")
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

        emoji = card_module.RARITY_EMOJIS.get(card["rarity"], "")
        rarity_colors = card_module.RARITY_COLORS
        detail = discord.Embed(
            title=f"{emoji} {card['name']}",
            color=rarity_colors.get(card["rarity"], 0x95A5A6),
        )
        detail.add_field(name="Rarity", value=f"{emoji} {card['rarity'].title()}", inline=True)
        detail.add_field(name="Type", value=card["type"].title(), inline=True)

        if card["type"] == "driver":
            detail.add_field(name="Code", value=card["code"], inline=True)
            detail.add_field(name="Team", value=card["team"], inline=True)
            detail.add_field(name="Skill", value=f"{card['skill']}/10", inline=True)
        else:
            detail.add_field(name="Team", value=card["team"], inline=True)
            detail.add_field(name="Top Speed", value=f"{card['top_speed']}km/h", inline=True)
            detail.add_field(name="Handling", value=f"{card.get('handling', '?')}/10", inline=True)

        if card.get("perks"):
            perk_key = card["perks"][0]
            perk_data = card_module.PERKS.get(perk_key, {})
            detail.add_field(name="✨ Perk", value=f"**{perk_data.get('name', perk_key)}**\n*{perk_data.get('description', '')}*", inline=False)

        obtained = card.get("obtained_at", "")
        if obtained:
            try:
                dt = datetime.fromisoformat(obtained)
                detail.add_field(name="📅 Obtained", value=dt.strftime("%B %d, %Y"), inline=True)
            except Exception:
                pass

        equipped = db.get_equipped(self.player_id)
        is_equipped = card["id"] in (equipped.get("driver_id"), equipped.get("car_id"))
        detail.add_field(name="Status", value="⚙️ **Currently Equipped**" if is_equipped else "Not equipped", inline=True)
        img = f1_images.get_card_image(card)
        if img:
            detail.set_image(url=img)
        detail.set_footer(text=f"ID: {card['id']}")

        await interaction.response.send_message(embed=detail, ephemeral=True)

    async def _on_quit(self, interaction: discord.Interaction):
        if not await self._check(interaction): return
        await interaction.response.edit_message(content="Collection closed.", embed=None, view=None)


# ==================== MAIN ====================

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable not set!")
        exit(1)
    bot.run(TOKEN)
