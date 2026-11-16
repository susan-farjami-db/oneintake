-- Metric view over gold.projects. Run after governance so the row filter is in place.
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
  - name: season
    expr: "CASE WHEN month(submitted_month) IN (4, 5, 6, 9, 10, 11) THEN 'Peak freight season' ELSE 'Off-peak' END"
    comment: Peak freight season is produce season (Apr-Jun) plus the Q4 peak (Sep-Nov)
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
  - name: duplicate_value_usd
    expr: SUM(CASE WHEN is_duplicate THEN est_value_usd ELSE 0 END)
    comment: Estimated annual value of requests that duplicate other work (double-funding exposure)
  - name: open_value_usd
    expr: SUM(CASE WHEN is_open THEN est_value_usd ELSE 0 END)
    comment: Estimated annual value of requests still waiting for a decision
  - name: median_cycle_days
    expr: PERCENTILE_APPROX(cycle_days, 0.5)
    comment: Median days from submission to decision (decided requests only)
  - name: high_urgency_share
    expr: AVG(CASE WHEN urgency = 'high' THEN 1.0 ELSE 0.0 END)
    comment: Share of requests the requester marked high urgency
$$;
