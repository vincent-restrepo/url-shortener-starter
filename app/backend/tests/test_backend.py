import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)


def test_generate_code_length_and_alphabet():
    code = main.generate_code(8)
    assert len(code) == 8
    assert set(code) <= set(main.ALPHABET)


def test_generate_code_is_random():
    assert len({main.generate_code() for _ in range(50)}) > 40


def test_health_is_open():
    assert client.get("/health").status_code == 200


def test_every_route_rejects_calls_without_the_shared_secret():
    assert client.get("/links").status_code == 401
    assert client.post("/links", json={"url": "https://x.com"}).status_code == 401
    assert client.get("/links/abc/stats").status_code == 401
    assert client.get("/abc").status_code == 401


def test_wrong_secret_is_rejected():
    assert client.get("/links", headers={"x-shared-secret": "incorrecto"}).status_code == 401


def test_invalid_url_is_rejected_before_touching_the_database():
    res = client.post("/links", json={"url": "ftp://x"}, headers={"x-shared-secret": main.SHARED_SECRET})
    assert res.status_code == 422
