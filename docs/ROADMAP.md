# OrganEyes Roadmap

> Status: **Design / Draft** · Last updated: 2026-10-02 · See [SPEC.md](SPEC.md)

Each milestone is releasable on its own. **Safety comes first:** v0.2 adds no new user-visible capability beyond what is needed to stop v0.1 from losing or exposing data.

## v0.2 — "Safe by default"

**Theme:** fix every Critical bug, restructure into a package, and build the journal.

Scope:
- Package split ([01 § 2](specs/01-architecture.md#2-package-layout)) with the `file_organizer.py` shim and legacy flag mapping ([05 § 1.4](specs/05-cli-and-api.md#14-legacy-flag-mapping)).
- Path containment and name validation ([02 § 2](specs/02-safety-and-security.md#2-path-containment)): **B01**.
- Plan validation ([02 § 3](specs/02-safety-and-security.md#3-plan-validation)): **B16**.
- Write-ahead journal, recovery, State dir ([02 § 4](specs/02-safety-and-security.md#4-write-ahead-journal)): **B08**, **B09**.
- Undo v2 with v1 import ([02 § 5](specs/02-safety-and-security.md#5-undo-v2), [04 § 5](specs/04-data-formats.md#5-legacy-v1-rollback-import)): **B02**, **B07**, **B15**.
- No-clobber moves ([02 § 6](specs/02-safety-and-security.md#6-atomic-no-clobber-moves)).
- Symlink, hardlink and special-file handling ([02 § 7](specs/02-safety-and-security.md#7-symlinks-hardlinks-and-special-files)): **B06**, **B11**, **B32**.
- Server hardening, with the v1 API kept behind the token ([02 § 8](specs/02-safety-and-security.md#8-gui-server-hardening)): **B03**, **B04**, **B12**, **B13**, **B14**, **B26**, **B27**.
- Protection model ([02 § 9](specs/02-safety-and-security.md#9-protection-model)), including cloud and library defaults and placeholder skipping: **B19**, **B31**.
- Self-exclusion ([02 § 10](specs/02-safety-and-security.md#10-self-exclusion)): **B09**.
- **Bundle and project guard** (hard-coded keep list, [03 § 2.2](specs/03-smart-detection.md#22-unit-policies)): **B05** (interim).
- Filename normalization rules ([03 § 7](specs/03-smart-detection.md#7-filename-normalization)): **B17**.
- `skipped_depth` reporting and a unified default depth: **B18**.
- Events and Reporter in place of prints, CLI subcommands, exit codes: **B28**, **B33**, **B34**, **B35**.
- Repo hygiene: `git rm --cached organizer_report.json` and a CI guard: **B10**.
- Test suite and CI matrix ([06](specs/06-testing.md)).
- Minimal GUI changes needed to keep working: token handling (G-2) and the `action_id`-based rename (G-8).

Exit criteria:
- All Critical and High tests for B01–B19 pass, plus B26–B28 and B31–B35.
- 100% branch coverage on the mutation modules.
- A round-trip property test over 1,000 generated trees.

## v0.3 — "Knows what things are"

**Theme:** Smart Detection I.

Scope:
- Detector framework and metadata cache ([03 § 1](specs/03-smart-detection.md#1-detector-framework)).
- Full unit detection and policies: bundle, project, library, DCIM, website and sidecar groups ([03 § 2](specs/03-smart-detection.md#2-unit-detection-bundles--projects)): **B05** (complete).
- Date resolution chain with built-in EXIF, `mvhd` and document metadata parsers ([03 § 4](specs/03-smart-detection.md#4-date-resolution)): **B30**.
- Content sniffing and mismatch warnings ([03 § 5](specs/03-smart-detection.md#5-content-sniffing)).
- Expanded taxonomy v2 ([03 § 6](specs/03-smart-detection.md#6-expanded-taxonomy)).
- Explainability: `reasons[]`, `plan --explain` ([03 § 9](specs/03-smart-detection.md#9-explainability)).
- Report v2 ([04 § 2](specs/04-data-formats.md#2-report-v2)) with v1 aliases.
- Optional extras `[exif]`, `[media]` and `[magic]`, plus `organeyes doctor`.

Exit criteria:
- Date-source accuracy of at least 95% on the fixture corpus.
- Zero Actions planned inside Units.
- The core CI job passes with no extras installed.

## v0.4 — "Finds the mess"

**Theme:** Smart Detection II, plus GUI and API catch-up.

Scope:
- Duplicate detection, keeper ranking and the opt-in quarantine ([03 § 3](specs/03-smart-detection.md#3-duplicate-detection)). Near-duplicates with `[exif]`.
- Plan export and import as JSON and CSV ([04 § 3](specs/04-data-formats.md#3-plan-file)).
- HTTP API v2 and JobManager ([05 § 2](specs/05-cli-and-api.md#2-http-api-v2)). Remove the v1 API.
- GUI fix requirements G-1 through G-15 ([05 § 3](specs/05-cli-and-api.md#3-gui-fix-requirements)): **B20**–**B25**, **B29**.
- `history` and `recover` in the GUI.
- Drop the v1 compatibility aliases from the Report.

Exit criteria:
- The E2E suite passes offline.
- A 5,000-item plan stays responsive.
- Zero code paths that delete user files (static check).

## v0.5 — "Asks for help when unsure"

**Theme:** optional AI classification.

Scope:
- The `[ai]` extra ([03 § 8](specs/03-smart-detection.md#8-optional-ai-classification-ai)): metadata-only by default, opt-in snippets with redaction, a cost preview, caching, and a confidence cap.
- GUI AI toggle and confirmation (G-14).
- Accuracy evaluation on a labeled set of "Other" files. Publish the precision per category in the docs.

Exit criteria:
- With AI off, there are zero network calls (proven by a test with the socket monkeypatched to raise).
- AI never overrides exif, sniff or unit evidence.

## Future (not scheduled)

These items came up in the design discussion but are **out of scope** for this cycle. The architecture leaves room for them: the detector registry, config layers and Plan model are their extension points.

- **Rules engine and profiles:**
  - User-defined categories and extension maps.
  - Path templates (`{category}/{year}/{month}`) and month or quarter grouping.
  - Per-folder profiles.
  - Batch rename patterns (`photo_{n:03}`).
- **Automation:** watch mode for a Downloads inbox, scheduled runs, launchd, systemd and Task Scheduler integration, notifications.
- **GUI redesign:** dark mode, keyboard shortcuts (j/k/space/enter), file previews and thumbnails, a timeline view, a desktop wrapper.
- **Content-aware grouping:** receipts and invoices by OCR, photo events by time and GPS clustering.
- **Network volumes:** SMB- and NFS-specific handling and performance.

## Mapping from the old TODO.md

| Old TODO item | Now |
|---------------|-----|
| Fix remaining file size summary bug | B11 (v0.2) |
| Fix dead GET `/api/analyze` | B12 (v0.2) |
| Editable suggestions in CLI (export/import) | Plan file (v0.4); interactive review (v0.2) |
| `--group-old` toggle in Web GUI | B23 / G-6 (v0.4) |
| Fix HTML file serving path | B13 (v0.2) |
| Improve error reporting in GUI | B22 / G-5 (v0.4) |
| Custom category rules | Future: rules engine |
| Date grouping by month or quarter | Future: rules engine |
| Duplicate file detection (hash-based, report-only) | v0.4 ([03 § 3](specs/03-smart-detection.md#3-duplicate-detection)) |
| File preview in GUI | Future: GUI redesign |
| Batch rename patterns | Future: rules engine |
| Export move plan to CSV | v0.4 ([04 § 3](specs/04-data-formats.md#3-plan-file)) |
| Dark mode | Future: GUI redesign |
| Keyboard shortcuts in GUI | Future: GUI redesign |
