"""Create or update the portfolio Genie space, document it, and check its answers against SQL.

Writes genie/space_config.md and evidence/genie_answers.txt (pass when at least 9 of 10 match).
Env: INTAKE_CATALOG, DATABRICKS_SQL_WAREHOUSE_ID. Prints GENIE_SPACE_ID for the app.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ops"))
import run  # noqa: E402

TITLE = "AI Task Force portfolio"
CAT = os.environ.get("INTAKE_CATALOG", "")
P, M = f"{CAT}.gold.projects", f"{CAT}.gold.portfolio_metrics"
INSTRUCTIONS = f"""This space answers questions about the AI Task Force portfolio at the carrier.
- {P} has one row per intake request (source = 'request') and per tracked project (source = 'project').
  Unless the user asks about projects, answer about requests only (source = 'request').
- {M} is a metric view over requests with measures request_count, total_est_value, avg_cycle_days,
  median_cycle_days, duplicate_rate, duplicate_value_usd, open_value_usd, high_urgency_share and dimensions
  category, business_unit, status, month, season. Query measures with MEASURE().
- Backlog means open requests: status 'submitted' or 'in_review' (is_open = true). Backlog value is the sum
  of est_value_usd for open requests.
- "Waiting" means open requests; days waiting = datediff(current_date(), submitted_at).
- "In review" means status = 'in_review'. Status values are exact lowercase codes:
  requests use submitted, in_review, approved, merged, rejected; projects use planned, in_progress,
  on_hold, completed. Always filter status with = on these codes, never LIKE.
- Duplicate rate is the share of requests where is_duplicate is true; use MEASURE(duplicate_rate).
  Duplicated value (double funding) is MEASURE(duplicate_value_usd). Peak season: season dimension.
