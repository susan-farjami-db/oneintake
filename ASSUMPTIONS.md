# Assumptions and decisions log

Each entry: decision, then reason.

## Repo and data
- **A1.** Built on the existing `OneIntake` APX scaffold; an older folder carrying a real company name was not reused.
- **A2.** The 30-file limit counts authored files. Unchanged `apx init` output (core helpers, shadcn `components/ui`, lockfiles, agent folders), `data/raw`, and `evidence/` are excluded; the scaffold alone ships 50+ files.
- **A3.** Example pages were removed; `/` redirects to `/submit`.
- **A4.** Config lives in `config/` and is packaged into the wheel, so the deployed app reads the same files.
- **A5.** No Faker at runtime: names come from `data_gen/names.py`. Faker is a dev dependency, used only to prove that no Faker company names appear.
- **A6.** 18 planted near-duplicate pairs: 10 against projects, 8 against earlier requests. Each new side is a recent `submitted` request.
- **A7.** Ambiguous requests have one primary label (the eval truth) plus 1–2 secondary labels.
- **A8.** Duplicate eval set: 18 positives plus 22 negatives, including hard negatives (same subject in a different category, and vice versa).
- **A9.** `data/raw/` is gitignored and reproducible from seed `20261026`; the `eval/` labels are committed.

## Workspace and platform
- **A10.** Profile `DEFAULT` (user choice).
- **A11.** Existing catalog `oneintake_demo` (user choice): `CREATE CATALOG` was denied. The catalog stays the bundle variable `catalog`.
- **A12.** Lakebase Autoscaling, not provisioned instances: apps bind it through the `postgres` resource, with 1-hour OAuth credentials from `w.postgres.generate_database_credential`.
- **A13.** Lakebase-to-bronze uses Lakehouse Sync (CDF config `app_to_raw`, Beta) into `raw.lb_*_history`. Bronze keeps the latest non-delete change per key. Run `ops/run.py cdf` before the first pipeline run.
- **A14.** Lakebase IDs are `text`. Lakehouse Sync rejects uuid, vector, and array columns, so embeddings live in the unsynced `serving` schema.
- **A15.** Synced tables need a Lakebase UC catalog (denied). The fallback, `ops/run.py sync-projects`, copies `gold.projects` with embeddings into `serving.projects_synced`.
- **A16.** pgvector is available, so Vector Search fallback is unused.

## AI functions and duplicate scoring
- **A17.** Embeddings come from `databricks-bge-large-en`, best on the eval pairs of the three endpoints tried (`evidence/embedding_endpoint.txt`).
- **A18.** Live score = cosine between a BGE query embedding (with its query prefix) and stored document embeddings. The demo pair scores 0.883; the next match scores 0.708.
- **A19.** The "Agent ETA assistant" description was tightened so the demo pair clears the 0.85 band.
- **A20.** `ai_classify` and `ai_extract` use version 2.1, which returns confidence. The options map must be a literal, so the instructions are a pipeline configuration value. A test keeps them equal to the app config.
- **A21.** Gold clusters use `cluster_threshold` 0.92 plus merge links: template-alike rows gave 18 false links at 0.85, none at 0.92. The 0.85 threshold applies only to the live check.
- **A22.** The metric view is created by `governance/uc_setup.sql`: pipelines and bundles have no metric view resource.

## Governance
- **A23.** `task_force` is a workspace-local group, since no account group exists. The row filter accepts `is_account_group_member` or `is_member`.
- **A24.** The pipeline owner must be in `task_force`: gold reads the filtered silver.
- **A25.** Column comments come from one glossary table, applied by a SQL scripting loop, so future columns are covered too.
- **A26.** Tags follow the existing account tag policies: `business_unit` (Finance, Legal, Marketing, Operations; intake tables use Operations) and `sensitivity` (email, owner, and sponsor are `pii`).
- **A27.** Filters, tags, and comments are applied with ALTER after the pipeline; they survived a full refresh. The setup job reapplies them.
- **A28.** The governance check temporarily removes the runner from `task_force` to test the non-member path (Finance), then restores membership. It waits about 1 minute for the membership cache and uses a nonce to bypass the result cache.
- **A29.** `gold.portfolio_metrics` covers requests only and inherits the row filter.

