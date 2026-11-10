# LovePilot AI V0.9 — AstrBot + Tencent iLink

## What this integration does

- Uses AstrBot's **Personal WeChat** adapter, documented as based on Tencent's `openclaw-weixin` interface.
- Connects a clearly identified AI bot account, not the operator's ordinary personal-chat identity.
- Bridges private messages to the existing LovePilot Agent HTTP API.
- Requires the chat participant to send `/start` before the bridge stores messages or replies.
- `/pause` revokes the conversation consent; `/forget` deletes that conversation's stored data.
- Auto reply is **off by default**. Enable it only after testing and only for the disclosed AI bot identity.

This does not let the bot read or take over the operator's other personal WeChat conversations, friends, or history. iLink bot access is a separate bot conversation surface. Availability and account eligibility are controlled by WeChat.

## Official references

- AstrBot Personal WeChat adapter: https://github.com/AstrBotDevs/AstrBot/blob/master/docs/zh/platform/weixin_oc.md
- Tencent iLink protocol repository: https://github.com/Tencent/openclaw-weixin
- Protocol details: https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol.md

## 1. Run LovePilot Agent

From the project root (Windows PowerShell):

```powershell
$env:LOVEPILOT_TOKEN = "generate-a-long-random-secret"
$env:DEEPSEEK_API_KEY = "your-DeepSeek-key"
python -m agent_server.server
```

The current prototype binds to `127.0.0.1:8768`. AstrBot must run on the same host for this simple local bridge. Do not expose this HTTP service to the public internet. For separate hosts, put it behind HTTPS with authentication, firewall allowlists, and secret rotation.

## 2. Install AstrBot and configure Personal WeChat

Follow the current official AstrBot installation guide: https://docs.astrbot.app/ . Use a current AstrBot release that includes the Personal WeChat adapter (the docs currently identify it as introduced in v4.22.0).

In AstrBot WebUI:

1. Open **机器人 / Platforms** and create a bot/adapter.
2. Select **个人微信 / Personal WeChat**.
3. Scan the displayed QR code with the WeChat app and confirm the login in WeChat.
4. Save the adapter after login succeeds.
5. Check AstrBot logs and test a message to the bot.

The adapter documentation currently lists Android WeChat >= 8.0.69 and iOS >= 8.0.70, and says the WeChat app must contain the ClawBot plugin. Check the current official docs and your account's in-app eligibility before proceeding; do not assume all accounts or regions have access.

## 3. Install this bridge plugin

Copy `integrations/astrbot_plugin_lovepilot` into AstrBot's plugin directory (the exact directory depends on your AstrBot deployment; commonly `data/plugins/`). Install its requirements in the AstrBot runtime:

```bash
pip install -r requirements.txt
```

Set these environment variables in the AstrBot process/container:

```text
LOVEPILOT_URL=http://127.0.0.1:8768
LOVEPILOT_TOKEN=<same token as LovePilot Agent>
LOVEPILOT_AUTO_REPLY=false
```

Restart AstrBot and enable the plugin. If AstrBot runs in Docker, `127.0.0.1` points inside the container, not the host; use a private Docker network service name or host-gateway route and keep the Agent bound to a protected interface. Never publish the Agent port openly.

## 4. Consent and staged test

1. Start with `LOVEPILOT_AUTO_REPLY=false`.
2. Message the bot with `/start`. It identifies itself as LovePilot AI and enables this conversation.
3. Send harmless test messages; inspect the suggested replies and Agent logs.
4. Send `/pause`; verify further messages do not generate drafts.
5. Send `/start` to opt in again.
6. Send `/forget`; verify the conversation's stored data is deleted.
7. Only after all checks pass, consider setting `LOVEPILOT_AUTO_REPLY=true` for this disclosed bot identity.

Do not use this bridge to impersonate a human, scrape unrelated chats, or message people who have not opted in. It does not automate the user's existing personal WeChat conversations.

## Known limitations

- The bridge uses AstrBot's legacy plugin API (`Star`, `filter`) and must be validated against the exact AstrBot version installed. AstrBot plugin APIs can evolve; if startup reports API incompatibility, adapt the plugin to that release's SDK rather than bypassing platform controls.
- The bridge uses `event.unified_msg_origin` as a conversation key. Verify this remains stable for your chosen adapter version before relying on persistent memory.
- Message IDs may not be exposed consistently by every adapter version; deduplication is strongest only when a stable ID is provided.
- The current LovePilot backend uses SQLite and basic keyword safety checks. It is a prototype, not a clinical or relationship decision system.
- Voice messages are not sent by this bridge as voice; AstrBot's adapter docs say inbound voice may be cloud-transcribed and outbound voice is not supported by that adapter.
- No APK is produced by this integration. It adds an official Bot channel and a server-side bridge.