- Values are estimated annual value in US dollars. Round money to whole dollars and rates to 3 decimals.
- Month means the submitted_month column (first day of the month)."""

# (question, reference SQL). The reference SQL is the ground truth for the answer check.
QUESTIONS = [
    ("What is the backlog value by business unit?",
     f"SELECT business_unit, SUM(est_value_usd) FROM {P} WHERE source = 'request' AND is_open GROUP BY 1"),
    ("How many requests have been waiting more than 30 days?",
     f"SELECT count(*) FROM {P} WHERE source = 'request' AND is_open "
     f"AND datediff(current_date(), submitted_at) > 30"),
    ("What is the duplicate rate by month?",
     f"SELECT month, MEASURE(duplicate_rate) FROM {M} GROUP BY ALL"),
    ("What are the top 5 requests by estimated value that are still in review?",
     f"SELECT title, est_value_usd FROM {P} WHERE source = 'request' AND status = 'in_review' "
     f"ORDER BY est_value_usd DESC LIMIT 5"),
    ("How many requests are there in each category?",
     f"SELECT category, MEASURE(request_count) FROM {M} GROUP BY ALL"),
    ("What is the average cycle time in days by business unit?",
     f"SELECT business_unit, MEASURE(avg_cycle_days) FROM {M} GROUP BY ALL"),
    ("What is the duplicated value by business unit?",
     f"SELECT business_unit, MEASURE(duplicate_value_usd) FROM {M} GROUP BY ALL"),
    ("How many tracked projects are in progress?",
     f"SELECT count(*) FROM {P} WHERE source = 'project' AND status = 'in_progress'"),
    ("Which business unit submitted the most requests?",
     f"SELECT business_unit, count(*) AS n FROM {P} WHERE source = 'request' GROUP BY 1 ORDER BY n DESC LIMIT 1"),
    ("What is the median cycle time in days in peak season versus off-peak?",
     f"SELECT season, MEASURE(median_cycle_days) FROM {M} GROUP BY ALL"),
]


def hid(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def serialized_space() -> dict:
    return {
        "version": 2,
        "config": {"sample_questions": sorted(({"id": hid(q), "question": [q]} for q, _ in QUESTIONS),
                                              key=lambda x: x["id"])},
        "data_sources": {"tables": [{"identifier": P}], "metric_views": [{"identifier": M}]},
        "instructions": {"text_instructions": [{"id": hid(INSTRUCTIONS), "content": [INSTRUCTIONS]}]},
    }


def upsert_space(w) -> str:
    payload = json.dumps(serialized_space())
    wh = os.environ["DATABRICKS_SQL_WAREHOUSE_ID"]
    existing = next((s for s in (w.genie.list_spaces().spaces or []) if s.title == TITLE), None)
    if existing:
        w.genie.update_space(existing.space_id, serialized_space=payload, warehouse_id=wh,
                             description="Portfolio questions over gold.projects and gold.portfolio_metrics")
        return existing.space_id
    return w.genie.create_space(wh, payload, title=TITLE,
                                description="Portfolio questions over gold.projects and gold.portfolio_metrics").space_id


def norm(v):
    """Numbers become floats; dates keep YYYY-MM-DD; text is lowercased."""
    if v is None:
        return "null"
    try:
        return float(v)
    except ValueError:
        s = str(v).strip().lower()
        return s[:10] if len(s) >= 10 and s[4] == "-" else s


def same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= max(0.001, 0.005 * abs(a))
    return a == b


def rows_match(ref, got):
    """Each reference row's values must appear together in a distinct Genie row; row counts must match.
    Numbers match within 0.001 absolute or 0.5% relative, since Genie rounds as instructed."""
    if len(ref) != len(got):
        return False
    pool = [list(map(norm, g)) for g in got]
    for r in ref:
        want = list(map(norm, r))
        hit = next((i for i, g in enumerate(pool) if all(any(same(x, y) for y in g) for x in want)), None)
        if hit is None:
            return False
        pool.pop(hit)
    return True


def ask(w, space_id, question):
    msg = w.genie.start_conversation_and_wait(space_id, question)
    att = next((a for a in (msg.attachments or []) if a.query), None)
    if not att:
        text = next((a.text.content for a in (msg.attachments or []) if a.text), "")
        return None, None, text
    res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, msg.message_id,
                                                      att.attachment_id)
    data = res.statement_response.result.data_array if res.statement_response.result else []
    return att.query.query, data or [], att.query.description


def write_config(space_id, host):
    lines = [f"# Genie space: {TITLE}", "", f"- Space id: set as `GENIE_SPACE_ID` (created by `genie/genie_space.py`)",
             f"- Open: `{{workspace}}/genie/rooms/<space id>`", "- Warehouse: bundle variable `warehouse_id`",
             "- Data sources:", f"  - table `{{catalog}}.gold.projects`", f"  - metric view `{{catalog}}.gold.portfolio_metrics`",
             "", "## General instructions", "", "```text", INSTRUCTIONS.replace(CAT, "{catalog}"), "```", "",
             "## Sample questions and reference SQL", ""]
    for i, (q, sql) in enumerate(QUESTIONS, 1):
        lines += [f"{i}. {q}", "", "   ```sql", f"   {sql.replace(CAT, '{catalog}')}", "   ```", ""]
    lines += ["Access follows Unity Catalog: the business-unit row filter on gold.projects applies to every Genie query.", ""]
    (ROOT / "genie" / "space_config.md").write_text("\n".join(lines))


def main():
    w = WorkspaceClient()
    space_id = upsert_space(w)
    print(f"GENIE_SPACE_ID={space_id}")
    write_config(space_id, w.config.host)
    lines, matched = [f"space_title={TITLE}", "comparison: Genie result rows vs reference SQL rows "
                      "(same row count; each reference row's values found in a Genie row)"], 0
    for i, (q, sql) in enumerate(QUESTIONS, 1):
        ref = [list(r.values()) for r in run.sql(w, sql)]
        try:
            gsql, got, desc = ask(w, space_id, q)
        except Exception as e:
            gsql, got, desc = None, None, f"error: {e}"
        ok = got is not None and rows_match(ref, got)
        matched += ok
        lines += [f"## Q{i} {'MATCH' if ok else 'MISMATCH'}: {q}", f"reference rows ({len(ref)}): {ref[:6]}",
                  f"genie rows ({len(got) if got is not None else 0}): {(got or [])[:6]}",
                  f"genie sql: {' '.join((gsql or desc or '').split())[:600]}"]
    lines.append(f"RESULT {matched}/10 matched -> {'PASS' if matched >= 9 else 'FAIL'} (need >= 9)")
    run.write_evidence("genie_answers.txt", lines)
    sys.exit(0 if matched >= 9 else 1)


if __name__ == "__main__":
    main()
