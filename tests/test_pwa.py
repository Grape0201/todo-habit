import json
import pytest
from fastapi.testclient import TestClient

from todo_habit.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TODO_HABIT_DATA_DIR", str(tmp_path))
    with TestClient(create_app(), follow_redirects=False) as c:
        yield c


def test_service_worker_route(client):
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "javascript" in res.headers.get("content-type", "")
    assert "no-cache" in res.headers.get("cache-control", "")
    assert "todo-habit-v1" in res.text


def test_favicon_route(client):
    res = client.get("/favicon.ico")
    assert res.status_code == 200
    assert len(res.content) > 0


def test_manifest_endpoint(client):
    res = client.get("/static/manifest.webmanifest")
    assert res.status_code == 200
    data = json.loads(res.text)
    assert data["name"] == "todo-habit"
    assert data["short_name"] == "todo-habit"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert len(data["icons"]) >= 4

    # アイコンが実在するか確認
    for icon in data["icons"]:
        icon_res = client.get(icon["src"])
        assert icon_res.status_code == 200, f"Icon {icon['src']} not found"


def test_offline_fallback_page(client):
    res = client.get("/static/offline.html")
    assert res.status_code == 200
    assert "オフラインです" in res.text


def test_base_template_includes_pwa_assets(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert 'rel="manifest" href="/static/manifest.webmanifest"' in html
    assert 'apple-mobile-web-app-capable' in html
    assert 'theme-color' in html
    assert '/sw.js' in html
