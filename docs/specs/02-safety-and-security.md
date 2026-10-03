# 02 — Safety & Security

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md) · Closes: B01–B04, B06–B09, B14–B17, B19, B26, B27, B31, B32 · Decisions: [ADR-0002](../adr/0002-write-ahead-journal.md), [ADR-0005](../adr/0005-localhost-token-server.md)

This is the most important spec in the set. v0.2 cannot ship until every requirement marked **MUST** has a passing test.

## 1. Threat & failure model

| Actor / event | What they can do today | Requirement |
|---------------|------------------------|-------------|
| Malicious web page in the user's browser | POST to `localhost:8765` and move files (B03) | MUST NOT be able to call any API |
| Device on the same LAN | Read and move files (B03, B04) | MUST NOT reach the server |
| User typo or bad edit in GUI or CLI | Rename to `../x` (B01) | MUST be rejected with a clear message |
| Forged or corrupted rollback file | Move arbitrary files (B02) | MUST NOT be loadable through the API; import validates containment |
| Crash, Ctrl+C, power loss, full disk mid-run | Undo record lost (B08) | MUST be able to resume or roll back from the journal |
| Files changed between scan and execute | Wrong file moved or overwritten | MUST detect it with fingerprints and skip |
| Concurrent jobs | Race on shared state (B14) | MUST serialize mutating jobs per Root |
| Cloud placeholders | Mass download (B31) | MUST skip by default |

Out of scope: a local attacker with the same UID (they can already move files), and malicious file *contents* (we never execute them).

## 2. Path containment

**MUST:** every path that reaches `execute.py` or `undo.py` passes both checks.

