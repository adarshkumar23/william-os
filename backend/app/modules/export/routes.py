"""
WILLIAM OS — Export Routes
GDPR-style user data export and account deletion endpoints.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from typing import Annotated

from app.core.database import get_db
from app.core.security import verify_password
from app.modules.auth.models import User
from app.modules.auth.routes import get_current_user_id
from app.modules.export.service import ExportService
from app.shared.types import AuthenticationError, NotFoundError, success
from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/export", tags=["Data Export"])


class JournalExportRequest(BaseModel):
    passphrase: str = Field(min_length=4, max_length=256)


class LifetimeExportRequest(BaseModel):
    passphrase: str = Field(min_length=4, max_length=256)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1)


UserIdDep = Annotated[uuid.UUID, Depends(get_current_user_id)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
DeleteRequestDep = Annotated[AccountDeleteRequest, Body(...)]


@router.get("/summary")
async def export_summary(
    user_id: UserIdDep,
    db: DbSessionDep,
) -> dict:
    service = ExportService(db)
    summary = await service.get_data_summary(user_id=user_id)
    return success(summary)


@router.post("/full")
async def export_full(
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_full(user_id=user_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_full_export_{timestamp}.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit-log.csv")
async def export_audit_log_csv(
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_audit_csv(user_id=user_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_audit_log_{timestamp}.csv"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/journal")
async def export_journal(
    request: JournalExportRequest,
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_journal(user_id=user_id, passphrase=request.passphrase)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_journal_export_{timestamp}.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/lifetime")
async def export_lifetime(
    request: LifetimeExportRequest,
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_lifetime(user_id=user_id, passphrase=request.passphrase)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_lifetime_export_{timestamp}.zip"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/weekly.pdf")
async def export_weekly_report_pdf(
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_weekly_report_pdf(user_id=user_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_weekly_report_{timestamp}.pdf"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/monthly.pdf")
async def export_monthly_report_pdf(
    user_id: UserIdDep,
    db: DbSessionDep,
):
    service = ExportService(db)
    payload = await service.export_monthly_report_pdf(user_id=user_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_monthly_report_{timestamp}.pdf"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/pdf")
async def export_custom_report_pdf(
    user_id: UserIdDep,
    db: DbSessionDep,
    days: int = 30,
):
    service = ExportService(db)
    payload = await service.export_report_pdf(user_id=user_id, days=days, title="Custom Report")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"william_report_{days}d_{timestamp}.pdf"
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/account")
async def delete_account(
    request: DeleteRequestDep,
    user_id: UserIdDep,
    db: DbSessionDep,
) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User", str(user_id))

    if not verify_password(request.password, user.hashed_password):
        raise AuthenticationError("Invalid password confirmation")

    service = ExportService(db)
    await service.delete_account(user_id=user_id)
    return success({"deleted": True})
