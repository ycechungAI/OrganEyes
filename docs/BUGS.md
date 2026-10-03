# OrganEyes v0.1 — Bug & Risk Audit

> Status: **Design / Draft** · Audited revision: `6e794e4` · Last updated: 2026-10-02

Line numbers refer to `file_organizer.py` (FO) or `organizer_preview.html` (HTML) at the audited revision. Each entry gives a **failure scenario**, a **fix design** and the **spec** and **milestone** that close it. Acceptance tests are listed in [specs/06-testing.md § 6](specs/06-testing.md#6-acceptance-criteria-per-bug).

Severity scale:
- **Critical:** data loss, security exposure, or files moved outside the user's intent.
- **High:** wrong results or a broken feature.
- **Medium:** UX or robustness.
- **Low:** polish.

## Summary

| ID | Sev | Title | Milestone |
|----|-----|-------|-----------|
| B01 | Critical | Path traversal through edited suggestions and renames | v0.2 |
| B02 | Critical | Undo endpoint trusts arbitrary rollback files and absolute paths | v0.2 |
| B03 | Critical | GUI server exposed to LAN and any website (no auth, CORS `*`) | v0.2 |
| B04 | Critical | Static fallback serves the whole target folder; `os.chdir` side effects | v0.2 |
| B05 | Critical | App bundles and code projects are torn apart | v0.2 (guard) / v0.3 (full) |
| B06 | Critical | Symlinked directories followed out of Root and into loops | v0.2 |
| B07 | Critical | Undo can silently overwrite files | v0.2 |
| B08 | Critical | Rollback written only after all moves finish | v0.2 |
| B09 | Critical | OrganEyes organizes its own artifacts | v0.2 |
| B10 | Critical | Private scan report committed to the repo | v0.2 |
| B11 | High | `total_size` double-counts hardlinks and symlinks | v0.2 |
| B12 | High | `GET /api/analyze` never responds | v0.2 |
| B13 | High | GUI HTML looked up in the target folder | v0.2 |
| B14 | High | Global, unsynchronized `TASK_STATUS`; concurrent jobs allowed | v0.2 |
| B15 | High | Cleanup deletes the user's pre-existing empty folders; leaves emptied sources | v0.2 |
| B16 | High | Collision handling races and ignores in-plan and case-fold collisions | v0.2 |
| B17 | High | `clean_filename` produces hidden, malformed or reserved names | v0.2 |
| B18 | High | Files deeper than `max_depth` silently ignored; inconsistent defaults | v0.2 |
| B19 | High | Protected-folder matching semantics inconsistent | v0.2 |
| B20 | Medium | GUI move count ignores user edits | v0.4 |
| B21 | Medium | Progress polling never times out | v0.4 |
| B22 | Medium | GUI reports success when moves failed | v0.4 |
| B23 | Medium | No `group-old` option in GUI | v0.4 |
| B24 | Medium | Review table renders every row | v0.4 |
| B25 | Medium | GUI depends on CDNs and in-browser Babel | v0.4 |
| B26 | Medium | Server threading and shutdown problems | v0.2 |
| B27 | Medium | Unvalidated request input | v0.2 |
| B28 | Low | Interactive `_id` leaks into plan and rollback data | v0.2 |
| B29 | Low | Analysis progress is always 0% | v0.4 |
| B30 | High | Year taken from mtime only | v0.3 |
| B31 | Medium | Moving cloud placeholder files triggers downloads | v0.2 |
| B32 | Medium | Relative symlinks break after a move | v0.2 |
| B33 | Low | Library code prints to stdout | v0.2 |
| B34 | Low | `--dry-run` naming is misleading | v0.2 |
| B35 | Low | `--execute` never saves the report or plan | v0.2 |

---

## Critical

### B01 — Path traversal through edited suggestions and renames
- **Where:**
  - FO:585-586 (`_execute_single_move` joins `root / original_path` and `root / suggested_path`)
  - FO:1053-1054 (server accepts client `suggestions` verbatim)
  - FO:727-731 (interactive `r`)
  - HTML:317-327 (`handleSave` builds the path from raw input)
- **Scenario:**
  - A GUI rename to `../../.ssh/authorized_keys` moves the file outside the Root.
  - A crafted POST to `/api/execute` with `original_path: "../../Documents/taxes.pdf"` moves any file the user can access.
- **Fix:**
  - The server never trusts client paths. The client sends only `action_id` plus an optional `new_name`. The server looks up the Action in its own Plan.
  - Every source and target passes `ensure_contained()` ([02 § 2](specs/02-safety-and-security.md#2-path-containment)).
  - Names pass `validate_name()`, which rejects separators, `..`, NUL, control characters and reserved names.

### B02 — Undo endpoint trusts arbitrary rollback files and absolute paths
- **Where:** FO:1093-1121, FO:779-845.
- **Scenario:** `POST /api/undo {"rollback_file":"/tmp/evil.json"}`, where the file lists `new_abs: ~/Documents/x`, `original_abs: /tmp/out/x`. The server moves the victim file anywhere.
- **Fix:**
  - Undo addresses runs only by `run_id` from the State dir journal index. It never accepts a path.
  - Journal entries store Root-relative paths. Absolute paths are re-derived and containment-checked.
  - v1 rollback files go through the explicit import in [04 § 5](specs/04-data-formats.md#5-legacy-v1-rollback-import), which also validates containment.

### B03 — GUI server exposed to LAN and any website
- **Where:**
  - FO:1156 binds `("", port)`, which means all interfaces.
  - FO:883 and FO:948 set `Access-Control-Allow-Origin: *`.
  - There is no authentication.
- **Scenario:**
  - Any web page the user visits can `fetch("http://localhost:8765/api/execute", {method:"POST", …})` as a CORS "simple request" or after preflight. With `*` it succeeds.
  - DNS rebinding works against `Host` too.
  - A coworker on the same Wi-Fi can do the same.
- **Fix:** bind `127.0.0.1`, require a per-session token, enforce `Host` and `Origin`, and remove CORS headers ([02 § 8](specs/02-safety-and-security.md#8-gui-server-hardening)).

### B04 — Static fallback serves the whole target folder
- **Where:** FO:917 `super().do_GET()`; FO:1154 `os.chdir(root_path)`.
- **Scenario:** `GET /Documents/2024/passport.pdf` returns the file to anyone who can reach the port (see B03).
- **Fix:**
  - Remove the `SimpleHTTPRequestHandler` base. Use a plain `BaseHTTPRequestHandler` with an explicit route table.
  - Static assets come only from the package's `web/` directory, through an allow-list.
  - Remove `os.chdir`.

### B05 — App bundles and code projects are torn apart
- **Where:** FO:242-293. Every directory that is not protected is recursed into, and each file is classified by extension.
- **Scenario:**
  - `MyApp.app/Contents/Info.plist` lands in `Other/2024/`.
  - A Python project's `.py`, `.json`, `.md` and `.png` files are scattered across Code, Documents and Images.
  - `Photos Library.photoslibrary` is destroyed.
- **Fix:**
  - v0.2: a **guard**. A built-in list of bundle extensions and project markers makes the scanner treat such a directory as opaque and `keep` it in place.
  - v0.3: full unit detection with policies ([03 § 2](specs/03-smart-detection.md#2-unit-detection-bundles--projects)).

### B06 — Symlinked directories followed
- **Where:** FO:260. `entry.is_dir()` follows symlinks.
- **Scenario:**
  - `~/Downloads/link -> /` makes the scan recurse into the whole disk, up to `max_depth`. Files found through the link are then **moved into the Root**.
  - A `a -> .` loop burns time until the depth limit.
- **Fix:**
  - Classify entries with `lstat` and never descend into symlinked directories. Report them as `skipped: symlink_dir`.
  - Symlinked files are Units of kind `symlink` ([02 § 7](specs/02-safety-and-security.md#7-symlinks-hardlinks-and-special-files)).

### B07 — Undo can silently overwrite
- **Where:** FO:827, FO:1121. `shutil.move(new_abs, original_abs)`. On POSIX, `os.rename` replaces an existing destination.
- **Scenario:** After organizing, the user creates a new `~/Downloads/report.pdf`. Undo moves the old `report.pdf` back over it, and the new file is gone.
- **Fix:**
  - Undo uses the same no-clobber move primitive as execute ([02 § 6](specs/02-safety-and-security.md#6-atomic-no-clobber-moves)).
  - Before moving back, it checks that the file at `new_path` still matches the journaled fingerprint.
  - Conflicts are reported and skipped, never forced.

### B08 — Rollback written only at the end
- **Where:** FO:564. `_save_rollback()` runs after the loop.
- **Scenario:** Ctrl+C, a crash, a power loss or a full disk at file 2,000 of 3,000 leaves no record of which 2,000 files moved.
- **Fix:** a write-ahead journal. An `intent` record is fsynced before each move and a `done` record after it. Recovery is defined in [02 § 4](specs/02-safety-and-security.md#4-write-ahead-journal).

### B09 — OrganEyes organizes its own artifacts
- **Where:**
  - FO:762 writes the rollback into the Root.
  - The default `--output`, `--log` and the GUI HTML file may also live in the Root.
  - None of them is excluded from the scan, and `.json`, `.html` and `.log` files are categorized.
- **Scenario:** The second run moves `organizer_rollback_*.json` into `Code/2026/`, and the GUI rollback list (which globs the Root) then loses track of it.
- **Fix:**
  - Journals and caches live in the State dir.
  - The scanner always excludes OrganEyes's own files (journals, `.organeyes/`, output and log paths given on the command line, and the running script's directory if it is inside the Root).

### B10 — Private scan report committed to the repository
- **Where:** `organizer_report.json` (57,765 lines) is tracked even though `.gitignore` lists it. It contains a real user's absolute paths and folder names.
- **Fix:**
  - `git rm --cached organizer_report.json`.
  - Add a small synthetic sample under `docs/examples/` if one is needed.
  - The owner decides on a history rewrite (SPEC Q4).
  - CI adds a check that fails if any `organizer_report*.json` or `organizer_rollback_*.json` is tracked.

## High

### B11 — Size summary double-counts
- **Where:** FO:417-418 sum `f["size"]`. `effective_size` is computed at FO:299-319 but not stored in `file_info`.
- **Fix:**
  - Store `effective_size` on each Entry.
  - Report `total_size` (effective) and `apparent_size` (raw) separately.
  - Add a warning if the effective size is larger than `shutil.disk_usage(root).total`.

### B12 — `GET /api/analyze` never responds
- **Where:** FO:899-900 → FO:992-995 → FO:1029-1032 (`pass`). No response is written, so the client hangs until timeout.
- **Fix:** delete the GET route and `_run_analysis`. API v2 uses `POST /api/v2/scan` → job ([05 § 2](specs/05-cli-and-api.md#2-http-api-v2)).

### B13 — GUI HTML looked up in the target folder
- **Where:** FO:954 `server_root / 'organizer_preview.html'`.
- **Scenario:** `--server ~/Downloads` returns `{"error": "HTML file not found"}`.
- **Fix:** serve from package resources (`importlib.resources`) or `Path(__file__).parent / "web"`.

### B14 — Global, unsynchronized task state
- **Where:** FO:191-209, FO:1005, FO:1042, FO:1078.
- **Scenario:**
  - Two browser tabs start analyze and execute at the same time, and both threads mutate `TASK_STATUS`.
  - Execute can run against a report that is being replaced.
  - `result` and `error` from earlier runs persist into later ones.
- **Fix:**
  - Use a `JobManager` with per-job objects behind a lock.
  - Allow **one mutating job at a time per Root**. Later requests get 409.
  - Each job's state is immutable once it is finished ([05 § 2.3](specs/05-cli-and-api.md#23-jobs)).

### B15 — Cleanup deletes the user's empty folders and leaves emptied sources
- **Where:** FO:848-864 walks every `Category/` directory and removes any empty directory, including ones the user made deliberately. Source folders emptied by a move are never cleaned.
- **Fix:**
  - The journal records every directory OrganEyes **created** (`mkdir` records). Undo removes only those, and only if they are empty.
  - Optional `--prune-empty-sources` removes source directories that became empty **during the Run**. Those are journaled as `rmdir` so undo can recreate them.

### B16 — Collision handling races and ignores in-plan collisions
- **Where:** FO:597-600 then FO:615. Check-then-act. The executor never looks at whether two Actions target the same path. On case-insensitive APFS or NTFS, `Photo.JPG` and `photo.jpg` collide.
- **Fix:**
  - The plan validator resolves all target collisions up front, deterministically, using case-folded comparison when the volume is case-insensitive (probed once per Root).
  - The executor uses no-clobber primitives, so a lost race becomes a re-suffix, never an overwrite ([02 § 3](specs/02-safety-and-security.md#3-plan-validation)).

### B17 — `clean_filename` produces bad names
- **Where:** FO:121-138.
- **Scenarios:**
  - `"   .pdf"` gives the stem `""`, so the result is `.pdf`, a hidden file. `"_.pdf"` becomes `" .pdf"`, with a leading space. (Verified against v0.1. Note that `"...txt"` is **not** a reproducer: `os.path.splitext` ignores leading dots, so it becomes `txt`.)
  - A long name is truncated to `name...` + `.pdf`, giving `name....pdf`.
  - `my_module.py` becomes `my module.py` (code breaks).
  - `CON.txt` and `aux.pdf` are invalid on Windows.
  - Trailing spaces are not normalized after removing characters.
  - NFC versus NFD Unicode can cause false "rename suggested".
- **Fix:** specified in [03 § 7](specs/03-smart-detection.md#7-filename-normalization):
  - Category-aware: never rename Code, or files inside Units.
  - Never produce an empty or dot-leading stem.
  - Truncate by bytes with an ellipsis character `…`, not `...`.
  - Remap reserved names.
  - Unicode NFC compare.

### B18 — Deep files silently ignored
- **Where:** FO:244. `max_depth` drops content without telling anyone. The GUI default is 3 (HTML:509) and the CLI default is 10 (FO:1214).
- **Fix:**
  - Use one default, 10, in both places.
  - The report includes `skipped_depth: {dirs, approx_files}`, and the CLI and GUI show a warning.

### B19 — Protected-folder semantics inconsistent
- **Where:** FO:268-283 and FO:140-148.
  - A bare name like `Church` is protected at **any** depth (through `should_skip_folder`).
  - `Parent/Child` works only when Parent is at depth 0.
  - There is no way to protect `a/b/c`.
- **Fix:** protection patterns are Root-relative paths or globs with explicit semantics ([02 § 9](specs/02-safety-and-security.md#9-protection-model)):
  - `Church` matches only a top-level `Church`.
  - `**/Church` matches anywhere.
  - `Work/Clients/*` matches every child of that path.
  - `DEFAULT_PROTECTED` is replaced by an explicit defaults table. Only unambiguous tool names (`.git`, `node_modules`, …) apply at any depth; words like `Library` and `env` apply at the top level only.

## Medium / Low

### B20 — GUI move count ignores edits
- **Where:** HTML:711-723. `filteredCount` reads `report.suggestions` while depending on `editableSuggestions`.
- **Fix:** derive the count from the edited Plan state.

### B21 — Polling never times out
- **Where:** HTML:538-558. Errors are logged and polling continues forever.
- **Fix:**
  - Use exponential backoff.
  - After 10 consecutive failures, show "Lost connection to OrganEyes server" with a Retry button.
  - Poll `/jobs/{id}` (no global state).

### B22 — GUI reports success when moves failed
- **Where:** HTML:643. The backend sets `TASK_STATUS["result"]` (FO:1078), but the frontend ignores it.
- **Fix:** show a result panel with moved, failed, skipped and conflict counts, an expandable error list, and a link to the Run in History.

### B23 — No group-old option in the GUI
- **Where:** FO:1014-1017 does not pass `group_old_files`, and there is no UI control.
- **Fix:** add a `group_old` field to the scan request, a checkbox in Settings, and the threshold in the config.

### B24 — Review table renders every row
- **Where:** HTML:345-348, HTML:379. 3,000+ rows in the DOM, and filtering re-renders them all.
- **Fix:** windowed rendering of about 50 rows plus overscan. Grouping by category and year can be collapsed.

### B25 — CDN and in-browser Babel
- **Where:** HTML:7-10.
- **Fix:** ship a prebuilt, vendored bundle in `organeyes/web/`, with no network at runtime ([05 § 3](specs/05-cli-and-api.md#3-gui-fix-requirements)).

### B26 — Server threading and shutdown
- **Where:** FO:1005 and FO:1042 use non-daemon threads. FO:1156 uses single-threaded `TCPServer` without `allow_reuse_address`.
- **Scenario:**
  - Ctrl+C hangs while a job runs.
  - A restart fails with "Address already in use".
  - A slow request blocks progress polling.
- **Fix:**
  - Use `ThreadingHTTPServer` with `daemon_threads = True` and `allow_reuse_address`.
  - Ctrl+C cancels the job cooperatively and then exits. The journal makes cancellation safe.

### B27 — Unvalidated request input
- **Where:**
  - FO:994 `int(params…)` raises.
  - FO:925-931 ignores invalid JSON, treating it as `{}`.
  - There is no body size limit.
- **Fix:**
  - Validate every request against a small schema (hand-written, stdlib).
  - Return 400 with an error envelope.
  - Reject bodies over 8 MiB with 413.

### B28 — Interactive `_id` leaks
- **Where:** FO:651-652 mutates the shared suggestion dicts. `_id` then ends up in rollback `failed` and `skipped` entries.
- **Fix:** Actions have a stable `action_id` assigned at plan time. The UI uses it directly, and the shared state is never mutated.

### B29 — Analysis progress always 0%
- **Where:** FO:360 calls `progress_callback(count, 0, …)` with total 0, so FO:207 gives 0%.
- **Fix:** two-phase progress. Counting directories gives an indeterminate state, then classifying files gives determinate progress. The job reports `phase`, `done` and `total`, where `total` may be null.

### B30 — Year from mtime only
- **Where:** FO:113-119.
- **Scenario:** Photos restored from a backup all land in the restore year. Copies across devices or downloads stamp the wrong year.
- **Fix:** the date resolution chain in [03 § 4](specs/03-smart-detection.md#4-date-resolution).

### B31 — Cloud placeholder files
- **Where:** No awareness of iCloud ("dataless", `SF_DATALESS` flag / `.icloud` stubs), OneDrive Files-On-Demand, or Dropbox online-only files.
- **Scenario:** Moving or hashing them triggers multi-GB downloads or fails.
- **Fix:**
  - Detect placeholders through `st_flags` (macOS), `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` and `FILE_ATTRIBUTE_OFFLINE` (Windows), and `.icloud` stub names.
  - Default policy: `skip`, with reason `cloud_placeholder`.
  - The default protected list adds known sync roots ([02 § 9](specs/02-safety-and-security.md#9-protection-model)).

### B32 — Relative symlinks break after a move
- **Where:** FO:615 moves the link object. A relative target such as `../data/x` no longer resolves.
- **Fix:** symlink policy ([02 § 7](specs/02-safety-and-security.md#7-symlinks-hardlinks-and-special-files)):
  - The default is `keep` (do not move symlinks).
  - The optional `rewrite` moves the link and rewrites the relative target so it still resolves. Journaled, with the old target recorded.

### B33 — Library code prints to stdout
- **Where:** FO:233-237, FO:356-357, all through `FileExecutor`.
- **Fix:**
  - The library emits events to a `Reporter` interface.
  - The CLI renders them as a progress bar or text.
  - The server feeds them into jobs.
  - `--json` mode produces clean, machine-readable output.

### B34 — `--dry-run` is misleading
- **Where:** FO:1218. The default run never moves files. `--dry-run` only suppresses the JSON dump.
- **Fix:**
  - Subcommands make intent explicit (`scan` and `plan` are always read-only).
  - `--dry-run` becomes a deprecated alias for `--summary`.

### B35 — `--execute` never saves the report or plan
- **Where:** FO:1299-1318 returns before the `--output` handling at FO:1321.
- **Fix:**
  - `apply` always stores the executed Plan next to its Journal.
  - `--output` and `--export-plan` work in every mode.
