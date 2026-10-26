"""Ops runner used locally and by bundle jobs.

Usage: python ops/run.py <command> [args]
Commands: discover | upload | lakebase-setup [app_role] | cdf | uc-sql <file> [section]
          | sync-projects | pipeline-evidence
Env: INTAKE_CATALOG, DATABRICKS_SQL_WAREHOUSE_ID, LAKEBASE_PROJECT, DATABRICKS_CONFIG_PROFILE
"""

import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import CdfConfig
from databricks.sdk.service.sql import Disposition, StatementState

sys.path.insert(0, str(Path(__file__).parent))
import lb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence"
PREFERRED_EMBEDDINGS = ["databricks-bge-large-en", "databricks-gte-large-en",
                        "databricks-qwen3-embedding-0-6b"]


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        sys.exit(f"missing env var {name}")
    return v


def write_evidence(name, lines):
    EVIDENCE.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (EVIDENCE / name).write_text(f"# generated {stamp}\n" + "\n".join(map(str, lines)) + "\n")
    print("\n".join(map(str, lines)))


def sql(w, stmt, wh=None):
    """Run one statement on the warehouse and return rows as dicts (all chunks)."""
    r = w.statement_execution.execute_statement(statement=stmt, wait_timeout="50s",
                                                warehouse_id=wh or env("DATABRICKS_SQL_WAREHOUSE_ID"),
                                                disposition=Disposition.INLINE)
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.error.message if r.status.error else r.status.state}\n{stmt[:300]}")
    if not r.manifest or not r.manifest.schema.columns:
        return []
    cols = [c.name for c in r.manifest.schema.columns]
    rows, chunk = list(r.result.data_array or []), r.result
    while chunk.next_chunk_index:
        chunk = w.statement_execution.get_statement_result_chunk_n(r.statement_id, chunk.next_chunk_index)
        rows += chunk.data_array or []
    return [dict(zip(cols, row)) for row in rows]


def render(path, section=None):
    text = (ROOT / path).read_text().replace("${catalog}", env("INTAKE_CATALOG"))
    if section:
        parts = re.split(r"^-- @section (\w+)\s*$", text, flags=re.M)
        text = dict(zip(parts[1::2], parts[2::2])).get(section, "")
    return lb.split_sql(text)


def discover(w):
    eps = {e.name: e for e in w.serving_endpoints.list()}
    found = [n for n in PREFERRED_EMBEDDINGS if n in eps]
    others = sorted(n for n in eps if "embed" in n or n.endswith(("-gte-large-en", "-bge-large-en")))
    chosen = found[0] if found else (others[0] if others else None)
    write_evidence("embedding_endpoint.txt", [f"available_embedding_endpoints={sorted(set(found + others))}",
                                              f"chosen={chosen}"])


def upload(w):
    sys.path.insert(0, str(ROOT / "data_gen"))
    import generate
    generate.main(ROOT)
    base = f"/Volumes/{env('INTAKE_CATALOG')}/raw/landing"
    files = {"opportunity_log/opportunity_log.csv": "data/raw/opportunity_log.csv",
             "opportunity_log/opportunity_log_rejects.csv": "data/raw/opportunity_log_rejects.csv",
             "project_tracker/project_tracker.json": "data/raw/project_tracker.json"}
    for dest, src in files.items():
        w.files.upload(f"{base}/{dest}", io.BytesIO((ROOT / src).read_bytes()), overwrite=True)
        print("uploaded", dest)


def cdf(w):
    db = lb.endpoint_name().rsplit("/endpoints/", 1)[0] + "/databases/" + env("LAKEBASE_DATABASE_ID", "databricks-postgres")
    try:
        existing = list(w.postgres.list_cdf_configs(parent=db))
    except Exception:
        existing = []
    if not existing:
        w.postgres.create_cdf_config(parent=db, cdf_config_id="app_to_raw", cdf_config=CdfConfig(
            catalog=env("INTAKE_CATALOG"), schema="raw", postgres_schema="app")).wait()
    for _ in range(60):
        st = list(w.postgres.list_cdf_statuses(parent=f"{db}/cdf-configs/app_to_raw"))
        print([(s.postgres_table, str(s.state), s.uc_table) for s in st])
        if st and all("STREAMING" in str(s.state) for s in st):
            break
        time.sleep(10)


