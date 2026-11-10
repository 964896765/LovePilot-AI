# LovePilot AI V1.0 — Bot Bridge Hardening

## Scope
V1.0 is a hardening release on top of V0.9. It improves the AstrBot bridge's operator guidance and basic burst handling. It does not claim a verified Tencent iLink login or a verified AstrBot runtime.

## Changes
- Adds `/help` command with an explicit AI-bot identity disclosure.
- Checks for a configured LovePilot bearer token before processing commands.
- Adds a configurable per-conversation cooldown (`LOVEPILOT_COOLDOWN_SECONDS`, default 3 seconds).
- Adds `.env.example` for local configuration.
- Keeps automatic replies disabled by default.
- Keeps `/start`, `/pause`, and `/forget` consent and data controls.

## Verification
- Python syntax compilation of the modified plugin: passed.
- Existing backend test suite: run separately using `python -m unittest discover -s tests -v`.
- AstrBot plugin loading, QR login, iLink message delivery and actual bot reply: NOT verified in this build.
- Android APK: NOT built.
- LangGraph and Mem0: still optional adapters, not asserted as fully integrated.

## Safety
The integration is for a clearly disclosed AI bot conversation. It does not access or take over the operator's personal WeChat friend chats. Keep `LOVEPILOT_AUTO_REPLY=false` until a test bot conversation is validated and participants know they are interacting with an AI bot.
