"""Service tests with a stubbed Ollama backend. Run: cd service && pytest -q"""
import json

import pytest
import requests
from fastapi.testclient import TestClient


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload, self.text = status, payload or {}, json.dumps(payload or {})

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.status_code)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "log.jsonl"))
    monkeypatch.setenv("MODEL", "stub:1b")
    import importlib
    import app.main as m
    m = importlib.reload(m)
    state = {"output": '{"category": "Mortgage"}', "status": 200, "raise": None}

    def fake_post(url, json=None, timeout=None):
        if state["raise"]:
            raise state["raise"]
        return FakeResp(state["status"], {"message": {"content": state["output"]},
                                          "total_duration": 2_000_000_000, "eval_count": 9})

    monkeypatch.setattr(m.requests, "post", fake_post)
    monkeypatch.setattr(m.requests, "get",
                        lambda url, timeout=None: FakeResp(200, {"models": [{"name": "stub:1b", "digest": "abc123"}]}))
    with TestClient(m.app) as c:
        c.state, c.log = state, tmp_path / "log.jsonl"
        yield c


def logs(c):
    return [json.loads(l) for l in c.log.read_text().splitlines()]


def test_post_classifies_stores_and_logs(client):
    r = client.post("/tickets", json={"narrative": "My escrow payment doubled"},
                    headers={"X-Request-ID": "run1-9001", "X-Run-ID": "run1"})
    assert r.status_code == 201 and r.json()["category"] == "Mortgage"
    assert r.headers["X-Request-ID"] == "run1-9001"
    line = [l for l in logs(client) if l.get("path") == "/tickets"][0]
    assert line["request_id"] == "run1-9001" and line["run_id"] == "run1"
    assert line["category"] == "Mortgage" and line["ollama_total_ms"] == 2000.0
    assert line["model_digest"] == "abc123"


def test_stats_counts_all_categories(client):
    client.post("/tickets", json={"narrative": "a"})
    client.state["output"] = '{"category": "Credit card"}'
    client.post("/tickets", json={"narrative": "b"})
    s = client.get("/stats").json()
    assert s["total"] == 2 and s["by_category"]["Mortgage"] == 1
    assert s["by_category"]["Consumer loan"] == 0 and len(s["by_category"]) == 7


def test_search_matches_and_escapes_wildcards(client):
    client.post("/tickets", json={"narrative": "escrow shortage on my loan"})
    client.post("/tickets", json={"narrative": "100% fee"})
    assert client.get("/search", params={"q": "escrow"}).json()["count"] == 1
    assert client.get("/search", params={"q": "%"}).json()["count"] == 1      # literal %, not wildcard
    assert client.get("/search", params={"q": "' OR 1=1 --"}).json()["count"] == 0


def test_validation(client):
    assert client.post("/tickets", json={"narrative": ""}).status_code == 422
    assert client.post("/tickets", json={"narrative": "   "}).status_code == 422
    assert client.post("/tickets", json={}).status_code == 422
    assert client.post("/tickets", json={"narrative": "x" * 20001}).status_code == 422
    assert client.get("/search").status_code == 422


def test_backend_failures_map_to_5xx_and_are_logged(client):
    client.state["output"] = "I think it's about pizza"
    assert client.post("/tickets", json={"narrative": "x"}).status_code == 502
    client.state["output"], client.state["status"] = '{"category": "Mortgage"}', 503
    assert client.post("/tickets", json={"narrative": "x"}).status_code == 502
    client.state["raise"] = requests.Timeout()
    assert client.post("/tickets", json={"narrative": "x"}).status_code == 504
    errs = [l for l in logs(client) if l.get("path") == "/tickets"]
    assert [l["status"] for l in errs] == [502, 502, 504] and all("error" in l for l in errs)
    assert client.get("/stats").json()["total"] == 0


def test_bad_request_id_header_is_replaced(client):
    r = client.post("/tickets", json={"narrative": "x"}, headers={"X-Request-ID": "<script>"})
    assert r.headers["X-Request-ID"] != "<script>"
