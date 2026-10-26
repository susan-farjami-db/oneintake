-- Unity Catalog setup for the intake demo. Run by ops/run.py uc-sql <file> <section>.
-- ${catalog} is replaced from the INTAKE_CATALOG env var / bundle variable.

-- @section bootstrap
CREATE SCHEMA IF NOT EXISTS ${catalog}.raw COMMENT 'Landing files and Lakebase change history (bronze inputs)';
CREATE SCHEMA IF NOT EXISTS ${catalog}.silver COMMENT 'Cleaned and AI-enriched intake requests';
CREATE SCHEMA IF NOT EXISTS ${catalog}.gold COMMENT 'Governed portfolio tables and metric views for leadership';
CREATE SCHEMA IF NOT EXISTS ${catalog}.ops COMMENT 'Access mappings and operational config for the intake app';
CREATE VOLUME IF NOT EXISTS ${catalog}.raw.landing COMMENT 'Landing zone for synthetic opportunity log and project tracker files';
CREATE TABLE IF NOT EXISTS ${catalog}.ops.user_business_unit (
  user_email STRING NOT NULL COMMENT 'Workspace user email',
  business_unit STRING NOT NULL COMMENT 'Business unit whose rows the user may see'
) COMMENT 'Maps non task_force users to the business unit they may see through row filters';

-- @section governance
-- Column glossary: one comment per column name, applied to every governed table below.
CREATE OR REPLACE TABLE ${catalog}.ops.column_glossary (
  column_name STRING COMMENT 'Column name the comment applies to in every governed table',
  comment STRING COMMENT 'Comment text applied to that column')
COMMENT 'Column descriptions applied to every governed table by uc_setup.sql';
INSERT INTO ${catalog}.ops.column_glossary VALUES
 ('request_id', 'Intake request identifier'), ('project_id', 'Tracked project identifier'),
 ('project_key', 'Request id or project id, unique across the portfolio'),
 ('source', 'Origin of the row (log, app, request, project)'),
 ('title', 'Short request or project title'), ('name', 'Tracked project name'),
 ('description', 'Free-text description'),
 ('business_unit', 'Business unit that owns the request or project'),
 ('requester_email', 'Email of the person who submitted the request'), ('user_email', 'Workspace user email'),
 ('owner', 'Display name of the project owner'), ('owner_email', 'Email of the request or project owner'),
 ('sponsor', 'Executive sponsor named on the request'), ('reviewer_email', 'Task Force member who made the decision'),
 ('problem_statement', 'Business problem the requester wants solved'),
 ('expected_benefit', 'Benefit the requester expects'), ('est_value_usd', 'Estimated annual value in US dollars'),
 ('data_sources', 'Systems the request expects to use'), ('systems', 'Systems the project uses'),
 ('urgency', 'Requester urgency: low, medium, or high'),
 ('status', 'Lifecycle status of the request or project'),
 ('submitted_at', 'When the request was submitted or the project started'),
 ('updated_at', 'Last change time in the source system'), ('start_date', 'Project start date'),
 ('decided_at', 'When the Task Force decided the request'), ('submitted_month', 'Month of submitted_at'),
 ('cycle_days', 'Days from submission to decision'),
 ('category', 'Primary category (ai_classify for requests)'),
 ('category_confidence', 'ai_classify confidence for the primary category'),
 ('secondary_categories', 'Other matching categories from multilabel ai_classify'),
 ('extracted_fields', 'Fields extracted by ai_extract'),
 ('duplicate_of', 'Request or project this row was merged into'),
 ('duplicate_cluster_id', 'Shared id for rows that are duplicates of each other'),
 ('is_duplicate', 'True when the request duplicates an earlier request or project'),
 ('is_open', 'True while the request is submitted or in review'),
 ('embedding', 'Title and description embedding (Foundation Model API)'),
 ('dup_score', 'Highest duplicate-check score shown when submitting'),
 ('dup_check_failed', 'True when the live duplicate check was unavailable at submit'),
 ('submit_anyway_reason', 'Reason given for submitting despite a likely duplicate'),
 ('extra_fields', 'Extra config-driven form fields as JSON'),
 ('decision_id', 'Review decision identifier'), ('action', 'Review action: approve, merge, or reject'),
 ('merged_into', 'Target request or project of a merge'), ('reason', 'Reviewer note for the decision'),
 ('label', 'Category label'), ('active', 'True when the label is offered to ai_classify'),
 ('field_name', 'Form field key'), ('type', 'Form field input type'), ('required', 'True when the field is mandatory'),
 ('options', 'Allowed values for select fields, as a JSON array'), ('display_order', 'Order of the field on the form'),
 ('bu_valid', 'True when business_unit is one of the configured options'),
 ('failed_rules', 'Data quality rules the row failed'), ('_rescued_data', 'Unparsed source fields from Auto Loader'),
 ('source_file', 'Landing file the row was read from'), ('ingested_at', 'When the row was ingested'),
 ('synced_at', 'When Lakehouse Sync captured the latest change'),
 ('_pg_change_type', 'Lakebase change type'), ('_pg_lsn', 'Lakebase log sequence number of the change'),
 ('_pg_xid', 'Lakebase transaction id'), ('_timestamp', 'Commit time of the Lakebase change'),
 ('_sort_by', 'Ordering key for Lakebase changes');

