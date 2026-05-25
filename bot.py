import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict, List
import random

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
bot = commands.Bot(command_prefix="/", intents=intents)

# ==================== DATA MODELS ====================

class Car:
    def __init__(self, car_id: str, name: str, team: str, top_speed: int, rarity: str):
        self.car_id = car_id
        self.name = name
        self.team = team
        self.top_speed = top_speed
        self.rarity = rarity
        self.stats = self._calculate_stats()
    
    def _calculate_stats(self) -> Dict:
        """Calculate car stats based on top speed and rarity"""
        base_multiplier = self.top_speed / 350  # Normalize against 350km/h rare car
        
        rarity_bonus = {
            "legendary": 1.15,
            "epic": 1.10,
            "rare": 1.05,
            "common": 1.00
        }.get(self.rarity, 1.0)
        
        multiplier = base_multiplier * rarity_bonus
        
        return {
            "top_speed": self.top_speed,
            "acceleration": min(10, 7.5 * multiplier),
            "handling": min(10, 7.0 * multiplier),
            "tire_wear_rate": max(10, 20 - (self.top_speed / 350 * 5)),  # Lower is better
            "fuel_efficiency": max(2.0, 3.0 - (self.top_speed / 350 * 0.5)),  # Lower is better
            "rarity_multiplier": rarity_bonus
        }

class Driver:
    def __init__(self, driver_id: str, name: str, code: str, skill: float, rarity: str):
        self.driver_id = driver_id
        self.name = name
        self.code = code  # e.g., "HAM", "VER", "LEC"
        self.skill = skill  # 0-10 scale
        self.rarity = rarity
    
    def get_skill_bonus(self) -> float:
        """Skill bonus multiplier for decision making"""
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
    
    def get_car(self, car_id: str) -> Optional[Car]:
        return next((c for c in self.cars if c.car_id == car_id), None)
    
    def get_driver(self, driver_id: str) -> Optional[Driver]:
        return next((d for d in self.drivers if d.driver_id == driver_id), None)

class RaceState:
    def __init__(self, player1_id: str, player2_id: str, p1_car: Car, p1_driver: Driver, 
                 p2_car: Car, p2_driver: Driver):
        self.player1_id = player1_id
        self.player2_id = player2_id
        self.turn = 0
        self.lap = 1
        self.total_laps = 3
        self.max_turns = 12  # 4 turns per lap
        
        # Player 1 state
        self.p1_car = p1_car
        self.p1_driver = p1_driver
        self.p1_position = 1
        self.p1_fuel = 100.0
        self.p1_tire_wear = 0.0
        self.p1_tire_type = "soft"
        self.p1_pit_stops = 0
        self.p1_choice = None
        self.p1_choice_time = None
        
        # Player 2 state
        self.p2_car = p2_car
        self.p2_driver = p2_driver
        self.p2_position = 2
        self.p2_fuel = 100.0
        self.p2_tire_wear = 0.0
        self.p2_tire_type = "soft"
        self.p2_pit_stops = 0
        self.p2_choice = None
        self.p2_choice_time = None
        
        # Race events
        self.weather = "clear"
        self.weather_chance = random.random()
        self.gap = 0.0
        self.events_log = []
        self.choice_history = {"p1": [], "p2": []}
    
    def get_tire_stats(self, tire_type: str) -> Dict:
        """Get tire performance characteristics"""
        tire_stats = {
            "soft": {"speed_bonus": 1.05, "durability": 3, "wear_rate": 8},
            "medium": {"speed_bonus": 1.02, "durability": 6, "wear_rate": 5},
            "hard": {"speed_bonus": 1.0, "durability": 9, "wear_rate": 2},
            "wet": {"speed_bonus": 0.8, "durability": 7, "wear_rate": 3}  # 0.8 on dry, 1.15 in rain
        }
        return tire_stats.get(tire_type, tire_stats["soft"])
    
    def get_lap_info(self) -> str:
        """Get formatted lap/turn info"""
        return f"Lap {self.lap}/{self.total_laps} | Turn {self.turn}/{self.max_turns}"
    
    def get_gap(self) -> float:
        """Calculate gap between players"""
        if self.p1_position > self.p2_position:
            return -(abs(self.gap))  # Negative means p2 is leading
        return abs(self.gap)

# ==================== RACE ENGINE ====================

