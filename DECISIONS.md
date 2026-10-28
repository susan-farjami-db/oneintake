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
- **Decision:** `governance/uc_setup.sql` applies a glossary of comments, tags under the existing tag policies, a business-unit row filter, and the metric view. The setup job reruns it after every pipeline refresh (A25–A29).
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
