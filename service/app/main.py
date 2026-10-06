"""Ticket Triage Service — Assignment 1 baseline.

Deliberately naive: each POST /tickets makes one blocking call to Ollama and
returns only after classification. No caching, no queue, no batching.
"""
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, closing

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

CATEGORIES = [
    "Credit reporting", "Debt collection", "Mortgage", "Credit card",
    "Bank account or service", "Consumer loan", "Money transfer or service",
]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434").rstrip("/")
MODEL = os.getenv("MODEL", "llama3.2:1b")
DB_PATH = os.getenv("DB_PATH", "/data/tickets.db")
LOG_FILE = os.getenv("LOG_FILE", "/logs/service.jsonl")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "600"))
NUM_CTX = int(os.getenv("NUM_CTX", "2048"))
MAX_NARRATIVE_CHARS = 20_000
_ID_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")

SYSTEM_PROMPT = (
    "You route consumer complaints at a financial services company. "
    "Classify the complaint into exactly one category, choosing the team that must act to resolve it.\n"
    "Categories:\n"
    "- Credit reporting: errors on credit reports, disputes with credit bureaus, inquiries, credit scores.\n"
    "- Debt collection: third-party collectors or debt buyers, collection calls, debt validation, debts not owed.\n"
    "- Mortgage: home loans, servicing, escrow, modification, foreclosure, HELOC.\n"
    "- Credit card: credit or prepaid card accounts, charges, fees, APR, rewards, billing disputes.\n"
    "- Bank account or service: checking or savings accounts, deposits, overdraft fees, holds, closures, debit cards.\n"
    "- Consumer loan: auto loans or leases, personal, payday, title and student loans.\n"
    "- Money transfer or service: wire transfers, remittances, Zelle, PayPal, Venmo, money orders, virtual currency.\n"
    'Respond with JSON only: {"category": "<one category name>"}'
)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"category": {"type": "string", "enum": CATEGORIES}},
    "required": ["category"],
}

_log_lock = threading.Lock()
_state = {"model_digest": None}
logging.getLogger("uvicorn.access").disabled = True


# ---------- logging ----------
def write_log(entry: dict) -> None:
    line = json.dumps(entry, ensure_ascii=False)
    with _log_lock, open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def safe_id(value: str | None) -> str | None:
    return value if value and _ID_RE.match(value) else None


# ---------- storage ----------
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with closing(db()) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   request_id TEXT,
                   narrative TEXT NOT NULL,
                   category TEXT NOT NULL,
                   model TEXT NOT NULL,
                   created_at REAL NOT NULL)"""
        )


# ---------- model backend ----------
class ClassificationError(Exception):
    pass


def fetch_model_digest() -> str | None:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        r.raise_for_status()
        for m in r.json().get("models", []):
            if m.get("name") == MODEL or m.get("model") == MODEL:
                return m.get("digest")
    except requests.RequestException:
        return None
    return None


def parse_category(text: str) -> str:
    try:
        value = json.loads(text).get("category", "")
    except (json.JSONDecodeError, AttributeError):
        value = text
    value = str(value).strip().strip('"').lower()
    for c in CATEGORIES:
        if value == c.lower():
            return c
    for c in CATEGORIES:  # tolerate minor formatting drift, e.g. trailing words
        if c.lower() in value:
            return c
    raise ClassificationError(f"unparseable model output: {text[:200]!r}")


def classify(narrative: str) -> tuple[str, dict]:
    body = {
        "model": MODEL,
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {"temperature": 0, "seed": 42, "num_ctx": NUM_CTX, "num_predict": 32},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": narrative},
        ],
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=OLLAMA_TIMEOUT_S)
    if r.status_code != 200:
        raise ClassificationError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    raw = data.get("message", {}).get("content", "")
    meta = {
        "raw_output": raw[:200],
        # Ollama reports durations in nanoseconds; convert to ms.
        "ollama_total_ms": round(data.get("total_duration", 0) / 1e6, 1),
        "ollama_load_ms": round(data.get("load_duration", 0) / 1e6, 1),
        "ollama_prompt_eval_ms": round(data.get("prompt_eval_duration", 0) / 1e6, 1),
        "ollama_eval_ms": round(data.get("eval_duration", 0) / 1e6, 1),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
    }
    return parse_category(raw), meta


# ---------- app ----------
@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    init_db()
    _state["model_digest"] = fetch_model_digest()
    write_log({"event": "startup", "ts": time.time(), "model": MODEL,
               "model_digest": _state["model_digest"], "ollama_url": OLLAMA_URL})
    yield


app = FastAPI(title="Ticket Triage Service", version="1.0-baseline", lifespan=lifespan)


@app.middleware("http")
async def request_log(request: Request, call_next):
    request.state.extra = {}
    rid = safe_id(request.headers.get("x-request-id")) or uuid.uuid4().hex
    run_id = safe_id(request.headers.get("x-run-id"))
    request.state.request_id = rid
    t_start, p_start = time.time(), time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        write_log({
            "event": "request", "request_id": rid, "run_id": run_id,
            "method": request.method, "path": request.url.path, "status": status,
            "ts_start": round(t_start, 6), "latency_ms": round((time.perf_counter() - p_start) * 1000, 2),
            "model": MODEL, "model_digest": _state["model_digest"], **request.state.extra,
        })


class TicketIn(BaseModel):
    narrative: str = Field(min_length=1, max_length=MAX_NARRATIVE_CHARS)


@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketIn, request: Request):
    narrative = ticket.narrative.strip()
    if not narrative:
        raise HTTPException(422, "narrative must not be blank")
    request.state.extra["narrative_chars"] = len(narrative)
    t0 = time.perf_counter()
    try:
        category, meta = classify(narrative)
    except requests.Timeout:
        request.state.extra["error"] = "ollama timeout"
        raise HTTPException(504, "model backend timed out")
    except (requests.RequestException, ClassificationError, ValueError) as e:
        request.state.extra["error"] = str(e)[:300]
        raise HTTPException(502, "classification failed")
    request.state.extra.update(meta, category=category,
                               classify_ms=round((time.perf_counter() - t0) * 1000, 2))
    with closing(db()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO tickets (request_id, narrative, category, model, created_at) VALUES (?,?,?,?,?)",
            (request.state.request_id, narrative, category, MODEL, time.time()),
        )
        ticket_id = cur.lastrowid
    return {"id": ticket_id, "category": category, "model": MODEL}


@app.get("/search")
def search(q: str = Query(min_length=1, max_length=200), limit: int = Query(20, ge=1, le=100)):
    # Naive baseline: full-table LIKE scan. Wildcards in user input are escaped.
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT id, category, substr(narrative, 1, 200) AS snippet, created_at FROM tickets "
            "WHERE narrative LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
            (pattern, limit),
        ).fetchall()
    return {"query": q, "count": len(rows), "results": [dict(r) for r in rows]}


@app.get("/stats")
def stats():
    with closing(db()) as conn:
        rows = conn.execute("SELECT category, COUNT(*) AS n FROM tickets GROUP BY category").fetchall()
    counts = {c: 0 for c in CATEGORIES}
    counts.update({r["category"]: r["n"] for r in rows})
    return {"total": sum(counts.values()), "by_category": counts}


@app.get("/health")
def health():
    digest = _state["model_digest"] or fetch_model_digest()
    _state["model_digest"] = digest
    return {"status": "ok" if digest else "model_not_found", "model": MODEL, "model_digest": digest}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    request.state.extra["error"] = f"unhandled: {type(exc).__name__}"
    return JSONResponse({"detail": "internal error"}, status_code=500)