def sync_projects(w):
    rows = sql(w, f"""SELECT project_key, source, title, description, business_unit, owner_email, status,
                      category, est_value_usd, to_json(embedding) AS embedding
                      FROM {env('INTAKE_CATALOG')}.gold.projects WHERE embedding IS NOT NULL""")
    n = lb.sync_projects(w, rows)
    write_evidence("projects_sync.txt", [f"synced_rows={n}"])


def pipeline_evidence(w):
    pid = next(p.pipeline_id for p in w.pipelines.list_pipelines(filter="name LIKE '%oneintake-medallion%'"))
    cat = env("INTAKE_CATALOG")
    exp = sql(w, f"""SELECT e.dataset, e.name, SUM(e.passed_records) AS passed, SUM(e.failed_records) AS failed
        FROM (SELECT explode(from_json(details:flow_progress:data_quality:expectations,
              'array<struct<name:string,dataset:string,passed_records:long,failed_records:long>>')) e
              FROM event_log('{pid}') WHERE event_type = 'flow_progress'
              AND origin.update_id = (SELECT origin.update_id FROM event_log('{pid}')
                  WHERE event_type = 'create_update' ORDER BY timestamp DESC LIMIT 1))
        GROUP BY ALL ORDER BY 1, 2""")
    counts = sql(w, f"""SELECT 'raw.bronze_opportunity_log' t, count(*) n FROM {cat}.raw.bronze_opportunity_log
        UNION ALL SELECT 'raw.bronze_projects', count(*) FROM {cat}.raw.bronze_projects
        UNION ALL SELECT 'raw.bronze_intake_app', count(*) FROM {cat}.raw.bronze_intake_app
        UNION ALL SELECT 'silver.requests', count(*) FROM {cat}.silver.requests
        UNION ALL SELECT 'silver.requests_quarantine', count(*) FROM {cat}.silver.requests_quarantine
        UNION ALL SELECT 'gold.projects', count(*) FROM {cat}.gold.projects""")
    n = {r["t"]: int(r["n"]) for r in counts}
    checks = {
        "bronze_rows_split_into_silver_or_quarantine": n["raw.bronze_opportunity_log"] + n["raw.bronze_intake_app"]
        == n["silver.requests"] + n["silver.requests_quarantine"],
        "gold_rows_equal_silver_plus_projects": n["gold.projects"] == n["silver.requests"] + n["raw.bronze_projects"],
        "silver_not_empty": n["silver.requests"] > 0,
    }
    write_evidence("pipeline_event_log.txt", [f"pipeline_id={pid}", "## expectations (latest update)"]
                   + [json.dumps(r) for r in exp] + ["## row counts"] + [json.dumps(r) for r in counts]
                   + ["## self-check"] + [f"{k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items()])
    if not all(checks.values()):
        sys.exit("pipeline self-check failed")


def main():
    w = WorkspaceClient()
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "discover":
        discover(w)
    elif cmd == "upload":
        upload(w)
    elif cmd == "lakebase-setup":
        print("\n".join(lb.setup(w, args[0] if args else None)))
    elif cmd == "cdf":
        cdf(w)
    elif cmd == "uc-sql":
        for stmt in render(args[0], args[1] if len(args) > 1 else None):
            print("--", stmt.splitlines()[0][:100])
            for row in sql(w, stmt):
                print(row)
    elif cmd == "sync-projects":
        sync_projects(w)
    elif cmd == "pipeline-evidence":
        pipeline_evidence(w)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
