---
name: BallsDex revamp features
description: Which BallsDex-inspired features were ported and where they live
---

## Implemented features

| Feature | Command | Location |
|---------|---------|----------|
| Trade history recording | auto on trade complete | `MultiTradeView.confirm_btn` → `db.record_trade()` |
| Trade history view | `/trade history [user]` | `trade_group` at end of bot.py |
| Give/Donate card | `/give @user` | `GiveCardView`, `GiveCardPickerView` at end of bot.py |
| Collection completion % | `/completion [user]` | `completion_command` at end of bot.py |
| Leaderboard | `/leaderboard [metric]` | `LeaderboardView`, `leaderboard_command` at end of bot.py |
| Card search | `/search [query] [rarity]` | `search_command` at end of bot.py |
| Coinflip betting | `/coinflip @user <amount>` | `CoinflipView`, `coinflip_command` at end of bot.py |
| Config status | `/config status` | `config_status` at end of bot.py |
| Config enable/disable | `/config enable`, `/config disable` | `config_enable`, `config_disable` at end of bot.py |
| Admin blacklist | `/config blacklist add/remove/list` | `blacklist_group` (nested in config_group) |
| Player info | `/player info [user]` | `player_info` in `player_group` |
| Player settings | `/player settings` | `player_settings` in `player_group` |
| Friends system | `/player friend add/remove/list` | `player_friend_group` nested in `player_group` |
| Block system | `/player block add/remove/list` | `player_block_group` nested in `player_group` |
| Better spawn messages | flavor text on spawn embed | `build_spawn_embed()` |
| Spawn enable/disable | per-guild toggle | `spawn_wild_card` loop + `db.is_spawn_enabled()` |
| Block protection | trades, gifts, coinflips | checked at command entry |
| Blacklist protection | catch modal | `CatchModal.on_submit` |

## Database additions (database.py)
- `record_trade`, `get_trade_history`
- `get_friends`, `add_friend`, `remove_friend`, `are_friends`, `get_pending_requests`, `add_pending_request`, `remove_pending_request`
- `get_blocks`, `add_block`, `remove_block`, `is_blocked`
- `get_privacy`, `set_privacy`
- `get_guild_config`, `set_guild_spawn_enabled`, `is_spawn_enabled`, `guild_blacklist_add`, `guild_blacklist_remove`, `is_guild_blacklisted`
- `get_leaderboard`

**Why:** User requested full BallsDex-inspired revamp. All features are free (no paywall).
