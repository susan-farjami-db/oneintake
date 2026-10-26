-- Bronze: landing files from the raw volume plus current state of Lakebase tables.
-- Lakebase rows arrive through Lakehouse Sync (CDF config) as raw.lb_<table>_history.

CREATE OR REFRESH STREAMING TABLE ${catalog}.raw.bronze_opportunity_log
COMMENT 'Raw opportunity log rows loaded from CSV files in the landing volume'
AS SELECT *, _metadata.file_name AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/raw/landing/opportunity_log/',
  format => 'csv', header => true,
  schemaHints => 'est_value_usd DOUBLE, submitted_at TIMESTAMP, updated_at TIMESTAMP'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.raw.bronze_projects
COMMENT 'Raw project tracker records loaded from JSON files in the landing volume'
AS SELECT *, _metadata.file_name AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/raw/landing/project_tracker/',
  format => 'json', multiLine => true,
  schemaHints => 'est_value_usd DOUBLE, start_date DATE'
);

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.raw.bronze_intake_app
COMMENT 'Current state of each request submitted in the intake app (latest Lakebase change per request)'
AS SELECT * EXCEPT (rn, _pg_xid, _sort_by, _timestamp), CAST(_timestamp AS TIMESTAMP) AS synced_at
FROM (
  SELECT *, row_number() OVER (PARTITION BY request_id ORDER BY _pg_lsn DESC, _sort_by DESC) AS rn
  FROM ${catalog}.raw.lb_intake_requests_history
  WHERE _pg_change_type IN ('insert', 'update_postimage', 'delete')
)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.raw.bronze_category_labels
COMMENT 'Current category labels configured in the intake app'
AS SELECT label, description, active
FROM (
  SELECT *, row_number() OVER (PARTITION BY label ORDER BY _pg_lsn DESC, _sort_by DESC) AS rn
  FROM ${catalog}.raw.lb_category_labels_history
  WHERE _pg_change_type IN ('insert', 'update_postimage', 'delete')
)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.raw.bronze_form_config
COMMENT 'Current form field configuration from the intake app'
AS SELECT field_name, label, type, required, options, display_order
FROM (
  SELECT *, row_number() OVER (PARTITION BY field_name ORDER BY _pg_lsn DESC, _sort_by DESC) AS rn
  FROM ${catalog}.raw.lb_form_config_history
  WHERE _pg_change_type IN ('insert', 'update_postimage', 'delete')
)
WHERE rn = 1 AND _pg_change_type <> 'delete';
