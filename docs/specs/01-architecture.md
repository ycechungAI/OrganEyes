# 01 — Architecture

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md) · Decisions: [ADR-0001](../adr/0001-stdlib-core-optional-extras.md)

## 1. Why restructure

v0.1 keeps everything in one 1,337-line module: scanning, classification, planning, execution, undo, the HTTP server and the CLI. The stages share mutable dicts (B28), print directly to stdout (B33), and rely on global state (B14). Nothing can be tested in isolation. The safety work in [02](02-safety-and-security.md) needs clean boundaries: only **one** module may modify the file system.

## 2. Package layout

```
organeyes/
├── __init__.py          # version, public API re-exports
├── __main__.py          # `python -m organeyes`
├── cli.py               # argparse subcommands → library calls; owns terminal rendering
├── config.py            # defaults + optional config file loading (stdlib tomllib on 3.11+, JSON fallback)
├── model.py             # dataclasses: Entry, Unit, Classification, ResolvedDate, Action, Plan, RunInfo
├── fsutil.py            # containment, name validation, case-sensitivity probe, no-clobber move, placeholders
├── scan.py              # read-only walker → Entries (lstat-based, never follows symlinked dirs)
├── protect.py           # protection pattern matching (see 02 §9)
├── detect/
│   ├── __init__.py      # detector registry + capability probing
│   ├── units.py         # bundles, projects, DCIM, libraries → Units
│   ├── sniff.py         # magic-byte signatures, text/binary heuristic
│   ├── dates.py         # date resolution chain
│   ├── meta_doc.py      # PDF / OOXML / ODF metadata (stdlib)
│   ├── meta_image.py    # EXIF: stdlib JPEG/TIFF APP1 parser; Pillow when [exif]
│   ├── meta_media.py    # MP4/MOV `mvhd` atom parser (stdlib); mutagen/ffprobe when [media]
│   ├── dupes.py         # size → partial hash → full hash grouping
│   └── ai.py            # optional LLM classifier ([ai] extra)
├── classify.py          # combines extension table + sniff + detectors → Classification
├── taxonomy.py          # category table, icons, confidence weights
├── plan.py              # Units + Classifications + Dates → Plan (pure)
├── validate.py          # Plan × live FS → ValidatedPlan | errors (read-only)
├── execute.py           # the ONLY module that mutates the FS; journaled
├── journal.py           # write-ahead JSONL journal, run index, recovery
├── undo.py              # journal → reverse Plan → execute.py
├── report.py            # Report v2 builder (JSON), human summary
├── events.py            # Reporter protocol: progress/warning/result events
├── state.py             # State-dir location, run index, caches
├── server/
│   ├── app.py           # ThreadingHTTPServer, routing, auth middleware
│   ├── jobs.py          # JobManager (one mutating job per Root)
│   └── schemas.py       # request validation
└── web/                 # vendored, prebuilt GUI assets (no CDN)
file_organizer.py        # compatibility shim → organeyes.cli.legacy_main()
```

