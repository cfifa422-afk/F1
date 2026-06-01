import discord
import asyncio
import os
import json
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import cards as card_module
from database import Database

RARITY_EMOJI = {"legendary": "🏆", "epic": "💜", "rare": "🔵", "common": "⚪"}
CARD_TYPE_EMOJI = {"driver": "👤", "car": "🏎️"}

def generate_card(rarity: str) -> dict:
    card_type = random.choice(["driver", "car"])
    now = datetime.now().isoformat()

    if card_type == "driver":
        pool = list(card_module.DRIVERS.get(rarity, card_module.DRIVERS["common"]))
        if not pool:
            pool = list(card_module.DRIVERS["common"])
        driver = random.choice(pool)
        perks = [random.choice(list(card_module.PERKS.keys()))] if random.random() < 0.30 else []
        return {
            "id": f"{random.randint(0, 0xFFFFFFF):07X}",
            "type": "driver",
            "name": driver["name"],
            "code": driver["code"],
            "skill": driver["skill"],
            "team": driver["team"],
            "rarity": rarity,
            "perks": perks,
            "obtained_at": now,
            "caught_at": now,
        }
    else:
        pool = list(card_module.CARS.get(rarity, card_module.CARS["common"]))
        if not pool:
            pool = list(card_module.CARS["common"])
        car = random.choice(pool)
        perks = [random.choice(list(card_module.PERKS.keys()))] if random.random() < 0.25 else []
        return {
            "id": f"{random.randint(0, 0xFFFFFFF):07X}",
            "type": "car",
            "name": car["name"],
            "team": car["team"],
            "top_speed": car["top_speed"],
            "handling": car["handling"],
            "rarity": rarity,
            "perks": perks,
            "obtained_at": now,
            "caught_at": now,
        }


def apply_rewards_to_all_players(db: Database):
    results = {}
    for player_id, player in db.data["players"].items():
        given_cards = []

        legendary = generate_card("legendary")
        given_cards.append(legendary)
        db.add_card_to_player(player_id, legendary, legendary["type"])

        for _ in range(5):
            card = generate_card("rare")
            given_cards.append(card)
            db.add_card_to_player(player_id, card, card["type"])

        for _ in range(10):
            card = generate_card("common")
            given_cards.append(card)
            db.add_card_to_player(player_id, card, card["type"])

        db.add_coins(player_id, 8000)

        results[player_id] = given_cards

    return results


def format_card_line(card: dict) -> str:
    emoji = RARITY_EMOJI.get(card["rarity"], "")
    type_emoji = CARD_TYPE_EMOJI.get(card["type"], "")
    return f"{emoji}{type_emoji} **{card['name']}** ({card['rarity'].capitalize()})"


intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    db = Database()
    print(f"📦 Applying rewards to {len(db.data['players'])} players...")
    rewards_map = apply_rewards_to_all_players(db)
    print("💾 Rewards saved to database.")

    sent = 0
    failed = 0

    for player_id, cards in rewards_map.items():
        try:
            user = await client.fetch_user(int(player_id))

            legendary_card = next((c for c in cards if c["rarity"] == "legendary"), None)
            rare_cards = [c for c in cards if c["rarity"] == "rare"]
            common_cards = [c for c in cards if c["rarity"] == "common"]

            rare_preview = "\n".join(f"  {format_card_line(c)}" for c in rare_cards[:3])
            if len(rare_cards) > 3:
                rare_preview += f"\n  *...and {len(rare_cards) - 3} more*"

            common_preview = "\n".join(f"  {format_card_line(c)}" for c in common_cards[:3])
            if len(common_cards) > 3:
                common_preview += f"\n  *...and {len(common_cards) - 3} more*"

            msg = (
                f"⚠️ **Important Notice from F1 Racing Bot**\n\n"
                f"We recently encountered some data errors that affected player records. "
                f"We've resolved the issue, but some old data may have been removed.\n\n"
                f"As a **compensation**, we've added the following to your account:\n\n"
                f"🏆 **1 Legendary Card**\n"
                f"  {format_card_line(legendary_card)}\n\n"
                f"🔵 **5 Rare Cards**, including:\n{rare_preview}\n\n"
                f"⚪ **10 Common Cards**, including:\n{common_preview}\n\n"
                f"💰 **+8,000 Race Credits** added to your wallet\n\n"
                f"We're sorry for any inconvenience. Thank you for racing with us! 🏁"
                f"This is the new F1 bot add this to your servers!"
            )

            await user.send(msg)
            sent += 1
            print(f"  ✉️  DM sent to {user.name} ({player_id})")
            await asyncio.sleep(1.2)

        except discord.Forbidden:
            print(f"  ⚠️  Can't DM {player_id} (DMs closed)")
            failed += 1
        except discord.NotFound:
            print(f"  ⚠️  User {player_id} not found")
            failed += 1
        except Exception as e:
            print(f"  ❌ Error for {player_id}: {e}")
            failed += 1

    print(f"\n✅ Done! Sent: {sent} | Failed/Skipped: {failed}")
    await client.close()


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN not set!")
    exit(1)

client.run(TOKEN)
