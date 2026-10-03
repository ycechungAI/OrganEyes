# OrganEyes — Master Specification (v0.2 → v0.5)

> Status: **Design / Draft** · Last updated: 2026-10-02 · Applies to: `file_organizer.py` v0.1 and the planned `organeyes` package

This document is the entry point to the OrganEyes design set. It defines what the next releases will do, the principles they must not break, and the vocabulary every other spec uses. **It contains no code.** Implementation follows the [roadmap](ROADMAP.md).

---

## 1. Vision

OrganEyes turns a messy folder into a predictable `Category / Year` layout. It shows you every change before it happens and can undo all of them afterwards.

v0.1 proved the idea. v0.2+ makes it **safe enough to point at a real home directory** and **smart enough to make the right call** on photos, projects, app bundles, duplicates and mislabelled files.

## 2. Goals

| # | Goal | Measured by |
|---|------|-------------|
| G1 | **No data loss, ever.** No overwrite, no deletion, no escaping the root. | Every Critical bug in [BUGS.md](BUGS.md) closed, with a regression test for each |
| G2 | **Every run can be fully undone, even after a crash.** | Crash-injection tests in [06-testing.md](specs/06-testing.md) pass |
| G3 | **Don't break things that must stay together.** Projects, app bundles and photo libraries move as one unit or not at all. | Bundle and project fixture suite |
| G4 | **Use the right date**: when the photo was taken or the document was written, not when it was last copied. | Date-source accuracy on a fixture corpus, at least 95% |
| G5 | **Find duplicates** without deleting anything. | Duplicate fixture suite; zero delete code paths |
| G6 | **Explain every suggestion.** | Every plan action carries `reasons[]` |
| G7 | **Keep the zero-install promise.** The core runs on Python stdlib alone. Richer features are opt-in extras. | CI job with no third-party packages installed |

## 3. Non-goals (this cycle)

- A user-defined **rules engine** or profiles (TOML rules, path templates). The architecture leaves room for it; see [ROADMAP.md § Future](ROADMAP.md#future-not-scheduled).
- **Automation**: watch mode, scheduled runs, launchd or systemd units.
- A **GUI redesign**, dark mode or a desktop wrapper. The GUI gets bug fixes and the minimum UI needed to show new data.
- **Deleting** files for any reason, including duplicates.
- Cloud or remote storage APIs. OrganEyes works only on local file systems.

## 4. Principles (ordered — earlier wins on conflict)

1. **Never lose data.** Never overwrite, never delete user files, and never touch anything outside the chosen root.
2. **Plan, then act.** Every change is first written down as a *Plan* that can be reviewed. Executing means applying a validated Plan, not re-deriving one.
3. **Every action is reversible.** The undo record is written *before* each action, not after.
4. **Local only.** No network listener except the loopback GUI. No outbound traffic unless the user turns on the AI extra.
5. **Stdlib core.** Missing extras degrade features. They never cause crashes.
6. **Explain yourself.** Confidence and reasons are first-class data.

## 5. Glossary

| Term | Definition |
|------|------------|
| **Root** | The absolute, resolved directory the user asked to organize. Nothing outside it is ever read for planning or modified. |
| **Scan** | A read-only walk of the Root that produces Entries. |
| **Entry** | One file system object seen during a Scan: path relative to Root, `lstat` data, and kind (file, dir or symlink). |
| **Unit** | The thing that gets moved. Usually one file, but it can be a whole directory that must stay intact (an app bundle, a git project, a photo library). See [03-smart-detection.md § 2](specs/03-smart-detection.md#2-unit-detection-bundles--projects). |
| **Classification** | `(category, confidence, source, reasons[])` assigned to a Unit. |
| **Resolved date** | `(datetime, date_source, confidence)` for a Unit. Decides the Year folder. |
| **Action** | One planned operation: `move`, `rename`, `move+rename`, `quarantine` or `skip`. Has a stable `action_id`. |
| **Plan** | An ordered, validated list of Actions plus scan fingerprints. It is serializable, so it can be exported, edited and imported. |
| **Journal** | An append-only, write-ahead log of the Actions executed in one *Run*. It is the only source of truth for undo. |
| **Run** | One execution of a Plan. It has a `run_id` and exactly one Journal. |
| **Rollback (v1)** | The legacy `organizer_rollback_*.json` file. Read-only import support only. |
| **State dir** | The per-user directory where OrganEyes keeps Journals and caches. It is never inside the Root. |

## 6. Pipeline overview

```
Scan ─► Detect Units ─► Sniff ─► Classify ─► Resolve Date ─► Plan ─► Validate ─► Execute (journaled) ─► Report
 │                                              │                       │
 └─ read-only ──────────────────────────────────┘                       └─ the only stage that mutates the FS
```

Details: [01-architecture.md](specs/01-architecture.md).

## 7. Document map

| Doc | Purpose |
|-----|---------|
| [BUGS.md](BUGS.md) | Audit of v0.1: 35 numbered defects (B01–B35) with location, failure scenario and fix design |
| [specs/01-architecture.md](specs/01-architecture.md) | Package layout, pipeline stages, core types, optional extras |
| [specs/02-safety-and-security.md](specs/02-safety-and-security.md) | Path containment, plan validation, journal, undo v2, atomic moves, server hardening |
| [specs/03-smart-detection.md](specs/03-smart-detection.md) | Units and bundles, duplicates, date resolution, content sniffing, taxonomy, optional AI |
| [specs/04-data-formats.md](specs/04-data-formats.md) | Report v2, Plan, Journal and Config schemas with examples |
| [specs/05-cli-and-api.md](specs/05-cli-and-api.md) | CLI subcommands, HTTP API v2, GUI fix requirements |
| [specs/06-testing.md](specs/06-testing.md) | Test strategy, fixtures, CI matrix, acceptance per bug |
| [ROADMAP.md](ROADMAP.md) | Milestones v0.2–v0.5 and future work |
| [adr/](adr/) | Architecture Decision Records 0001–0005 |

## 8. Compatibility promise

- `python3 file_organizer.py …` keeps working through v0.x as a thin shim over the package. Deprecated flags print a one-line warning ([05-cli-and-api.md § 1.4](specs/05-cli-and-api.md#14-legacy-flag-mapping)).
- v1 rollback files stay undoable through an import path ([04-data-formats.md § 5](specs/04-data-formats.md#5-legacy-v1-rollback-import)).
- The default output layout `Category/Year/name` does not change. New categories only appear when their detector applies with high confidence (see [03 § 6](specs/03-smart-detection.md#6-expanded-taxonomy)).

## 9. Open questions

| # | Question | Default if unresolved |
|---|----------|-----------------------|
| Q1 | Should detected projects move to `Projects/<year>/` or stay in place? | **Stay in place** (`unit_policy = "keep"`) |
| Q2 | Should we split Images into Photos and Graphics by default? | **Yes**, but only when EXIF evidence exists. Otherwise keep `Images`. |
| Q3 | Should the minimum Python version rise to 3.9 (for `Path.is_relative_to`, `hashlib.file_digest` backport)? | **Yes**, 3.9. The README must be updated. |
| Q4 | Should B10 be fixed with a history rewrite of `organizer_report.json`, or only `git rm --cached`? | `git rm --cached`. The owner decides on the rewrite. |
