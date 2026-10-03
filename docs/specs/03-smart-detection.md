# 03 — Smart Detection

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md) · Closes: B05, B17, B30 · Decisions: [ADR-0003](../adr/0003-units-are-atomic.md), [ADR-0004](../adr/0004-duplicates-never-deleted.md)

v0.1 decides everything from the file extension and the mtime year. This spec replaces that with a set of **detectors** that each add evidence. A **resolver** then turns the evidence into a category, a date and a confidence score, and records the reasons.

## 1. Detector framework

- Each detector declares `name`, `requires` (a capability such as `exif:pillow`, or none), `cost` (`stat`, `header` (reads up to 64 KiB), `content` (reads the whole file), `network`), and `applies_to(unit) -> bool`.
- Each detector returns **Evidence**: `{kind: category|date|unit|dup|warning, value, weight 0..1, reason}`.
- The resolver combines the evidence:
  - **Category:** the highest weighted score wins. Ties go to the more specific category. If the top score is below 0.5, the category is `Other` with `low_confidence`.
  - **Date:** the first source in the chain (§ 4) that yields a *plausible* date wins.
- Cost control:
  - `--detect` picks the detectors. Default: `units,dates,sniff`; `dupes` is opt-in because it reads content.
  - `header` detectors are capped at 64 KiB per file.
  - Metadata is cached in `<StateDir>/cache/meta.sqlite` (stdlib `sqlite3`), keyed by `(dev, ino, size, mtime_ns)`, so re-scans are fast.
