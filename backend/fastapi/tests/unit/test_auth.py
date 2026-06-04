"""Tests pour le système d'authentification ZASKA."""
import pytest
from unittest.mock import patch, MagicMock


class TestRegister:
    def test_register_success(self, client):
        with patch("app.services.auth_service.redis_sync") as mock_redis:
            mock_redis.setex.return_value = True
            mock_redis.get.return_value = None
            resp = client.post("/api/auth/register", json={
                "phone": "+22891000001",
                "email": "newuser@zaska.app",
                "firstName": "Kofi",
                "lastName": "Agyemang",
                "password": "SecurePass1",
                "role": "client",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_register_duplicate_phone(self, client, test_user):
        with patch("app.services.auth_service.redis_sync") as mock_redis:
            mock_redis.setex.return_value = True
            mock_redis.get.return_value = None
            resp = client.post("/api/auth/register", json={
                "phone": test_user.phone,
                "email": "other@zaska.app",
                "firstName": "Dup",
                "lastName": "User",
                "password": "SecurePass1",
                "role": "client",
            })
        assert resp.status_code == 400

    def test_register_weak_password(self, client):
        resp = client.post("/api/auth/register", json={
            "phone": "+22891000002",
            "email": "weak@zaska.app",
            "firstName": "Test",
            "lastName": "User",
            "password": "weak",
            "role": "client",
        })
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client, test_user):
        with patch("app.services.auth_service.redis_sync") as mock_redis:
            mock_redis.get.return_value = None
            resp = client.post("/api/auth/login", json={
                "email": test_user.email,
                "password": "TestPass1",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "accessToken" in data["data"]
        assert "refreshToken" in data["data"]

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "WrongPass1",
        })
        assert resp.status_code == 401

    def test_login_unknown_phone(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "unknown@zaska.app",
            "password": "TestPass1",
        })
        assert resp.status_code == 401


class TestAuthProtection:
    def test_protected_route_no_token(self, client):
        resp = client.get("/api/wallet/balance/USD")
        assert resp.status_code == 401

    def test_protected_route_with_token(self, client, auth_headers):
        with patch("app.api.deps.redis_sync") as mock_redis:
            mock_redis.get.return_value = None
            resp = client.get("/api/wallet/balance/USD", headers=auth_headers)
        assert resp.status_code in (200, 404)  # 404 si wallet pas créé

    def test_admin_route_blocked_for_user(self, client, auth_headers):
        with patch("app.api.deps.redis_sync") as mock_redis:
            mock_redis.get.return_value = None
            resp = client.get("/api/admin/payouts", headers=auth_headers)
        assert resp.status_code == 403

    def test_admin_route_accessible_for_admin(self, client, admin_headers):
        with patch("app.api.deps.redis_sync") as mock_redis:
            mock_redis.get.return_value = None
            resp = client.get("/api/admin/payouts", headers=admin_headers)
        assert resp.status_code == 200