- `validate_name(name)`, for any single component the user can edit:
  - Not empty. Not `.` or `..`. Contains no `/`, `\`, NUL or control characters (`\x00-\x1f`, `\x7f`).
  - No leading `.` unless the original name had one (no accidental hiding).
  - Not a Windows reserved name, case-insensitive, with or without an extension. This applies on **all** platforms, because a Root may sync to Windows.
  - No trailing space or dot.
  - At most 255 bytes UTF-8 (the stem is truncated per [03 § 7](03-smart-detection.md#7-filename-normalization)).
- `ensure_contained(root, rel)`:
  - `rel` is a relative POSIX-style path with no `..` component and no drive or anchor.
  - `(root / rel).resolve(strict=False)` must be `is_relative_to(root.resolve())`. This also catches parent directories that are symlinks.
  - Every *existing* parent between Root and the target is `lstat`-checked: none may be a symlink. This prevents `Documents -> /etc` style escapes created after the scan.

**Server rule (B01):** the client never sends a path. It sends `action_id` plus an optional `new_name` (single component) or `category` and `year` override, chosen from known values or validated with `validate_name`. The server rebuilds `dst` itself.

## 3. Plan validation

`validate.py` runs immediately before execute. It is read-only and fails closed.

| Check | Failure handling |
|-------|------------------|
| Plan `root` equals the requested Root (resolved) | Abort the whole plan |
| Every `src` and `dst` passes containment | Action → `rejected: NOT_CONTAINED` |
| Source still matches its fingerprint `(size, mtime_ns, ino)` | Action → `skipped: FINGERPRINT_CHANGED` |
| Source is not a cloud placeholder (unless `placeholder_policy=allow`) | `skipped: PLACEHOLDER` |
| `dst` collides with an existing path **or** another Action's `dst`, compared case-folded and NFC-normalized when the volume is case-insensitive | Deterministic re-suffix ` (2)`, ` (3)` … in `action_id` order. Recorded in `reasons[]`. |
| Case-only rename on a case-insensitive volume | Plan a two-step rename through a temporary name `.<name>.organeyes-tmp-<rand>`, journaled as one Action |
| `dst` directory would be created inside a protected path | `rejected: PROTECTED` |
| Free space: the sum of cross-device Action sizes plus 5% must be under `disk_usage(dst_dev).free` | Abort with a message (same-device renames need no space) |
| Plan is older than `plan_max_age` (default 24 h) | Warn (CLI) or require re-scan (GUI) |

The case-sensitivity probe is a one-time `lstat` of the Root path with its case swapped. If the Root name has no letters, create a probe file in the State dir on the same device. The result is cached per `st_dev`.

## 4. Write-ahead journal

Replaces the post-hoc rollback file (B08, B09). Format: [04 § 4](04-data-formats.md#4-journal-jsonl).

**Location:** `<StateDir>/runs/<root_hash>/<run_id>.jsonl`, plus `plan.json` and `index.json`. `root_hash = blake2b(str(resolved_root)).hexdigest()[:16]`. **Never** inside the Root.

**Protocol for each Action:**
1. Append an `intent` record (`seq`, `action_id`, `op`, `src`, `dst`, fingerprint, `mkdirs[]` to be created). `flush` + `os.fsync`.
2. Create any missing directories, and append one `mkdir` record per directory created (needed for B15 cleanup).
3. Perform the no-clobber move (§ 6).
4. Append a `done` record with the final `dst` (after any re-suffix) or a `failed` record with an error code. `fsync` every N=16 `done` records and always on the last one. `intent` records are always fsynced.

**Run header and footer:** the first line is `run_start` (Root, plan_id, versions, host, platform). The last line is `run_end` (status `complete|cancelled|aborted`, counts).

**Recovery:** on startup, and before any new apply or undo on that Root, scan for journals without `run_end`.
- An `intent` without `done` or `failed` is **in doubt**. Resolve it by `lstat`-ing `src` and `dst` and comparing the fingerprint. If it is at `dst`, record `done (recovered)`. If it is at `src`, record `failed (not_started)`. If it is at both or neither, record `conflict` and leave it for the user.
- Then offer two choices: **resume** (continue the remaining Actions of the same plan after re-validation) or **roll back** (undo what was done).
- The CLI command `organeyes recover` and a GUI banner expose this.

**Durability:** a journal write failure (ENOSPC, EIO) aborts the run **before** the next move. Each move has its `intent` durable before the move starts.

## 5. Undo v2

Closes B02, B07 and B15.

- Undo addresses runs by `run_id` taken from `index.json`. File paths are never accepted from the API. The CLI may accept a journal path but loads it only from the State dir, unless `--import-legacy` is used ([04 § 5](04-data-formats.md#5-legacy-v1-rollback-import)).
- An undo builds a **reverse Plan** from `done` records in reverse `seq` order:
  - `move src→dst` becomes `move dst→src`.
  - `mkdir d` becomes `rmdir d`, only if `d` is empty.
  - `rmdir` (pruned source) becomes `mkdir`.
  - `symlink_rewrite` restores the old target.
  - `quarantine` reverses like a move.
- The reverse Plan goes through **the same validation (§ 3) and executor (§ 6)**:
  - It verifies that the file at `dst` still matches the fingerprint recorded in `done`. Size and `mtime_ns` are compared; `ino` only on the same device.
  - It never overwrites. If `src` exists, it records `conflict`. The user can choose `--restore-conflicts-to <dir>`, which puts the item under `_OrganEyes Restored/<run_id>/<original rel path>`.
- Partial undo: `--only action_id,...` or GUI row selection.
- Undo itself writes a journal (`kind: undo`, `undoes: run_id`), so an undo can be undone.
- The run index marks runs as `undone`, `partially_undone` or `complete`.

## 6. Atomic, no-clobber moves

`fsutil.safe_move(src, dst)` contract: **either `dst` did not exist and now holds src's data and `src` is gone, or nothing changed**. Existing data is never replaced.

- **Same device:**
  - Linux: `renameat2(RENAME_NOREPLACE)` through `ctypes` if available.
  - macOS: `renamex_np(RENAME_EXCL)` through `ctypes` if available.
  - Otherwise (and on Windows), use `os.link(src, dst)` then `os.unlink(src)`. `link` fails atomically if `dst` exists.
  - On file systems without hardlinks (exFAT, some SMB), fall back to `os.rename` guarded by an `lstat(dst)` check. Windows `os.rename` already refuses to overwrite. The remaining TOCTOU window on POSIX is documented and accepted only on those file systems.
  - Directories (Units): the same idea. Use `renameat2`/`renamex_np` where possible. Otherwise check, then `os.rename`; POSIX `rename` onto a non-empty directory fails, which helps.
- **Cross device (EXDEV):**
  1. Copy to `dst.parent/.<name>.organeyes-partial-<rand>` with `O_EXCL`.
  2. `fsync`.
  3. Compare size and BLAKE2b.
  4. Preserve mtime, atime, mode and xattrs where possible (`shutil.copystat`).
  5. No-clobber rename of the partial file to `dst`.
  6. `unlink(src)`.
  7. On verify failure, delete **only the partial copy**, which OrganEyes created, and record `failed: EXDEV_VERIFY_FAILED`.
  - Directory Units across devices are copied as a tree with the same rules, and the source tree is removed only after the full tree verifies. Default: cross-device Unit moves are **disabled** (`skipped: CROSS_DEVICE_UNIT`) unless `--allow-cross-device-units` is given.
- Collisions found at move time (a lost race): re-suffix and retry up to 100 times, then fail with `CONFLICT`.

## 7. Symlinks, hardlinks and special files

Closes B06 and B32.

- The scan uses `lstat` / `DirEntry.is_dir(follow_symlinks=False)` and **never descends into symlinked directories**. They are reported in `skipped[]` with reason `symlink_dir`.
- Symlinked files: `symlink_policy`:
  - `keep` (default): no Action, listed in the report.
  - `move`: move the link unchanged. Only allowed for absolute-target links.
  - `rewrite`: move it and recompute the relative target. Journaled `symlink_rewrite` with the old target.
- Hardlinks: `effective_size` is counted once per `(dev, ino)` (B11). Moving one name is safe, and the report notes `nlink > 1`.
- FIFOs, sockets and device nodes are always skipped (`special_file`).
- Mount points (`st_dev` differs from the parent) are not descended into by default (`--cross-mounts` to allow).

## 8. GUI server hardening

Closes B03, B04, B12–B14, B26 and B27. API shape: [05 § 2](05-cli-and-api.md#2-http-api-v2).

**MUST:**
1. **Bind `127.0.0.1`** (plus `::1` if available). `--host` lets a user override it, but non-loopback hosts require `--i-understand-remote-risk` and print a red warning. The token stays mandatory.
2. **Session token:** 32 random bytes (`secrets.token_urlsafe`) generated at start. The browser is opened at `http://127.0.0.1:PORT/#token=…` (a fragment, so it never appears in server logs or Referer). The SPA stores it in `sessionStorage` and sends `Authorization: Bearer <token>` on every API call. A missing or wrong token returns 401, compared with `hmac.compare_digest`.
3. **Host check:** `Host` must be `127.0.0.1:PORT`, `localhost:PORT` or `[::1]:PORT`. Anything else returns 421 (blocks DNS rebinding).
4. **Origin check** on state-changing methods: `Origin` must be absent or equal to the server origin. Anything else returns 403.
5. **No CORS headers at all.** `OPTIONS` returns 405.
6. **No generic static serving.** An explicit allow-list (`/`, `/assets/<hash>.js|css`) is served from package resources with correct `Content-Type` and `X-Content-Type-Options: nosniff`.
7. **Security headers:**
   - `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`
   - `Referrer-Policy: no-referrer`
   - `Cache-Control: no-store` on API responses.
