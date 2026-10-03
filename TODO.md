# TODO

The design for the next releases is in [docs/SPEC.md](docs/SPEC.md). Work is tracked by **bug ID** ([docs/BUGS.md](docs/BUGS.md)) and **milestone** ([docs/ROADMAP.md](docs/ROADMAP.md)). The old ad-hoc items are mapped in [ROADMAP § Mapping from the old TODO.md](docs/ROADMAP.md#mapping-from-the-old-todomd).

## Done (v0.1)

- [x] Progress bar in CLI and Web GUI
- [x] Interactive CLI review mode
- [x] Year range grouping for old files (`--group-old`)
- [x] Editable suggestions in Web GUI
- [x] Symlink and hardlink deduplication in category stats
- [x] Error handling: permission errors, retry on locked files, `--verbose`, `--log`
- [x] ARIA labels for icon-only buttons

## v0.2 — Safe by default (next)

- [ ] Package split + `file_organizer.py` shim
- [ ] B01 path containment & name validation
- [ ] B02 / B07 / B15 undo v2 (no-clobber, run-id only, journaled mkdir cleanup)
- [ ] B03 / B04 / B12–B14 / B26 / B27 server hardening (loopback, token, no static fallback, JobManager)
- [ ] B05 bundle & project guard (interim)
- [ ] B06 / B11 / B32 symlink, hardlink & special-file handling
- [ ] B08 / B09 write-ahead journal in State dir + recovery + self-exclusion
- [ ] B10 untrack `organizer_report.json` + CI hygiene check
- [ ] B16 plan validation (collisions, case-fold, fingerprints, free space)
- [ ] B17 filename normalization rules
- [ ] B18 `skipped_depth` reporting, unified default depth
- [ ] B19 / B31 protection globs, cloud & library defaults, placeholder skip
- [ ] B28 / B33 / B34 / B35 CLI subcommands, Reporter events, exit codes
- [ ] Test suite + CI matrix ([docs/specs/06-testing.md](docs/specs/06-testing.md))

## v0.3 — Smart Detection I

- [ ] Detector framework + metadata cache
- [ ] Full unit detection (bundles, projects, libraries, DCIM, sidecars)
- [ ] B30 date resolution chain (EXIF, mvhd, doc metadata, filename, birthtime)
- [ ] Content sniffing + extension-mismatch warnings
- [ ] Taxonomy v2 + explainability (`reasons[]`, `plan --explain`)
- [ ] Optional extras `[exif]`, `[media]`, `[magic]` + `organeyes doctor`

## v0.4 — Smart Detection II + GUI/API

- [ ] Duplicate detection, keeper ranking, opt-in quarantine
- [ ] Plan export/import (JSON, CSV)
- [ ] HTTP API v2
- [ ] GUI fixes G-1…G-15 (B20–B25, B29)

## v0.5 — Optional AI

- [ ] `[ai]` extra: metadata-only fallback classifier, cost preview, cache
