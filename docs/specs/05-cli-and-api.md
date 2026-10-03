# 05 — CLI, HTTP API v2 & GUI Fix Requirements

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md) · Closes: B12, B14, B18, B20–B25, B27, B29, B33–B35 (interface side)

## 1. CLI

Entry points: `organeyes …`, `python -m organeyes …`, and the legacy `python3 file_organizer.py …` (§ 1.4).

### 1.1 Subcommands

| Command | Mutates? | Purpose |
|---------|----------|---------|
| `organeyes scan [ROOT]` | No | Scan and detect, then print a summary. `--output report.json` saves Report v2. |
| `organeyes plan [ROOT]` | No | Scan, detect and plan. Prints a summary and a sample. `--export-plan FILE(.json\|.csv)`, `--explain PATH\|ACTION_ID`, `--interactive` (review TUI, § 1.3). |
| `organeyes apply [ROOT]` | **Yes** | Without `--plan`, it plans and then applies after confirmation. `--plan FILE` applies an exported or edited plan after re-validation. Filters: `--category`, `--year`, `--only ACTION_ID,...`. |
| `organeyes undo [RUN_ID]` | **Yes** | Undo the latest run, or the given one. `--only ACTION_ID,...`, `--restore-conflicts-to DIR`, `--import-legacy FILE`. |
| `organeyes recover [ROOT]` | Optional | Inspect incomplete journals. `--resume` or `--rollback`. |
| `organeyes history [ROOT]` | No | List runs with their counts and undo state. `--show RUN_ID` prints its actions. |
| `organeyes dupes [ROOT]` | Optional | Duplicate report. `--quarantine` plans and applies quarantine moves (confirmation required). `--keep PATH` overrides the keeper. |
| `organeyes serve [ROOT]` | Through the GUI | Start the GUI server ([02 § 8](02-safety-and-security.md#8-gui-server-hardening)). `--port`, `--no-browser`, `--host` (guarded). |
| `organeyes doctor` | No | Capabilities, State dir, case sensitivity of the Root volume, orphaned temp files, incomplete journals, `--reindex`. |

### 1.2 Common flags

| Flag | Applies to | Notes |
|------|-----------|-------|
| `--max-depth N` | scan/plan/apply/dupes | Default 10. Prints a warning with `skipped_depth` counts if it truncates (B18). |
| `--protect PATTERN` (repeatable) | all scanning commands | Glob semantics ([02 § 9](02-safety-and-security.md#9-protection-model)) |
| `--detect LIST` | scan/plan/apply | `units,dates,sniff,dupes`, or `all` / `none` |
| `--ai` | scan/plan/apply | Turns on AI fallback for this session ([03 § 8](03-smart-detection.md#8-optional-ai-classification-ai)) |
| `--group-old [YEARS]` | plan/apply | Decade folding |
| `--rename-mode off\|conservative\|tidy` | plan/apply | |
| `--unit-policy keep\|move_whole` | plan/apply | |
| `--prune-empty-sources` | apply | Journaled `rmdir` |
| `--yes` | apply/undo/dupes/ai | Skip the interactive confirmation (replaces `--no-confirm`) |
| `--json` | all | Machine output on stdout (one JSON document; events as JSONL on stderr). No progress bars. |
| `--quiet` / `-v` / `--log FILE` | all | Logging (B33). The default log goes to the State dir. |
| `--config FILE` | all | Extra config layer |

### 1.3 Interactive review (`plan --interactive`)

This keeps v0.1's command set but addresses Actions by a short index that maps to `action_id` (B28). New commands:

- `e <n>` explains an Action.
- `d` lists duplicate groups.
- `w` lists warnings (mismatches and suspicious files).
- `x <file>` exports the plan.

`run` applies the plan through the normal validate-and-journal path. No second confirmation is needed, because `run` is itself the confirmation.

### 1.4 Legacy flag mapping

`file_organizer.py` maps the old flags. Each mapping prints one deprecation line on stderr.

| v0.1 | v0.2+ |
|------|-------|
| `PATH` (no mode flags) | `plan PATH --output -` (prints the JSON report as before) |
| `--dry-run` | `plan --summary` (B34) |
| `--execute [--category C] [--year Y]` | `apply --category C --year Y` |
| `--no-confirm` | `--yes` |
| `-i/--interactive` | `plan --interactive` |
| `--undo FILE` | `undo --import-legacy FILE` if it is a v1 file; otherwise refuse |
| `--server [--port] [--no-browser]` | `serve …` |
| `-e/--exclude X` | `--protect X` (and a hint that bare names are now top-level only) |
| `-d/--depth N` | `--max-depth N` |
| `-o/--output F` | `--output F`, now honored with `--execute` too (B35) |

### 1.5 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success (for apply/undo: every enabled Action was `done`) |
| 1 | Completed with per-item failures, conflicts or skips |
| 2 | Usage or config error |
| 3 | Validation aborted the plan (Root mismatch, free space, …) |
| 4 | Cancelled by the user (Ctrl+C or confirmation declined) |
| 5 | Incomplete journal found; run `organeyes recover` |
| 10 | Internal error |

## 2. HTTP API v2

Base: `http://127.0.0.1:PORT/api/v2`. Every request needs `Authorization: Bearer <token>` and passes the Host and Origin checks ([02 § 8](02-safety-and-security.md#8-gui-server-hardening)). The v1 endpoints are **removed** in v0.4. In v0.2 they remain as thin, token-protected wrappers, except `GET /api/analyze` (B12), which is deleted.

### 2.1 Envelope

- Success: `{ "ok": true, "data": … }`
- Error: `{ "ok": false, "error": { "code": "VALIDATION|NOT_FOUND|CONFLICT|BUSY|UNAUTHORIZED|INTERNAL", "message": "…", "details": [ {"field": "depth", "issue": "must be 1..64"} ] } }`
- HTTP status codes: 200 / 202 (job accepted) / 400 / 401 / 403 / 404 / 409 / 413 / 421 / 500.

### 2.2 Endpoints

| Method & path | Body / query | Returns |
|---------------|--------------|---------|
| `GET /session` | — | `{root, version, capabilities, config_effective, incomplete_runs[]}` |
| `POST /scan` | `{max_depth?, protect?[], detect?[], group_old?, ai?: false}` | 202 `{job_id}`. Result: a Report v2 with an embedded Plan (`plan_id`). |
| `GET /plan/{plan_id}` | `?offset&limit&category&year&q&warning&source` | A page of Actions plus facet counts. Paging supports the virtualized table (B24). |
| `PATCH /plan/{plan_id}/actions` | `{edits: [{action_id, enabled?, new_name?, category?, year?}]}` | Updated Actions, each re-validated, or per-item errors. **Paths are never accepted** (B01). |
| `POST /plan/{plan_id}/export` | `{format: "json"\|"csv"}` | File download |
| `POST /apply` | `{plan_id, filter?: {category?, year?, action_ids?[]}, prune_empty_sources?}` | 202 `{job_id, run_id}`. 409 if another mutating job is running. |
| `GET /jobs/{job_id}` | — | `{job_id, kind, state: queued\|running\|complete\|failed\|cancelled, phase, done, total \| null, bytes_done?, bytes_total?, current?, started, ended?, result?, error?}` (B29) |
| `POST /jobs/{job_id}/cancel` | — | 202 |
| `GET /history` | — | Run index entries |
| `GET /history/{run_id}` | `?offset&limit&outcome` | Journaled actions with outcomes |
| `POST /undo` | `{run_id, action_ids?[], restore_conflicts?: bool}` | 202 `{job_id, run_id}` |
| `POST /recover` | `{run_id, mode: "resume"\|"rollback"}` | 202 `{job_id}` |
| `GET /dupes/{plan_id}` | `?offset&limit` | Duplicate groups |
| `PATCH /dupes/{plan_id}` | `{group_id, keeper_path?, quarantine?: bool}` | Updated group. `keeper_path` must be one of the group's members. |
| `GET /folders` | `?path=` (Root-relative, contained) | Child directory names, for the protection picker |

### 2.3 Jobs

- `JobManager` keeps the last 20 jobs in memory. Job objects are copied under a lock when read (B14).
- One **mutating** job (apply, undo, recover, quarantine) per Root at a time.
- A new scan cancels any running scan.
- Job results larger than 1 MiB (big plans) are stored server-side and fetched through `/plan/{id}` pages, not embedded in the job status.
- Progress is two-phase for scans: `phase: "walking"` (`total: null`, the UI shows an indeterminate bar) → `"detecting"` → `"planning"`, which have determinate totals.

### 2.4 v0.2 interim v1 API

v0.2 must close B01 before API v2 exists. The v1 endpoints therefore change shape in v0.2, and all of them require the token:

| v1 endpoint | v0.2 behavior |
|-------------|---------------|
| `GET /api/analyze` | Removed (B12) |
| `POST /api/analyze` | Unchanged request. The server stores the resulting Plan and returns `plan_id`. Suggestions in `/api/report` now carry `action_id`. |
| `POST /api/execute` | Body `{plan_id, action_ids?[], renames?: {action_id: new_name}, category?, year?}`. The old `suggestions` field is **rejected** (400), not ignored. The server builds the paths from its own Plan. |
| `POST /api/undo` | Body `{run_id}`. `rollback_file` is rejected (B02). |
| `GET /api/rollbacks` | Returns the run index (same shape as `GET /history`) |
| `GET /api/progress` | Snapshot of the current job from `JobManager` (B14), instead of the global dict |

## 3. GUI fix requirements

This is **not** a redesign (that is a non-goal). These are the minimum changes needed to fix the GUI bugs and show the new data.

| Req | Fixes | Requirement |
|-----|-------|-------------|
| G-1 | B25 | No CDN. Ship a prebuilt bundle (React plus compiled JSX, Tailwind purged to static CSS) under `organeyes/web/assets/` with hashed file names. A build step (`npm run build` in `web-src/`) runs only for maintainers. Users need no Node.js. CSP compliant: no inline scripts or `eval`. |
| G-2 | B03 | Read the token from `location.hash` on load, put it in `sessionStorage`, and clear the hash with `history.replaceState`. Add the `Authorization` header in the `api()` helper. On 401, show "Session expired — restart `organeyes serve`". |
| G-3 | B20 | Every count derives from the server's plan facets plus local edits. There is no second copy of the suggestions list. |
| G-4 | B21 | Polling uses backoff from 500 ms up to 5 s. After 10 consecutive failures it shows a connection-lost banner with Retry. Polling stops on unmount. |
| G-5 | B22 | Result panel: Done / Failed / Skipped / Conflicts with counts, an expandable error list (code plus path), and a "View in History" link. A green success message appears only when `failed + conflict == 0`. |
| G-6 | B23 | Settings: "Group files older than N years into decades" checkbox plus a number field. |
| G-7 | B24 | Virtualized review table (about 50 rows rendered), server-side paging and filtering (`/plan/{id}?…`), and group headers for Category/Year. |
| G-8 | B01 | Rename editing sends `{action_id, new_name}` only. Inline validation mirrors `validate_name()`, and server errors show per row. |
| G-9 | B18 | A warning chip when `skipped_depth.dirs > 0`. The default depth matches the CLI (10). |
| G-10 | new | Per-row **reasons** (expand), a confidence badge, a `date_source` pill, and a red **Suspicious** badge for extension mismatches. |
| G-11 | new | Panels for "Kept in place" Units (projects, bundles, libraries) and "Skipped" items (symlinks, placeholders, special files). |
| G-12 | new | Duplicates tab: groups, wasted bytes, keeper radio button, quarantine toggle (off by default), and near-duplicate list when available. |
| G-13 | new | History tab: runs from `/history`, full or partial undo, an incomplete-run banner with Resume/Roll back. Replaces the rollback-file list. |
| G-14 | new | AI toggle (disabled when the capability is missing). The confirmation dialog shows the item count, the fields sent and the estimated cost. |
| G-15 | a11y | Keep the existing ARIA labels (`.Jules/palette.md`). New controls need labels. Progress uses `role="progressbar"` with `aria-valuenow`, or `aria-busy` while indeterminate. |
