# Genie space: AI Task Force portfolio

- Space id: set as `GENIE_SPACE_ID` (created by `genie/genie_space.py`)
- Open: `{workspace}/genie/rooms/<space id>`
- Warehouse: bundle variable `warehouse_id`
- Data sources:
  - table `{catalog}.gold.projects`
  - metric view `{catalog}.gold.portfolio_metrics`

## General instructions

```text
This space answers questions about the AI Task Force portfolio at the carrier.
- {catalog}.gold.projects has one row per intake request (source = 'request') and per tracked project (source = 'project').
  Unless the user asks about projects, answer about requests only (source = 'request').
- {catalog}.gold.portfolio_metrics is a metric view over requests with measures request_count, total_est_value, avg_cycle_days,
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
- Month means the submitted_month column (first day of the month).
```

## Sample questions and reference SQL

1. What is the backlog value by business unit?

   ```sql
   SELECT business_unit, SUM(est_value_usd) FROM {catalog}.gold.projects WHERE source = 'request' AND is_open GROUP BY 1
   ```

2. How many requests have been waiting more than 30 days?

   ```sql
   SELECT count(*) FROM {catalog}.gold.projects WHERE source = 'request' AND is_open AND datediff(current_date(), submitted_at) > 30
   ```

3. What is the duplicate rate by month?

   ```sql
   SELECT month, MEASURE(duplicate_rate) FROM {catalog}.gold.portfolio_metrics GROUP BY ALL
   ```

4. What are the top 5 requests by estimated value that are still in review?

   ```sql
   SELECT title, est_value_usd FROM {catalog}.gold.projects WHERE source = 'request' AND status = 'in_review' ORDER BY est_value_usd DESC LIMIT 5
   ```

5. How many requests are there in each category?

   ```sql
   SELECT category, MEASURE(request_count) FROM {catalog}.gold.portfolio_metrics GROUP BY ALL
   ```

6. What is the average cycle time in days by business unit?

   ```sql
   SELECT business_unit, MEASURE(avg_cycle_days) FROM {catalog}.gold.portfolio_metrics GROUP BY ALL
   ```

7. What is the duplicated value by business unit?

   ```sql
   SELECT business_unit, MEASURE(duplicate_value_usd) FROM {catalog}.gold.portfolio_metrics GROUP BY ALL
   ```

8. How many tracked projects are in progress?

   ```sql
   SELECT count(*) FROM {catalog}.gold.projects WHERE source = 'project' AND status = 'in_progress'
   ```

9. Which business unit submitted the most requests?

   ```sql
   SELECT business_unit, count(*) AS n FROM {catalog}.gold.projects WHERE source = 'request' GROUP BY 1 ORDER BY n DESC LIMIT 1
   ```

10. What is the median cycle time in days in peak season versus off-peak?

   ```sql
   SELECT season, MEASURE(median_cycle_days) FROM {catalog}.gold.portfolio_metrics GROUP BY ALL
   ```

Access follows Unity Catalog: the business-unit row filter on gold.projects applies to every Genie query.