class RaceEngine:
    def __init__(self):
        self.active_races: Dict[str, RaceState] = {}
    
    def create_race(self, p1_id: str, p2_id: str, p1_car: Car, p1_driver: Driver,
                   p2_car: Car, p2_driver: Driver) -> RaceState:
        """Create a new race"""
        race_id = f"{p1_id}_{p2_id}_{int(datetime.now().timestamp())}"
        race = RaceState(p1_id, p2_id, p1_car, p1_driver, p2_car, p2_driver)
        self.active_races[race_id] = race
        return race, race_id
    
    def process_turn(self, race: RaceState, p1_choice: str, p2_choice: str) -> Dict:
        """Process a single race turn and return results"""
        race.turn += 1
        race.p1_choice = p1_choice
        race.p2_choice = p2_choice
        race.choice_history["p1"].append(p1_choice)
        race.choice_history["p2"].append(p2_choice)
        
        # Check for lap change
        if race.turn % 4 == 0 and race.turn > 0:
            race.lap += 1
            if race.lap > race.total_laps:
                return {"race_finished": True}
        
        # Random event generation
        event = self._generate_event(race)
        if event:
            race.events_log.append(event)
        
        # Process choices
        p1_time_gain = self._calculate_lap_time(race, "p1", p1_choice, event)
        p2_time_gain = self._calculate_lap_time(race, "p2", p2_choice, event)
        
        # Update fuel and tire wear
        self._update_consumables(race, "p1", p1_choice)
        self._update_consumables(race, "p2", p2_choice)
        
        # Handle pit stops
        if p1_choice == "pit_stop":
            race.p1_pit_stops += 1
            race.p1_fuel = 100.0
            race.p1_tire_wear = 0.0
            race.p1_tire_type = self._get_optimal_tire(race, "p1", event)
            p1_time_gain = -3.2  # Pit stop penalty
        
        if p2_choice == "pit_stop":
            race.p2_pit_stops += 1
            race.p2_fuel = 100.0
            race.p2_tire_wear = 0.0
            race.p2_tire_type = self._get_optimal_tire(race, "p2", event)
            p2_time_gain = -3.2
        
        # Update gap
        race.gap += (p2_time_gain - p1_time_gain)
        
        # Update positions
        if race.gap > 0.5:
            race.p1_position = 2
            race.p2_position = 1
        else:
            race.p1_position = 1
            race.p2_position = 2
        
        # Check for DNF (did not finish)
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
            "p1_time_gain": p1_time_gain,
            "p2_time_gain": p2_time_gain,
            "event": event,
            "gap": race.gap,
            "p1_position": race.p1_position,
            "p2_position": race.p2_position
        }
    
    def _generate_event(self, race: RaceState) -> Optional[str]:
        """Generate random race events"""
        rand = random.random()
        
        if rand < 0.05:
            race.weather = "rain"
            return "rain_incoming"
        elif rand < 0.10:
            return "drs_available"
        elif rand < 0.12:
            return "safety_car"
        
        return None
    
    def _calculate_lap_time(self, race: RaceState, player: str, choice: str, event: Optional[str]) -> float:
        """Calculate lap time gain/loss based on choice"""
        car = race.p1_car if player == "p1" else race.p2_car
        driver = race.p1_driver if player == "p1" else race.p2_driver
        tire_type = race.p1_tire_type if player == "p1" else race.p2_tire_type
        tire_wear = race.p1_tire_wear if player == "p1" else race.p2_tire_wear
        
        # Base speed from car
        base_speed = car.stats["acceleration"]
        
        # Tire wear penalty
        wear_penalty = (tire_wear / 100) * 2.0
        
        # Choice impact
        choice_impact = {
            "accelerate": 0.8,
            "same_speed": 0.0,
            "slow_down": -0.6,
            "pit_stop": -3.2
        }.get(choice, 0.0)
        
        # Tire type bonus/penalty
        tire_bonus = self.get_tire_stats(tire_type)["speed_bonus"]
        
        # Event modifiers
        event_modifier = 0.0
        if event == "drs_available" and choice == "accelerate":
            event_modifier = 0.5
        elif event == "rain_incoming" and tire_type == "wet":
            event_modifier = 0.3
        
        # Weather impact
        weather_impact = 0.0
        if race.weather == "rain":
            if tire_type == "wet":
                weather_impact = 0.4
            else:
                weather_impact = -1.0
        
        total_time = base_speed * tire_bonus + choice_impact + event_modifier + weather_impact - wear_penalty
        
        return total_time
    
    def _update_consumables(self, race: RaceState, player: str, choice: str):
        """Update fuel and tire wear"""
        fuel_burn = {
            "accelerate": 5.0,
            "same_speed": 3.0,
            "slow_down": 2.0,
            "pit_stop": 0.0
        }.get(choice, 3.0)
        
        car = race.p1_car if player == "p1" else race.p2_car
        fuel_efficiency = car.stats["fuel_efficiency"]
        
        if player == "p1":
            race.p1_fuel -= (fuel_burn * fuel_efficiency)
            if choice != "pit_stop":
                race.p1_tire_wear += {
                    "accelerate": 8.0,
                    "same_speed": 4.0,
                    "slow_down": 2.0
                }.get(choice, 4.0)
        else:
            race.p2_fuel -= (fuel_burn * fuel_efficiency)
            if choice != "pit_stop":
                race.p2_tire_wear += {
                    "accelerate": 8.0,
                    "same_speed": 4.0,
                    "slow_down": 2.0
                }.get(choice, 4.0)
    
    def _get_optimal_tire(self, race: RaceState, player: str, event: Optional[str]) -> str:
        """Determine optimal tire choice based on conditions"""
        if race.weather == "rain" or event == "rain_incoming":
            return "wet"
        elif race.lap >= 2:
            return "hard"
        return "soft"
    
    def get_tire_stats(self, tire_type: str) -> Dict:
        """Get tire performance stats"""
        tire_stats = {
            "soft": {"speed_bonus": 1.05, "durability": 3, "wear_rate": 8},
            "medium": {"speed_bonus": 1.02, "durability": 6, "wear_rate": 5},
            "hard": {"speed_bonus": 1.0, "durability": 9, "wear_rate": 2},
            "wet": {"speed_bonus": 0.8, "durability": 7, "wear_rate": 3}
        }
        return tire_stats.get(tire_type, tire_stats["soft"])