8. **Request limits:** body at most 8 MiB, `Content-Type: application/json` required for POST, a JSON schema check (hand-written validators in `server/schemas.py`), and 400 with an error envelope on failure.
9. **Concurrency:** `ThreadingHTTPServer`, `daemon_threads=True`, `allow_reuse_address=True`, and `JobManager` (one mutating job per Root, 409 otherwise).
10. **No `os.chdir`.**
11. **Shutdown:** Ctrl+C sets the cancel token, waits up to 10 s for the current Action to finish, writes `run_end: cancelled`, and exits.

## 9. Protection model

Closes B19 and part of B31.

Protection patterns are **Root-relative, POSIX-style globs** (`fnmatch` per segment plus `**`):

| Pattern | Matches |
|---------|---------|
| `Church` | the top-level `Church` only |
| `Work/Clients` | exactly that path |
| `Work/Clients/*` | every direct child of it |
| `**/node_modules` | `node_modules` at any depth |
| `**/*.photoslibrary` | any Photos library |

A protected directory is **not descended into** and **never a move target**. Planning a `dst` under a protected path is rejected.

**Defaults** (all `**/`-anchored):
- VCS: `.git`, `.svn` and `.hg`.
- Dependency and cache folders: `node_modules`, `__pycache__`, `venv`, `.venv`, `env`, `.tox`, `.gradle` and `target/` when they sit inside a detected project.
- System and app data: `Library` at the top level only, `Applications`, `.Trash` and `$RECYCLE.BIN`.
- **Cloud sync roots:** `Dropbox`, `OneDrive*`, `Google Drive`, `iCloud Drive`, `Library/Mobile Documents` and `Library/CloudStorage`.
- Media libraries: `*.photoslibrary`, `*.musiclibrary`, `Music/Music`, `*.aplibrary` and `*.lrlibrary` / Lightroom catalogs.
- VM disks: `*.vmwarevm`, `*.pvm`, `*.utm` and `*.vbox` directories.
- Mail stores: `Library/Mail`.

Hidden entries (dot-prefixed) stay skipped by default (`--include-hidden` to include files only; hidden directories are never descended).

**Legacy mapping:**
- `--exclude Name` becomes `Name` (top level). A deprecation note explains `**/Name`.
- `--exclude Parent/Child` becomes the same path, now working at any nesting under the Root.
- The v0.1 behavior where a bare name matched at any depth is reproduced **only** for `DEFAULT_PROTECTED` names, as explicit `**/` patterns.

## 10. Self-exclusion

Closes B09. The scanner always skips:
- `.organeyes/` and `.organeyes.toml` (the per-Root config).
- `organizer_rollback_*.json` and `organizer_report*.json` (v0.1 artifacts), with a hint to import or remove them.
- Any path passed as `--output`, `--log` or `--export-plan`.
- The installed package directory and the `file_organizer.py` shim, if they are inside the Root.
- `*.organeyes-partial-*` and `*.organeyes-tmp-*` leftovers. These are also reported as "orphaned temp files" in `organeyes doctor`, but never deleted automatically.

## 11. Privacy

- No telemetry, ever.
- Reports and plans contain absolute paths. Saving them inside a git working tree prints a warning (B10 lesson).
- The AI extra's data contract is in [03 § 8](03-smart-detection.md#8-optional-ai-classification-ai).
- Logs default to the State dir, with file names but not contents. `--log` can redirect them.
