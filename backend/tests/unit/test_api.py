"""
WILLIAM OS — API Endpoint Tests
Health check and auth flow tests.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "timestamp" in data


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@william.os",
            "username": "newuser",
            "password": "StrongPass1",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["ok"] is True
        assert data["data"]["email"] == "new@william.os"
        assert data["data"]["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_register_weak_password_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@william.os",
            "username": "weakuser",
            "password": "nodigits",
            "full_name": "Weak User",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_email_rejected(self, client: AsyncClient):
        payload = {
            "email": "dupe@william.os",
            "username": "dupeuser1",
            "password": "StrongPass1",
            "full_name": "Dupe User",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        payload["username"] = "dupeuser2"
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        # Register first
        await client.post("/api/v1/auth/register", json={
            "email": "login@william.os",
            "username": "loginuser",
            "password": "StrongPass1",
            "full_name": "Login User",
        })

        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@william.os",
            "password": "StrongPass1",
            "device_name": "Test Device",
            "device_type": "web",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "badlogin@william.os",
            "username": "badloginuser",
            "password": "StrongPass1",
            "full_name": "Bad Login",
        })

        resp = await client.post("/api/v1/auth/login", json={
            "email": "badlogin@william.os",
            "password": "WrongPass1",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 422  # Missing Authorization header

    @pytest.mark.asyncio
    async def test_get_me_with_token(self, client: AsyncClient):
        # Register + Login
        await client.post("/api/v1/auth/register", json={
            "email": "me@william.os",
            "username": "meuser",
            "password": "StrongPass1",
            "full_name": "Me User",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "me@william.os",
            "password": "StrongPass1",
        })
        token = login_resp.json()["data"]["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["email"] == "me@william.os"

    @pytest.mark.asyncio
    async def test_token_refresh(self, client: AsyncClient):
        await client.post("/api/v1/auth/register", json={
            "email": "refresh@william.os",
            "username": "refreshuser",
            "password": "StrongPass1",
            "full_name": "Refresh User",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "refresh@william.os",
            "password": "StrongPass1",
        })
        refresh_token = login_resp.json()["data"]["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "access_token" in data["data"]
        # New tokens should be different
        assert data["data"]["refresh_token"] != refresh_token