**Rules:**
- `execute.py` (and `undo.py` only by calling into it) are the only callers of `rename`, `link`, `unlink`, `mkdir`, `rmdir` and `copy` on user data. A CI lint step ([06 § 5](06-testing.md#5-static-checks)) uses `grep` to enforce this.
- `scan`, `detect/*`, `classify`, `plan` and `validate` are **read-only**.
- Only `cli.py` and `server/` do I/O to the user. Everything else emits events through `events.Reporter`.

## 3. Pipeline stages

| Stage | Input | Output | Pure? | Notes |
|-------|-------|--------|-------|-------|
| Scan | Root, ScanOptions | `list[Entry]`, `ScanStats` | Reads the FS | `os.scandir` + `lstat`. Skips protected paths and own artifacts. Records `skipped_depth`. |
| Detect units | Entries | `list[Unit]` | Reads the FS | Collapses bundle and project subtrees into a single Unit ([03 § 2](03-smart-detection.md#2-unit-detection-bundles--projects)) |
| Sniff | Units | `Unit.sniffed_type` | Reads the first 4 KiB | Only for files whose extension is missing, unknown or mismatched (configurable: `all`) |
| Classify | Units | `Classification` per Unit | Pure except for AI | Extension → sniff → metadata hints → optional AI fallback |
| Resolve date | Units | `ResolvedDate` per Unit | Reads metadata | Ordered chain with confidence ([03 § 4](03-smart-detection.md#4-date-resolution)) |
| Plan | Units + classifications + dates + PlanOptions | `Plan` | **Pure** | Deterministic: the same input gives the same `action_id`s and targets |
| Duplicates (optional) | Units | `list[DupGroup]` + optional `quarantine` Actions | Reads content | Runs after Plan so keepers can prefer files that already sit at their target |
| Validate | Plan + live FS | `ValidatedPlan` | Reads the FS | Containment, fingerprints, collisions, free space ([02 § 3](02-safety-and-security.md#3-plan-validation)) |
| Execute | ValidatedPlan | `RunResult` + Journal | **Mutates** | Write-ahead journaled, no-clobber, cancellable |
| Report | Everything | Report v2 JSON + summary | Pure | [04 § 2](04-data-formats.md#2-report-v2) |

Stages talk only through the types in `model.py`. Each stage takes a `Reporter` for progress and warnings and a `CancelToken`.

## 4. Core types (sketch)

Field-level detail lives in [04-data-formats.md](04-data-formats.md). The sketches below show *intent*, not code to copy.

- **Entry**: `rel_path: PurePosixPath`, `kind: file|dir|symlink|special`, `size`, `effective_size`, `mtime_ns`, `birthtime_ns?`, `dev`, `ino`, `nlink`, `flags` (placeholder, hidden, etc.).
- **Unit**: `unit_id`, `kind: file|bundle|project|library|dcim|symlink`, `rel_path`, `members_count`, `total_size`, `markers[]` (why it is a unit), `entries` (for single files: the one Entry).
- **Classification**: `category`, `subcategory?`, `confidence: 0..1`, `source: extension|sniff|metadata|unit|ai|user`, `reasons[]`.
- **ResolvedDate**: `value: datetime` (tz-aware or naive local), `source: exif|media|doc_meta|filename|birthtime|mtime|unknown`, `confidence`, `reasons[]`.
- **Action**: `action_id` (stable hash of `rel_path` + scan fingerprint), `op: move|rename|move_rename|quarantine|skip`, `src`, `dst`, `fingerprint` (size, mtime_ns, ino), `reasons[]`, `enabled: bool`, `user_edited: bool`.
- **Plan**: `plan_id`, `root`, `created`, `options`, `actions[]`, `warnings[]`, `schema_version`.
- **RunResult**: `run_id`, counts per outcome (`done`, `failed`, `skipped`, `conflict`, `cancelled`), `journal_path`, `errors[]`.

## 5. Optional extras & capability registry

`pyproject.toml` declares:

| Extra | Packages | Unlocks | Stdlib fallback |
|-------|----------|---------|-----------------|
| *(none)* | — | Everything in [02](02-safety-and-security.md), unit detection, duplicates (BLAKE2b), sniffing (built-in table), the doc metadata date source, a minimal JPEG/TIFF EXIF date parser, the MP4/MOV `mvhd` date parser | — |
| `[exif]` | `Pillow` | Full EXIF (HEIC through `pillow-heif` if present), camera make/model for Photo vs Graphic, perceptual near-duplicate images | Built-in EXIF parser (JPEG/TIFF only, date tags only) |
| `[media]` | `mutagen` | Audio tags (year, album) and more video containers. Uses `ffprobe` if it is on PATH (not a pip dependency). | `mvhd` parser for MP4/MOV only |
| `[magic]` | `python-magic` (libmagic) | Broad content detection | Built-in signature table (about 40 types) |
| `[ai]` | `anthropic` | LLM fallback classification | Feature disabled |
| `[all]` | all of the above | | |

`detect/__init__.py` probes each optional import once and exposes `capabilities()`, for example `{"exif": "pillow", "media": "builtin", "magic": "builtin", "ai": None}`. The CLI prints this in `organeyes doctor`, and the GUI shows it in Settings. **A missing extra never raises.** The feature reports `capability_missing` in `warnings[]`.

## 6. Configuration (minimal, not a rules engine)

The configuration covers only **knobs**, not user rules (the rules engine is a non-goal). It is loaded in this order, where later entries win:

1. Built-in defaults.
2. `~/.config/organeyes/config.toml` (macOS: `~/Library/Application Support/OrganEyes/config.toml`). JSON is accepted on Python versions without `tomllib`.
3. `<Root>/.organeyes.toml`.
4. CLI flags or GUI request fields.

Knobs: `max_depth`, `group_old` + `group_old_years`, `unit_policy`, `symlink_policy`, `placeholder_policy`, `rename_policy`, `detectors` on/off, `dupes.min_size`, `ai.*`, extra `protect` patterns, `split_images`. Schema: [04 § 6](04-data-formats.md#6-config).

## 7. Concurrency model

- The CLI is single-threaded, except for an optional hashing thread pool in `dupes` (`--jobs N`, default `min(4, cpu)`). Hashing is I/O-bound, so threads are enough.
- Server: `ThreadingHTTPServer` for requests, plus `JobManager` running jobs on daemon worker threads. The rule is **at most one mutating job (apply or undo) per Root, and at most one scan job per Root**. A new scan for the same Root cancels the previous one. Job state sits behind one `threading.Lock`. Snapshots are copied out for `GET /jobs/{id}`.
- Cancellation is cooperative through `CancelToken`, checked between files. Execute checks it **between** Actions, never in the middle of one.

## 8. Error-handling policy

- Per-file errors (permission denied, a file vanished, a locked file) **never abort a stage**. They become `skipped` or `failed` outcomes with an error code from a fixed enum (`EACCES`, `ENOENT`, `EBUSY`, `EXDEV_VERIFY_FAILED`, `CONFLICT`, `NOT_CONTAINED`, `FINGERPRINT_CHANGED`, `PLACEHOLDER`, …).
- Errors that affect the whole stage (the Root is missing, the journal cannot be written, the State dir is not writable) abort **before** the first mutation.
- Retry: up to 3 attempts with backoff of 0.25, 0.5 and 1 s, only for `EBUSY`, `EAGAIN` and Windows sharing violations. No retry for `EACCES` or `ENOENT`. This replaces the blanket `OSError` retry at FO:612-638.

## 9. Platform notes

| Concern | macOS | Linux | Windows |
|---------|-------|-------|---------|
| Case sensitivity | Usually insensitive (APFS). Probe per Root. | Usually sensitive. Probe. | Insensitive. Probe. |
| Birth time | `st_birthtime` | `statx` is not in stdlib, so not available | `st_birthtime` (3.12+) or `st_ctime` |
| Placeholders | `st_flags & SF_DATALESS`, `.icloud` stubs | n/a | `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS`, `OFFLINE` |
| Reserved names | `:` is shown as `/` in Finder | `/`, NUL | `CON PRN AUX NUL COM1-9 LPT1-9`, trailing dot or space, `<>:"/\|?*` |
| State dir | `~/Library/Application Support/OrganEyes` | `$XDG_STATE_HOME/organeyes` or `~/.local/state/organeyes` | `%LOCALAPPDATA%\OrganEyes` |

Minimum Python: **3.9** (SPEC Q3).