# ==================== GLOBAL INSTANCES ====================

race_engine = RaceEngine()
player_decks: Dict[str, PlayerDeck] = {}
active_race_dms: Dict[str, str] = {}  # Maps (p1_id, p2_id) to race_id

# ==================== BOT EVENTS ====================

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    print(f"🏁 F1 Card Racing Bot is ready!")

# ==================== HELPER FUNCTIONS ====================

def create_race_embed(race: RaceState, title: str) -> discord.Embed:
    """Create a formatted embed for race turn"""
    embed = discord.Embed(
        title=f"🏎️ {title}",
        description=race.get_lap_info(),
        color=discord.Color.blue()
    )
    
    # Positions
    if race.p1_position == 1:
        p1_pos = "🥇 P1"
        p2_pos = "🥈 P2"
    else:
        p1_pos = "🥈 P2"
        p2_pos = "🥇 P1"
    
    embed.add_field(
        name="Positions",
        value=f"{p1_pos} | Gap: {abs(race.gap):.1f}s | {p2_pos}",
        inline=False
    )
    
    # Cars & Drivers
    embed.add_field(
        name="Player 1",
        value=f"{race.p1_driver.name} ({race.p1_driver.code}) in {race.p1_car.name}\nFuel: {race.p1_fuel:.0f}% | Tires: {race.p1_tire_type.upper()} ({race.p1_tire_wear:.0f}%)",
        inline=True
    )
    
    embed.add_field(
        name="Player 2",
        value=f"{race.p2_driver.name} ({race.p2_driver.code}) in {race.p2_car.name}\nFuel: {race.p2_fuel:.0f}% | Tires: {race.p2_tire_type.upper()} ({race.p2_tire_wear:.0f}%)",
        inline=True
    )
    
    # Events
    if race.events_log:
        events_text = "\n".join(race.events_log[-3:])  # Last 3 events
        embed.add_field(name="🌧️ Events", value=events_text, inline=False)
    
    return embed

# ==================== COMMANDS ====================

