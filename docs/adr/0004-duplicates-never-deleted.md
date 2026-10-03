# ADR-0004: Duplicates are reported or quarantined, never deleted

- **Status:** Proposed · **Date:** 2026-10-02 · **Specs:** [03 § 3](../specs/03-smart-detection.md#3-duplicate-detection)

## Context
Duplicate detection is the most requested feature with real destructive potential. Users expect "remove duplicates". A wrong keeper choice, a hash bug, or hardlinks mistaken for copies would destroy data. Principle #1 is "never lose data".

## Decision
- Duplicate detection is **report-only** by default.
- The only action OrganEyes offers is an opt-in **quarantine**: a journaled move of the extras into `_Duplicates/<keeper-stem>/…`, which is undoable like any move.
- OrganEyes **never destroys the last copy of any user data**. Precisely, the only removal operations allowed are:
  1. `unlink(src)` as the final step of a move, after `dst` is a verified copy (cross-device: size plus hash) or a hardlink to the same inode (link-then-unlink);
  2. `unlink` of OrganEyes's own temp files (`*.organeyes-partial-*`, `*.organeyes-tmp-*`, probe files);
  3. `rmdir` of **empty** directories that were journaled as created or pruned by OrganEyes.

  These all live in one module, `fsutil.py`, behind three named functions. A CI check enforces that no other `unlink`/`remove`/`rmdir`/`rmtree` call exists ([06 § 5](../specs/06-testing.md#5-static-checks)), and property tests check the "content multiset never shrinks" invariant. Duplicates are never removed. Users empty `_Duplicates/` themselves, in Finder or Explorer, after review.
- Hardlinks are reported as `hardlinked`, not duplicates. Near-duplicates (perceptual hash) are report-only and can never produce Actions.

## Consequences
- **Positive:** no hash collision or keeper mistake can lose data. The behavior is simple to explain.
- **Negative:** users must do a final manual delete, and disk space is not reclaimed automatically. The quarantine folder is clearly named, and the CLI or GUI shows the bytes that can be reclaimed.

## Alternatives considered
- **Delete to the OS trash:** platform-specific (the trash API differs everywhere), still a deletion from OrganEyes's point of view, and it complicates undo.
- **Replace extras with hardlinks:** saves space transparently, but changes edit semantics (editing one file edits all) and surprises users.
