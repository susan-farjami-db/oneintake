# Build report: AI Task Force intake

All 8 phases are built, deployed to the `dev` target, and checked. The deployed app passed the demo flow on 4 of 4 cold restarts, and again on 2026-11-16 after the freight-shaped data refresh (D10). Evidence for every claim below is in `evidence/`.

## What was built
- **Data (P1):** seeded synthetic opportunity log (300 requests, with planted near-duplicates, ambiguous items, and bad rows) plus a project tracker (60 projects). Names come only from `data_gen/names.py`. `data_gen/shape.py` adds freight seasonality, business-unit skew in volume, value, and urgency, and cross-unit duplicates (D10); the distributions are printed in `evidence/data_gen.txt`.
- **Pipeline (P2):** SDP SQL, bronze → silver (expectations, quarantine, `ai_extract`, `ai_classify`) → gold (BGE embeddings, duplicate clusters, one row per request or project). Lakebase app rows arrive through Lakehouse Sync.
- **Governance (P3):** glossary-driven comments on every table and column, tags under the account tag policies, a business-unit row filter, the `gold.portfolio_metrics` metric view, and the Lakebase schema with pgvector.
- **API (P4):** FastAPI and sqlmodel on Lakebase: form config, duplicate check (embedding cache, rate limit), submit with classification, my requests, review queue and decisions, portfolio KPIs (OBO).
- **UI (P5):** React and shadcn pages: Submit (live similar-projects panel, join existing, submit anyway with a reason), My requests, Review (approve, merge, reject), Portfolio (KPIs, link to Genie).
- **ML (P6):** classifier evaluation and duplicate-threshold tuning, logged to MLflow.
- **Genie (P7):** a space over `gold.projects` and the metric view, with instructions and 10 sample questions (`genie/space_config.md`).
- **Bundle (P8):** Lakebase project, pipeline, app, and the `oneintake-data-setup` and `oneintake-evaluation` jobs, with variables. Plus README (Mermaid), DECISIONS (draft), and this report.

## Self-check results
| Phase | Check | Result |
|---|---|---|
| P1 | `tests/test_data_gen.py` (11 tests: counts, planted pairs, names, no Faker companies, config parity, seasonality and skew, cross-unit duplicates) | PASS |
| P2 | Pipeline event log (full refresh on the shaped data): bronze 304 + 0 app rows = silver 300 + quarantine 4; gold 360 = silver + 60 projects | PASS |
| P3 | Governance: 0 missing comments or tags; member sees 360/360; Finance-only user sees only Finance (28 silver, 35 gold rows) | PASS |
| P4 | `tests/test_api.py` (10 tests); duplicate-check p95 500 ms (target < 800) | PASS |
| P5 | Playwright demo flow, local and deployed | PASS |
| P6 | Classifier accuracy 0.940, macro F1 0.931 (job reruns 0.920, macro F1 0.911); likely-duplicate threshold kept at 0.85 (precision 1.0) | PASS |
| P7 | Genie vs reference SQL: 10/10 matched (need ≥ 9), including the CFO questions on duplicated value and peak-season cycle time | PASS |
| P8 | `bundle validate` OK; deploy OK; both jobs SUCCESS; deployed demo 4/4 cold runs (`app_run_log.txt`) | PASS |

**Demo flow on the deployed app** (`evidence/deployed_demo_flow.txt`):
1. Typing "Chatbot so agents can check load ETA" shows **Agent ETA assistant** as a likely duplicate (0.88) 3.6 s after typing starts, with an empty description.
2. A unique request is categorized in 2.8 s.
3. The reviewer approves one request and merges one into PRJ-0001; both rows are in Lakebase `app.review_decisions`.
4. Genie answers "backlog value by business unit" with the same rows as the SQL (Q1 in `genie_answers.txt`).

