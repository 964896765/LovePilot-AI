# LovePilot AI V0.9 — AstrBot + Tencent iLink Bot bridge

## Implemented in this source package

- Added `integrations/astrbot_plugin_lovepilot`, a private-message bridge plugin for AstrBot.
- Added explicit `/start` opt-in, `/pause` consent revocation, and `/forget` data deletion commands.
- Added a clear AI identity disclosure in the opt-in response.
- Auto reply defaults to OFF (`LOVEPILOT_AUTO_REPLY=false`); can be enabled only for the disclosed bot identity after staged testing.
- Uses the existing LovePilot backend API and preserves the backend's contact consent gate and sensitive-topic handoff.
- Added `ILINK_ASTRBOT_SETUP.md` with installation, network, consent, and testing instructions.

## Validation

- Existing backend suite: 29 tests total; 26 passed, 3 skipped because optional LangGraph package is not installed.
- The AstrBot plugin was syntax-compiled only; AstrBot runtime/API compatibility and a real iLink QR login were not available in this environment.
- No APK was built. No live WeChat account was connected. No messages were sent to real users.

## Important identity boundary

This integration connects an independent Bot identity through AstrBot's Personal WeChat adapter, which its current documentation says is based on Tencent's `openclaw-weixin` interface. It does not take over the operator's ordinary personal chats or read the operator's unrelated friend conversations.

## Known limitations

- Plugin uses AstrBot's legacy `Star`/`filter` plugin API; verify compatibility with the installed AstrBot release. If the installed release requires the newer SDK, port the handler to that SDK instead of bypassing platform controls.
- Verify `unified_msg_origin` stability and message ID availability in the exact adapter build.
- `LOVEPILOT_AUTO_REPLY=true` sends as the clearly identified AI bot, not as the user's human identity. Keep false until consent and regression tests pass.
- Current keyword-based sensitive-topic policy is only a basic safeguard and requires broader testing.
