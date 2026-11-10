# V1.0 Acceptance Checklist

- [ ] Agent starts with a non-empty random bearer token.
- [ ] AstrBot loads the plugin without import/API errors.
- [ ] WeChat iLink QR login succeeds for an eligible account.
- [ ] Bot identity is visibly disclosed as AI.
- [ ] `/start` creates an opted-in conversation.
- [ ] `/pause` prevents future drafts.
- [ ] `/forget` deletes that conversation's stored data.
- [ ] Rapid repeated messages are throttled.
- [ ] Auto-reply remains off until explicitly configured.
- [ ] No access to unrelated personal WeChat chats is attempted.
- [ ] Logs do not contain API keys or full private message bodies.
