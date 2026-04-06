# OpenClaw Setup Guide

This guide wires OpenClaw to WILLIAM OS as a multi-channel chat gateway.

## 1) Prepare runtime

```bash
chmod +x scripts/setup-openclaw.sh
make openclaw-setup
```

If you run setup as root, the systemd unit is installed automatically.

## 2) Configure env

Edit `/opt/openclaw/.env`:

- `WILLIAM_API_BASE_URL=http://127.0.0.1:8000/api/v1`
- `WILLIAM_GATEWAY_BEARER_TOKEN=<jwt token>`
- Channel tokens as needed (`OPENCLAW_TELEGRAM_BOT_TOKEN`, etc.)

## 3) Enable service

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw.service
sudo systemctl status openclaw.service
```

## 4) Verify command routing

Use any connected channel and send:

- `/today`
- `/habits`
- `/sleep`
- `/briefing`
- `/journal passphrase123|Today was productive`
- `/checkin <habit_id>`
- Free-form text like `reschedule my day after 5pm`

Expected behavior:

- Structured commands map directly to WILLIAM OS endpoints.
- Free text is delegated to `/voice/command`.
- Responses return as plain channel-friendly text.