COMMENT ON TABLE ${catalog}.raw.lb_intake_requests_history IS 'Lakehouse Sync change history of app.intake_requests in Lakebase';
COMMENT ON TABLE ${catalog}.raw.lb_review_decisions_history IS 'Lakehouse Sync change history of app.review_decisions in Lakebase';
COMMENT ON TABLE ${catalog}.raw.lb_form_config_history IS 'Lakehouse Sync change history of app.form_config in Lakebase';
COMMENT ON TABLE ${catalog}.raw.lb_category_labels_history IS 'Lakehouse Sync change history of app.category_labels in Lakebase';

-- Comment every governed column; tag email and name columns as PII.
BEGIN
  FOR c AS SELECT concat_ws('.', '`${catalog}`', t.table_schema, t.table_name) AS fq,
      CASE t.table_type WHEN 'MATERIALIZED_VIEW' THEN 'MATERIALIZED VIEW'
        WHEN 'STREAMING_TABLE' THEN 'STREAMING TABLE' ELSE 'TABLE' END AS kind,
      col.column_name AS col_name, g.comment AS col_comment
    FROM ${catalog}.information_schema.tables t
    JOIN ${catalog}.information_schema.columns col USING (table_schema, table_name)
    JOIN ${catalog}.ops.column_glossary g ON g.column_name = col.column_name
    WHERE t.table_schema IN ('raw', 'silver', 'gold', 'ops') AND t.table_type IN ('MANAGED', 'MATERIALIZED_VIEW', 'STREAMING_TABLE')
      AND t.table_name NOT LIKE '\_\_%' AND t.table_name NOT LIKE 'event_log%'
  DO
    EXECUTE IMMEDIATE 'ALTER ' || c.kind || ' ' || c.fq || ' ALTER COLUMN `' || c.col_name || '` COMMENT \'' || c.col_comment || '\'';
    IF c.col_name RLIKE 'email|^owner$|^sponsor$' THEN
      EXECUTE IMMEDIATE 'ALTER ' || c.kind || ' ' || c.fq || ' ALTER COLUMN `' || c.col_name || '` SET TAGS (\'sensitivity\' = \'pii\')';
    END IF;
  END FOR;
END;

-- Table tags follow the account tag policies: business_unit = billed-to unit, sensitivity in (pii, internal, public).
ALTER MATERIALIZED VIEW ${catalog}.silver.requests SET TAGS ('sensitivity' = 'pii', 'business_unit' = 'Operations');
ALTER MATERIALIZED VIEW ${catalog}.gold.projects SET TAGS ('sensitivity' = 'pii', 'business_unit' = 'Operations');
ALTER MATERIALIZED VIEW ${catalog}.gold.projects_embedded SET TAGS ('sensitivity' = 'pii', 'business_unit' = 'Operations');
ALTER TABLE ${catalog}.ops.user_business_unit SET TAGS ('sensitivity' = 'pii', 'business_unit' = 'Operations');

-- Row filter: task_force sees everything; everyone else sees only their mapped business unit.
CREATE OR REPLACE FUNCTION ${catalog}.ops.business_unit_filter(bu STRING)
RETURN is_account_group_member('task_force') OR is_member('task_force')
  OR EXISTS (SELECT 1 FROM ${catalog}.ops.user_business_unit u
             WHERE lower(u.user_email) = lower(current_user()) AND u.business_unit = bu);
ALTER MATERIALIZED VIEW ${catalog}.silver.requests SET ROW FILTER ${catalog}.ops.business_unit_filter ON (business_unit);
ALTER MATERIALIZED VIEW ${catalog}.gold.projects SET ROW FILTER ${catalog}.ops.business_unit_filter ON (business_unit);

-- @section metric_view
CREATE OR REPLACE VIEW ${catalog}.gold.portfolio_metrics
WITH METRICS LANGUAGE YAML
COMMENT 'Intake request KPIs for the AI Task Force portfolio (requests only, row filter inherited from gold.projects)'
AS $$
version: 1.1
source: ${catalog}.gold.projects
filter: source = 'request'
dimensions:
  - name: category
    expr: category
  - name: business_unit
    expr: business_unit
  - name: status
    expr: status
  - name: month
    expr: submitted_month
    comment: First day of the submission month
measures:
  - name: request_count
    expr: COUNT(1)
  - name: total_est_value
    expr: SUM(est_value_usd)
    comment: Sum of estimated annual value in USD
  - name: avg_cycle_days
    expr: AVG(cycle_days)
    comment: Average days from submission to decision (decided requests only)
  - name: duplicate_rate
    expr: AVG(CASE WHEN is_duplicate THEN 1.0 ELSE 0.0 END)
    comment: Share of requests that duplicate an earlier request or project
$$;
