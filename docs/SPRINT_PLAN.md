# WILLIAM OS — Sprint Plan
## 6-Week MVP Timeline → Ship by May 18, 2026

---

## Week 1: Foundation (Apr 6–12)
**Theme:** "Build the skeleton right, and the muscles follow."

### Deliverables
- [x] Architecture document
- [x] Database schema + migrations
- [x] Project scaffold (backend + frontend)
- [ ] Auth system (register, login, JWT, refresh, logout)
- [ ] User profile + settings CRUD
- [ ] Multi-device session management
- [ ] Core event bus implementation
- [ ] Audit trail middleware
- [ ] Error handling + structured logging
- [ ] Docker Compose (dev environment)
- [ ] CI pipeline (GitHub Actions: lint + test)
- [ ] Health check endpoints
- [ ] API documentation (auto-generated OpenAPI)

### Risk Mitigation
- Oracle VM provisioning may take 1-2 days → use local Docker until ready
- PostgreSQL version compatibility → pin to v16

---

## Week 2: Scheduling + Journal (Apr 13–19)
**Theme:** "The two features users will touch every single day."

### Deliverables
- [ ] Schedule data model + CRUD API
- [ ] Gemini API integration for schedule generation
- [ ] Midnight auto-regeneration worker (cron)
- [ ] Schedule conflict detection + resolution
- [ ] Manual reschedule endpoint
- [ ] Journal vault: encrypted CRUD
- [ ] Journal: zero-knowledge encryption (client-side key derivation)
- [ ] Journal: search over encrypted entries
- [ ] Journal: export as encrypted archive
- [ ] React web: auth pages (login, register, forgot password)
- [ ] React web: schedule dashboard (day/week view)
- [ ] React web: journal editor

### Risk Mitigation
- Gemini API rate limits → implement retry with exponential backoff
- Encryption performance on mobile → benchmark, consider WebCrypto API

---

## Week 3: Health + Habits (Apr 20–26)
**Theme:** "Know the body, train the mind."

### Deliverables
- [ ] Wearable data ingestion API (generic adapter pattern)
- [ ] Apple HealthKit adapter
- [ ] Samsung Health adapter
- [ ] Noise Watch adapter
- [ ] OpenRouter health AI integration
- [ ] Energy level forecasting model
- [ ] Sleep quality scoring
- [ ] Habit CRUD + streak tracking
- [ ] Procrastination detection algorithm
- [ ] Medicine/supplement reminder system
- [ ] React web: health dashboard
- [ ] React web: habit tracker UI
- [ ] N8N workflow: health data sync

### Risk Mitigation
- Wearable API authentication complexity → start with manual CSV import fallback
- OpenRouter rate limits → cache AI responses for 6 hours

---

## Week 4: Study + Communication (Apr 27–May 3)
**Theme:** "Learn smarter, stay connected."

### Deliverables
- [ ] IAS study mentor: subject tracking + progress
- [ ] Spaced repetition engine (SM-2 algorithm)
- [ ] Pomodoro timer with smart break scheduling
- [ ] Quiz system + weak area detection
- [ ] Pre-wake email intelligence (Gmail API)
- [ ] Email summarization via OpenRouter
- [ ] Telegram bot integration
- [ ] WhatsApp Business API integration
- [ ] Family ecosystem: multi-user management
- [ ] Family: shared schedule view
- [ ] React web: study dashboard
- [ ] React web: email digest view

### Risk Mitigation
- WhatsApp Business API requires business verification → implement Telegram first
- Gmail API OAuth flow complexity → use google-auth library

---

## Week 5: Voice + Trading + Polish (May 4–10)
**Theme:** "Hands-free control, financial awareness."

### Deliverables
- [ ] Whisper API integration for voice transcription
- [ ] Voice command parser + intent detection
- [ ] Alexa Skill: schedule queries + rescheduling
- [ ] Real-time voice rescheduling flow
- [ ] Trading dashboard: market data integration
- [ ] Trading: watchlist + alerts
- [ ] Decision assistant module
- [ ] Accountability partner: notification system
- [ ] React Native: core app shell (iOS + Android)
- [ ] React Native: schedule + journal views
- [ ] Offline mode: local SQLite sync
- [ ] Load testing with Locust (target: 100 concurrent users)

### Risk Mitigation
- Alexa Skill certification takes 2-4 weeks → submit early, iterate
- React Native build tooling → use Expo for faster iteration

---

## Week 6: Integration + Deployment (May 11–17)
**Theme:** "Ship it. Ship it right."

### Deliverables
- [ ] End-to-end integration testing
- [ ] A/B testing framework
- [ ] Lifetime data export (encrypted JSON + CSV)
- [ ] Privacy audit: data flow review
- [ ] Security audit: penetration testing basics
- [ ] Performance optimization pass
- [ ] Oracle VM deployment
- [ ] SSL/TLS configuration
- [ ] Monitoring: Prometheus + Grafana dashboards
- [ ] Error tracking: Sentry integration
- [ ] User documentation
- [ ] API documentation finalization
- [ ] Demo video recording
- [ ] MVP launch 🚀

### Risk Mitigation
- Last-minute bugs → feature freeze on May 14, bug fixes only after
- Deployment issues → maintain staging environment from Week 3

---

## Definition of Done (Every Feature)
1. Code reviewed (self-review checklist)
2. Unit tests pass (>80% coverage for core modules)
3. Integration test exists for API endpoints
4. Error handling covers edge cases
5. Logging added for debugging
6. API docs updated
7. No hardcoded secrets
8. Works offline where applicable
