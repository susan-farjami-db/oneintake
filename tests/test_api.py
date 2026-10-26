"""Phase 4 self-check: every API endpoint against the live Lakebase, warehouse, and embedding endpoint.

The caller's CLI token stands in for the OBO header. Rows created here are deleted at the end.
Writes evidence/duplicate_latency.txt. Skipped when INTAKE_CATALOG is not set.
"""

import csv
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("INTAKE_CATALOG"), reason="needs a live workspace")
ROOT = Path(__file__).resolve().parent.parent
DEMO_TITLE = "Chatbot so agents can check load ETA"
created: list[str] = []


@pytest.fixture(scope="module")
def client():
    from databricks.sdk import WorkspaceClient
    from fastapi.testclient import TestClient

    from oneintake.backend.app import app
    token = WorkspaceClient().config.authenticate()["Authorization"].split(" ", 1)[1]
    with TestClient(app, headers={"X-Forwarded-Access-Token": token}) as c:
        yield c
        from sqlmodel import Session, text
        with Session(app.state.engine) as s:
            for rid in created:
                s.execute(text("DELETE FROM app.review_decisions WHERE request_id = :i"), {"i": rid})
                s.execute(text("DELETE FROM app.intake_requests WHERE request_id = :i"), {"i": rid})
            s.commit()


def check(client, title, description="", draft_id=None):
    time.sleep(0.55)  # stay under the 2 calls per second limit
    r = client.post("/api/requests/check-duplicates",
                    json={"title": title, "description": description, "draft_id": draft_id})
    assert r.status_code == 200, r.text
    return r.json()


def submit(client, title, description, **extra):
    fields = {"title": title, "description": description, "business_unit": "Technology",
              "sponsor": "Test Sponsor", "problem_statement": "Test problem.", "expected_benefit": "Test benefit.",
              "est_value_usd": 125000, "data_sources": ["TMS", "ERP"], "urgency": "medium"}
    r = client.post("/api/requests", json={"fields": fields, **extra})
    if r.status_code == 200:
        created.append(r.json()["request_id"])
    return r


def test_form_config(client):
    body = client.get("/api/form-config").json()
    assert len(body["fields"]) == 10 and [f["display_order"] for f in body["fields"]] == sorted(
        f["display_order"] for f in body["fields"])
    assert len(body["categories"]) == 7
    assert body["thresholds"] == {"likely_duplicate": 0.85, "related": 0.70}


def test_demo_title_is_likely_duplicate(client):
    top = check(client, DEMO_TITLE)["matches"][0]
    assert top["title"] == "Agent ETA assistant" and top["score"] >= 0.85 and top["band"] == "likely_duplicate"
    assert top["status"] and top["owner"]


def test_rate_limit(client):
    time.sleep(1.1)
    codes = [client.post("/api/requests/check-duplicates", json={"title": DEMO_TITLE}).status_code for _ in range(3)]
    assert codes[:2] == [200, 200] and codes[2] == 429
    time.sleep(1.1)


def test_duplicate_latency(client):
    with open(ROOT / "eval" / "duplicate_pairs.csv") as fh:
        texts = [(r["title_b"], r["description_b"][:120]) for r in csv.DictReader(fh)][:20]
    cold, warm = [], []
    for title, desc in texts:
        cold.append(check(client, title, desc)["elapsed_ms"])
    for title, desc in texts:
        body = check(client, title, desc)
        assert body["cached"]
        warm.append(body["elapsed_ms"])
    p95 = lambda xs: statistics.quantiles(xs, n=20)[18]  # noqa: E731
    all_ms = cold + warm
    lines = [f"# generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
             f"calls={len(all_ms)} (20 cache misses then the same 20 as cache hits), server-side ms",
             f"cold p50={statistics.median(cold):.0f} p95={p95(cold):.0f} max={max(cold)}",
             f"warm p50={statistics.median(warm):.0f} p95={p95(warm):.0f} max={max(warm)}",
             f"overall p95={p95(all_ms):.0f} target<800 {'PASS' if p95(all_ms) < 800 else 'FAIL'}"]
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence" / "duplicate_latency.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    assert p95(all_ms) < 800


def test_submit_classifies_and_lists_mine(client):
    r = submit(client, "Forecast forklift battery replacement at cross docks",
               "Predict when warehouse forklift batteries will fail using charger logs so we can order spares early.")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] and body["classify_ms"] < 5000
    mine = client.get("/api/requests/mine").json()
    assert body["request_id"] in [m["request_id"] for m in mine]


def test_likely_duplicate_requires_reason(client):
    assert submit(client, DEMO_TITLE, "Agents ask for ETA.", dup_score=0.9).status_code == 422


def test_excludes_rejected_and_own_draft(client):
    title = "Predict pallet jack maintenance windows from sensor logs"
    rid = submit(client, title, "Use pallet jack sensor logs to schedule maintenance before breakdowns.").json()[
        "request_id"]
    assert rid in [m["key"] for m in check(client, title)["matches"]]
    assert rid not in [m["key"] for m in check(client, title, draft_id=rid)["matches"]]
    assert client.post(f"/api/review/{rid}", json={"action": "reject", "reason": "test"}).status_code == 200
    assert rid not in [m["key"] for m in check(client, title)["matches"]]


def test_review_queue_approve_and_merge(client):
    from sqlmodel import Session, text

    from oneintake.backend.app import app
    unique = submit(client, "Summarize lumper receipts for accounting", "Read lumper receipts and post totals.").json()
    dup = submit(client, DEMO_TITLE, "Agents want load ETA without calling dispatch.", dup_score=0.88,
                 submit_anyway_reason="Different user group").json()
    queue = {q["request_id"]: q for q in client.get("/api/review/queue").json()}
    assert unique["request_id"] in queue and dup["request_id"] in queue
    target = queue[dup["request_id"]]["top_match"]
    assert target and target["title"] == "Agent ETA assistant"
    a = client.post(f"/api/review/{unique['request_id']}", json={"action": "approve"})
    m = client.post(f"/api/review/{dup['request_id']}", json={"action": "merge", "merged_into": target["key"]})
    assert a.json()["status"] == "approved" and m.json()["status"] == "merged"
    with Session(app.state.engine) as s:
        rows = s.execute(text("SELECT action FROM app.review_decisions WHERE request_id IN (:a, :b)"),
                         {"a": unique["request_id"], "b": dup["request_id"]}).scalars().all()
    assert sorted(rows) == ["approve", "merge"]


def test_review_requires_task_force(client, monkeypatch):
    from oneintake.backend import services
    monkeypatch.setattr(services, "TASK_FORCE_GROUP", "group_nobody_is_in")
    assert client.get("/api/review/queue").status_code == 403
