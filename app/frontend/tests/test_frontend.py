import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)


def fake_backend(monkeypatch, status=200, body=b"[]", headers=None, calls=None):
    async def fake(method, path, **kwargs):
        if calls is not None:
            calls.append((method, path, kwargs))
        return httpx.Response(status, content=body, headers=headers or {})

    monkeypatch.setattr(main, "call_backend", fake)


def test_index_serves_the_page_and_never_exposes_the_secret():
    res = client.get("/")
    assert res.status_code == 200
    assert "Acortador de enlaces" in res.text
    assert main.SHARED_SECRET not in res.text


def test_health_does_not_need_the_backend():
    assert client.get("/health").status_code == 200


def test_list_links_is_relayed(monkeypatch):
    calls = []
    fake_backend(monkeypatch, body=b'[{"code":"abc"}]', calls=calls)
    res = client.get("/api/links")
    assert res.status_code == 200
    assert res.json() == [{"code": "abc"}]
    assert calls[0][:2] == ("GET", "/links")


def test_create_link_forwards_the_body(monkeypatch):
    calls = []
    fake_backend(monkeypatch, status=201, body=b'{"code":"abc","url":"https://x.com"}', calls=calls)
    res = client.post("/api/links", json={"url": "https://x.com"})
    assert res.status_code == 201
    assert calls[0][0] == "POST"
    assert b"https://x.com" in calls[0][2]["content"]


def test_redirect_is_relayed(monkeypatch):
    fake_backend(monkeypatch, status=302, body=b"", headers={"location": "https://example.com"})
    res = client.get("/abc", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "https://example.com"


def test_unreachable_backend_gives_502(monkeypatch):
    async def down(method, path, **kwargs):
        return None

    monkeypatch.setattr(main, "call_backend", down)
    assert client.get("/api/links").status_code == 502
