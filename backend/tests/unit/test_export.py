"""
WILLIAM OS - Export Module Tests
Covers summary/full/journal export and account deletion privacy workflow.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, time
from typing import TYPE_CHECKING

import pytest
from app.core.security import create_access_token, decrypt_text, encrypt_text
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.auth.models import User
from app.modules.export.service import ExportService
from app.modules.habits.models import Habit, HabitCheckIn
from app.modules.journal.models import JournalEntry
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.scheduler.models import BlockCategory, DailyPlan, RescheduleEvent, ScheduleBlock
from sqlalchemy import func, select

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


def _auth_headers(user_id) -> dict[str, str]:
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _seed_user_data(db_session: AsyncSession, user_id, passphrase: str) -> None:
    db_session.add_all(
        [
            JournalEntry(
                user_id=user_id,
                entry_date=date.today(),
                encrypted_content=encrypt_text("Today I made progress.", passphrase),
                encrypted_summary=encrypt_text("Progress day", passphrase),
                tags=["focus", "growth"],
                word_count=4,
            ),
        ]
    )

    habit = Habit(user_id=user_id, name="Meditate")
    db_session.add(habit)
    await db_session.flush()

    db_session.add(
        HabitCheckIn(
            habit_id=habit.id,
            check_date=date.today(),
            completed=True,
        )
    )

    medicine = Medicine(user_id=user_id, name="Vitamin D", dosage="2000 IU")
    db_session.add(medicine)
    await db_session.flush()

    db_session.add(
        MedicineLog(
            medicine_id=medicine.id,
            log_date=date.today(),
            scheduled_time=time(8, 0),
            taken=True,
        )
    )

    plan = DailyPlan(user_id=user_id, plan_date=date.today())
    db_session.add(plan)
    await db_session.flush()

    db_session.add(
        ScheduleBlock(
            plan_id=plan.id,
            title="Deep Work",
            category=BlockCategory.WORK,
            start_time=time(9, 0),
            end_time=time(10, 0),
            duration_minutes=60,
        )
    )
    db_session.add(
        RescheduleEvent(
            plan_id=plan.id,
            trigger="manual",
            old_schedule={"start": "09:00"},
            new_schedule={"start": "10:00"},
        )
    )
    await db_session.flush()


class TestExportRoutes:
    @pytest.mark.asyncio
    async def test_export_summary_counts_user_data(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        passphrase = "JournalPass123"
        await _seed_user_data(db_session, test_user.id, passphrase)

        response = await client.get(
            "/api/v1/export/summary",
            headers=_auth_headers(test_user.id),
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        summary = payload["data"]
        assert summary["journal_entries"] == 1
        assert summary["habits"] == 1
        assert summary["habit_check_ins"] == 1
        assert summary["medicines"] == 1
        assert summary["medicine_logs"] == 1
        assert summary["schedule_plans"] == 1
        assert summary["schedule_blocks"] == 1
        assert summary["reschedule_events"] == 1
        assert summary["total_records"] >= 8

    @pytest.mark.asyncio
    async def test_export_full_returns_zip_payload(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        passphrase = "JournalPass123"
        await _seed_user_data(db_session, test_user.id, passphrase)

        response = await client.post(
            "/api/v1/export/full",
            headers=_auth_headers(test_user.id),
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")

        with io.BytesIO(response.content) as buffer, zipfile.ZipFile(buffer, "r") as archive:
            assert "william_export_full.json" in archive.namelist()
            payload = json.loads(archive.read("william_export_full.json"))

        assert payload["user_id"] == str(test_user.id)
        assert payload["summary"]["journal_entries"] == 1
        assert len(payload["data"]["auth_profile"]) == 1
        assert len(payload["data"]["journal_metadata"]) == 1
        assert len(payload["data"]["schedule_blocks"]) == 1

    @pytest.mark.asyncio
    async def test_export_journal_decrypts_entry_content(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        passphrase = "JournalPass123"
        await _seed_user_data(db_session, test_user.id, passphrase)

        response = await client.post(
            "/api/v1/export/journal",
            headers=_auth_headers(test_user.id),
            json={"passphrase": passphrase},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
            assert "william_export_journal.json" in archive.namelist()
            payload = json.loads(archive.read("william_export_journal.json"))

        assert payload["entry_count"] == 1
        assert payload["entries"][0]["content"] == "Today I made progress."
        assert payload["entries"][0]["summary"] == "Progress day"

    @pytest.mark.asyncio
    async def test_export_lifetime_returns_encrypted_json_and_csv(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        passphrase = "JournalPass123"
        await _seed_user_data(db_session, test_user.id, passphrase)

        response = await client.post(
            "/api/v1/export/lifetime",
            headers=_auth_headers(test_user.id),
            json={"passphrase": passphrase},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
            encrypted_json = archive.read("william_lifetime_export.json.enc")
            encrypted_csv = archive.read("william_lifetime_export.csv.enc")
            manifest = json.loads(archive.read("manifest.json"))

        decrypted_json = decrypt_text(encrypted_json, passphrase)
        decrypted_csv = decrypt_text(encrypted_csv, passphrase)
        parsed_json = json.loads(decrypted_json)

        assert manifest["encryption"].startswith("AES-256-GCM")
        assert parsed_json["summary"]["journal_entries"] == 1
        assert "dataset,records" in decrypted_csv

    @pytest.mark.asyncio
    async def test_delete_account_cascades_and_creates_system_audit_log(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        passphrase = "JournalPass123"
        await _seed_user_data(db_session, test_user.id, passphrase)

        response = await client.request(
            "DELETE",
            "/api/v1/export/account",
            headers=_auth_headers(test_user.id),
            json={"password": "TestPass123"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["deleted"] is True

        user_count = await db_session.scalar(
            select(func.count()).select_from(User).where(User.id == test_user.id)
        )
        habits_count = await db_session.scalar(
            select(func.count()).select_from(Habit).where(Habit.user_id == test_user.id)
        )
        checkins_count = await db_session.scalar(select(func.count()).select_from(HabitCheckIn))
        medicine_count = await db_session.scalar(
            select(func.count()).select_from(Medicine).where(Medicine.user_id == test_user.id)
        )
        medicine_logs_count = await db_session.scalar(select(func.count()).select_from(MedicineLog))
        journal_count = await db_session.scalar(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.user_id == test_user.id)
        )
        plans_count = await db_session.scalar(
            select(func.count()).select_from(DailyPlan).where(DailyPlan.user_id == test_user.id)
        )
        blocks_count = await db_session.scalar(select(func.count()).select_from(ScheduleBlock))
        reschedule_count = await db_session.scalar(
            select(func.count()).select_from(RescheduleEvent)
        )

        assert user_count == 0
        assert habits_count == 0
        assert checkins_count == 0
        assert medicine_count == 0
        assert medicine_logs_count == 0
        assert journal_count == 0
        assert plans_count == 0
        assert blocks_count == 0
        assert reschedule_count == 0

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.user_id.is_(None),
                AuditLog.action == AuditAction.DATA_DELETE,
            )
        )
        system_logs = result.scalars().all()
        assert len(system_logs) == 1
        assert system_logs[0].details["deleted_user_id"] == str(test_user.id)
        assert system_logs[0].details["verified"] is True

        service = ExportService(db_session)
        summary = await service.get_data_summary(test_user.id)
        assert summary["total_records"] == 0
