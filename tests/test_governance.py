"""Phase 3 self-check against the live catalog: comments, tags, and the business-unit row filter.

Writes evidence/governance_check.txt. Skipped when INTAKE_CATALOG is not set.
"""

import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ops"))
pytestmark = pytest.mark.skipif(not os.environ.get("INTAKE_CATALOG"), reason="needs a live workspace")

GOVERNED = """t.table_schema IN ('raw', 'silver', 'gold', 'ops') AND t.table_type IN ('MANAGED', 'MATERIALIZED_VIEW', 'STREAMING_TABLE')
  AND t.table_name NOT LIKE '\\_\\_%' AND t.table_name NOT LIKE 'event_log%'"""
FILTERED = ("silver.requests", "gold.projects")


def static_checks(cat):
    tables = f"{cat}.information_schema.tables t"
    cols = f"{cat}.information_schema.columns c"
    return {
        "tables_without_comment": f"SELECT count(*) n FROM {tables} WHERE {GOVERNED} AND coalesce(t.comment, '') = ''",
        "columns_without_comment": f"""SELECT count(*) n FROM {tables} JOIN {cols} USING (table_schema, table_name)
            WHERE {GOVERNED} AND coalesce(c.comment, '') = ''""",
        "email_columns_without_pii_tag": f"""SELECT count(*) n FROM {tables} JOIN {cols} USING (table_schema, table_name)
            LEFT JOIN {cat}.information_schema.column_tags g ON g.schema_name = c.table_schema
              AND g.table_name = c.table_name AND g.column_name = c.column_name
              AND g.tag_name = 'sensitivity' AND g.tag_value = 'pii'
            WHERE {GOVERNED} AND c.column_name LIKE '%email%' AND g.tag_name IS NULL""",
        "filtered_tables_missing_tags": f"""SELECT 4 - count(*) n FROM {cat}.information_schema.table_tags
            WHERE concat(schema_name, '.', table_name) IN {FILTERED} AND tag_name IN ('sensitivity', 'business_unit')""",
        "filtered_tables_missing_row_filter": f"""SELECT 2 - count(DISTINCT table_name) n FROM {cat}.information_schema.row_filters
            WHERE concat(table_schema, '.', table_name) IN {FILTERED}""",
    }


def set_task_force(w, member: bool):
    from databricks.sdk.service import iam
    me = w.current_user.me()
    g = next(w.groups.list(filter='displayName eq "task_force"'))
    op = iam.Patch(op=iam.PatchOp.ADD, path="members", value=[{"value": me.id}]) if member else \
        iam.Patch(op=iam.PatchOp.REMOVE, path=f'members[value eq "{me.id}"]')
    w.groups.patch(g.id, operations=[op], schemas=[iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP])
    return me.user_name


def wait_member(run, w, expected: bool):
    for _ in range(30):  # group membership is cached by the warehouse for about a minute
        if run.sql(w, f"SELECT is_member('task_force') m, {time.time_ns()} AS nonce")[0]["m"] == str(expected).lower():
            return
        time.sleep(10)


def visible(run, w, cat):
    nonce = time.time_ns()  # bypasses the warehouse result cache, which ignores group changes
    return {t: run.sql(w, f"""SELECT count(*) n, count(DISTINCT business_unit) bus, max(business_unit) bu,
                              {nonce} AS nonce FROM {cat}.{t}""")[0] for t in FILTERED}


def test_governance():
    import run
    from databricks.sdk import WorkspaceClient
    w, cat = WorkspaceClient(), os.environ["INTAKE_CATALOG"]
    lines, ok = [], True
    for name, stmt in static_checks(cat).items():
        n = int(run.sql(w, stmt)[0]["n"])
        ok &= n == 0
        lines.append(f"{name}={n} {'PASS' if n == 0 else 'FAIL'}")

    expected = {"silver.requests": run.sql(w, f"SELECT count(*) n FROM {cat}.silver.requests_quarantine")[0]["n"]}
    set_task_force(w, True)
    wait_member(run, w, True)
    full = visible(run, w, cat)
    unfiltered_gold = int(run.sql(w, f"SELECT count(*) n FROM {cat}.gold.projects_embedded")[0]["n"])
    tf_ok = int(full["gold.projects"]["n"]) == unfiltered_gold
    ok &= tf_ok
    lines.append(f"task_force member sees all gold rows: {full['gold.projects']['n']}/{unfiltered_gold} "
                 f"{'PASS' if tf_ok else 'FAIL'}")

    user = set_task_force(w, False)
    run.sql(w, f"INSERT INTO {cat}.ops.user_business_unit VALUES ('{user}', 'Finance')")
    try:
        wait_member(run, w, False)
        seen = visible(run, w, cat)
        finance = int(run.sql(w, f"""SELECT count(*) n FROM {cat}.gold.projects_embedded
                                     WHERE business_unit = 'Finance'""")[0]["n"])
        for t, s in seen.items():
            good = s["bus"] == "1" and s["bu"] == "Finance" and int(s["n"]) > 0
            if t == "gold.projects":
                good &= int(s["n"]) == finance
            ok &= good
            lines.append(f"non-member mapped to Finance sees {t}: rows={s['n']} units={s['bus']} unit={s['bu']} "
                         f"{'PASS' if good else 'FAIL'}")
    finally:
        run.sql(w, f"DELETE FROM {cat}.ops.user_business_unit WHERE user_email = '{user}'")
        set_task_force(w, True)
    lines.append(f"quarantine rows (unfiltered, context)={expected['silver.requests']}")
    lines.append(f"OVERALL {'PASS' if ok else 'FAIL'}")
    run.write_evidence("governance_check.txt", lines)
    assert ok
