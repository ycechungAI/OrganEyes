# 06 — Testing Strategy

> Status: **Design / Draft** · Parent: [SPEC.md](../SPEC.md)

v0.1 has no tests. Because OrganEyes moves user files, **safety properties are tested before features**. No milestone ships with a failing or skipped Critical test.

## 1. Tooling

- **Runner:** `pytest`, a dev dependency only. Tests must not import any optional extra unless they are marked `@pytest.mark.extra("exif")`. They are skipped when the extra is missing, and run in the `extras` CI job.
- **Property tests:** `hypothesis` (dev dependency) for name validation, containment and filename normalization.
- **Coverage:** `coverage.py`. Gate: **100% branch coverage for `fsutil.py`, `execute.py`, `journal.py`, `undo.py` and `validate.py`**, and 85% overall.
- **Layout:** `tests/unit/`, `tests/integration/`, `tests/security/`, `tests/fixtures/` (generators, not binary blobs where possible), `tests/e2e/` (GUI with Playwright, v0.4+).

## 2. Test tiers

| Tier | Scope | Examples |
|------|-------|----------|
| Unit | Pure functions | `validate_name`, `ensure_contained`, the date-pattern parser, signature matching, keeper ranking, plan determinism |
| Integration | Real temp directories (`tmp_path`) | scan → plan → apply → undo round-trip that restores a byte-identical tree (compared by path, size and hash) |
| Fault injection | Monkeypatched `os` functions | Crash after `intent` and before `rename`; crash after `rename` and before `done`; `ENOSPC` while writing the journal; `EXDEV` paths; `EBUSY` retry |
| Security | HTTP server in a thread | Token, Host, Origin and traversal payloads |
| Platform | CI matrix | Case-insensitive collisions (macOS and Windows runners), reserved names (Windows), `st_birthtime`, placeholder flags (mocked) |
| E2E (v0.4) | Playwright against `organeyes serve` | Analyze → edit → apply → undo in the browser, with an offline network to prove no CDN calls |

## 3. Fixture corpus

`tests/fixtures/build.py` generates trees on demand, so the repo holds no large binaries:

- **Tiny media:** a 1×1 JPEG with an EXIF `DateTimeOriginal` (hand-assembled bytes), JPEG with the camera-default date `2000:01:01`, PNG screenshot-named, HEIC header stub, MP4 with an `mvhd` creation time, and MP4 with `mvhd = 0`.
- **Documents:** a minimal PDF with `/CreationDate`, a DOCX zip with `docProps/core.xml`, an ODT zip with `meta.xml`, and an EPUB with `dc:date`.
- **Mismatches:** `invoice.pdf` containing `MZ`, `photo.jpg` containing PNG bytes, extension-less ZIP and text files.
- **Units:** `Foo.app/Contents/Info.plist`, a `proj/` with `.git/HEAD` + `package.json`, `My.photoslibrary/`, `DCIM/100CANON/IMG_0001.JPG`, `page.html` + `page_files/`, and `IMG_1.CR2` + `IMG_1.xmp`.
- **Links:** a symlink directory pointing at `/` (or at `tmp_path.parent`), a loop `a -> .`, a relative file symlink, an absolute file symlink, and a hardlink pair.
- **Names:** `...txt`, `   .pdf`, a 300-byte name, `CON.txt`, an NFD `café.txt`, `Photo.JPG` + `photo.jpg` (on case-sensitive FS), and `my_module.py`.
- **Duplicates:** three identical 4 MiB files, files with the same size but different content, same-prefix files that differ only in the last 64 KiB, and empty files.
- **Self-artifacts:** v0.1 `organizer_rollback_*.json` and `organizer_report.json` in the Root.

## 4. Key test cases (non-exhaustive)

### Safety invariants (property-based)
- For any generated tree and any sequence of user edits, `apply` followed by `undo` restores the original multiset of `(rel_path, size, blake2b)`.
- No operation ever leaves a file outside the Root that was not there before. A checksum of `tmp_path.parent` stays unchanged.
- No operation ever reduces the number of distinct content hashes in the Root. Proves "no data loss".
- `ensure_contained` rejects every string that contains a `..` segment or an absolute anchor, under hypothesis-generated Unicode, separators and NUL.

### Journal & recovery
- Kill after N actions, for N in {0, 1, mid, last}, using a `CancelToken` that raises, plus monkeypatched `os.rename` that raises `SystemExit` at a chosen call. `recover --rollback` restores the original tree. `recover --resume` reaches the same end state as an uninterrupted run.
- A truncated last JSONL line (a partial write) is tolerated and treated as absent.
- The index can be rebuilt from journals.

### No-clobber
- A destination created between validation and the move gets a re-suffix, and the original is untouched.
- Undo when the original path has been re-occupied: conflict reported, both files intact, `--restore-conflicts-to` works.
- A cross-device move with injected corruption: verify fails, the partial copy is removed, and the source is intact.

