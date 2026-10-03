# 04 — Data Formats

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md) · Closes: B11, B18, B28, B35 (data side)

Every persisted or exchanged document carries `"schema": "<name>"` and `"schema_version": <int>`. Readers MUST reject an unknown major version with a clear error, and MUST ignore unknown fields (forward compatible). Paths in all documents are **Root-relative POSIX strings**. The only absolute path is the top-level `root`.

## 1. Conventions

- Timestamps: ISO 8601. Wall-clock instants are UTC with a `Z` suffix. Resolved content dates keep their source offset or are naive (`tz_assumed: true`).
- Sizes: integer bytes. `*_formatted` fields are kept in the Report only, for the legacy GUI.
- IDs:
  - `plan_id`: `p_` + 12 base32 characters.
  - `run_id`: `r_` + UTC timestamp + 6 random characters, e.g. `r_20261002T143022Z_k3f9qa`.
  - `action_id`: `a_` + the first 12 hex digits of `blake2b(rel_path + "\0" + size + "\0" + mtime_ns)`. Stable across re-plans of an unchanged file.
- Error codes come from a fixed enum ([01 § 8](01-architecture.md#8-error-handling-policy)).

## 2. Report v2

Produced by `scan` and `plan`. It is a superset of v1, so v1 fields stay for the legacy GUI until v0.4.

```json
{
  "schema": "organeyes.report",
  "schema_version": 2,
  "tool_version": "0.3.0",
  "root": "/Users/alex/Downloads",
  "scan_time": "2026-10-02T14:30:22Z",
  "options": { "max_depth": 10, "detectors": ["units", "dates", "sniff"], "group_old": false, "taxonomy_version": 2 },
  "capabilities": { "exif": "builtin", "media": "builtin", "magic": "builtin", "ai": null },
  "summary": {
    "total_files": 3383,
    "total_units": 3290,
    "total_size": 5410000000,
    "apparent_size": 5829873056,
    "moves_suggested": 3100,
    "renames_suggested": 210,
    "kept_in_place": 41,
    "skipped": 57,
    "warnings": 12,
    "duplicate_groups": 88,
    "duplicate_wasted_bytes": 812000000
  },
  "skipped_depth": { "dirs": 3, "approx_files": 140 },
  "category_stats": { "Photos": { "count": 1200, "size": 2100000000, "icon": "📷", "size_formatted": "2.0 GB" } },
  "year_stats": { "2023": 900, "2024": 1400, "Unknown": 12 },
  "date_source_stats": { "exif": 1100, "filename": 300, "doc_meta": 410, "birthtime": 900, "mtime": 660, "unknown": 13 },
  "protected_found": [ { "path": "Work/Clients", "pattern": "Work/Clients" } ],
  "units": [
    { "unit_id": "u_9a1c…", "kind": "project", "path": "code/my-app", "markers": [".git", "package.json"], "members": 4120, "size": 210000000, "policy": "keep" }
  ],
  "skipped": [
    { "path": "link-to-root", "reason": "symlink_dir" },
    { "path": "Movies/big.mov", "reason": "PLACEHOLDER" }
  ],
  "warnings": [
    { "code": "extension_mismatch", "path": "invoice.pdf", "detail": "sniffed: exe (MZ)", "severity": "high" },
    { "code": "capability_missing", "detail": "HEIC EXIF needs [exif] extra; 34 files fell back to birthtime" }
  ],
  "duplicates": [ "…see §2.2…" ],
  "suggestions": [ "…see §2.1…" ]
}
```

Changes from v1:
- `total_size` is now the **effective** size (B11), and `apparent_size` holds the old raw sum.
- `protected_folders` (the full default list) is removed from the report. It was noise.
- `proposed_structure` is removed. The GUI derives the tree from `suggestions`.

### 2.1 Suggestion (Report) / Action (Plan)

The same object appears in both. The Report embeds it as `suggestions[]` and the Plan as `actions[]`.

```json
{
  "action_id": "a_3f0c9e12ab44",
  "op": "move_rename",
  "unit_kind": "file",
  "src": "IMG  0001 .HEIC",
  "dst": "Photos/2023/IMG 0001.HEIC",
  "category": "Photos",
  "category_confidence": 0.95,
  "category_source": "metadata",
  "year": "2023",
  "date": "2023-05-14T09:12:03",
  "date_source": "exif",
  "date_confidence": 0.95,
  "tz_assumed": true,
  "size": 2840211,
  "fingerprint": { "size": 2840211, "mtime_ns": 1704153600000000000, "ino": 81273361, "dev": 16777230 },
  "enabled": true,
  "user_edited": false,
  "reasons": [
    "category=Photos (0.95): exif Make=Apple",
    "date=2023-05-14 (exif DateTimeOriginal)",
    "rename: collapsed whitespace; trimmed stem"
  ],
  "warnings": [],

  "original_path": "IMG  0001 .HEIC",
  "original_name": "IMG  0001 .HEIC",
  "suggested_path": "Photos/2023/IMG 0001.HEIC",
  "suggested_name": "IMG 0001.HEIC",
  "rename_suggested": true,
  "move_required": true,
  "size_formatted": "2.7 MB"
}
```

The fields after the blank line are **v1 compatibility aliases**, kept until v0.4 and then dropped. `move_required` mirrors `enabled && op != "skip"`. Temporary UI fields like `_id` (B28) are never serialized.

`op` values: `move`, `rename`, `move_rename`, `move_unit`, `quarantine`, `symlink_rewrite`, `skip`. A `skip` carries `skip_reason`.

### 2.2 Duplicate group

```json
{
  "group_id": "d_5be1…",
  "hash": "blake2b-256:9f2c…",
  "size": 4194304,
  "count": 3,
  "wasted_bytes": 8388608,
  "keeper": "Photos/2021/beach.jpg",
  "keeper_reason": "already at planned target",
  "members": [
    { "path": "Photos/2021/beach.jpg", "role": "keeper" },
    { "path": "Downloads/beach (1).jpg", "role": "extra", "action_id": "a_77…" },
    { "path": "Desktop/old/beach.jpg", "role": "extra", "action_id": "a_78…" }
  ],
  "hardlinked": []
}
```

`near_duplicates[]` (with the `[exif]` extra): `{ "a": path, "b": path, "distance": 4, "similarity": 0.94 }`.

## 3. Plan file

Written by `organeyes plan --export-plan plan.json`, edited by hand or by the GUI, and consumed by `organeyes apply --plan plan.json`. Closes the TODO "Editable suggestions in CLI (export/import)".

```json
{
  "schema": "organeyes.plan",
  "schema_version": 1,
  "plan_id": "p_q3m7x0c2hk1z",
  "root": "/Users/alex/Downloads",
  "created": "2026-10-02T14:31:00Z",
  "tool_version": "0.4.0",
  "options": { "…": "same as report.options plus unit_policy, symlink_policy, rename_policy, quarantine_dupes" },
  "scan_fingerprint": { "entries": 3383, "root_mtime_ns": 1759415400000000000 },
  "actions": [ "…Action objects (§2.1) without v1 aliases…" ]
}
```

**Edit rules (enforced on import):**
- Users may change `enabled`, and may change `dst` **only** in its last component (rename) or its `Category/Year` prefix to another valid value. All of it is re-validated ([02 § 2](02-safety-and-security.md#2-path-containment)).
- Users may delete Actions. Users may **not** add Actions with a `src` that is not in the plan (rejected: `unknown_action`).
- Any edited Action gets `user_edited: true` on import.
- Import always runs plan validation ([02 § 3](02-safety-and-security.md#3-plan-validation)). Fingerprint mismatches skip that Action.

**CSV export** (`--export-plan plan.csv`): `action_id,enabled,op,src,dst,category,year,date_source,reasons` (with `;`-joined reasons). It is read-only. Importing CSV is supported only for the columns `action_id,enabled,dst`.

## 4. Journal (JSONL)

One JSON object per line, append-only, at `<StateDir>/runs/<root_hash>/<run_id>.jsonl`. Protocol: [02 § 4](02-safety-and-security.md#4-write-ahead-journal).

```jsonl
{"t":"run_start","run_id":"r_20261002T143300Z_k3f9qa","kind":"apply","root":"/Users/alex/Downloads","plan_id":"p_q3m7x0c2hk1z","tool_version":"0.2.0","platform":"darwin","case_insensitive":true,"ts":"2026-10-02T14:33:00Z"}
{"t":"mkdir","seq":1,"path":"Photos","ts":"…"}
{"t":"mkdir","seq":2,"path":"Photos/2023","ts":"…"}
{"t":"intent","seq":3,"action_id":"a_3f0c9e12ab44","op":"move_rename","src":"IMG  0001 .HEIC","dst":"Photos/2023/IMG 0001.HEIC","fp":{"size":2840211,"mtime_ns":1704153600000000000,"ino":81273361},"ts":"…"}
{"t":"done","seq":4,"action_id":"a_3f0c9e12ab44","final_dst":"Photos/2023/IMG 0001.HEIC","method":"rename","fp_dst":{"size":2840211,"mtime_ns":1704153600000000000,"ino":81273361,"dev":16777230},"ts":"…"}
{"t":"intent","seq":5,"action_id":"a_91aa…","op":"move","src":"locked.docx","dst":"Documents/2024/locked.docx","fp":{"…":"…"},"ts":"…"}
{"t":"failed","seq":6,"action_id":"a_91aa…","code":"EBUSY","detail":"Resource busy after 3 attempts","ts":"…"}
{"t":"rmdir","seq":7,"path":"old-empty-folder","reason":"prune_empty_sources","ts":"…"}
{"t":"run_end","status":"complete","counts":{"done":3099,"failed":1,"skipped":0,"conflict":0},"ts":"…"}
```

Record types:
- `run_start`, `run_end`
- `mkdir`, `rmdir`
- `intent`, `done`, `failed`, `skipped`, `conflict`
- `recovered` (produced by recovery, with `resolution: done|not_started|conflict`)
- `symlink_rewrite` (`old_target`, `new_target`)

An undo run's `run_start` has `"kind":"undo","undoes":"<run_id>"`.

**Run index:** `<StateDir>/runs/<root_hash>/index.json`:

```json
{ "schema": "organeyes.run_index", "schema_version": 1, "root": "/Users/alex/Downloads",
  "runs": [ { "run_id": "r_…", "kind": "apply", "started": "…", "ended": "…", "status": "complete", "counts": {"done": 3099, "failed": 1}, "undo_state": "none|partial|undone", "plan": "r_….plan.json" } ] }
```

Index writes are atomic (write a temp file, `fsync`, then `os.replace`). The index is a cache and can be rebuilt from the journals (`organeyes doctor --reindex`).

## 5. Legacy v1 rollback import

`organeyes undo --import-legacy organizer_rollback_YYYYMMDD_HHMMSS.json`:

1. Parse the v1 file: `{created, root_path, moves[{original_path,new_path,original_abs,new_abs,size,timestamp}], failed, skipped}`.
2. Require that `root_path`, after resolving, **equals** the Root given on the command line or the current directory. Otherwise refuse.
3. Ignore the `*_abs` fields. Use `original_path` and `new_path`, and containment-check both.
4. Synthesize a journal with `kind: "imported_v1"` (fingerprint: size only), register it in the index, then undo it normally (no-clobber, conflict reporting).
5. The v1 file is **not** modified or deleted. The CLI suggests moving it out of the Root.

## 6. Config

`config.toml` (or `config.json` with the same structure). All keys are optional.

```toml
max_depth = 10
group_old = false
group_old_years = 5
split_images = true
include_hidden = false

[protect]
patterns = ["Church", "Work/Clients", "**/Keep Out"]
use_defaults = true

[units]
policy = "keep"                 # keep | move_whole
dcim = "explode"
sidecars = "move_together"
allow_cross_device = false

[symlinks]
policy = "keep"                 # keep | move | rewrite

[placeholders]
policy = "skip"                 # skip | allow

[rename]
mode = "conservative"           # off | conservative | tidy
skip_categories = ["Code", "Data", "Projects", "Apps"]
add_missing_ext = false

[detect]
enabled = ["units", "dates", "sniff"]   # + "dupes"
sniff_scope = "unknown_or_missing"      # or "all"

[dupes]
min_size = 1
quarantine = false
paranoid = false
jobs = 4

[ai]                            # still requires --ai per session
model = "claude-haiku-4-5"
content = "metadata"            # metadata | snippet
max_items = 500
key_source = "env"              # env | keychain

[execute]
prune_empty_sources = false
plan_max_age_hours = 24
```

Unknown keys print a warning and are otherwise ignored. Invalid values are a hard error before scanning.
