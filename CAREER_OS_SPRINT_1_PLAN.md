# Career OS — Sprint 1 Plan

## Tables (career schema)

### career.problems
- id UUID PK, user_id UUID NOT NULL FK auth.users, created_at TIMESTAMP, updated_at TIMESTAMP
- platform VARCHAR(32), external_id VARCHAR(128), title VARCHAR(256), difficulty VARCHAR(16)
- topics TEXT[], url TEXT, solved_at TIMESTAMP (tz-naive UTC), time_spent_minutes INT, notes TEXT
- UNIQUE(user_id, platform, external_id)
- INDEX(user_id, solved_at DESC)
- GIN INDEX(topics)

### career.projects
- id UUID PK, user_id UUID NOT NULL FK, created_at, updated_at
- name VARCHAR(128), description TEXT, tech_stack TEXT[], status VARCHAR(32) default 'planning'
- live_url TEXT, github_url TEXT, on_resume BOOLEAN default false
- started_at DATE, shipped_at DATE, notes TEXT
- GIN INDEX(tech_stack)

### career.applications
- id UUID PK, user_id UUID NOT NULL FK, created_at, updated_at
- company VARCHAR(128), role VARCHAR(128), platform VARCHAR(64)
- stage VARCHAR(32) default 'researching', stage_updated_at TIMESTAMP (tz-naive UTC)
- applied_at DATE, next_action TEXT, next_action_due DATE
- stipend_or_ctc VARCHAR(64), notes TEXT, archived BOOLEAN default false
- PARTIAL INDEX(user_id, stage) WHERE archived = false

### career.contacts
- id UUID PK, user_id UUID NOT NULL FK, created_at, updated_at
- name VARCHAR(128), company VARCHAR(128), role VARCHAR(128), tags TEXT[]
- linkedin_url TEXT, email VARCHAR(256), temperature VARCHAR(16) default 'cold'
- last_contacted_at DATE, next_followup_at DATE, relationship_notes TEXT
- PARTIAL INDEX(user_id, next_followup_at) WHERE next_followup_at IS NOT NULL
- GIN INDEX(tags)

### career.opportunities
- id UUID PK, user_id UUID NOT NULL FK, created_at, updated_at
- title VARCHAR(256), source VARCHAR(64), kind VARCHAR(32)
- url TEXT, description TEXT, deadline TIMESTAMP (tz-naive UTC), stipend_info VARCHAR(128)
- status VARCHAR(16) default 'inbox', converted_to_application_id UUID FK career.applications
- PARTIAL INDEX(user_id, deadline) WHERE status = 'inbox'

### career.score_snapshots
- id UUID PK, user_id UUID NOT NULL FK, created_at, updated_at
- snapshot_date DATE, overall_score INT, components JSONB
- UNIQUE(user_id, snapshot_date)

---

## Endpoint List

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/career/dashboard | Score + momentum + stats + warnings |
| GET | /api/v1/career/score/history | Snapshots for trend |
| POST | /api/v1/career/score/recompute | Force recompute |
| POST | /api/v1/career/score/cf-rating | Update CF rating |
| GET | /api/v1/career/problems | List (filter: platform, difficulty, topic) |
| POST | /api/v1/career/problems | Create |
| GET | /api/v1/career/problems/{id} | Single |
| PATCH | /api/v1/career/problems/{id} | Update |
| DELETE | /api/v1/career/problems/{id} | Delete |
| GET | /api/v1/career/projects | List |
| POST | /api/v1/career/projects | Create |
| GET | /api/v1/career/projects/{id} | Single |
| PATCH | /api/v1/career/projects/{id} | Update |
| DELETE | /api/v1/career/projects/{id} | Delete |
| GET | /api/v1/career/applications | List (filter: stage, archived) |
| POST | /api/v1/career/applications | Create |
| GET | /api/v1/career/applications/pipeline | Kanban shape |
| GET | /api/v1/career/applications/{id} | Single |
| PATCH | /api/v1/career/applications/{id} | Update |
| DELETE | /api/v1/career/applications/{id} | Delete |
| POST | /api/v1/career/applications/{id}/stage | Update stage |
| GET | /api/v1/career/contacts | List |
| POST | /api/v1/career/contacts | Create |
| GET | /api/v1/career/contacts/followups | Followup queue |
| GET | /api/v1/career/contacts/{id} | Single |
| PATCH | /api/v1/career/contacts/{id} | Update |
| DELETE | /api/v1/career/contacts/{id} | Delete |
| POST | /api/v1/career/contacts/{id}/draft-message | Gemini outreach |
| GET | /api/v1/career/opportunities | List |
| POST | /api/v1/career/opportunities | Create |
| GET | /api/v1/career/opportunities/{id} | Single |
| PATCH | /api/v1/career/opportunities/{id} | Update |
| DELETE | /api/v1/career/opportunities/{id} | Delete |
| POST | /api/v1/career/opportunities/{id}/convert | Create application |

---

## Frontend Routes + Component Paths

| Route | Component |
|-------|-----------|
| /career | frontend/web/src/pages/career/CareerDashboardPage.tsx |
| /career/coach | frontend/web/src/pages/career/CareerCoachPage.tsx |
| /career/problems | frontend/web/src/pages/career/ProblemsPage.tsx |
| /career/projects | frontend/web/src/pages/career/ProjectsPage.tsx |
| /career/applications | frontend/web/src/pages/career/ApplicationsKanbanPage.tsx |
| /career/opportunities | frontend/web/src/pages/career/OpportunitiesPage.tsx |
| /career/network | frontend/web/src/pages/career/NetworkPage.tsx |

Supporting components:
- `frontend/web/src/components/OSModeSwitcher.tsx`
- `frontend/web/src/hooks/useCareerDashboard.ts`

---

## Sidebar Mode Switcher — 5 Bullets

1. `OSModeSwitcher` is mounted directly below the logo block in `layout/Sidebar.tsx`
2. Current mode derived from `useLocation().pathname` — `/career*` maps to `career`, else `william`
3. Active pill: `bg-indigo-500/20 text-indigo-300 border border-indigo-400/40`, inactive: `text-text-secondary hover:bg-surface-raised`
4. On Career pill click: navigate to `localStorage.getItem('wos.lastCareerRoute') ?? '/career'`; on William pill: `localStorage.getItem('wos.lastWilliamRoute') ?? '/dashboard'`
5. Sidebar `useEffect` on pathname persists current path to the matching `wos.last*Route` key

---

## Commit Plan

1. `docs(career): sprint 1 plan` — this file
2. `feat(career): add career schema, models, empty routes module` — Phase 2 (migration + models + schemas + empty routes)
3. `feat(career): routes, services, score algorithm, celery beat` — Phase 3
4. `feat(career): sidebar mode switcher, dashboard page, score ring` — Phase 4
5. `feat(career): applications kanban with drag-to-stage` — Phase 5
6. `feat(career): problems page with streak and heatmap` — Phase 6a
7. `feat(career): projects grid` — Phase 6b
8. `feat(career): network CRM with gemini outreach draft` — Phase 6c
9. `feat(career): opportunities inbox with convert flow` — Phase 6d
