-- Lakebase (Postgres 17) schema for the intake app. Idempotent.
-- Schema `app` is replicated to Unity Catalog by Lakehouse Sync (CDF config), so it
-- only uses CDF-supported types (text, bool, numeric, real, int4, jsonb, timestamptz).
-- Schema `serving` is NOT replicated: pgvector embeddings and the read-only project copy.
-- Placeholder :app_role is replaced by the app service principal client id.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS serving;

CREATE TABLE IF NOT EXISTS app.intake_requests (
  request_id           text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  title                text NOT NULL,
  description          text NOT NULL,
  business_unit        text,
  requester_email      text NOT NULL,
  sponsor              text,
  problem_statement    text,
  expected_benefit     text,
  est_value_usd        numeric(14, 2),
  data_sources         text,
  urgency              text CHECK (urgency IN ('low', 'medium', 'high')),
  status               text NOT NULL DEFAULT 'submitted'
                       CHECK (status IN ('submitted', 'in_review', 'approved', 'merged', 'rejected')),
  category             text,
  category_confidence  real,
  duplicate_of         text,
  dup_score            real,
  dup_check_failed     boolean NOT NULL DEFAULT false,
  submit_anyway_reason text,
  extra_fields         jsonb NOT NULL DEFAULT '{}'::jsonb,
  submitted_at         timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_requests_requester ON app.intake_requests (requester_email);
CREATE INDEX IF NOT EXISTS ix_requests_status ON app.intake_requests (status);

CREATE TABLE IF NOT EXISTS app.review_decisions (
  decision_id    text PRIMARY KEY DEFAULT gen_random_uuid()::text,
  request_id     text NOT NULL REFERENCES app.intake_requests (request_id),
  reviewer_email text NOT NULL,
  action         text NOT NULL CHECK (action IN ('approve', 'merge', 'reject')),
  merged_into    text,
  reason         text,
  decided_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.form_config (
  field_name    text PRIMARY KEY,
  label         text NOT NULL,
  type          text NOT NULL,
  required      boolean NOT NULL DEFAULT false,
  options       jsonb,
  display_order integer NOT NULL
);

CREATE TABLE IF NOT EXISTS app.category_labels (
  label       text PRIMARY KEY,
  description text NOT NULL,
  active      boolean NOT NULL DEFAULT true
);

ALTER TABLE app.intake_requests REPLICA IDENTITY FULL;
ALTER TABLE app.review_decisions REPLICA IDENTITY FULL;
ALTER TABLE app.form_config REPLICA IDENTITY FULL;
ALTER TABLE app.category_labels REPLICA IDENTITY FULL;

CREATE TABLE IF NOT EXISTS serving.request_embeddings (
  request_id text PRIMARY KEY REFERENCES app.intake_requests (request_id) ON DELETE CASCADE,
  embedding  vector(1024) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Read-only copy of gold.projects, refreshed by the sync_projects job task.
CREATE TABLE IF NOT EXISTS serving.projects_synced (
  project_key   text PRIMARY KEY,
  source        text NOT NULL,
  title         text NOT NULL,
  description   text,
  business_unit text,
  owner_email   text,
  status        text,
  category      text,
  est_value_usd numeric(14, 2),
  embedding     vector(1024),
  synced_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_req_emb_hnsw ON serving.request_embeddings
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS ix_proj_emb_hnsw ON serving.projects_synced
  USING hnsw (embedding vector_cosine_ops);

-- @grants (run once the app service principal role exists)
GRANT USAGE ON SCHEMA app, serving TO ":app_role";
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO ":app_role";
GRANT SELECT, INSERT, UPDATE ON serving.request_embeddings TO ":app_role";
GRANT SELECT ON serving.projects_synced TO ":app_role";
