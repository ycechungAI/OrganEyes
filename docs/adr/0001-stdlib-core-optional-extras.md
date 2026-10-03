# ADR-0001: Stdlib core with optional extras

- **Status:** Proposed · **Date:** 2026-10-02 · **Specs:** [01 § 5](../specs/01-architecture.md#5-optional-extras--capability-registry)

## Context
v0.1 advertises "No dependencies — uses only Python standard library". It is a single file that users run with `python3 file_organizer.py`. The smart-detection features (EXIF from HEIC, broad MIME detection, LLM classification) are much better with third-party libraries. Requiring those libraries would break the zero-install promise and add supply-chain surface to a tool that moves user files.

## Decision
- The **core** (scan, plan, validate, execute, journal, undo, server, duplicate hashing, built-in sniffing, and the minimal EXIF, `mvhd` and document-metadata parsers) imports **only the standard library**.
- Richer features are pip **extras**: `[exif]`, `[media]`, `[magic]`, `[ai]` and `[all]`. A capability registry probes them once. A missing extra degrades the feature and adds a `capability_missing` warning. It never raises.
- The code becomes the `organeyes` package. `file_organizer.py` stays as a shim.
- The minimum Python version is raised to 3.9.

## Consequences
- **Positive:** the zero-install path still works. The security-critical code has no third-party dependencies. CI can prove the core is stdlib-only.
- **Negative:** we maintain small hand-written parsers (EXIF date tags, MP4 `mvhd`, PDF Info) with limited coverage. The docs must explain why HEIC dates need `[exif]`.
- The GUI still needs a one-time maintainer build (Node.js) to produce vendored assets. Users never need Node.

## Alternatives considered
- **Strict zero dependencies:** this rules out HEIC EXIF and AI, and accepts much worse accuracy.
- **Dependencies welcome** (FastAPI, Pillow, watchdog as hard requirements): easier to build, but it breaks the promise and adds attack surface to the mutating path.
