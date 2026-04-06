"""
WILLIAM OS — Load Tests (Locust)
Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

from __future__ import annotations

import json
import random

from locust import HttpUser, between, task


class WilliamUser(HttpUser):
    wait_time = between(1, 3)
    access_token: str | None = None

    def on_start(self):
        """Register and login on spawn."""
        uid = random.randint(100000, 999999)
        email = f"loadtest{uid}@william.os"
        password = "LoadTest1!"

        self.client.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"load{uid}",
            "password": password,
            "full_name": f"Load User {uid}",
        })

        resp = self.client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
            "device_name": "Locust",
            "device_type": "web",
        })
        if resp.status_code == 200:
            self.access_token = resp.json()["data"]["access_token"]

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"} if self.access_token else {}

    @task(5)
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def get_profile(self):
        self.client.get("/api/v1/auth/me", headers=self.auth_headers)

    @task(2)
    def get_today_schedule(self):
        self.client.get("/api/v1/schedule/today", headers=self.auth_headers)

    @task(1)
    def generate_schedule(self):
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.client.post(
            "/api/v1/schedule/generate",
            json={"target_date": tomorrow, "force_regenerate": True},
            headers=self.auth_headers,
        )
