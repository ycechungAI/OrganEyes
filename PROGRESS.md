# Progress Log

## v0.1 - Initial Release

- [x] **Add progress bar to CLI script**
  - Show progress during file scanning
  - Show progress during file moves
  - Display ETA for large operations

- [x] **Add progress bar to Web GUI**
  - Visual progress indicator during analysis
  - Real-time progress bar during file moves
  - Show current file being processed

- [x] **Interactive CLI mode for reviewing changes**
  - Menu to View/Skip/Rename files before execution
  - Filter view by category

- [x] **Year range grouping for old files**
  - Group files older than 5 years into decades (e.g., "2010s")
  - CLI argument `--group-old`

- [x] **Editable suggestions in Web GUI**
  - Inline editing of suggested filenames
  - Checkboxes to select/deselect individual file moves
  - Search/filter within suggestion list

- [x] **Symlink and hardlink deduplication**
  - `lstat()` to detect symlinks (size zeroed)
  - Track seen inodes via `(st_dev, st_ino)` to skip hardlink duplicates
  - `effective_size` used in category stats

- [x] **Error handling improvements**
  - PermissionError caught during directory scanning
  - Retry logic (3 attempts, 0.5s backoff) for locked files during moves
  - `--verbose` flag for debug console logging
  - `--log FILE` flag for file-based logging

- [x] **ARIA accessibility labels for Web GUI**
  - Added `aria-label` attributes to icon-only buttons