- Every detector is independently testable with fixture files ([06 § 3](06-testing.md#3-fixture-corpus)).

## 2. Unit detection (bundles & projects)

**Problem (B05):** some directories are a single logical object. Moving their contents apart destroys them.

### 2.1 Unit kinds & markers

| Kind | Detected when | Confidence | Default policy |
|------|---------------|-----------|----------------|
| `bundle` | The directory extension is in the bundle list: `.app .bundle .framework .plugin .kext .xcodeproj .xcworkspace .playground .pages .numbers .key .rtfd .scptd .photoslibrary .musiclibrary .fcpbundle .logicx .band .imovielibrary .lrdata .sparsebundle .vmwarevm .pvm .utm .docset`, **or** it contains `Contents/Info.plist` | 1.0 | `keep` |
| `project` (VCS) | Contains `.git` (directory or file, for worktrees and submodules), `.hg` or `.svn` | 1.0 | `keep` |
| `project` (build) | Contains any marker: `package.json pyproject.toml setup.py requirements.txt Pipfile Cargo.toml go.mod pom.xml build.gradle* CMakeLists.txt Makefile *.sln *.csproj composer.json Gemfile mix.exs pubspec.yaml Package.swift deno.json` | 0.9 (0.6 for `Makefile` or `requirements.txt` alone) | `keep` |
| `library` | Contains a DB-like signature: `*.lrcat`, `Calibre Library/metadata.db`, `Zotero/zotero.sqlite`, `Obsidian` vault (`.obsidian/`), `Logseq` (`logseq/`) | 0.95 | `keep` |
| `dcim` | Named `DCIM` with `NNNXXXXX` camera subfolders, or contains `MISC/` + `DCIM/` | 0.9 | `explode` (photos are organized individually; folder structure dropped) |
| `website` | `index.html` plus a sibling `*_files/` directory (a browser "Save page as") | 0.9 | `move_whole` with the HTML |
| `sidecar group` | Files sharing a stem with known sidecar pairs: `.RAW/.CR2/.NEF/.ARW` + `.xmp` / `.jpg`, `.srt/.vtt` + video, `.cue` + `.bin`, `.shp/.shx/.dbf/.prj` | 0.9 | `move_together` (each member keeps its name and lands in the primary member's target directory) |

A Unit's descendants are **not** scanned individually. A Unit nested inside another Unit is absorbed into the outer one. Only `stat` totals are gathered (size, member count, newest mtime), for display and dating.

### 2.2 Unit policies

`unit_policy` (global, with an optional per-kind override):

- `keep` (default for bundles, projects and libraries): no Action. Listed under "Kept in place" with reasons.
- `move_whole`: the Unit is moved as one directory to `<UnitCategory>/<Year>/<name>`:
  - `bundle` (.app, …) → `Apps/`
  - `project` → `Projects/`
  - `library` → stays `keep` (moving libraries is never offered)
  - document bundles (`.pages`, `.numbers`, `.key`, `.rtfd`) → `Documents/`
- `explode`: only valid for `dcim`. Members are planned as normal files.
- `move_together`: only for sidecar groups.

The year of a Unit comes from the newest member's resolved date for projects ("last worked on"), and from the bundle's own birthtime or mtime for bundles.

**Guard (v0.2 subset):** before full detection ships, the scanner hard-codes the bundle extension list and the VCS and build markers as `keep`, so no v0.2 build can shred a project.

## 3. Duplicate detection

**Goal (G5):** find byte-identical files and show them. **Never delete** ([ADR-0004](../adr/0004-duplicates-never-deleted.md)).

### 3.1 Pipeline

1. **Candidates:** Units of kind `file` with `size >= dupes.min_size` (default 1 byte; 0-byte files are grouped separately as "empty files"). Placeholders and protected files are excluded. Files inside Units are **not** included unless `--dupes-include-units`.
2. **Group by size**, dropping singletons.
3. **Hardlink fold:** entries sharing `(dev, ino)` are one physical file. They are reported as `hardlinked`, not as duplicates.
4. **Partial hash:** BLAKE2b-128 of the first 64 KiB, the last 64 KiB and the size. Drop singletons.
5. **Full hash:** BLAKE2b-256, streamed in 1 MiB chunks, using `hashlib.file_digest` on 3.11+. Threaded with `--jobs`.
6. **Optional byte compare** (`--paranoid`): `filecmp.cmp(shallow=False)` against the group keeper.
7. Results are cached in `meta.sqlite` by `(dev, ino, size, mtime_ns)`.

Progress reports bytes hashed against the total candidate bytes. The run is cancellable.

### 3.2 Keeper suggestion

Within each group, rank the members by these rules and suggest the top one as **keeper**. The rest are **extras**.

1. A file inside a protected path or a Unit (it cannot be moved anyway).
2. A file already at its planned target (already organized).
3. The best name: no ` (1)`, ` copy`, `Copy of`, or `-1` suffix.
4. The oldest resolved date.
5. The shortest path.

The user can override the keeper (CLI `dupes --keep <path>`, or a GUI radio button).

### 3.3 Actions

- **Default: report-only.** `report.duplicates[]` lists groups with wasted bytes, and the CLI `organeyes dupes` prints them.
- **Opt-in quarantine** (`--quarantine-dupes`): extras get `op: quarantine` Actions to `_Duplicates/<keeper-stem>/<original rel path>`. They are journaled and undoable like any move. Quarantined files are excluded from future scans.
- Planned moves of extras are suppressed when quarantine is active, so a file is never both moved and quarantined.

### 3.4 Near-duplicates (`[exif]` extra, report-only)

Perceptual hash (dHash 64-bit) for images. Pairs with a Hamming distance ≤ 6 are reported as `near_duplicates[]` with similarity. No Actions are ever planned from near-duplicates.

## 4. Date resolution

**Problem (B30):** mtime reflects the last copy, not when a photo was taken or a document was written.

### 4.1 Source chain (first plausible wins)

| # | Source | Applies to | How | Confidence |
|---|--------|------------|-----|-----------|
| 1 | `exif` | JPEG, TIFF, HEIC, DNG and RAW | `DateTimeOriginal` (0x9003) → `CreateDate` (0x9004), plus `OffsetTimeOriginal` if present. Built-in parser: JPEG APP1 / TIFF IFD walk (stdlib `struct`). Pillow for HEIC/RAW with `[exif]`. | 0.95 |
| 2 | `media` | MP4, MOV, M4A, 3GP | `mvhd` creation_time (seconds since 1904-01-01 UTC). Built-in atom walker. `[media]` adds MKV/AVI/audio tags. | 0.85 (0.5 when the value is 0 or 1904) |
| 3 | `doc_meta` | PDF, DOCX/XLSX/PPTX, ODT/ODS/ODP, EPUB | PDF: `/CreationDate` in the trailer `Info` dictionary or XMP `xmp:CreateDate` (regex over the first and last 64 KiB). OOXML: `docProps/core.xml` `dcterms:created` (via `zipfile` + `xml.etree`). ODF: `meta.xml` `meta:creation-date`. EPUB: OPF `dc:date`. | 0.8 |
| 4 | `filename` | any | Patterns, in order: `IMG_YYYYMMDD_HHMMSS`, `VID_…`, `PXL_YYYYMMDD…`, `Screenshot YYYY-MM-DD at …`, `Screen Shot …`, `WhatsApp Image YYYY-MM-DD`, `YYYY-MM-DD`, `YYYY_MM_DD`, `YYYYMMDD` (only with a separator or prefix boundary, and only if month and day are valid) | 0.7 (0.5 for bare `YYYYMMDD`) |
| 5 | `birthtime` | any | `st_birthtime` (macOS, BSD, Windows 3.12+) | 0.5 |
| 6 | `mtime` | any | `st_mtime` (v0.1 behavior) | 0.4 |
| 7 | `unknown` | — | Everything failed | 0 → year folder `Unknown` |

### 4.2 Plausibility

A date is rejected, and the chain moves on, when:
- it is before 1990-01-01, except for `exif` and `doc_meta`, where the limit is 1970;
- it is more than 2 days in the future;
- it is a known camera default (`2000-01-01 00:00:00`, `1970-01-01`, `1980-01-01`, `2004-01-01`) **and** another source disagrees.

`birthtime > mtime` is allowed, because copies do that. The resolver records each rejected candidate in `reasons[]`, for example `exif rejected: 2000-01-01 looks like camera default`.

### 4.3 Time zones

- EXIF without an offset is treated as a naive local time and **used as is** for the year. A file shot at 23:30 on Dec 31 stays in the year it was taken.
- `mvhd` is UTC. Convert to the local time zone for the year.
- The report stores the ISO string with an offset when known, plus `tz_assumed: bool`.

### 4.4 Folder granularity

The year is the default. The `group_old` decade folding from v0.1 is kept (`group_old_years`, default 5) and now uses the resolved date. Month or quarter granularity remains a Future rules-engine item.

## 5. Content sniffing

**Goal:** catch files with a missing, wrong or misleading extension.

- A built-in signature table covers about 40 formats. Each entry has an offset and magic bytes, plus a secondary check where needed:
  - Images: PDF `%PDF-`; PNG; JPEG `FF D8 FF`; GIF87a/89a; WEBP (`RIFF....WEBP`); HEIC/AVIF (`ftypheic|heix|mif1|avif`); TIFF (`II*\0` / `MM\0*`); BMP; ICO; PSD `8BPS`.
  - Media: MP4/MOV (`ftyp` brand at 4), MKV/WebM (`1A 45 DF A3`), AVI, WAV, MP3 (`ID3` or a frame sync), FLAC, OGG.
  - Archives and installers: ZIP family (then a ZIP central-directory peek to tell DOCX/XLSX/PPTX/ODF/EPUB/JAR/APK/IPA apart), RAR, 7z, GZIP, BZ2, XZ, ZSTD, DMG (`koly` trailer), ISO (`CD001` at 0x8001), MSI/OLE (`D0 CF 11 E0`), EXE (`MZ`), ELF, Mach-O.
  - Other: SQLite, fonts (OTF, TTF, WOFF, WOFF2).
- **Text heuristic** for files without a match: UTF-8 decodable, under 1% control bytes, followed by a light shebang, JSON, CSV or Markdown check.
- `[magic]` extra: libmagic MIME type is used when the built-in table has no match.
- Outcomes:
  - The extension matches the signature: weight boosts the category.
  - **No extension:** the sniffed type sets the category (`source: sniff`). The rename suggestion appends the canonical extension, which is opt-in (`rename_policy.add_missing_ext`).
  - **Mismatch** (for example `invoice.pdf` that is really a ZIP or an EXE): category from the sniff, plus a `warning: extension_mismatch` that is **highlighted in red in the GUI**. A `.pdf` that is really an executable is shown as **Suspicious** and never auto-renamed.
- Sniffing reads at most 64 KiB (plus the ZIP central directory, which is up to 64 KiB from the end).

## 6. Expanded taxonomy

The built-in table lives in `taxonomy.py`. Each category has an icon, extensions, sniff types, and optional evidence rules. New categories apply **only with confidence ≥ 0.7**. Otherwise the v0.1 parent category is used, so existing layouts stay stable.

| Category | Parent (fallback) | Evidence |
|----------|-------------------|----------|
| Documents | — | pdf, doc(x), odt, rtf, txt, md, pages* |
| Spreadsheets | Documents | xls(x), ods, csv, tsv, numbers* |
| Presentations | Documents | ppt(x), odp, key* |
| Ebooks | Documents | epub, mobi, azw3, fb2, cbz, cbr, djvu |
| Photos | Images | Image **with** EXIF camera make/model or DateTimeOriginal (needs EXIF evidence), HEIC/RAW (cr2, nef, arw, dng, orf, rw2, raf) |
| Screenshots | Images | Filename pattern (`Screenshot*`, `Screen Shot*`, `CleanShot*`), or PNG with a screen-size dimension set and no camera EXIF |
| Graphics | Images | svg, ai, eps, psd, sketch, fig, xcf, afdesign; plus images with no camera EXIF (only when `split_images=true`) |
| Images | — | Remaining image types |
| Videos | — | as v0.1, plus mts, m2ts, vob, ts (when sniffed as MPEG-TS) |
| Audio | — | as v0.1, plus mid, alac, ape |
| Subtitles | Videos | srt, vtt, ass, ssa, sub (unless sidecar-grouped with a video) |
| Code | — | as v0.1, **minus** json, xml, yaml, toml, ini and cfg (moved to Data) |
| Data | Code | json, xml, yaml, yml, toml, ini, cfg, sqlite, db, parquet, ndjson |
| Fonts | Other | ttf, otf, woff, woff2, ttc |
| Installers | Archives | dmg, pkg, mpkg, exe, msi, deb, rpm, appimage, apk, ipa |
| Archives | — | zip, rar, 7z, tar, gz, bz2, xz, zst, iso |
| 3D & CAD | Other | stl, obj, fbx, blend, step, stp, iges, dwg, dxf, 3mf, gltf, glb, skp |
| Apps / Projects | — | Unit-only categories (§ 2.2) |
| Other | — | fallback |

\* As directories, these are bundle Units (§ 2.1).

`split_images` (default `true`, needs evidence) and `taxonomy_version` are recorded in the report so plans can be reproduced.

## 7. Filename normalization

Closes B17. `rename_policy` (config):

| Setting | Default | Meaning |
|---------|---------|---------|
| `mode` | `conservative` | `off`, `conservative` or `tidy` |
| `skip_categories` | `Code, Data, Projects, Apps` | Never renamed |
| `add_missing_ext` | `false` | Append the sniffed extension when the name has none |

**Conservative:**
- Trim leading and trailing whitespace from the stem.
- Collapse runs of whitespace into one space.
- Remove the characters `<>:"/\|?*` and control characters.
- Strip trailing dots and spaces.
- Normalize to Unicode NFC.
- **Underscores are kept.**

**Tidy** (opt-in): conservative, plus `_` → space, removal of duplicate ` (1)` copy markers, and lowercasing of the extension.

**Hard rules:**
- The resulting stem is never empty and never starts with `.`, unless the original did. If cleaning yields an empty stem, keep the original name.
- Truncate to 200 bytes UTF-8 at a character boundary and append `…` (U+2026), keeping the extension.
- Windows reserved stems get an `_` suffix (`CON` → `CON_`).
- Compare after NFC on both sides, so NFD names on macOS are not flagged as changed.
- No rename is planned for files inside a Unit.

Each rename Action lists exactly which rules fired in `reasons[]`.

## 8. Optional AI classification (`[ai]`)

**Purpose:** improve the long tail (`Other` and low-confidence Units) without becoming a privacy problem.

### 8.1 When it runs

- It is enabled **only** by `--ai` (CLI) or the GUI toggle, plus an API key in `ANTHROPIC_API_KEY` or the OS keychain through config `ai.key_source`. It is **never** on by default, and never enabled by a config file alone. Each session requires the flag or toggle.
- Candidates: Units whose classification confidence is below 0.6 or whose category is `Other`, up to `ai.max_items` (default 500).
- Before any request, the CLI and GUI show: the item count, the fields to be sent, an estimated token count and cost, and the model. The user must confirm (`--yes` skips this in scripts).

### 8.2 Data contract

| Level | Sent | Default |
|-------|------|---------|
| `metadata` | File name, extension, size bucket, sniffed type, parent folder name (one level), resolved year | **Yes** |
| `snippet` | Plus the first 2 KiB of **text** files only, after secret redaction (regexes for keys, tokens, emails and numbers longer than 8 digits) | Opt-in: `ai.content = "snippet"` |
| Never sent | Absolute paths, file contents of binary files, other files' names beyond the parent folder, user name | — |

### 8.3 Mechanics

- Model: configurable `ai.model`, default `claude-haiku-4-5`. Requests are batched (up to 50 items per request) with a JSON-schema structured output: `{item_id, category ∈ taxonomy, confidence, reason ≤ 120 chars}`. Categories outside the taxonomy are rejected.
- AI evidence weight is capped at 0.75. It can never override `exif`, `sniff` mismatch warnings or Unit detection.
- Cache: `meta.sqlite` keyed by `(name, size, sniffed_type, content_hash?)` and model. A re-scan costs nothing.
- Failures (network, rate limit, invalid output) degrade to non-AI classification with a warning. They never block a plan.
- Every AI-classified Action shows `source: ai` and the model's reason in the GUI and CLI. Users can filter on it.

## 9. Explainability

Every Action in a Plan carries `reasons[]`, an ordered list of short machine-coded, human-readable strings:

```
category=Photos (0.95): exif Make=Apple Model="iPhone 14"
date=2023-05-14 (exif DateTimeOriginal, 0.95); mtime 2025-01-02 ignored
rename: collapsed whitespace; NFC
target: re-suffixed " (2)" — collides with Photos/2023/IMG_0001.HEIC
```

- CLI: `plan --explain <path|action_id>`.
- GUI: an expandable row and a hover tooltip.
- Report: `reasons` on each suggestion ([04 § 2](04-data-formats.md#2-report-v2)).
