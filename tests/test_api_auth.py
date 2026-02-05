"""Tests for API authentication."""

import sys
from unittest.mock import patch

sys.path.insert(0, ".")

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_engine_manager
from src.api.state import EngineManager


@pytest.fixture
def mgr():
    return EngineManager()


@pytest.fixture
def client(mgr):
    app.dependency_overrides[get_engine_manager] = lambda: mgr
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAuthDisabled:
    @patch("src.api.auth.API_KEY", "")
    def test_all_routes_accessible_without_key(self, client):
        """When API_KEY is empty, auth is disabled."""
        resp = client.get("/api/account")
        # Should get 400 (no broker), not 401
        assert resp.status_code != 401

    @patch("src.api.auth.API_KEY", "")
    def test_health_always_accessible(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthEnabled:
    @patch("src.api.auth.API_KEY", "test-secret-key")
    def test_401_without_key(self, client):
        resp = client.get("/api/account")
        assert resp.status_code == 401

    @patch("src.api.auth.API_KEY", "test-secret-key")
    def test_401_wrong_key(self, client):
        resp = client.get("/api/account", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    @patch("src.api.auth.API_KEY", "test-secret-key")
    def test_200_with_header_key(self, client):
        resp = client.get("/api/account", headers={"X-API-Key": "test-secret-key"})
        # Should get 400 (no broker), not 401
        assert resp.status_code != 401

    @patch("src.api.auth.API_KEY", "test-secret-key")
    def test_200_with_query_key(self, client):
        resp = client.get("/api/account?api_key=test-secret-key")
        # Should get 400 (no broker), not 401
        assert resp.status_code != 401
