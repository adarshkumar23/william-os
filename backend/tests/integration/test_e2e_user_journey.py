"""
WILLIAM OS - End-to-end integration journey tests.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import TYPE_CHECKING

import pytest

from app.core.security import decrypt_text

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_authenticated_user_journey_and_lifetime_export(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "e2e@william.os",
            "username": "e2euser",
            "password": "StrongPass1",
            "full_name": "E2E User",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "e2e@william.os",
            "password": "StrongPass1",
            "device_name": "E2E Browser",
            "device_type": "web",
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200

    habit_response = await client.post(
        "/api/v1/habits",
        json={"name": "Deep Work"},
        headers=headers,
    )
    assert habit_response.status_code == 201
    habit_id = habit_response.json()["data"]["id"]

    checkin_response = await client.post(
        f"/api/v1/habits/{habit_id}/check-in",
        json={"completed": True, "skipped": False},
        headers=headers,
    )
    assert checkin_response.status_code == 200

    journal_passphrase = "E2EPassphrase"
    journal_create = await client.post(
        "/api/v1/journal",
        json={
            "content": "Today was productive.",
            "passphrase": journal_passphrase,
            "tags": ["e2e"],
        },
        headers=headers,
    )
    assert journal_create.status_code == 201
    journal_id = journal_create.json()["data"]["id"]

    journal_list = await client.get("/api/v1/journal", headers=headers)
    assert journal_list.status_code == 200
    assert len(journal_list.json()["data"]) >= 1

    journal_read = await client.post(
        f"/api/v1/journal/{journal_id}/read",
        json={"passphrase": journal_passphrase},
        headers=headers,
    )
    assert journal_read.status_code == 200
    assert journal_read.json()["data"]["content"] == "Today was productive."

    medicine_create = await client.post(
        "/api/v1/medicine",
        json={
            "name": "Omega 3",
            "dosage": "1 capsule",
            "reminder_times": ["09:00"],
        },
        headers=headers,
    )
    assert medicine_create.status_code == 201
    medicine_id = medicine_create.json()["data"]["id"]

    medicine_log = await client.post(
        f"/api/v1/medicine/{medicine_id}/log",
        params={"log_date": "2026-04-06", "scheduled_time": "09:00:00"},
        json={"taken": True, "skipped": False},
        headers=headers,
    )
    assert medicine_log.status_code == 200

    experiments = await client.get("/api/v1/experiments/assignments", headers=headers)
    assert experiments.status_code == 200
    assignments = experiments.json()["data"]["assignments"]
    assert "dashboard_layout" in assignments

    summary_response = await client.get("/api/v1/export/summary", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()["data"]
    assert summary["habits"] >= 1
    assert summary["journal_entries"] >= 1
    assert summary["medicines"] >= 1

    lifetime_response = await client.post(
        "/api/v1/export/lifetime",
        json={"passphrase": journal_passphrase},
        headers=headers,
    )
    assert lifetime_response.status_code == 200
    assert lifetime_response.headers["content-type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(lifetime_response.content), "r") as archive:
        encrypted_json = archive.read("william_lifetime_export.json.enc")
        encrypted_csv = archive.read("william_lifetime_export.csv.enc")
        manifest = json.loads(archive.read("manifest.json"))

    decrypted_json = decrypt_text(encrypted_json, journal_passphrase)
    decrypted_csv = decrypt_text(encrypted_csv, journal_passphrase)
    parsed_json = json.loads(decrypted_json)

    assert manifest["encryption"].startswith("AES-256-GCM")
    assert parsed_json["summary"]["journal_entries"] >= 1
    assert "dataset,records" in decrypted_csv
