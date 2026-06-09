---
name: Bot architecture
description: Single-file bot structure, command group rules, registration pattern
---

All commands live in bot.py (~6500 lines). No Cog system. Groups use @group.command decorators and must be registered near the bottom with bot.tree.add_command(group).

**Critical Discord API rule**: A command group cannot have BOTH direct subcommands AND subgroups. If it does, Discord silently hides everything. Solution: move nested groups to top-level and register them separately.

Current top-level registrations (near end of bot.py):
- bot.tree.add_command(pack_group)
- bot.tree.add_command(f1_group)
- bot.tree.add_command(config_group)
- bot.tree.add_command(channels_group)   ← standalone (not nested in config)
- bot.tree.add_command(trade_group)
- bot.tree.add_command(player_group)
- bot.tree.add_command(blacklist_group)  ← standalone (not nested in config)

**Why:** config_group has direct subcommands (status/enable/disable/adddriver etc.). Discord forbids mixing subcommands + subgroups at same level.