@bot.command(name="race")
async def start_race(ctx, opponent: discord.User):
    """Start a 1v1 race: /race @opponent"""
    
    player_id = str(ctx.author.id)
    opponent_id = str(opponent.id)
    
    # Initialize decks if not exist
    if player_id not in player_decks:
        player_decks[player_id] = PlayerDeck(player_id)
        # Add starter cards
        starter_car = Car("merc-starter", "Mercedes AMG", "Mercedes", 380, "rare")
        starter_driver = Driver("ham-starter", "Lewis Hamilton", "HAM", 8.5, "rare")
        player_decks[player_id].add_car(starter_car)
        player_decks[player_id].add_driver(starter_driver)
    
    if opponent_id not in player_decks:
        player_decks[opponent_id] = PlayerDeck(opponent_id)
        redbull_car = Car("rb-starter", "Red Bull RB18", "RedBull", 385, "rare")
        max_driver = Driver("ver-starter", "Max Verstappen", "VER", 9.0, "rare")
        player_decks[opponent_id].add_car(redbull_car)
        player_decks[opponent_id].add_driver(max_driver)
    
    # Get decks
    p1_deck = player_decks[player_id]
    p2_deck = player_decks[opponent_id]
    
    # Select cars (for now, first in deck)
    p1_car = p1_deck.cars[0] if p1_deck.cars else Car("default", "Unknown", "Unknown", 350, "rare")
    p1_driver = p1_deck.drivers[0] if p1_deck.drivers else Driver("default", "Unknown", "UNK", 5.0, "rare")
    
    p2_car = p2_deck.cars[0] if p2_deck.cars else Car("default", "Unknown", "Unknown", 350, "rare")
    p2_driver = p2_deck.drivers[0] if p2_deck.drivers else Driver("default", "Unknown", "UNK", 5.0, "rare")
    
    # Create race
    race, race_id = race_engine.create_race(player_id, opponent_id, p1_car, p1_driver, p2_car, p2_driver)
    active_race_dms[(player_id, opponent_id)] = race_id
    
    # Send confirmation
    embed = discord.Embed(
        title="🏁 Race Started!",
        description=f"{ctx.author.mention} vs {opponent.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="Player 1", value=f"{p1_driver.name} ({p1_car.name})", inline=False)
    embed.add_field(name="Player 2", value=f"{p2_driver.name} ({p2_car.name})", inline=False)
    embed.add_field(name="Status", value="Check your DMs for the race!", inline=False)
    
    await ctx.send(embed=embed)
    
    # Start race in DMs
    await send_race_turn(race, ctx.author, opponent, race_id)

async def send_race_turn(race: RaceState, p1_user: discord.User, p2_user: discord.User, race_id: str):
    """Send race turn to both players in DMs"""
    
    embed = create_race_embed(race, f"Turn {race.turn + 1}")
    
    # Add choice buttons
    view = RaceChoiceView(race_id, race, "p1")
    
    p1_dm = await p1_user.create_dm()
    await p1_dm.send(embed=embed, view=view)
    
    view2 = RaceChoiceView(race_id, race, "p2")
    p2_dm = await p2_user.create_dm()
    await p2_dm.send(embed=embed, view=view2)
    
    # Wait 30 seconds for responses
    await asyncio.sleep(30)
    
    # If both chose, process turn
    if race.p1_choice and race.p2_choice:
        await process_race_turn(race, p1_user, p2_user, race_id)
    else:
        # Auto-default to "same_speed"
        if not race.p1_choice:
            race.p1_choice = "same_speed"
        if not race.p2_choice:
            race.p2_choice = "same_speed"
        await process_race_turn(race, p1_user, p2_user, race_id)

async def process_race_turn(race: RaceState, p1_user: discord.User, p2_user: discord.User, race_id: str):
    """Process the race turn and send results"""
    
    result = race_engine.process_turn(race, race.p1_choice, race.p2_choice)
    
    if result.get("race_finished"):
        await finish_race(race, p1_user, p2_user)
        return
    
    if result.get("dnf"):
        await dnf_race(race, p1_user, p2_user, result)
        return
    
    # Send results and continue
    embed = create_race_embed(race, f"Turn {race.turn} Results")
    embed.add_field(name="P1 Choice", value=race.p1_choice, inline=True)
    embed.add_field(name="P2 Choice", value=race.p2_choice, inline=True)
    
    if result.get("event"):
        embed.add_field(name="🌧️ Event", value=result["event"], inline=False)
    
    p1_dm = await p1_user.create_dm()
    p2_dm = await p2_user.create_dm()
    
    await p1_dm.send(embed=embed)
    await p2_dm.send(embed=embed)
    
    # Continue race if not finished
    if race.lap <= race.total_laps:
        race.p1_choice = None
        race.p2_choice = None
        await send_race_turn(race, p1_user, p2_user, race_id)

async def finish_race(race: RaceState, p1_user: discord.User, p2_user: discord.User):
    """Handle race finish"""
    
    winner = p1_user if race.p1_position == 1 else p2_user
    loser = p2_user if race.p1_position == 1 else p1_user
    
    embed = discord.Embed(
        title="🏁 RACE FINISHED!",
        description=f"🥇 {winner.mention} WINS!",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Winner", value=f"{winner.mention}", inline=True)
    embed.add_field(name="Runner-up", value=f"{loser.mention}", inline=True)
    embed.add_field(name="Gap", value=f"{abs(race.gap):.2f}s", inline=False)
    embed.add_field(name="Pit Stops", value=f"P1: {race.p1_pit_stops} | P2: {race.p2_pit_stops}", inline=False)
    
    winner_dm = await winner.create_dm()
    loser_dm = await loser.create_dm()
    
    await winner_dm.send(embed=embed)
    await loser_dm.send(embed=embed)

async def dnf_race(race: RaceState, p1_user: discord.User, p2_user: discord.User, result: Dict):
    """Handle DNF (Did Not Finish)"""
    
    dnf_player = p1_user if result["dnf"] == "p1" else p2_user
    reason = result["reason"]
    
    embed = discord.Embed(
        title="❌ RACE DNF",
        description=f"{dnf_player.mention} did not finish!",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason.replace("_", " ").title(), inline=False)
    
    # Winner gets all points
    winner = p2_user if result["dnf"] == "p1" else p1_user
    embed.add_field(name="Winner", value=f"{winner.mention}", inline=False)
    
    p1_dm = await p1_user.create_dm()
    p2_dm = await p2_user.create_dm()
    
    await p1_dm.send(embed=embed)
    await p2_dm.send(embed=embed)

@bot.command(name="deck")
async def show_deck(ctx):
    """Show your current deck: /deck"""
    
    player_id = str(ctx.author.id)
    
    if player_id not in player_decks:
        await ctx.send("You don't have any cards yet! Start a race to earn cards.")
        return
    
    deck = player_decks[player_id]
    
    embed = discord.Embed(
        title=f"🎴 {ctx.author.name}'s Deck",
        color=discord.Color.blue()
    )
    
    if deck.drivers:
        drivers_text = "\n".join([f"- **{d.name}** ({d.code}) - {d.rarity.capitalize()}" for d in deck.drivers])
        embed.add_field(name="🏎️ Drivers", value=drivers_text, inline=False)
    
    if deck.cars:
        cars_text = "\n".join([f"- **{c.name}** ({c.team}) - {c.top_speed}km/h - {c.rarity.capitalize()}" for c in deck.cars])
        embed.add_field(name="🚗 Cars", value=cars_text, inline=False)
    
    embed.set_footer(text=f"Total cards: {len(deck.drivers) + len(deck.cars)}")
    
    await ctx.send(embed=embed)

@bot.command(name="addcard")
async def add_test_card(ctx, card_type: str, name: str):
    """Dev command: Add a test card"""
    
    player_id = str(ctx.author.id)
    
    if player_id not in player_decks:
        player_decks[player_id] = PlayerDeck(player_id)
    
    deck = player_decks[player_id]
    
    if card_type.lower() == "car":
        car = Car(f"car_{len(deck.cars)}", name, "Test", random.randint(340, 410), random.choice(["legendary", "epic", "rare", "common"]))
        deck.add_car(car)
        await ctx.send(f"✅ Added car: {car.name} ({car.top_speed}km/h - {car.rarity})")
    elif card_type.lower() == "driver":
        driver = Driver(f"driver_{len(deck.drivers)}", name, name[:3].upper(), random.uniform(5, 9.5), random.choice(["legendary", "epic", "rare", "common"]))
        deck.add_driver(driver)
        await ctx.send(f"✅ Added driver: {driver.name} ({driver.code} - {driver.rarity})")

# ==================== UI COMPONENTS ====================

class RaceChoiceView(discord.ui.View):
    def __init__(self, race_id: str, race: RaceState, player: str):
        super().__init__(timeout=30)
        self.race_id = race_id
        self.race = race
        self.player = player
    
    @discord.ui.button(label="🛑 Slow Down", style=discord.ButtonStyle.danger)
    async def slow_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "slow_down"
        else:
            self.race.p2_choice = "slow_down"
        
        await interaction.response.defer()
        await interaction.followup.send("✅ Choice recorded: Slow Down", ephemeral=True)
    
    @discord.ui.button(label="➡️ Same Speed", style=discord.ButtonStyle.secondary)
    async def same_speed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "same_speed"
        else:
            self.race.p2_choice = "same_speed"
        
        await interaction.response.defer()
        await interaction.followup.send("✅ Choice recorded: Same Speed", ephemeral=True)
    
    @discord.ui.button(label="🚀 Accelerate", style=discord.ButtonStyle.success)
    async def accelerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "accelerate"
        else:
            self.race.p2_choice = "accelerate"
        
        await interaction.response.defer()
        await interaction.followup.send("✅ Choice recorded: Accelerate", ephemeral=True)
    
    @discord.ui.button(label="⛽ Pit Stop", style=discord.ButtonStyle.primary)
    async def pit_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player == "p1":
            self.race.p1_choice = "pit_stop"
        else:
            self.race.p2_choice = "pit_stop"
        
        await interaction.response.defer()
        await interaction.followup.send("✅ Choice recorded: Pit Stop", ephemeral=True)

# ==================== MAIN ====================

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    bot.run(TOKEN)