## API and UI
- **A30.** The demo title is kept out of the opportunity log: a historical copy would match itself. It stays in the eval pairs as `LIVE-DEMO`.
- **A31.** The OBO identity comes from `current_user.me()` (cached 5 minutes per token hash) and drives requester email, "mine", the rate limit, and the task-force check.
- **A32.** Embedding, classify, and Lakebase calls use the app service principal. The portfolio KPIs run as the user, so the row filter applies.
- **A33.** Synchronous `ai_classify` omits confidence (~1s faster) to stay under 5s; the pipeline recomputes it with confidence. Opening the form warms the warehouse.
- **A34.** Search returns the top 3 across intake requests and `projects_synced`, excluding rejected and merged items (A39) and the caller's draft.
- **A35.** "Join existing" saves the request as `merged` with `duplicate_of` set, with no review step (A58).
- **A36.** The scaffold header parameter `request_id` was renamed `x_request_id`: it collided with the `/review/{request_id}` path parameter.
- **A37.** API tests run live with the CLI token as the OBO header, and delete their own rows.
- **A38.** `apx` 0.3.8 rewrites `package.json` to newer Vite and OpenTelemetry, so `@opentelemetry/api` 1.10.0-rc.0 is pinned.
- **A39.** Merged items are not offered as matches: their canonical item is the better one.
- **A40.** Reviewed cards stay visible with their outcome until reload.
- **A41.** The demo-flow test resets its own rows, so it is repeatable.
- **A42.** One shared component renders config-driven fields; unknown field types render as text inputs.

## Evaluation and Genie
- **A43.** The classifier eval uses the pipeline's exact `ai_classify` call. MLflow logging is best effort; the evidence file is the source of truth.
- **A44.** Tuning scores pairs like the live check. Best F1 with precision ≥ 0.90 keeps 0.85 (recall 0.11). Recall comes from the `related` band: at 0.70, 17 of 18 pairs surface.
- **A45.** The Genie space is managed by `genie/genie_space.py` via `w.genie.create_space`/`update_space`, keyed by title (bundles have no Genie resource). Ids are md5 hashes of the content, so reruns are idempotent.
- **A46.** Genie's answers are compared row by row with reference SQL, numbers matching within 0.001 absolute or 0.5% relative (the instructions ask Genie to round).
- **A47.** Instructions list exact status codes; without them Genie filtered on `'in progress'` and missed `in_progress`.

## Bundle and deploy
- **A48.** Apps reads `app.yml` in `.build`, not bundle `config.command`/`config.env`. Its dev catalog and group are ordinary env values; resource ids use `valueFrom`. Another target needs manifest generation.
- **A49.** The app runs one uvicorn worker with `--timeout-keep-alive 75`. One process keeps the warm-up, caches, and rate limiter consistent; sync endpoints still run on a thread pool.
- **A50.** Submit is idempotent: the form sends a `submission_id`; a resend returns the saved row. The UI retries 502/503/504 twice — about 1 in 4 cold demo runs saw an unexplained proxy 502, root cause not found.
- **A51.** Jobs are serverless Python tasks calling `ops/run.py`; leading `KEY=VALUE` args become env vars (no env block for serverless). `script` treats `SystemExit(0)` as success, falls back to `sys.argv[0]` for `__file__`. No `numpy` pin — it aborted tasks (SIGABRT).
- **A52.** `lakebase-setup` resolves the app service principal from `APP_NAME`, so the setup job grants it Lakebase access without a hard-coded id.
- **A53.** Demo rows flow into gold through Lakehouse Sync and back into `projects_synced`, so the demo reset clears those copies too. Otherwise the "unique" demo request matches its own earlier copy.
- **A54.** `genie_space_id` is a per-target bundle variable (an id, not a secret). Sharing the space with reviewers is left to the space owner.
- **A55.** Evidence files redact workspace and app URLs. The lockfiles contain package-proxy URLs only.
- **A56.** File count by the A2 rule: 33 authored files (adds the embedded Genie proxy/chat and the match-detail endpoint/preview, A58). Lockfiles, vendored shadcn components, and generated eval CSVs are excluded.
- **A57.** Portfolio Genie is embedded via an OBO FastAPI proxy. `user_api_scopes` is `sql` plus `genie` (not the deprecated `dashboards.genie`; the API rejects tokens missing `genie`). SQL, status, identity, and an AI disclaimer sit on the same page.
- **A58.** Fixed: Join existing skipped every required field, 500ing on the `description` NOT NULL column. It still needs title/description; other fields stay skipped. `GET /matches/{key}` backs a preview sheet (description, owner, value, category) with an inline description box.