### Server security (`tests/security/test_server.py`)
- No token → 401. Wrong token → 401. A correct token works.
- `Host: evil.com` → 421. `Origin: https://evil.com` on POST → 403.
- `OPTIONS` → 405, with no `Access-Control-*` header on any response.
- `GET /Documents/secret.pdf` → 404 (no static fallback).
- `PATCH` with `new_name: "../../x"`, `"a/b"`, `"CON"`, `"\u0000"` → 400 per item.
- `POST /undo {"rollback_file": "/tmp/x.json"}` → 400 (unknown field) and nothing moved.
- A 9 MiB body → 413.
- Two simultaneous `POST /apply` → one 202 and one 409.
- The socket binds only to the loopback interface (assert `server_address[0]`).

## 5. Static checks

- `ruff` (lint), `mypy --strict` on `organeyes/` (types). Stdlib-only import check: a CI job installs the package **without extras** and imports every module.
- **Mutation-surface lint:** a grep test asserts that `os.rename`, `os.replace`, `os.link`, `os.unlink`, `os.remove`, `os.rmdir`, `shutil.move`, `shutil.rmtree` and `Path.unlink/rename/rmdir` appear only in `fsutil.py`, `execute.py` and `journal.py` (the latter only for its own files). `shutil.rmtree` must not appear anywhere.
- Repo hygiene (B10): CI fails if `git ls-files` matches `organizer_report*.json` or `organizer_rollback_*.json` outside `docs/examples/`.

## 6. Acceptance criteria per bug

| Bug | Test(s) that must pass |
|-----|------------------------|
| B01 | security: traversal `new_name` payloads rejected; unit: containment property test |
| B02 | security: undo by path rejected; integration: legacy import with a foreign `root_path` refused |
| B03 | security: loopback bind, token, Host and Origin checks |
| B04 | security: arbitrary GET → 404; no `os.chdir` (assert cwd unchanged) |
| B05 | integration: `.app`, git project and `.photoslibrary` fixtures produce no Actions under `keep` |
| B06 | integration: symlink-to-root and loop fixtures; the scan stays inside the Root and terminates |
| B07 | integration: undo with a re-occupied original gives a conflict and both files survive |
| B08 | fault injection: crash mid-run, then a full rollback from the journal |
| B09 | integration: two consecutive runs; no OrganEyes artifact is ever planned |
| B10 | static: repo hygiene check |
| B11 | unit: hardlink pair is counted once in `total_size`, and `apparent_size` counts both |
| B12 | security: `GET /api/analyze` → 404 |
| B13 | integration: `serve` from an unrelated Root serves the UI |
| B14 | security: concurrent apply → 409; job state isolated per job |
| B15 | integration: a pre-existing empty `Documents/Keep/` survives undo; `--prune-empty-sources` is undone faithfully |
| B16 | platform: `Photo.JPG` + `photo.jpg` targets get deterministic suffixes; case-only rename succeeds on a case-insensitive FS |
| B17 | property: normalized stem never empty or dot-leading, ≤ 200 bytes, no reserved names; `my_module.py` unchanged |
| B18 | integration: deep tree gives a `skipped_depth` count and a CLI warning |
| B19 | unit: pattern matrix from [02 § 9](02-safety-and-security.md#9-protection-model) |
| B20–B25 | E2E (v0.4): counts reflect edits; connection-lost banner; result panel shows failures; group-old toggle sent; 5k-row plan renders under 100 ms per scroll frame; offline load works |
| B26 | integration: Ctrl+C during apply exits within 10 s with `run_end: cancelled`; immediate restart on the same port succeeds |
| B27 | security: malformed JSON or a bad `max_depth` → 400 envelope |
| B28 | unit: serialized plan and journal contain no `_id` |
| B29 | integration: scan job reports `phase` and a determinate `total` after walking |
| B30 | unit: each date source fixture resolves to the expected year and source; camera-default rejected |
| B31 | unit: mocked `SF_DATALESS` or `.icloud` stub → `skipped: PLACEHOLDER` |
| B32 | integration: relative symlink under `rewrite` still resolves after move and after undo |
| B33 | unit: library functions write nothing to stdout (capsys) |
| B34 | CLI: `--dry-run` prints the deprecation notice and summary, and creates no files |
| B35 | CLI: `apply --output r.json` writes the report; the plan is stored with the journal |

## 7. CI matrix

| Job | OS | Python | Extras |
|-----|----|--------|--------|
| core | ubuntu, macos, windows | 3.9, 3.11, 3.13 | none |
| extras | ubuntu, macos | 3.12 | `[all]` (ffprobe installed on ubuntu) |
| security | ubuntu | 3.12 | none |
| e2e (v0.4+) | ubuntu | 3.12 | none + Playwright |
| lint/type/hygiene | ubuntu | 3.12 | dev |

The macOS runner covers the case-insensitive APFS and `st_birthtime` paths. On Linux, a case-insensitive volume is simulated with a tmpfs `casefold` mount if available; otherwise those tests are skipped.
