# Design decisions

**DRAFT for author review.** These were written during the build to explain the main choices. They need the author's review before they are shared. Detailed, dated entries are in `ASSUMPTIONS.md` (A-numbers below).

## D1. Duplicate check while typing, before the description is written
- **Decision:** Embed the draft title (plus any description), search pgvector in Lakebase, and show results in a side panel. The check runs after 4 title words, with a 600 ms debounce, aborts stale calls, and allows 2 calls per second per user. Bands: likely ≥ 0.85, related ≥ 0.70.
- **Why:** The goal is to stop duplicates at the moment of writing. Lakebase answers in milliseconds next to the app's own rows, and p95 is 0.5–0.6 s cold.
- **Alternatives:** Vector Search, which is not needed while pgvector is available (A16). Scoring in the pipeline only, which is too late to change the requester's behavior.
- **Review:** The 0.85 band is high precision and low recall on synthetic pairs (A44). The `related` band carries the recall. Re-tune it on real submissions.

## D2. Lakebase is the system of record; Unity Catalog is the system of analysis
- **Decision:** The app writes to Lakebase `app.*`. Lakehouse Sync (CDF) lands changes in `raw`, and the SDP pipeline builds silver and gold. Gold is copied back to `serving.projects_synced` for matching (A13–A15).
- **Why:** Transactional writes and low-latency reads for the app; governed history for analytics and Genie.
- **Review:** Lakehouse Sync is Beta, and the gold copy back is a fallback for synced tables (no catalog rights). Switch to synced tables when a Lakebase catalog is allowed.

## D3. Classification: synchronous `ai_classify` on submit, recomputed in the pipeline
- **Decision:** On submit, the app calls `ai_classify` 2.1 on the warehouse without confidence scores, to stay under 5 s. The pipeline reclassifies with confidence and also runs `ai_extract`. Label descriptions and instructions come from config (A20, A33).
- **Why:** The requester sees a category immediately, while the stored category stays consistent with batch evaluation (accuracy 0.92–0.94, macro F1 0.93).
- **Review:** Labels and descriptions are a business decision. The eval set is synthetic.

## D4. Identity and access
- **Decision:** User identity comes from the OBO token. Reviewing requires the `task_force` group. Portfolio KPIs run as the user so the Unity Catalog row filter applies. Embedding, classify, and Lakebase calls use the app service principal (A31, A32).
- **Why:** Requesters need no warehouse or endpoint grants, and anything showing cross-business-unit data respects row-level access.
- **Review:** `task_force` is a workspace-local group (A23). Move to an account group, and confirm which business units non-members may see.

## D5. Governance as code, applied after each pipeline run
- **Decision:** `governance/uc_setup.sql` applies a glossary of comments, tags under the existing tag policies, and a business-unit row filter; `governance/metric_view.sql` adds the metric view. The setup job reruns it after every pipeline refresh (A25–A29).
- **Why:** Pipelines don't declare row filters and tags on all objects. One script keeps it repeatable, and a check proves both the member and non-member paths.

## D6. Duplicate clusters in gold use a stricter rule than the live check
- **Decision:** Gold links items at cosine ≥ 0.92 or by explicit merges; `duplicate_rate` therefore reflects confirmed overlap (A21).
- **Why:** Template-alike text produced false clusters at 0.85.
- **Review:** Revisit the threshold with real text.

## D7. Genie over the gold table and the metric view
- **Decision:** A script creates the space, with instructions that define backlog, waiting, in review, and the exact status codes, plus 10 sample questions. Each answer is checked against SQL (10/10) (A45–A47). The Portfolio tab embeds chat through an OBO FastAPI proxy rather than opening the workspace Genie UI. The app requests the `genie` user scope (A57).
- **Why:** Bundles have no Genie resource, and governed measures keep Genie's numbers equal to the app's KPIs. Staying in the app keeps row-filter identity next to the KPIs. AppKit `GenieChat` is not used because this stack is APX.

## D8. Delivery: one bundle, two jobs, one app
- **Decision:** The bundle holds the Lakebase project, pipeline, app (env and resources in the bundle), a data-setup job, and an evaluation job, all serverless (A48–A52).
- **Review:** Submit is idempotent and the UI retries gateway errors because of an intermittent cold-start 502 at the app proxy whose cause was not found (A50).

## D9. Join existing shows a preview, and still needs a minimal description
- **Decision:** Clicking "Join existing" (from the similar-projects panel or the duplicate-choice card) no longer submits directly. It opens a preview sheet fetched from `GET /matches/{key}`, showing the candidate's own description, owner, status, business unit, value, and category, with an inline box for the requester's own short description. "Confirm join" stays disabled until that box has text (A58).
- **Why:** The backend's "join bypasses every required field" shortcut (A35) was too broad: `description` is NOT NULL on the table, so a bare join 500'd. The preview both fixes that (the requester supplies the missing field inline) and answers the original ask — see what you're joining before you join it.
- **Review:** The preview reuses `DuplicateMatch`'s key; it looks the row up in both the Lakebase table and the synced copy, so it works whether the match is a live request or a tracked project.

## D10. The data tells the business story, and the KPIs are owned by the CFO
- **Decision:** `data_gen/shape.py` shapes the synthetic log the way an asset-light, agent-based carrier sees it: requests spike in produce season and the Q4 peak, the units closest to loads and capacity file the most (and the highest-value) requests, safety and claims skew urgent, and each planted duplicate comes from a different business unit than the work it repeats. `gold.portfolio_metrics` adds the CFO's measures (`duplicate_value_usd`, `open_value_usd`, `median_cycle_days`, `high_urgency_share`) and a `season` dimension, and two Genie check questions ask them (A59–A61).
- **Why:** Generic counts showed that the app works, not why it matters. The shaped log is the baseline (manual triage today), and every outcome is stated as baseline → target on a governed measure: duplicated value reaching funding, median submit-to-decision, peak-season decision time, backlog value.
- **Review:** The shaping runs after generation with its own seed, so ids, titles, statuses, planted pairs, and both eval sets are byte-identical to before; the duplicate and classifier evaluations still apply.
- **Assumptions:**
  - **A59.** Seasonality and skew are illustrative, not fitted to a real log: month weights favor Apr–Jun and Sep–Nov (peak share 0.67); manual decision time is gamma-distributed (median 34 days) and 1.5× slower in peak months; business-unit share, value multipliers, and urgency weights are in `BU_PROFILE`. Re-fit them to the real opportunity log before quoting baselines to a customer.
  - **A60.** The metric view moved to `governance/metric_view.sql` so `uc_setup.sql` stays under the 9,000-character file limit. The job's `metric_view` task points at the new file.
  - **A61.** Two Genie check questions changed (approved-value total → duplicated value by business unit; September count → median cycle time by season), keeping 10 questions and the ≥ 9 bar. The rerun matched 10/10. Targets in the business case (e.g., −80% duplicated value, ≤ 10-day median decision) are projections from the measured detection and classifier results, to be validated over two quarters.
