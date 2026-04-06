# WILLIAM OS OpenClaw Skill

## Purpose
Route multi-channel chat messages (Telegram, WhatsApp, Discord, web chat) into WILLIAM OS APIs.

## Required Environment
- `WILLIAM_API_BASE_URL` (example: `http://127.0.0.1:8000/api/v1`)
- `WILLIAM_GATEWAY_BEARER_TOKEN` (JWT token for the target user or service account)
- `WILLIAM_GATEWAY_TIMEOUT_SECONDS` (optional, default `20`)

## Command Routing
- `/today` -> `GET /schedule/today`
- `/habits` -> `GET /habits?active_only=true&limit=20&offset=0`
- `/sleep` -> `GET /sleep/stats`
- `/briefing` -> `GET /email/briefing`
- `/journal <passphrase>|<text>` -> `POST /journal`
- `/checkin <habit_id>` -> `POST /habits/{habit_id}/check-in`
- Everything else -> `POST /voice/command`

## Response Contract
`handle_message(text: str, channel: str, metadata: dict | None) -> str`

The function returns plain text, suitable for any chat channel.

## Notes
- This skill assumes WILLIAM OS uses the standard API envelope: `{ ok, data, error }`.
- For natural language requests, the skill falls back to `/voice/command` so existing intent logic remains centralized in backend.