## Business outcomes (baseline → target)
Measured on the shaped baseline log through `gold.portfolio_metrics` (targets are projections, A61):
- **Duplicates:** 30 requests ($6.4M, 10%) repeat existing work across all 10 business units, found only at review a median 34 days after submission. Target: caught while typing (3.6 s in the deployed demo), with duplicated value reaching funding cut 80% to under $1.3M.
- **Decision time:** median 34 days (36 in peak season, 32 off-peak). Target: 10 days or less.
- **Backlog:** $39.7M of estimated annual value waiting for a decision. Target: −50%.
- **Who it's for:** the CFO funds the portfolio and owns duplicated value, open value, and cycle time. The AI Task Force runs intake against the same measures.

## Open issues
1. **Intermittent cold-start 502.** About 1 in 4 early cold runs hit a 502 from the app proxy after 5 s, on a request the app never logged. The cause is not found. Mitigations: idempotent submit with UI retry, query retries, one worker, and a longer keep-alive. After those, 4/4 cold runs passed. Worth raising with the Apps team if it recurs.
2. **Fallbacks to revisit:** Lakehouse Sync is Beta. `projects_synced` is copied by a job because synced tables need a Lakebase catalog. The catalog is a shared workspace catalog, not a dedicated one (catalog creation was denied).
3. **Recall at 0.85 is low** on synthetic pairs (0.11); the `related` band (0.70) surfaces 17 of 18. Re-tune on real submissions.
4. **Genie sharing:** the space is created by script and shared only with its owner. Reviewers need access granted.
5. **`task_force` is workspace-local;** replace it with an account group.
6. **Rate limit:** 2 checks per second per user returns an occasional 429 during fast typing. The UI keeps the last result.
7. **Classifier results vary** between runs (0.92–0.94) because model output is not deterministic.
8. **Size limit:** every authored file is under 9,000 characters. Only the generated eval CSVs and the unchanged APX agent-skill files are larger.

## Assumptions (full text in ASSUMPTIONS.md)
- **Repo and data:** A1 existing APX scaffold · A2 authored-file count · A3 example pages removed · A4 packaged config · A5 no Faker at runtime · A6 18 planted pairs · A7 primary and secondary labels · A8 hard-negative eval set · A9 seeded raw data, gitignored.
- **Platform:** A10 profile DEFAULT · A11 shared catalog (catalog creation denied) · A12 Lakebase Autoscaling with OAuth · A13 Lakehouse Sync to raw · A14 text IDs, unsynced `serving` · A15 `projects_synced` fallback · A16 pgvector over Vector Search.
- **AI:** A17 BGE endpoint · A18 query-prefixed cosine · A19 tightened demo description · A20 `ai_classify` 2.1 with literal options · A21 cluster threshold 0.92 · A22 metric view in SQL.
- **Governance:** A23 local `task_force` group · A24 pipeline owner in the group · A25 glossary comments · A26 tags under the account policies · A27 ALTER after the pipeline · A28 membership flip in the test · A29 metric view covers requests only.
- **API and UI:** A30 demo title kept out of the log · A31 OBO identity · A32 service principal for model and DB calls; KPIs as the user · A33 no confidence on submit · A34 search scope · A35 join existing = merged · A36 header parameter rename · A37 live API tests · A38 OTEL pin · A39 skip merged matches · A40 reviewed cards stay visible · A41 demo reset · A42 shared field component.
- **Eval and Genie:** A43 same classify call in eval · A44 threshold rule · A45 Genie by script · A46 tolerant answer match · A47 status codes in instructions.
- **Bundle:** A48 app config in the bundle · A49 one worker, keep-alive · A50 idempotent submit and retry · A51 serverless job runner details · A52 app service principal from `APP_NAME` · A53 demo reset clears synced copies · A54 Genie id variable · A55 redacted evidence URLs · A56 29 authored files.
- **Business story:** A59 illustrative seasonality and skew · A60 metric view file · A61 Genie questions and projected targets.
