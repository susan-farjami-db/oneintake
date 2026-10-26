"""Intake services: config, identity, embeddings with cache, duplicate search, classification."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict, defaultdict, deque
from functools import lru_cache
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, StatementParameterListItem, StatementState
from fastapi import HTTPException
from sqlmodel import Session, text

from .models import DuplicateMatch

TASK_FORCE_GROUP = os.environ.get("TASK_FORCE_GROUP", "task_force")


@lru_cache(maxsize=1)
def config_dir() -> Path:
    here = Path(__file__).resolve().parent.parent
    for d in (here / "config", here.parent.parent / "config"):
        if (d / "app_config.json").exists():
            return d
    raise FileNotFoundError("config/app_config.json not found")


@lru_cache(maxsize=1)
def app_config() -> dict:
    return json.loads((config_dir() / "app_config.json").read_text())


@lru_cache(maxsize=1)
def form_fields() -> list[dict]:
    return json.loads((config_dir() / "form_fields.json").read_text())


def band(score: float) -> str:
    t = app_config()["thresholds"]
    return "likely_duplicate" if score >= t["likely_duplicate"] else "related" if score >= t["related"] else "none"


# --- identity (OBO) ---

_identity: dict[str, tuple[float, str, set[str]]] = {}


def identity(user_ws: WorkspaceClient) -> tuple[str, set[str]]:
    """Email and group names of the calling user, resolved with the OBO token (cached 5 minutes)."""
    key = hashlib.sha256((user_ws.config.token or "").encode()).hexdigest()
    hit = _identity.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1], hit[2]
    me = user_ws.current_user.me()
    groups = {g.display for g in (me.groups or []) if g.display}
    _identity[key] = (time.monotonic() + 300, me.user_name, groups)
    return me.user_name, groups


def require_task_force(groups: set[str]) -> None:
    if TASK_FORCE_GROUP not in groups:
        raise HTTPException(status_code=403, detail=f"Only members of {TASK_FORCE_GROUP} can review requests")


# --- rate limit ---


class RateLimiter:
    def __init__(self, per_second: int):
        self.per_second, self.calls, self.lock = per_second, defaultdict(deque), threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            q = self.calls[key]
            while q and now - q[0] >= 1.0:
                q.popleft()
            if len(q) >= self.per_second:
                raise HTTPException(status_code=429, detail="Duplicate check rate limit exceeded")
            q.append(now)


rate_limiter = RateLimiter(app_config()["duplicate_check"]["rate_limit_per_sec"])


# --- embeddings ---


def normalize(title: str, description: str) -> str:
    return " ".join(f"{title.strip()}. {description.strip()}".split()).strip(". ")


class EmbeddingCache:
    """In-memory LRU keyed by a hash of the normalized text and its role (query or document)."""

    def __init__(self, size: int = 4096):
        self.size, self.items, self.lock = size, OrderedDict(), threading.Lock()

    def get_or_embed(self, ws: WorkspaceClient, text_: str, query: bool) -> tuple[list[float], bool]:
        key = hashlib.sha256(f"{query}|{text_.lower()}".encode()).hexdigest()
        with self.lock:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key], True
        emb = cfg_embedding()
        payload = (emb["query_prefix"] + text_) if query else text_
        vec = ws.serving_endpoints.query(name=emb["endpoint"], input=payload).data[0].embedding
        with self.lock:
            self.items[key] = vec
            while len(self.items) > self.size:
                self.items.popitem(last=False)
        return vec, False


def cfg_embedding() -> dict:
    emb = dict(app_config()["embedding"])
    emb["endpoint"] = os.environ.get("EMBEDDING_ENDPOINT", emb["endpoint"])
    return emb


embeddings = EmbeddingCache()

SEARCH_SQL = text("""
WITH q AS (SELECT CAST(:v AS vector) AS v)
(SELECT 'request' AS kind, r.request_id AS key, r.title, r.status, r.requester_email AS owner,
        r.business_unit, 1 - (e.embedding <=> q.v) AS score
   FROM serving.request_embeddings e JOIN app.intake_requests r USING (request_id), q
  WHERE r.status <> 'rejected' AND r.request_id <> :draft
  ORDER BY e.embedding <=> q.v LIMIT :k)
