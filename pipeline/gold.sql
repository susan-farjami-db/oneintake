-- Gold: one row per request or tracked project with portfolio fields, embedding, and duplicate cluster.
-- The metric view gold.portfolio_metrics is created over this table by governance/metric_view.sql
-- (section metric_view) because pipelines cannot define metric views.

CREATE TEMPORARY VIEW portfolio_base AS
SELECT request_id AS project_key, 'request' AS source, title, description, business_unit,
       requester_email AS owner_email, sponsor, status, category, category_confidence,
       secondary_categories, extracted_fields, est_value_usd, urgency, submitted_at,
       CASE WHEN status IN ('approved', 'merged', 'rejected') THEN updated_at END AS decided_at,
       duplicate_of
FROM ${catalog}.silver.requests
UNION ALL
SELECT project_id, 'project', name, description, business_unit, owner_email, CAST(NULL AS STRING),
       status, category, CAST(NULL AS DOUBLE), CAST(array() AS ARRAY<STRING>),
       named_struct('data_sources', CAST(array() AS ARRAY<STRING>), 'systems', systems,
                    'value_drivers', CAST(array() AS ARRAY<STRING>)),
       est_value_usd, CAST(NULL AS STRING), CAST(start_date AS TIMESTAMP), CAST(NULL AS TIMESTAMP),
       CAST(NULL AS STRING)
FROM ${catalog}.raw.bronze_projects;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.projects_embedded
COMMENT 'Portfolio rows with document embeddings from the Foundation Model API embedding endpoint'
AS SELECT *, ai_query('${embedding_endpoint}', concat_ws('. ', title, description)) AS embedding
FROM portfolio_base;

CREATE TEMPORARY VIEW similar_pairs AS
WITH v AS (
  SELECT project_key, embedding, sqrt(aggregate(embedding, 0D, (acc, x) -> acc + x * x)) AS norm
  FROM ${catalog}.gold.projects_embedded
)
SELECT a.project_key AS key_a, b.project_key AS key_b,
       aggregate(zip_with(a.embedding, b.embedding, (x, y) -> x * y), 0D, (acc, x) -> acc + x)
         / (a.norm * b.norm) AS similarity
FROM v a JOIN v b ON a.project_key < b.project_key;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.projects
COMMENT 'Governed AI portfolio: one row per intake request or tracked project, with category, value, cycle time, duplicate cluster, and embedding'
AS
WITH links AS (
  SELECT key_a AS k, key_b AS other FROM similar_pairs WHERE similarity >= ${cluster_threshold}
  UNION ALL
  SELECT key_b, key_a FROM similar_pairs WHERE similarity >= ${cluster_threshold}
  UNION ALL
  SELECT project_key, duplicate_of FROM ${catalog}.gold.projects_embedded WHERE duplicate_of IS NOT NULL
  UNION ALL
  SELECT duplicate_of, project_key FROM ${catalog}.gold.projects_embedded WHERE duplicate_of IS NOT NULL
),
clusters AS (
  SELECT k, least(k, min(other)) AS cluster_id, count(*) AS link_count FROM links GROUP BY k
)
SELECT p.project_key, p.source, p.title, p.description, p.business_unit, p.owner_email, p.sponsor,
       p.status, p.category, p.category_confidence, p.secondary_categories, p.extracted_fields,
       p.est_value_usd, p.urgency, p.submitted_at, p.decided_at,
       date_trunc('MONTH', p.submitted_at) AS submitted_month,
       datediff(p.decided_at, p.submitted_at) AS cycle_days,
       p.duplicate_of,
       coalesce(c.cluster_id, p.project_key) AS duplicate_cluster_id,
       (p.source = 'request' AND (p.duplicate_of IS NOT NULL OR p.status = 'merged'
         OR coalesce(c.cluster_id, p.project_key) <> p.project_key)) AS is_duplicate,
       p.status IN ('submitted', 'in_review') AS is_open,
       p.embedding
FROM ${catalog}.gold.projects_embedded p
LEFT JOIN clusters c ON c.k = p.project_key;
