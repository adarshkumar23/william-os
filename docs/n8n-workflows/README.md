# William OS n8n Workflows

Environment variables required in n8n:

- WILLIAM_API_BASE_URL (example: https://williamos.duckdns.org/api/v1)
- WILLIAM_API_KEY (permanent key with wos- prefix)
- TELEGRAM_BOT_TOKEN (for telegram workflow)
- TELEGRAM_CHAT_ID (for telegram workflow)

Workflows:

1. 01_william_webhook_intake.json
2. 02_william_daily_summary_to_telegram.json
3. 03_william_telegram_daily_actions.json
4. 04_william_study_habits_pipeline.json
5. 05_william_trading_sleep_decisions_pipeline.json
