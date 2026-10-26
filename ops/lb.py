"""Lakebase helpers: OAuth connection, schema setup, config seeding, project sync."""

import json
import os
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parent.parent


def endpoint_name(project=None, branch=None, endpoint="primary"):
    project = project or os.environ.get("LAKEBASE_PROJECT", "oneintake")
    branch = branch or os.environ.get("LAKEBASE_BRANCH", "production")
    return f"projects/{project}/branches/{branch}/endpoints/{endpoint}"


def connect(w: WorkspaceClient, **kw) -> psycopg.Connection:
    """Connect with a fresh OAuth database credential (valid for one hour)."""
    ep = w.postgres.get_endpoint(name=endpoint_name(**kw))
    token = w.postgres.generate_database_credential(endpoint=ep.name).token
    user = w.config.client_id or w.current_user.me().user_name
    return psycopg.connect(host=ep.status.hosts.host, dbname="databricks_postgres",
                           user=user, password=token, sslmode="require", autocommit=True)


def split_sql(text: str) -> list[str]:
    stmts, buf = [], []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmts.append("\n".join(buf).strip().rstrip(";"))
            buf = []
    return [s for s in stmts if s]


def setup(w: WorkspaceClient, app_role: str | None = None) -> list[str]:
    text = (ROOT / "lakebase/setup.sql").read_text()
    schema_sql, grant_sql = text.split("-- @grants", 1)
    log = []
    with connect(w) as conn:
        for stmt in split_sql(schema_sql):
            conn.execute(stmt)
            log.append(stmt.splitlines()[0][:80])
        if app_role:
            for stmt in split_sql(grant_sql):
                conn.execute(stmt.replace(":app_role", app_role))
                log.append(stmt.replace(":app_role", app_role)[:100])
        log += seed_config(conn)
    return log


def seed_config(conn: psycopg.Connection) -> list[str]:
    fields = json.loads((ROOT / "config/form_fields.json").read_text())
    cfg = json.loads((ROOT / "config/app_config.json").read_text())
    for f in fields:
        conn.execute(
            """INSERT INTO app.form_config (field_name, label, type, required, options, display_order)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (field_name) DO UPDATE SET label = EXCLUDED.label, type = EXCLUDED.type,
                 required = EXCLUDED.required, options = EXCLUDED.options,
                 display_order = EXCLUDED.display_order""",
            (f["field_name"], f["label"], f["type"], f["required"],
             json.dumps(f["options"]) if f["options"] else None, f["display_order"]))
    for c in cfg["categories"]:
        conn.execute(
            """INSERT INTO app.category_labels (label, description, active) VALUES (%s, %s, true)
               ON CONFLICT (label) DO UPDATE SET description = EXCLUDED.description""",
            (c["label"], c["description"]))
    return [f"seeded form_config={len(fields)} category_labels={len(cfg['categories'])}"]


def sync_projects(w: WorkspaceClient, rows: list[dict]) -> int:
    """Replace serving.projects_synced with the current gold.projects rows."""
    with connect(w) as conn, conn.transaction():
        conn.execute("DELETE FROM serving.projects_synced")
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO serving.projects_synced (project_key, source, title, description,
                     business_unit, owner_email, status, category, est_value_usd, embedding)
                   VALUES (%(project_key)s, %(source)s, %(title)s, %(description)s, %(business_unit)s,
                     %(owner_email)s, %(status)s, %(category)s, %(est_value_usd)s, %(embedding)s::vector)""",
                rows)
    return len(rows)
