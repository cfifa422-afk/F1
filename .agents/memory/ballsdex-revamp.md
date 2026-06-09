---
name: BallsDex revamp
description: Exact BallsDex UI patterns used for trade, give, spawn, catch
---

All UIs were ported from BallsDex source (github.com/laggron42/BallsDex-DiscordBot).

**Trade flow (TradeProposalView → TradeConfirmView):**
- Content on start: "Hey {target.mention}, {offerer.name} is proposing a trade with you!"
- Embed title: "F1 cards trading"
- Embed color progression: blurple → yellow (both locked) → green (done) / dark_red (cancelled)
- Description footer: "This message is updated every 15 seconds, but you can keep on editing your proposal."
- Phase 1 buttons: "Add card" (➕ secondary), "Reset" (— secondary, needs confirm), "Lock proposal" (🔒 primary), "Cancel trade" (✖ danger, needs confirm)
- Phase 2 buttons: ✅ (green, no label) + ✖ (red, no label) — emoji only, no text
- Field prefix: 🚫 cancelled, ✅ accepted, 🔒 locked, "" otherwise
- Cards in fields: `- card` plain, `- *card*` italic if locked, `~~- card~~` strikethrough if cancelled
- 15-second background update loop via asyncio task
- State dict: _active_trades, keys: offerer/target _locked/_accepted
- _InlineConfirmView: used for Reset and Cancel confirmations (emoji-only ✅/✖)

**Give/donation flow (DonationRequest):**
- Picker sends ephemeral select to giver; on pick, sends PUBLIC followup
- Content: "{receiver.mention}, {giver.name} wants to give you **{emoji} {name}** ({rarity})!"
- Buttons: ✅ (green, no label) + ✖ (red, no label) — emoji only
- On accept: edit_message appending "\n✅ The donation was accepted!" to content
- On deny: edit_message appending "\n❌ The donation was denied." to content
- On timeout: disable buttons only (no extra text)

**Spawn announcements:**
- content text varies by rarity (common/rare/epic/legendary/mythic/special)
- embed sent alongside (BallsDex style: content + embed together)

**Catch success:**
- Rich embed with rarity color, type badge, card ID, tip text
- Footer: "Use /f1 collection to view your cards · /completion to track progress"
