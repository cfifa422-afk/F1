---
name: Bot architecture
description: How the F1 card bot is structured — single file, no Cogs, how to add commands
---

## Core facts

- All commands are in `bot.py` (6300+ lines). No Cog system.
- Commands use `@bot.tree.command` or `@group.command` decorators at module level.
- New top-level groups must be registered with `bot.tree.add_command(group)` — these calls live near the bottom of bot.py before `if __name__ == "__main__":`.
- Nested sub-groups use `parent=parent_group` in the `app_commands.Group(...)` constructor.
- Data layer: `database.py` — flat JSON file (`f1_data.json`), `Database` class with all methods.
- Entry point: `python bot.py` (workflow: "Start application").

**Why:** The original bot was built without Cogs and adding them would require a large refactor. Future additions should follow the same pattern: append commands/groups to bot.py, add helper classes/functions above, register new top-level groups at the bottom.

**How to apply:** When adding new commands, append them before `if __name__ == "__main__":` and register any new top-level groups with `bot.tree.add_command(...)`.
