"""Security review M2-M4: API v1 switch and startup warnings for an unsafe deployment."""
import pytest

from app.core.deploy_checks import deployment_warnings
from tests.conftest import PASSWORD


def test_v1_is_on_by_default(make_client):
    with make_client() as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401  # reached the route, not switched off


def test_v1_off_refuses_routes_but_not_health(make_client):
    with make_client({"api": {"v1_enabled": False}}) as client:
        assert client.get("/api/v1/health").status_code == 200
        for method, path in [("get", "/api/v1/auth/me"), ("get", "/api/v1/topics"),
                             ("post", "/api/v1/auth/login"), ("put", "/api/v1/admin/config")]:
            r = getattr(client, method)(path)
            assert r.status_code == 404, path
            assert r.json()["code"] == "not_found"


def test_v1_off_leaves_v2_working(make_client):
    with make_client({"api": {"v1_enabled": False}}) as client:
        services = client.app.state.services
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        assert client.get("/api/v2/auth/csrf").status_code == 200
        r = client.post("/api/v2/auth/login", json={"username": "prof", "password": PASSWORD})
        assert r.status_code == 200
        assert client.get("/api/v2/auth/me").status_code == 200


def _settings(use_config, monkeypatch, **env):
    for name in ("VLLM_BASE_URL", "VLLM_KEY", "SITE_ADDRESS"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return use_config()


def test_no_warnings_for_local_defaults(use_config, monkeypatch):
    s = _settings(use_config, monkeypatch, VLLM_BASE_URL="http://127.0.0.1:8001/v1", SITE_ADDRESS=":80")
    assert deployment_warnings(s) == []


@pytest.mark.parametrize("url", ["http://vllm:8000/v1", "http://192.168.1.5:8000/v1", "http://gpu.local/v1"])
def test_private_vllm_without_key_is_fine(use_config, monkeypatch, url):
    assert deployment_warnings(_settings(use_config, monkeypatch, VLLM_BASE_URL=url)) == []


def test_public_vllm_needs_https_and_key(use_config, monkeypatch):
    s = _settings(use_config, monkeypatch, VLLM_BASE_URL="http://93.184.216.34:8000/v1")
    assert len(deployment_warnings(s)) == 2
    s = _settings(use_config, monkeypatch, VLLM_BASE_URL="https://pod-8000.proxy.example.com/v1",
                  VLLM_KEY="k")
    assert deployment_warnings(s) == []
    s = _settings(use_config, monkeypatch, VLLM_BASE_URL="https://pod-8000.proxy.example.com/v1")
    assert len(deployment_warnings(s)) == 1


def test_https_site_without_secure_cookie_warns(use_config, monkeypatch):
    s = _settings(use_config, monkeypatch, SITE_ADDRESS="tutor.example.edu")
    assert len(deployment_warnings(s)) == 1
    s = _settings(use_config, monkeypatch, SITE_ADDRESS="tutor.example.edu", AUTH__COOKIE_SECURE="true")
    assert deployment_warnings(s) == []
