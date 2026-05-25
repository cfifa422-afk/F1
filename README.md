# 🏁 F1 Card Collection Racing Discord Bot

A turn-based 1v1 F1 racing game for Discord with card collection, strategic decision-making, and dynamic race mechanics.

## Features

✅ **Turn-Based Racing System**
- 3-lap races with 4 turns per lap
- Real-time DM notifications with interactive choice buttons
- Three core decision types: Slow Down, Same Speed, Accelerate
- Pit stop mechanics with tire changes

✅ **Realistic Race Physics**
- Tire degradation (soft/medium/hard/wet)
- Fuel consumption management
- Weather events (rain, DRS zones, safety cars)
- Car stats based on rarity and top speed

✅ **Card Collection**
- Legendary, Epic, Rare, Common rarity tiers
- Driver cards with skill ratings
- Car/Team cards with top speed and handling stats
- Deck management system

✅ **Dynamic Events**
- Random weather changes
- DRS (Drag Reduction System) opportunities
- Safety car deployments
- Tire degradation mechanics

## Setup Instructions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Go to "Bot" section and click "Add Bot"
4. Copy the **TOKEN** (keep this secret!)
5. Enable these "Privileged Gateway Intents":
   - Message Content Intent
   - Direct Messages

### 2. Add Bot to Your Server

1. Go to OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Read Messages/View Channels`, `Send DMs`
4. Copy the generated URL and open it in your browser
5. Select your server and authorize

### 3. Setup on Replit

1. **Fork this project to Replit** or create new Replit project
2. **Create `.env` file** with:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the bot:**
   ```bash
   python bot.py
   ```

### 4. Keep Bot Running (Replit)

- Use Replit's **"Always On"** feature (paid)
- OR use an external service like [Uptime Robot](https://uptimerobot.com/) to ping Replit keep-alive endpoint

## Commands

```
/race @opponent          - Start a 1v1 race
/deck                    - Show your card collection
/addcard car NAME        - [DEV] Add test car
/addcard driver NAME     - [DEV] Add test driver
```

## How Races Work

### Turn-Based Decision Making

Every 15-20 seconds, each player gets a DM with 4 buttons:

1. **🛑 Slow Down** - Conserve fuel/tires, lose position
2. **➡️ Same Speed** - Maintain position, balanced approach
3. **🚀 Accelerate** - Gain position, burn fuel/tires
4. **⛽ Pit Stop** - Fresh tires/fuel, lose track position

### Race Progression

- **Turn 1-4**: Lap 1 (build lead or chase)
- **Turn 5-8**: Lap 2 (tire degradation starts showing)
- **Turn 9-12**: Lap 3 (final lap drama - comeback window)

### Win Conditions

- Complete 3 laps in best time
- Opponent DNF (tire failure or fuel depletion)
- Most positions gained during race

## Game Mechanics

### Car Rarity Impact

| Rarity | Top Speed | Acceleration | Handling | Tire Wear | Fuel Eff |
|--------|-----------|--------------|----------|-----------|----------|
| Legendary | 400km/h | 9.5/10 | 9.0/10 | -15%/turn | -2.5%/turn |
| Epic | 380km/h | 9.0/10 | 8.5/10 | -17%/turn | -2.7%/turn |
| Rare | 350km/h | 7.5/10 | 7.0/10 | -20%/turn | -3.0%/turn |
| Common | 320km/h | 6.5/10 | 6.0/10 | -22%/turn | -3.2%/turn |

### Tire Types

| Tire | Speed | Durability | Best For |
|------|-------|-----------|----------|
| Soft 🔴 | +5% | 3 laps | Early race push |
| Medium 🟡 | +2% | 6 laps | Balanced strategy |
| Hard 🟢 | 0% | 9 laps | Tire management |
| Wet 💧 | +40% (rain) | 7 laps | Rainy conditions |

### Race Events

- **Rain** (5% chance): Wet tires gain +3.0s/lap, dry tires lose -2.0s/lap
- **DRS** (5% chance): Accelerate button gets +0.5s bonus
- **Safety Car** (2% chance): All cars slow to pit lane speed

## Example Race Flow

```
Player 1 (HAM-Mercedes, 400km/h Legendary)
vs
Player 2 (VER-RedBull, 385km/h Epic)

Turn 1: Both Accelerate → Equal pace
Turn 2: P1 Accelerate, P2 Same Speed → P1 gains 0.4s
Turn 3: P1 Same, P2 Accelerate → Gap closes to 0.1s
Turn 4: P2 Pit Stop (fresh tires), P1 Accelerate → P1 extends lead 2.1s
Turn 5: Rain event! P2's fresh wets gain advantage
Turn 6-8: P2 closes gap with wet tire advantage
Turn 9: P1's tires degraded, P2's still fresh
Turn 10: P2 OVERTAKES! Final lap drama
Finish: P2 WINS by 0.1s (photo finish!)
```

## Development

### Project Structure

```
f1_discord_bot/
├── bot.py                 # Main bot file (race engine, commands, UI)
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── README.md             # This file
└── (future)
    ├── database.py       # Database layer
    ├── cards.py          # Card data and generation
    ├── stats.py          # Player stats/leaderboards
    └── events.py         # Custom race events
```

### Future Features

- [ ] Persistent database (SQLite/PostgreSQL)
- [ ] Leaderboards & seasonal rankings
- [ ] Card pack generation & trading
- [ ] Team leagues (guild vs guild races)
- [ ] Custom tracks with different layouts
- [ ] Sponsorship system (temporary stat boosts)
- [ ] Skill rating system
- [ ] Replay system (save race footage)
- [ ] Mobile companion app
- [ ] Web dashboard

## Configuration

Edit `bot.py` to customize:

```python
# Race settings
self.total_laps = 3           # Number of laps
self.max_turns = 12           # 4 turns per lap

# Tire wear rates
"soft": {"wear_rate": 8},     # Higher = faster degradation
"hard": {"wear_rate": 2},

# Fuel burn
"accelerate": 5.0,            # Fuel % burned per turn
"slow_down": 2.0,
```

## Troubleshooting

### Bot won't start
- Check `DISCORD_TOKEN` in `.env`
- Verify token is correct (no spaces)
- Check bot has Message Content Intent enabled

### No DM received during race
- Verify bot can send DMs to both players
- Check Discord privacy settings allow bot DMs
- Ensure both players aren't in a race already

### Race gets stuck
- Bot will auto-default to "Same Speed" after 30s
- Check bot logs for errors
- Restart bot if needed

## Support

For bugs or feature requests, open an issue or DM the bot owner!

---

**Made with ❤️ for F1 fans** 🏁
