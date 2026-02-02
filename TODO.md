# 📋 TODO

## High Priority

- [ ] **Add progress bar to CLI script**
  - Show progress during file scanning (e.g., `Scanning... [=====>    ] 50%`)
  - Show progress during file moves (e.g., `Moving files... [12/50]`)
  - Display ETA for large operations

- [ ] **Add progress bar to Web GUI**
  - Visual progress indicator during analysis
  - Real-time progress bar during file moves
  - Show current file being processed

- [ ] **Fix file size calculation bug**
  - BUG: Total size shows impossible values (e.g., 2TB on 256GB drive)
  - Avoid counting same file multiple times (symlinks, hard links)
  - Skip counting symlinks or resolve them properly
  - Validate total size against drive capacity
  - Handle sparse files correctly
  - Add sanity check: warn if total exceeds drive size

- [ ] **Debug and error handling improvements**
  - Add better error messages for permission denied
  - Handle special characters in filenames
  - Handle symlinks and aliases gracefully
  - Add logging option (`--verbose` or `--log`)
  - Test on external drives (SD cards, USB drives)
  - Test on network drives
  - Handle very long file paths
  - Add retry logic for locked files

## Medium Priority

- [ ] **Editable suggestions after dry run**
  - Allow user to review and edit move/rename suggestions before executing
  - Enable renaming suggested filenames inline
  - Allow deleting/skipping individual file moves
  - Add checkboxes to select which files to move
  - Save edited plan for later execution
  - CLI: Export editable plan to JSON, re-import after editing
  - GUI: Inline editing in the suggestions list

## Future Enhancements

- [ ] **Year range grouping for old files**
  - Group years below threshold into single folder (e.g., "Pre-2000")
  - User-configurable cutoff year (`--group-before 2000`)
  - Support custom year ranges (e.g., "2010-2015", "2000-2009")
  - CLI flags: `--group-before YEAR` and `--year-range START-END`
  - GUI: Dropdown or input for year grouping options
  - Example structure:
    ```
    Documents/
    ├── 2024/
    ├── 2023/
    ├── 2010-2019/
    └── Pre-2000/
    ```

- [ ] Custom category rules (user-defined extensions)
- [ ] Date grouping options (by month, by quarter)
- [ ] Duplicate file detection
- [ ] File preview in GUI before moving
- [ ] Batch rename patterns (e.g., `photo_001.jpg`)
- [ ] Export move plan to CSV
- [ ] Dark mode for GUI
