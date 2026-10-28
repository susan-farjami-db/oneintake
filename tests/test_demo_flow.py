"""Phase 5/8 self-check: the demo flow in a real browser, against the dev server or the deployed app.

DEMO_BASE_URL defaults to the local dev server. For a deployed app, the caller's OAuth token is
sent as a bearer header. Writes evidence/<prefix>demo_flow.txt and screenshots.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
BASE = os.environ.get("DEMO_BASE_URL", "http://127.0.0.1:9002").rstrip("/")
PREFIX = os.environ.get("DEMO_EVIDENCE_PREFIX", "")
EVIDENCE = ROOT / "evidence"
DEMO_TITLE = "Chatbot so agents can check load ETA"
UNIQUE_PREFIX = "Predict reefer unit failures from temperature logs"
pytestmark = pytest.mark.skipif(not os.environ.get("INTAKE_CATALOG"), reason="needs a live workspace")
log: list[str] = []


def note(msg):
    log.append(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")
    print(log[-1])


def shot(page, name):
    page.screenshot(path=str(EVIDENCE / f"{PREFIX}demo_{name}.png"), full_page=True)


def fill_form(page, title, description, unit="Agent Operations", value="250000"):
    page.fill("#field-title", title)
    page.fill("#field-description", description)
    page.select_option("#field-business_unit", unit)
    page.fill("#field-sponsor", "Demo Sponsor")
    page.fill("#field-problem_statement", "Agents spend time on repetitive lookups.")
    page.fill("#field-expected_benefit", "Faster answers for agents.")
    page.fill("#field-est_value_usd", value)
    page.select_option("#field-urgency", "high")


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    headers = {}
    if not BASE.startswith("http://127.0.0.1") and not BASE.startswith("http://localhost"):
        from databricks.sdk import WorkspaceClient
        headers = WorkspaceClient().config.authenticate()
    EVIDENCE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(extra_http_headers=headers, viewport={"width": 1400, "height": 1000})
        pg = ctx.new_page()
        pg.set_default_timeout(20000)
        pg.on("response", lambda r: r.status >= 500 and "/api/" in r.url and not r.request.is_navigation_request()
              and note(f"HTTP {r.status} {r.request.method} {r.url.split('/api', 1)[1]}"))
        yield pg
        browser.close()
    (EVIDENCE / f"{PREFIX}demo_flow.txt").write_text(f"base_url={BASE}\n" + "\n".join(log) + "\n")


def reset_demo_rows():
    """Remove rows from earlier demo runs so the flow starts clean."""
    import lb
    from databricks.sdk import WorkspaceClient
    with lb.connect(WorkspaceClient()) as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT request_id FROM app.intake_requests WHERE title = %s OR title LIKE %s",
            (DEMO_TITLE, UNIQUE_PREFIX + "%")).fetchall()]
        conn.execute("DELETE FROM app.review_decisions WHERE request_id = ANY(%s)", (ids,))
        conn.execute("DELETE FROM serving.request_embeddings WHERE request_id = ANY(%s)", (ids,))
        conn.execute("DELETE FROM app.intake_requests WHERE request_id = ANY(%s)", (ids,))
        # earlier rows reach gold via Lakehouse Sync and return via sync-projects
        conn.execute("DELETE FROM serving.projects_synced WHERE title = %s OR title LIKE %s",
                     (DEMO_TITLE, UNIQUE_PREFIX + "%"))
    note(f"reset {len(ids)} rows from earlier runs")


def test_demo_flow(page):
    from playwright.sync_api import expect
    reset_demo_rows()
    page.goto(f"{BASE}/submit")
    expect(page.locator("#field-title")).to_be_visible()
    note("opened Submit")

    # 1. Live duplicate detection before the description is written.
    start = time.perf_counter()
    page.type("#field-title", DEMO_TITLE, delay=60)
    likely = page.locator('[data-testid="similar-match"][data-band="likely_duplicate"]').filter(
        has_text="Agent ETA assistant")
    expect(likely).to_be_visible(timeout=10000)
    score = float(likely.locator('[data-testid="match-score"]').inner_text())
    assert page.input_value("#field-description") == "" and score >= 0.85
    note(f"PASS likely dup score={score:.2f} {time.perf_counter() - start:.1f}s after typing, desc empty")
    shot(page, "1_likely_duplicate")

    # 2. Submit anyway needs a reason; goes to review queue.
    fill_form(page, DEMO_TITLE, "Agents want load ETA in chat without calling dispatch.")
    page.click('[data-testid="submit-button"]')
    expect(page.locator('[data-testid="duplicate-choice"]')).to_be_visible()
    submit_anyway = page.get_by_role("button", name="Submit anyway")
    assert submit_anyway.is_disabled()
    page.fill('[data-testid="anyway-reason"]', "Brokerage needs it in the agent portal, not the TMS.")
    submit_anyway.click()
    expect(page.locator('[data-testid="submit-result"]')).to_be_visible()
    note("PASS Submit anyway needed a reason, saved dup")
    shot(page, "2_submitted_anyway")

    # 3. Unique request categorized within 5s.
    page.goto(f"{BASE}/submit")
    unique = UNIQUE_PREFIX
    fill_form(page, unique, "Use reefer temperature and alarm logs to predict compressor failures early.",
              unit="Safety and Compliance", value="410000")
    page.wait_for_timeout(1500)
    start = time.perf_counter()
    page.click('[data-testid="submit-button"]')
    category = page.locator('[data-testid="result-category"]')
    expect(category).to_be_visible(timeout=10000)
    elapsed = time.perf_counter() - start
    assert category.inner_text() not in ("", "Pending") and elapsed < 5
    note(f"PASS categorized '{category.inner_text()}' in {elapsed:.1f}s")
    shot(page, "3_unique_categorized")

    # 4. Reviewer approves the unique, merges the duplicate.
    page.goto(f"{BASE}/review")
    card = page.locator(f'[data-testid="review-item"][data-title="{unique}"]').first
    card.get_by_role("button", name="Approve").click()
    expect(card.locator('[data-testid="review-done"]')).to_have_text("Marked approved.")
    dup = page.locator(f'[data-testid="review-item"][data-title="{DEMO_TITLE}"]').first
    expect(dup).to_contain_text("Agent ETA assistant")
    target = dup.get_by_placeholder("Merge into id").input_value()
    dup.get_by_role("button", name="Merge").click()
    expect(dup.locator('[data-testid="review-done"]')).to_have_text("Marked merged.")
    note(f"PASS approved '{unique}', merged dup into {target}")
    shot(page, "4_review_done")

    # 5. Both decisions are rows in Lakebase.
    import lb
    from databricks.sdk import WorkspaceClient
    with lb.connect(WorkspaceClient()) as conn:
        rows = conn.execute("""SELECT r.title, r.status, d.action, d.merged_into FROM app.review_decisions d
                               JOIN app.intake_requests r USING (request_id)
                               WHERE r.title IN (%s, %s) ORDER BY d.decided_at DESC LIMIT 2""",
                            (unique, DEMO_TITLE)).fetchall()
    actions = {r[2] for r in rows}
    assert actions == {"approve", "merge"}, rows
    note(f"PASS review rows: {rows}")

    # 6. Duplicate-check failure shows the fallback message.
    page.route("**/api/requests/check-duplicates", lambda route: route.fulfill(status=503, body="down"))
    page.goto(f"{BASE}/submit")
    page.type("#field-title", "Automate fuel card exception review weekly", delay=20)
    expect(page.locator('[data-testid="dup-unavailable"]')).to_have_text("Duplicate check unavailable")
    note("PASS fallback message shown when check fails")
    shot(page, "5_check_unavailable")
    page.unroute("**/api/requests/check-duplicates")

    # 7. Portfolio KPIs.
    page.goto(f"{BASE}/portfolio")
    expect(page.locator('[data-testid="kpi"]')).to_have_count(3, timeout=20000)
    expect(page.locator('[data-testid="genie-chat"]')).to_be_visible()
    note("PASS Portfolio KPIs: " + " | ".join(t.replace("\n", " ") for t in page.locator('[data-testid="kpi"]').all_inner_texts()))
    shot(page, "6_portfolio")

    # 8. Join existing opens a preview (regression: 500'd with no description).
    page.goto(f"{BASE}/submit")
    page.type("#field-title", DEMO_TITLE, delay=20)
    again = page.locator('[data-testid="similar-match"]').filter(has_text="Agent ETA assistant").first
    expect(again).to_be_visible(timeout=10000)
    again.get_by_role("button", name="Join existing").click()
    expect(page.locator('[data-testid="join-preview"]')).to_contain_text("Agent ETA assistant")
    confirm = page.locator('[data-testid="confirm-join"]')
    assert confirm.is_disabled()
    page.fill('[data-testid="join-description"]', "Joining the ETA assistant.")
    assert not confirm.is_disabled()
    confirm.click()
    expect(page.locator('[data-testid="submit-result"]')).to_contain_text("Joined existing work", timeout=10000)
    note("PASS Join existing previews the match, needs description")
    shot(page, "7_join_existing")
