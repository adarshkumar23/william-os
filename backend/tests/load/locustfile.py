"""
WILLIAM OS — Load Tests (Locust)
Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

from __future__ import annotations

import json
import random
from datetime import date

from locust import HttpUser, between, task


class WilliamUser(HttpUser):
    wait_time = between(1, 3)
    access_token: str | None = None
    journal_passphrase = "LoadVault123"
    created_habit_id: str | None = None
    created_medicine_id: str | None = None

    def on_start(self):
        """Register and login on spawn."""
        uid = random.randint(100000, 999999)
        email = f"loadtest{uid}@william.os"
        password = "LoadTest1!"

        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"load{uid}",
                "password": password,
                "full_name": f"Load User {uid}",
            },
        )

        resp = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
                "device_name": "Locust",
                "device_type": "web",
            },
        )
        if resp.status_code == 200:
            self.access_token = resp.json()["data"]["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    @task(5)
    def health_check(self):
        self.client.get("/health")

    @task(4)
    def get_profile(self):
        self.client.get("/api/v1/auth/me", headers=self.auth_headers)

    @task(3)
    def get_today_schedule(self):
        self.client.get("/api/v1/schedule/today", headers=self.auth_headers)

    @task(2)
    def export_summary(self):
        self.client.get("/api/v1/export/summary", headers=self.auth_headers)

    @task(1)
    def generate_schedule(self):
        from datetime import timedelta

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.client.post(
            "/api/v1/schedule/generate",
            json={"target_date": tomorrow, "force_regenerate": True},
            headers=self.auth_headers,
        )

    @task(2)
    def habits_flow(self):
        if not self.created_habit_id:
            created = self.client.post(
                "/api/v1/habits",
                json={"name": f"Load Habit {random.randint(1, 9999)}"},
                headers=self.auth_headers,
            )
            if created.status_code in {200, 201}:
                self.created_habit_id = created.json()["data"]["id"]
            return

        self.client.post(
            f"/api/v1/habits/{self.created_habit_id}/check-in",
            json={"completed": True, "skipped": False},
            headers=self.auth_headers,
        )

    @task(2)
    def journal_flow(self):
        self.client.post(
            "/api/v1/journal",
            json={
                "content": "Load test journal entry",
                "passphrase": self.journal_passphrase,
                "tags": ["load"],
            },
            headers=self.auth_headers,
        )
        self.client.get("/api/v1/journal", headers=self.auth_headers)

    @task(1)
    def medicine_flow(self):
        if not self.created_medicine_id:
            created = self.client.post(
                "/api/v1/medicine",
                json={
                    "name": f"LoadMed-{random.randint(1, 9999)}",
                    "dosage": "1 tablet",
                    "reminder_times": ["08:00"],
                },
                headers=self.auth_headers,
            )
            if created.status_code in {200, 201}:
                self.created_medicine_id = created.json()["data"]["id"]
            return

        self.client.post(
            f"/api/v1/medicine/{self.created_medicine_id}/log",
            params={"log_date": date.today().isoformat(), "scheduled_time": "08:00:00"},
            json={"taken": True, "skipped": False},
            headers=self.auth_headers,
        )
