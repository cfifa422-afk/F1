import discord
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

MESSAGE = (
    "⚠️ **Important Notice from F1 Racing Bot**\n\n"
    "We recently encountered some data errors that affected player records. "
    "We've resolved the issue, but some old data may have been removed as a result.\n\n"
    "As a **compensation**, every registered player has received:\n\n"
    "🏆 **1 Legendary Card**\n"
    "🔵 **10 Rare Cards**\n"
    "⚪ **10 Common Cards**\n"
    "💰 **+8,000 Race Credits**\n\n"
    "Your rewards are already in your account — use `/garage` or `/f1 deck` to see them.\n\n"
    "We're sorry for any inconvenience. Thank you for racing with us! 🏁"
)


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

    with open("f1_data.json") as f:
        data = json.load(f)

    spawn_channels = data.get("spawn_channels", {})

    sent_to = set()
    sent = 0
    failed = 0

    for guild_id, channel_ids in spawn_channels.items():
        for channel_id in channel_ids:
            if channel_id in sent_to:
                continue
            try:
                channel = await client.fetch_channel(int(channel_id))
                await channel.send(MESSAGE)
                sent_to.add(channel_id)
                sent += 1
                print(f"  ✅ Sent to #{channel.name} (guild {guild_id})")
                await asyncio.sleep(1)
            except discord.Forbidden:
                print(f"  ⚠️  No permission for channel {channel_id}")
                failed += 1
            except discord.NotFound:
                print(f"  ⚠️  Channel {channel_id} not found")
                failed += 1
            except Exception as e:
                print(f"  ❌ Error for channel {channel_id}: {e}")
                failed += 1

    print(f"\n✅ Done! Sent: {sent} | Failed: {failed}")
    await client.close()


TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN not set!")
    exit(1)

client.run(TOKEN)
