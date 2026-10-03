# ADR-0003: Bundles and projects are atomic Units

- **Status:** Proposed · **Date:** 2026-10-02 · **Specs:** [03 § 2](../specs/03-smart-detection.md#2-unit-detection-bundles--projects) · **Fixes:** B05

## Context
v0.1 recurses into every directory that is not protected and classifies each file by extension. macOS bundles (`.app`, `.photoslibrary`, `.pages`), code projects (git repositories, npm and Python projects) and app libraries (Lightroom, Calibre, Obsidian) get scattered across category folders. That is unrecoverable in practice without undo, and it silently corrupts libraries.

## Decision
- Introduce the **Unit**: the thing that gets moved. Detectors recognize bundles, projects, libraries, DCIM trees, saved web pages and sidecar groups from markers. A Unit's members are never planned individually.
- The default policy for bundles, projects and libraries is **`keep`** (leave in place, list under "Kept in place"). `move_whole` is opt-in. Libraries are never moved.
- v0.2 ships a hard-coded guard (bundle extensions plus VCS and build markers) before full detection arrives in v0.3.

## Consequences
- **Positive:** OrganEyes is safe to run on a home folder that contains projects. "Kept in place" makes the behavior visible.
- **Negative:** loose files inside a project are no longer organized, which is intended. False positives (a stray `Makefile` turns a folder into a "project") are handled with confidence levels and a `--unit-policy` override. The marker list needs maintenance.

## Alternatives considered
- **Only expand `DEFAULT_PROTECTED`:** cannot express "a folder that *contains* X".
- **Ask the user per folder:** too much friction for the beginner-focused GUI. It may come later as a review option.
