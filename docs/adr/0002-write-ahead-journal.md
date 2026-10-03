# ADR-0002: Write-ahead journal instead of a post-hoc rollback file

- **Status:** Proposed · **Date:** 2026-10-02 · **Specs:** [02 § 4–5](../specs/02-safety-and-security.md#4-write-ahead-journal), [04 § 4](../specs/04-data-formats.md#4-journal-jsonl) · **Fixes:** B02, B07, B08, B09, B15

## Context
v0.1 writes `organizer_rollback_<ts>.json` into the target folder **after** all moves finish. A crash loses the record (B08). The file then gets organized by the next run (B09). It holds absolute paths, which the GUI undo trusts (B02). It also cannot tell directories OrganEyes created from ones the user created (B15).

## Decision
- Each Run appends JSONL records to `<StateDir>/runs/<root_hash>/<run_id>.jsonl`, which is outside the Root.
- For each Action, an `intent` record is fsynced **before** the move, and a `done` or `failed` record is written after it. Directory creation and removal are journaled.
- Paths are Root-relative. Absolute paths are recomputed and containment-checked.
- Recovery resolves in-doubt intents by inspecting the file system. The user can then resume or roll back.
- Undo is a journaled run in its own right, which addresses runs by `run_id`, never by file path.
- v1 rollback files are supported only through an explicit, validated import.

## Consequences
- **Positive:** a crash-safe undo. Cleanup is precise. The GUI cannot load forged rollback files. History becomes queryable.
- **Negative:** one fsync per Action slows large runs. Mitigation: `intent` is fsynced every time, `done` is batched every 16 records, and the recovery logic tolerates a missing `done`. State lives outside the folder, so moving the folder to another machine loses its history. This is documented, and `history --export` can be added later.

## Alternatives considered
- **Write the rollback file incrementally inside the Root:** still self-organizes, still sits in user space, and is still forgeable.
- **SQLite journal:** good durability, but harder to inspect and recover by hand. JSONL can be read with `cat`.
- **Copy-then-delete for everything:** doubles I/O and needs free space. Only used across devices.
