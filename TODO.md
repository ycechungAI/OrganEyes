# TODO

## High Priority

- [x] **Add progress bar to CLI script** (v0.1)
  - Show progress during file scanning
  - Show progress during file moves
  - Display ETA for large operations

- [x] **Add progress bar to Web GUI** (v0.1)
  - Visual progress indicator during analysis
  - Real-time progress bar during file moves
  - Show current file being processed

- [ ] **Fix remaining file size summary bug**
  - ~~Symlink/hardlink deduplication~~ — done via `lstat()` + `seen_inodes`
  - BUG: `_build_report()` sums raw `f["size"]` instead of `effective_size`, inflating totals
  - Store `effective_size` in each `file_info` dict and use it for the summary total
  - Add sanity check: warn if total exceeds drive capacity (`shutil.disk_usage`)

- [ ] **Fix dead GET `/api/analyze` endpoint**
  - `_run_analysis()` at line 1029 is a no-op (`pass`)
  - Remove the method or wire it to the async thread flow

## Medium Priority

- [ ] **Editable suggestions in CLI (export/import)**
  - GUI already supports inline editing and checkboxes
  - Add `--export-plan plan.json` to save suggestions after analysis
  - Add `--import-plan plan.json` to load edited suggestions for execution

- [ ] **Add `--group-old` toggle to Web GUI**
  - CLI supports `--group-old` but the GUI has no toggle for it
  - `_run_analysis_thread` never passes `group_old_files` to `FileOrganizer`
  - Add checkbox in Settings section, pass value through to the analyzer

- [ ] **Fix HTML file serving path**
  - `_serve_html()` looks for `organizer_preview.html` in the target folder (`server_root`)
  - Should locate it relative to the script: `Path(__file__).parent / 'organizer_preview.html'`

- [ ] **Improve error reporting in GUI**
  - Show moved/failed/skipped breakdown after execution (not just generic success)
  - Display permission errors clearly in the UI
  - Data already exists in `TASK_STATUS["result"]` but frontend ignores it

## Future Enhancements

- [x] **Year range grouping for old files** (v0.1)
  - `--group-old` flag with decade grouping

- [x] **Interactive CLI mode for reviewing changes** (v0.1)
  - Menu to View/Skip/Rename files before execution
  - Filter view by category

- [ ] Custom category rules (user-defined extension mappings via config file)
- [ ] Date grouping options (by month, by quarter)
- [ ] Duplicate file detection (hash-based, report-only)
- [ ] File preview in GUI before moving
- [ ] Batch rename patterns (e.g., `photo_001.jpg`)
- [ ] Export move plan to CSV
- [ ] Dark mode for GUI
- [ ] Keyboard shortcuts in GUI (j/k navigation, space to toggle, enter to confirm)
