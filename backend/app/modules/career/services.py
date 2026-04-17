"""
WILLIAM OS — Career Services
Business logic: score algorithm, CRUD helpers, Gemini outreach.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.career.models import (
    Application,
    Contact,
    Opportunity,
    Problem,
    Project,
    ScoreSnapshot,
)
from app.modules.career.schemas import (
    ApplicationCreate,
    ApplicationStageUpdate,
    ApplicationUpdate,
    ContactCreate,
    ContactUpdate,
    OpportunityCreate,
    OpportunityUpdate,
    ProblemCreate,
    ProblemUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.shared.types import NotFoundError

logger = structlog.get_logger(__name__)
settings = get_settings()


# ── Score Algorithm ────────────────────────────────────────────────


async def compute_career_score(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Compute career score (0-100) and persist as today's snapshot. Upserts on conflict."""
    today = date.today()

    # DSA component (max 25)
    problems_solved = await db.scalar(
        select(func.count(Problem.id)).where(
            Problem.user_id == user_id,
            Problem.solved_at.isnot(None),
        )
    ) or 0
    dsa = min(25, round((problems_solved / 400) * 25))

    # Projects component (max 25)
    projects_result = await db.execute(
        select(Project.status, Project.on_resume).where(Project.user_id == user_id)
    )
    projects_rows = projects_result.all()
    deployed_count = sum(1 for r in projects_rows if r.status in ("deployed", "on_resume"))
    on_resume_count = sum(1 for r in projects_rows if r.on_resume)
    projects = min(25, deployed_count * 4 + on_resume_count)

    # Applications component (max 20)
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    applied_last_30d = await db.scalar(
        select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.stage.in_(["applied", "oa", "interview", "offer"]),
            Application.stage_updated_at >= cutoff_30d,
            Application.archived.is_(False),
        )
    ) or 0
    has_active = await db.scalar(
        select(func.count(Application.id)).where(
            Application.user_id == user_id,
            Application.stage.in_(["interview", "offer"]),
            Application.archived.is_(False),
        )
    ) or 0
    applications = min(20, applied_last_30d * 2) + (5 if has_active > 0 else 0)
    applications = min(20, applications)

    # Network component (max 15)
    contacts_count = await db.scalar(
        select(func.count(Contact.id)).where(Contact.user_id == user_id)
    ) or 0
    network = min(15, round(contacts_count * 0.3))

    # CP component (max 15) — read cf_rating from latest snapshot
    latest_snap = await db.scalar(
        select(ScoreSnapshot).where(ScoreSnapshot.user_id == user_id)
        .order_by(ScoreSnapshot.snapshot_date.desc())
        .limit(1)
    )
    cf_rating = 0
    if latest_snap and isinstance(latest_snap.components, dict):
        cf_rating = int(latest_snap.components.get("cf_rating", 0) or 0)
    cp = max(0, min(15, round((cf_rating - 800) / 600 * 15)))

    overall = dsa + projects + applications + network + cp
    components = {
        "dsa": dsa,
        "projects": projects,
        "applications": applications,
        "network": network,
        "cp": cp,
        "cf_rating": cf_rating,
        "problems_solved": problems_solved,
        "deployed_count": deployed_count,
        "on_resume_count": on_resume_count,
        "contacts_count": contacts_count,
    }

    # Upsert the snapshot
    stmt = (
        insert(ScoreSnapshot)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            snapshot_date=today,
            overall_score=overall,
            components=components,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        .on_conflict_do_update(
            constraint="uq_score_snapshots_user_date",
            set_={"overall_score": overall, "components": components, "updated_at": datetime.utcnow()},
        )
    )
    await db.execute(stmt)
    await db.commit()

    logger.info("career_score_computed", user_id=str(user_id), overall=overall)
    return {"overall": overall, "components": components, "snapshot_date": today.isoformat()}


# ── Problems ───────────────────────────────────────────────────────


class ProblemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, data: ProblemCreate) -> Problem:
        obj = Problem(
            user_id=user_id,
            **data.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list(
        self,
        user_id: uuid.UUID,
        platform: str | None = None,
        difficulty: str | None = None,
        topic: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Problem]:
        q = select(Problem).where(Problem.user_id == user_id)
        if platform:
            q = q.where(Problem.platform == platform)
        if difficulty:
            q = q.where(Problem.difficulty == difficulty)
        if topic:
            q = q.where(Problem.topics.contains([topic]))
        if date_from:
            q = q.where(Problem.solved_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            q = q.where(Problem.solved_at <= datetime.combine(date_to, datetime.max.time()))
        q = q.order_by(Problem.solved_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get(self, user_id: uuid.UUID, problem_id: uuid.UUID) -> Problem:
        obj = await self.db.scalar(
            select(Problem).where(Problem.id == problem_id, Problem.user_id == user_id)
        )
        if not obj:
            raise NotFoundError("Problem", str(problem_id))
        return obj

    async def update(self, user_id: uuid.UUID, problem_id: uuid.UUID, data: ProblemUpdate) -> Problem:
        obj = await self.get(user_id, problem_id)
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, user_id: uuid.UUID, problem_id: uuid.UUID) -> None:
        obj = await self.get(user_id, problem_id)
        await self.db.delete(obj)
        await self.db.commit()


# ── Projects ───────────────────────────────────────────────────────


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, data: ProjectCreate) -> Project:
        obj = Project(user_id=user_id, **data.model_dump(), created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list(self, user_id: uuid.UUID) -> list[Project]:
        result = await self.db.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, user_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        obj = await self.db.scalar(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        if not obj:
            raise NotFoundError("Project", str(project_id))
        return obj

    async def update(self, user_id: uuid.UUID, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        obj = await self.get(user_id, project_id)
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        obj = await self.get(user_id, project_id)
        await self.db.delete(obj)
        await self.db.commit()


# ── Applications ───────────────────────────────────────────────────


class ApplicationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, data: ApplicationCreate) -> Application:
        obj = Application(
            user_id=user_id,
            **data.model_dump(),
            stage_updated_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_all(
        self,
        user_id: uuid.UUID,
        stage: str | None = None,
        archived: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Application]:
        q = select(Application).where(
            Application.user_id == user_id,
            Application.archived.is_(archived),
        )
        if stage:
            q = q.where(Application.stage == stage)
        q = q.order_by(Application.stage_updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_pipeline(self, user_id: uuid.UUID) -> dict[str, list[Application]]:
        stages = ["researching", "applied", "oa", "interview", "offer", "rejected"]
        result = await self.db.execute(
            select(Application).where(
                Application.user_id == user_id,
                Application.archived.is_(False),
            ).order_by(Application.stage_updated_at.desc())
        )
        apps = list(result.scalars().all())
        pipeline: dict[str, list[Application]] = {s: [] for s in stages}
        for app in apps:
            if app.stage in pipeline:
                pipeline[app.stage].append(app)
        return pipeline

    async def get(self, user_id: uuid.UUID, application_id: uuid.UUID) -> Application:
        obj = await self.db.scalar(
            select(Application).where(Application.id == application_id, Application.user_id == user_id)
        )
        if not obj:
            raise NotFoundError("Application", str(application_id))
        return obj

    async def update(self, user_id: uuid.UUID, application_id: uuid.UUID, data: ApplicationUpdate) -> Application:
        obj = await self.get(user_id, application_id)
        payload = data.model_dump(exclude_none=True)
        if "stage" in payload and payload["stage"] != obj.stage:
            payload["stage_updated_at"] = datetime.utcnow()
        for k, v in payload.items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update_stage(
        self, user_id: uuid.UUID, application_id: uuid.UUID, data: ApplicationStageUpdate
    ) -> tuple[Application, str]:
        obj = await self.get(user_id, application_id)
        old_stage = obj.stage
        obj.stage = data.stage
        obj.stage_updated_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj, old_stage

    async def delete(self, user_id: uuid.UUID, application_id: uuid.UUID) -> None:
        obj = await self.get(user_id, application_id)
        await self.db.delete(obj)
        await self.db.commit()


# ── Contacts ────────────────────────────────────────────────────────


class ContactService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, data: ContactCreate) -> Contact:
        obj = Contact(user_id=user_id, **data.model_dump(), created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_all(self, user_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[Contact]:
        result = await self.db.execute(
            select(Contact).where(Contact.user_id == user_id)
            .order_by(Contact.name)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_followups(self, user_id: uuid.UUID) -> list[Contact]:
        today = date.today()
        cutoff_30d = today - timedelta(days=30)
        result = await self.db.execute(
            select(Contact).where(
                Contact.user_id == user_id,
                or_(
                    Contact.next_followup_at <= today,
                    and_(
                        Contact.last_contacted_at <= cutoff_30d,
                        Contact.temperature.in_(["warm", "hot"]),
                    ),
                ),
            ).order_by(Contact.next_followup_at.asc())
        )
        return list(result.scalars().all())

    async def get(self, user_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
        obj = await self.db.scalar(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
        )
        if not obj:
            raise NotFoundError("Contact", str(contact_id))
        return obj

    async def update(self, user_id: uuid.UUID, contact_id: uuid.UUID, data: ContactUpdate) -> Contact:
        obj = await self.get(user_id, contact_id)
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, user_id: uuid.UUID, contact_id: uuid.UUID) -> None:
        obj = await self.get(user_id, contact_id)
        await self.db.delete(obj)
        await self.db.commit()

    async def draft_message(self, contact: Contact, context: str | None = None) -> str:
        """Generate a 3-sentence Gemini outreach draft."""
        import google.generativeai as genai  # type: ignore[import]

        genai.configure(api_key=settings.gemini_api_key.get_secret_value())
        model = genai.GenerativeModel(settings.gemini_model)

        contact_info = f"Name: {contact.name}"
        if contact.company:
            contact_info += f", Company: {contact.company}"
        if contact.role:
            contact_info += f", Role: {contact.role}"
        if contact.relationship_notes:
            contact_info += f", Notes: {contact.relationship_notes}"

        prompt = (
            f"Write a concise, warm 3-sentence professional outreach message to {contact.name}. "
            f"Contact info: {contact_info}. "
        )
        if context:
            prompt += f"Context: {context}. "
        prompt += "Be genuine and brief. Return only the message text, no subject line."

        response = await model.generate_content_async(prompt)
        return response.text.strip()


# ── Opportunities ──────────────────────────────────────────────────


class OpportunityService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, data: OpportunityCreate) -> Opportunity:
        obj = Opportunity(user_id=user_id, **data.model_dump(), created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def list(
        self,
        user_id: uuid.UUID,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Opportunity]:
        q = select(Opportunity).where(Opportunity.user_id == user_id)
        if status:
            q = q.where(Opportunity.status == status)
        if kind:
            q = q.where(Opportunity.kind == kind)
        q = q.order_by(Opportunity.deadline.asc().nullslast()).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get(self, user_id: uuid.UUID, opportunity_id: uuid.UUID) -> Opportunity:
        obj = await self.db.scalar(
            select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.user_id == user_id)
        )
        if not obj:
            raise NotFoundError("Opportunity", str(opportunity_id))
        return obj

    async def update(self, user_id: uuid.UUID, opportunity_id: uuid.UUID, data: OpportunityUpdate) -> Opportunity:
        obj = await self.get(user_id, opportunity_id)
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, user_id: uuid.UUID, opportunity_id: uuid.UUID) -> None:
        obj = await self.get(user_id, opportunity_id)
        await self.db.delete(obj)
        await self.db.commit()

    async def convert(
        self, user_id: uuid.UUID, opportunity_id: uuid.UUID, role: str, platform: str | None
    ) -> Application:
        opp = await self.get(user_id, opportunity_id)
        app = Application(
            user_id=user_id,
            company=opp.source or opp.title,
            role=role,
            platform=platform,
            stage="researching",
            stage_updated_at=datetime.utcnow(),
            notes=opp.description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(app)
        await self.db.flush()

        opp.status = "converted"
        opp.converted_to_application_id = app.id
        opp.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(app)
        return app


# ── Dashboard ──────────────────────────────────────────────────────


async def get_career_dashboard(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Assemble the full dashboard payload."""
    score_data = await compute_career_score(db, user_id)

    # Last 7 snapshots for momentum
    history_result = await db.execute(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.user_id == user_id)
        .order_by(ScoreSnapshot.snapshot_date.desc())
        .limit(7)
    )
    history = [
        {"date": s.snapshot_date.isoformat(), "score": s.overall_score}
        for s in history_result.scalars().all()
    ]

    # Pipeline preview (top 3 per stage)
    pipeline_result = await db.execute(
        select(Application).where(
            Application.user_id == user_id,
            Application.archived.is_(False),
        ).order_by(Application.stage_updated_at.desc()).limit(20)
    )
    apps = list(pipeline_result.scalars().all())
    pipeline_preview: dict[str, list[dict]] = {}
    for app in apps:
        if app.stage not in pipeline_preview:
            pipeline_preview[app.stage] = []
        if len(pipeline_preview[app.stage]) < 3:
            pipeline_preview[app.stage].append({
                "id": str(app.id),
                "company": app.company,
                "role": app.role,
                "platform": app.platform,
                "stage": app.stage,
            })

    # Recent opportunities
    opp_result = await db.execute(
        select(Opportunity).where(
            Opportunity.user_id == user_id,
            Opportunity.status == "inbox",
        ).order_by(Opportunity.deadline.asc().nullslast()).limit(5)
    )
    recent_opps = [
        {
            "id": str(o.id),
            "title": o.title,
            "kind": o.kind,
            "deadline": o.deadline.isoformat() if o.deadline else None,
        }
        for o in opp_result.scalars().all()
    ]

    # Stats
    components = score_data["components"]
    stats = {
        "problems_solved": components.get("problems_solved", 0),
        "deployed_projects": components.get("deployed_count", 0),
        "active_applications": await db.scalar(
            select(func.count(Application.id)).where(
                Application.user_id == user_id,
                Application.stage.in_(["applied", "oa", "interview"]),
                Application.archived.is_(False),
            )
        ) or 0,
        "contacts": components.get("contacts_count", 0),
        "cf_rating": components.get("cf_rating", 0),
    }

    # Simple warnings
    warnings: list[str] = []
    if stats["problems_solved"] < 50:
        warnings.append("DSA practice is low — aim for 50+ solved problems")
    if stats["deployed_projects"] == 0:
        warnings.append("No deployed projects yet — build something shippable")
    if stats["active_applications"] == 0:
        warnings.append("No active applications — start applying")

    return {
        "score": score_data,
        "score_history": history,
        "stats": stats,
        "pipeline_preview": pipeline_preview,
        "recent_opportunities": recent_opps,
        "warnings": warnings,
    }
