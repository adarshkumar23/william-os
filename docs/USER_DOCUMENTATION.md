# WILLIAM OS User Documentation (Task 6.8)

## Overview
WILLIAM OS is a personal operations system for daily planning, habits, journal privacy, medicine reminders, and cross-device sync.

## Core User Flows

### 1. Create Account and Sign In
1. Open the web app.
2. Register with email, username, and strong password.
3. Sign in and keep the issued session tokens secure.

### 2. Daily Planning
1. Open the Dashboard.
2. Generate or refresh your schedule for today.
3. Start and complete blocks as your day progresses.

### 3. Habit Tracking
1. Create habits from the Habits page.
2. Check in daily.
3. Review streak consistency over time.

### 4. Journal Vault
1. Create journal entries with your passphrase.
2. Use the same passphrase to read/decrypt entries.
3. Keep passphrase private; recovery is not possible without it.

### 5. Medicine Reminders
1. Add medicine/supplement plans and reminder times.
2. Log taken/skipped events from medicine cards.

### 6. Offline and Reconnect Behavior
1. When offline, mutation requests are queued locally.
2. On reconnect, queued actions replay and critical views resync.
3. Offline banner indicates sync status.

### 7. Real-Time Sync
1. Keep multiple devices signed in.
2. Updates in schedule/habits/medicine propagate via WebSocket sync.

## Data Control and Privacy
- Export summary: GET /api/v1/export/summary
- Full export: POST /api/v1/export/full
- Journal export: POST /api/v1/export/journal
- Lifetime encrypted export: POST /api/v1/export/lifetime
- Delete account and associated data: DELETE /api/v1/export/account

## Troubleshooting
- 401 or 422 on protected routes: verify Authorization header and token freshness.
- Journal decryption errors: verify passphrase correctness.
- Offline queue not replaying: confirm network is restored and API is reachable.
- Real-time updates missing: verify WebSocket route availability at /ws/v1/sync.

## Security Notes
- Use a strong unique account password.
- Use a separate strong journal passphrase.
- Log out from unknown devices and rotate credentials when suspicious activity is detected.
