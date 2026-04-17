"""
WILLIAM OS — Career Routes
All career module endpoints. JWT required on every route.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.career.events import (
    emit_application_status_changed,
    emit_career_score_recomputed,
    emit_problem_solved,
)
from app.modules.career.models import ScoreSnapshot
from app.modules.career.schemas import (
    ApplicationCreate,
    ApplicationStageUpdate,
    ApplicationUpdate,
    CFRatingUpdate,
    ContactCreate,
    ContactUpdate,
    OpportunityConvert,
    OpportunityCreate,
    OpportunityUpdate,
    ProblemCreate,
    ProblemUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.modules.career.services import (
    ApplicationService,
    ContactService,
    OpportunityService,
    ProblemService,
    ProjectService,
    compute_career_score,
    get_career_dashboard,
)
from app.shared.types import success

router = APIRouter(prefix="/career", tags=["Career"])


# ── Dashboard & Score ──────────────────────────────────────────────


@router.get("/dashboard")
async def career_dashboard(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await get_career_dashboard(db, user_id)
    return success(data)


@router.get("/score/history")
async def score_history(
    days: int = Query(default=30, ge=7, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import timedelta
    from datetime import datetime as dt

    cutoff = dt.utcnow().date() - timedelta(days=days)
    result = await db.execute(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.user_id == user_id, ScoreSnapshot.snapshot_date >= cutoff)
        .order_by(ScoreSnapshot.snapshot_date.asc())
    )
    snapshots = [
        {"date": s.snapshot_date.isoformat(), "score": s.overall_score, "components": s.components}
        for s in result.scalars().all()
    ]
    return success(snapshots)


@router.post("/score/recompute")
async def recompute_score(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    score_data = await compute_career_score(db, user_id)
    await emit_career_score_recomputed(user_id, score_data["overall"], score_data["snapshot_date"])
    return success(score_data)


@router.post("/score/cf-rating")
async def update_cf_rating(
    data: CFRatingUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from datetime import datetime

    latest = await db.scalar(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.user_id == user_id)
        .order_by(ScoreSnapshot.snapshot_date.desc())
        .limit(1)
    )
    components: dict[str, Any] = {}
    if latest and isinstance(latest.components, dict):
        components = dict(latest.components)
    components["cf_rating"] = data.rating

    score_data = await compute_career_score(db, user_id)
    return success({"cf_rating": data.rating, "score": score_data})


# ── Problems ───────────────────────────────────────────────────────


@router.get("/problems")
async def list_problems(
    platform: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProblemService(db)
    items = await svc.list(user_id, platform, difficulty, topic, date_from, date_to, limit, offset)
    return success([_serialize(i) for i in items])


@router.post("/problems", status_code=201)
async def create_problem(
    data: ProblemCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProblemService(db)
    item = await svc.create(user_id, data)
    if data.solved_at:
        await emit_problem_solved(user_id, item.id, data.platform or "manual")
    return success(_serialize(item))


@router.get("/problems/{problem_id}")
async def get_problem(
    problem_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProblemService(db)
    item = await svc.get(user_id, problem_id)
    return success(_serialize(item))


@router.patch("/problems/{problem_id}")
async def update_problem(
    problem_id: uuid.UUID,
    data: ProblemUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProblemService(db)
    item = await svc.update(user_id, problem_id, data)
    return success(_serialize(item))


@router.delete("/problems/{problem_id}")
async def delete_problem(
    problem_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProblemService(db)
    await svc.delete(user_id, problem_id)
    return success({"deleted": True})


# ── Projects ───────────────────────────────────────────────────────


@router.get("/projects")
async def list_projects(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProjectService(db)
    items = await svc.list(user_id)
    return success([_serialize(i) for i in items])


@router.post("/projects", status_code=201)
async def create_project(
    data: ProjectCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProjectService(db)
    item = await svc.create(user_id, data)
    return success(_serialize(item))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProjectService(db)
    item = await svc.get(user_id, project_id)
    return success(_serialize(item))


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProjectService(db)
    item = await svc.update(user_id, project_id, data)
    return success(_serialize(item))


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ProjectService(db)
    await svc.delete(user_id, project_id)
    return success({"deleted": True})


# ── Applications ───────────────────────────────────────────────────


@router.get("/applications/pipeline")
async def get_pipeline(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    pipeline = await svc.get_pipeline(user_id)
    return success({stage: [_serialize(a) for a in apps] for stage, apps in pipeline.items()})


@router.get("/applications")
async def list_applications(
    stage: str | None = Query(default=None),
    archived: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    items = await svc.list(user_id, stage, archived, limit, offset)
    return success([_serialize(i) for i in items])


@router.post("/applications", status_code=201)
async def create_application(
    data: ApplicationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    item = await svc.create(user_id, data)
    return success(_serialize(item))


@router.get("/applications/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    item = await svc.get(user_id, application_id)
    return success(_serialize(item))


@router.patch("/applications/{application_id}")
async def update_application(
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    item = await svc.update(user_id, application_id, data)
    return success(_serialize(item))


@router.delete("/applications/{application_id}")
async def delete_application(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    await svc.delete(user_id, application_id)
    return success({"deleted": True})


@router.post("/applications/{application_id}/stage")
async def update_application_stage(
    application_id: uuid.UUID,
    data: ApplicationStageUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ApplicationService(db)
    item, old_stage = await svc.update_stage(user_id, application_id, data)
    await emit_application_status_changed(user_id, application_id, old_stage, data.stage)
    return success(_serialize(item))


# ── Contacts ────────────────────────────────────────────────────────


@router.get("/contacts/followups")
async def get_followups(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    items = await svc.get_followups(user_id)
    return success([_serialize(i) for i in items])


@router.get("/contacts")
async def list_contacts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    items = await svc.list(user_id, limit, offset)
    return success([_serialize(i) for i in items])


@router.post("/contacts", status_code=201)
async def create_contact(
    data: ContactCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    item = await svc.create(user_id, data)
    return success(_serialize(item))


@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    item = await svc.get(user_id, contact_id)
    return success(_serialize(item))


@router.patch("/contacts/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    item = await svc.update(user_id, contact_id, data)
    return success(_serialize(item))


@router.delete("/contacts/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    await svc.delete(user_id, contact_id)
    return success({"deleted": True})


@router.post("/contacts/{contact_id}/draft-message")
async def draft_outreach_message(
    contact_id: uuid.UUID,
    body: dict = {},
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = ContactService(db)
    contact = await svc.get(user_id, contact_id)
    context = body.get("context") if body else None
    draft = await svc.draft_message(contact, context)
    return success({"draft": draft, "contact_id": str(contact_id)})


# ── Opportunities ──────────────────────────────────────────────────


@router.get("/opportunities")
async def list_opportunities(
    status: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    items = await svc.list(user_id, status, kind, limit, offset)
    return success([_serialize(i) for i in items])


@router.post("/opportunities", status_code=201)
async def create_opportunity(
    data: OpportunityCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    item = await svc.create(user_id, data)
    return success(_serialize(item))


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(
    opportunity_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    item = await svc.get(user_id, opportunity_id)
    return success(_serialize(item))


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: uuid.UUID,
    data: OpportunityUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    item = await svc.update(user_id, opportunity_id, data)
    return success(_serialize(item))


@router.delete("/opportunities/{opportunity_id}")
async def delete_opportunity(
    opportunity_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    await svc.delete(user_id, opportunity_id)
    return success({"deleted": True})


@router.post("/opportunities/{opportunity_id}/convert")
async def convert_opportunity(
    opportunity_id: uuid.UUID,
    data: OpportunityConvert,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = OpportunityService(db)
    app = await svc.convert(user_id, opportunity_id, data.role, data.platform)
    return success(_serialize(app))


# ── Helpers ────────────────────────────────────────────────────────


def _serialize(obj: Any) -> dict:
    """Convert a SQLAlchemy model instance to a JSON-safe dict."""
    from sqlalchemy.inspection import inspect as sa_inspect

    result = {}
    for col in sa_inspect(type(obj)).columns:
        val = getattr(obj, col.key)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        result[col.key] = val
    return result
