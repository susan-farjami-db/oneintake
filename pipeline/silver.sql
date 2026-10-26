-- Silver: cleaned requests with expectations, ai_classify (v2.1) categories, ai_extract fields.

CREATE TEMPORARY VIEW requests_union AS
SELECT request_id, title, description, business_unit, requester_email, sponsor, problem_statement,
       expected_benefit, CAST(est_value_usd AS DOUBLE) AS est_value_usd, data_sources, urgency, status,
       CAST(submitted_at AS TIMESTAMP) AS submitted_at, CAST(updated_at AS TIMESTAMP) AS updated_at,
       CAST(NULL AS STRING) AS duplicate_of, 'opportunity_log' AS source
FROM ${catalog}.raw.bronze_opportunity_log
UNION ALL
SELECT request_id, title, description, business_unit, requester_email, sponsor, problem_statement,
       expected_benefit, CAST(est_value_usd AS DOUBLE), data_sources, urgency, status,
       CAST(submitted_at AS TIMESTAMP), CAST(updated_at AS TIMESTAMP), duplicate_of, 'intake_app'
FROM ${catalog}.raw.bronze_intake_app;

CREATE TEMPORARY VIEW allowed_units AS
SELECT DISTINCT explode(from_json(options, 'array<string>')) AS business_unit
FROM ${catalog}.raw.bronze_form_config
WHERE field_name = 'business_unit';

CREATE TEMPORARY VIEW requests_checked AS
SELECT r.*, a.business_unit IS NOT NULL AS bu_valid
FROM requests_union r
LEFT JOIN allowed_units a ON r.business_unit = a.business_unit;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.requests (
  CONSTRAINT title_not_null EXPECT (title IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT description_not_null EXPECT (description IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT business_unit_allowed EXPECT (bu_valid) ON VIOLATION DROP ROW,
  CONSTRAINT est_value_non_negative EXPECT (coalesce(est_value_usd >= 0, false)) ON VIOLATION DROP ROW
)
COMMENT 'Cleaned intake requests from the opportunity log and the intake app, categorized with ai_classify and enriched with ai_extract'
AS
WITH labels AS (
  SELECT to_json(map_from_entries(collect_list(struct(label, description)))) AS labels_json
  FROM ${catalog}.raw.bronze_category_labels
  WHERE active
),
scored AS (
  SELECT r.*,
    ai_classify(concat_ws('. ', title, description, problem_statement, expected_benefit), l.labels_json,
      map('version', '2.1', 'instructions', '${classify_instructions}', 'enableConfidenceScores', 'true')) AS cls,
    ai_classify(concat_ws('. ', title, description, problem_statement, expected_benefit), l.labels_json,
      map('version', '2.1', 'instructions', '${classify_instructions}', 'multilabel', 'true')) AS cls_multi,
    ai_extract(concat_ws('. ', title, description, problem_statement, expected_benefit, data_sources),
      '{"data_sources": {"type": "array", "items": {"type": "string"}, "description": "Data sources or datasets the request would use"},
        "systems": {"type": "array", "items": {"type": "string"}, "description": "Business systems named, such as TMS or ERP"},
        "value_drivers": {"type": "array", "items": {"type": "string"}, "description": "Benefits such as hours saved, errors avoided, or revenue"}}',
      map('version', '2.1')) AS ext
  FROM requests_checked r CROSS JOIN labels l
)
SELECT * EXCEPT (cls, cls_multi, ext, bu_valid),
  cls:response[0].value::string AS category,
  cls:response[0].confidence_score::double AS category_confidence,
  filter(transform(cast(cls_multi:response AS ARRAY<VARIANT>), x -> x:value::string),
         x -> x <> cls:response[0].value::string) AS secondary_categories,
  named_struct(
    'data_sources', transform(cast(ext:response.data_sources AS ARRAY<VARIANT>), x -> x:value::string),
    'systems', transform(cast(ext:response.systems AS ARRAY<VARIANT>), x -> x:value::string),
    'value_drivers', transform(cast(ext:response.value_drivers AS ARRAY<VARIANT>), x -> x:value::string)
  ) AS extracted_fields,
  bu_valid
FROM scored;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.requests_quarantine
COMMENT 'Rows dropped by the silver.requests expectations, with the rules each row failed'
AS SELECT *,
  filter(array(
    IF(title IS NULL, 'title_not_null', NULL),
    IF(description IS NULL, 'description_not_null', NULL),
    IF(NOT bu_valid, 'business_unit_allowed', NULL),
    IF(NOT coalesce(est_value_usd >= 0, false), 'est_value_non_negative', NULL)
  ), x -> x IS NOT NULL) AS failed_rules
FROM requests_checked
WHERE title IS NULL OR description IS NULL OR NOT bu_valid OR NOT coalesce(est_value_usd >= 0, false);