UNION ALL
(SELECT p.source, p.project_key, p.title, p.status, p.owner_email, p.business_unit,
        1 - (p.embedding <=> q.v)
   FROM serving.projects_synced p, q
  WHERE coalesce(p.status, '') <> 'rejected' AND p.project_key <> :draft
  ORDER BY p.embedding <=> q.v LIMIT :k)
""")


def find_duplicates(session: Session, vec: list[float], draft_id: str | None) -> list[DuplicateMatch]:
    k = app_config()["duplicate_check"]["top_k"]
    rows = session.execute(SEARCH_SQL, {"v": json.dumps(vec), "draft": draft_id or "", "k": k}).mappings()
    best: dict[str, DuplicateMatch] = {}
    for r in rows:
        m = to_match(r)
        if m.key not in best or best[m.key].score < m.score:
            best[m.key] = m
    return sorted(best.values(), key=lambda m: -m.score)[:k]


def to_match(r) -> DuplicateMatch:
    score = round(float(r["score"]), 4)
    return DuplicateMatch(key=r["key"], kind=r["kind"], title=r["title"], score=score, band=band(score),
                          status=r["status"], owner=r["owner"], business_unit=r["business_unit"])


def store_embedding(session: Session, request_id: str, vec: list[float]) -> None:
    session.execute(text("""INSERT INTO serving.request_embeddings (request_id, embedding)
                            VALUES (:id, CAST(:v AS vector))
                            ON CONFLICT (request_id) DO UPDATE SET embedding = EXCLUDED.embedding,
                                                                   updated_at = now()"""),
                    {"id": request_id, "v": json.dumps(vec)})


# --- classification ---


def _sql_literal(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def classify(ws: WorkspaceClient, title: str, description: str) -> tuple[str | None, float | None]:
    """Synchronous ai_classify (version 2.1) on the SQL warehouse; options must be a literal map.

    Confidence scores are left to the pipeline: they add about a second to each call."""
    cfg = app_config()
    labels = json.dumps({c["label"]: c["description"] for c in cfg["categories"]})
    stmt = (f"SELECT ai_classify(:content, :labels, map('version', '2.1', 'instructions', "
            f"{_sql_literal(cfg['classify_instructions'])})) AS r")
    rows = run_sql(ws, stmt, [StatementParameterListItem(name="content", value=normalize(title, description)),
                              StatementParameterListItem(name="labels", value=labels)])
    top = (json.loads(rows[0][0]).get("response") or [{}])[0]
    conf = top.get("confidence_score")
    return top.get("value"), float(conf) if conf is not None else None


def portfolio_kpis(user_ws: WorkspaceClient) -> dict:
    cat = os.environ["INTAKE_CATALOG"]
    stmt = (f"SELECT MEASURE(request_count) AS request_count, MEASURE(total_est_value) AS total_est_value, "
            f"MEASURE(duplicate_rate) AS duplicate_rate FROM {cat}.gold.portfolio_metrics")
    backlog = (f"SELECT MEASURE(total_est_value) AS v FROM {cat}.gold.portfolio_metrics "
               f"WHERE status IN ('submitted', 'in_review')")
    a, b = run_sql(user_ws, stmt)[0], run_sql(user_ws, backlog)[0]
    return {"request_count": int(a[0] or 0), "total_est_value": float(a[1] or 0),
            "duplicate_rate": float(a[2] or 0), "open_backlog_value": float(b[0] or 0)}


def run_sql(ws: WorkspaceClient, stmt: str, params: list | None = None) -> list[list]:
    r = ws.statement_execution.execute_statement(
        statement=stmt, warehouse_id=os.environ["DATABRICKS_SQL_WAREHOUSE_ID"], wait_timeout="30s",
        disposition=Disposition.INLINE, parameters=params)
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(0.3)
        r = ws.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(r.status.error.message if r.status.error else str(r.status.state))
    return r.result.data_array or []


_last_warm = [0.0]


def warm_up(ws: WorkspaceClient) -> None:
    """Wake the warehouse and ai_classify in the background when someone opens the form."""
    if time.monotonic() - _last_warm[0] < 600:
        return
    _last_warm[0] = time.monotonic()
    threading.Thread(target=lambda: classify(ws, "warm up", "warm up"), daemon=True).start()
