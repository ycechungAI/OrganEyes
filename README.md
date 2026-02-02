# 📂 Organ Eyes

A smart file organizer that automatically sorts your files into a clean **Category / Year** folder structure. Features both a command-line interface and a beginner-friendly web GUI.

## ✨ Features

- **Auto-categorization** - Sorts files by type (Documents, Images, Videos, Audio, Code, Archives)
- **Year-based grouping** - Organizes by file modification year
- **Protected folders** - Mark folders as "hands off" so they won't be touched
- **Web GUI** - Easy-to-use browser interface for non-technical users
- **Undo support** - Rollback any changes with one click
- **Preview mode** - See what will happen before committing
- **No dependencies** - Uses only Python standard library

## 📁 Folder Structure

Files are organized into a clean 3-tier structure:

```
Your Folder/
├── Documents/
│   ├── 2024/
│   │   ├── report.pdf
│   │   └── notes.docx
│   └── 2023/
│       └── budget.xlsx
├── Images/
│   └── 2024/
│       └── photo.jpg
├── Videos/
│   └── 2024/
│       └── clip.mp4
└── ...
```

## 🚀 Quick Start

### Option 1: Web GUI (Recommended for beginners)

```bash
python3 file_organizer.py --server
```

This opens a friendly web interface in your browser where you can:
1. Set scan depth and protected folders
2. Click "Analyze" to preview changes
3. Filter by category or year
4. Click "Move Files" to organize
5. Undo any changes with one click

### Option 2: Command Line

**Preview what will happen:**
```bash
python3 file_organizer.py ~/Downloads --dry-run
```

**Execute the organization:**
```bash
python3 file_organizer.py ~/Downloads --execute
```

## 📖 Usage Examples

### Basic Commands

```bash
# Analyze current folder
python3 file_organizer.py .

# Analyze specific folder
python3 file_organizer.py ~/Downloads

# Preview only (no JSON output)
python3 file_organizer.py ~/Documents --dry-run

# Save report to file
python3 file_organizer.py . --output report.json
```

### Protected Folders

Protect folders from being reorganized:

```bash
# Protect a top-level folder
python3 file_organizer.py . --exclude "Work Projects"

# Protect a nested folder (tier 2)
python3 file_organizer.py . --exclude "Personal/Private"

# Multiple protected folders
python3 file_organizer.py . --exclude "Church" --exclude "Important" --exclude "Clients"
```

### Execute Mode

Actually move files (creates a rollback file):

```bash
# Move all files
python3 file_organizer.py ~/Downloads --execute

# Move only Documents
python3 file_organizer.py . --execute --category Documents

# Move only files from 2024
python3 file_organizer.py . --execute --year 2024

# Move Documents from 2024 only
python3 file_organizer.py . --execute --category Documents --year 2024

# Skip confirmation prompt (use with caution!)
python3 file_organizer.py . --execute --no-confirm
```

### Undo Changes

Rollback files are automatically created when you execute moves:

```bash
# Undo using the rollback file
python3 file_organizer.py --undo organizer_rollback_20240215_143022.json
```

### Web GUI Options

```bash
# Start GUI on default port (8765)
python3 file_organizer.py --server

# Start GUI for a specific folder
python3 file_organizer.py ~/Downloads --server

# Use a different port
python3 file_organizer.py --server --port 8080

# Don't auto-open browser
python3 file_organizer.py --server --no-browser
```

## 📂 File Categories

| Category | File Extensions |
|----------|----------------|
| 📄 Documents | pdf, doc, docx, txt, rtf, xls, xlsx, ppt, pptx, csv, md, epub, mobi |
| 🖼️ Images | jpg, jpeg, png, gif, bmp, svg, webp, tiff, ico, heic, psd |
| 🎬 Videos | mp4, avi, mkv, mov, wmv, flv, webm, m4v, mpeg |
| 🎵 Audio | mp3, wav, flac, aac, ogg, wma, m4a, aiff |
| 💻 Code | py, js, ts, html, css, java, c, cpp, go, rs, rb, php, json, xml, yaml |
| 📦 Archives | zip, rar, 7z, tar, gz, bz2, iso, dmg |
| 📁 Other | Everything else |

## 🔒 Default Protected Folders

These folders are automatically protected (never touched):

- Hidden folders (starting with `.`)
- System folders: Library, Applications, node_modules
- Config folders: .git, .vscode, .config, .cache
- Environment folders: venv, .env, .npm, .nvm

## ⚙️ Command Reference

```
usage: file_organizer.py [-h] [-e EXCLUDE] [-o OUTPUT] [-d DEPTH] [--dry-run]
                         [--execute] [--category CATEGORY] [--year YEAR]
                         [--no-confirm] [--undo ROLLBACK_FILE] [--server]
                         [--port PORT] [--no-browser]
                         [path]

Options:
  path                  Folder to analyze (default: current directory)
  -e, --exclude         Folders to protect (can use multiple times)
  -o, --output          Save report to JSON file
  -d, --depth           Max folder depth to scan (default: 10)
  --dry-run             Show summary only, no full report
  --execute             Actually move the files
  --category            Filter by category (use with --execute)
  --year                Filter by year (use with --execute)
  --no-confirm          Skip confirmation prompt
  --undo                Undo moves from a rollback file
  --server              Start web GUI
  --port                Web server port (default: 8765)
  --no-browser          Don't auto-open browser
```

## 🛡️ Safety Features

1. **Preview first** - Always shows what will happen before moving
2. **Confirmation prompt** - Requires typing "yes" before executing
3. **Rollback files** - Every execution creates an undo file
4. **No overwrites** - Adds (1), (2) suffix if target exists
5. **No deletions** - Files are only moved, never deleted
6. **Protected folders** - Mark important folders as untouchable

## 📋 Requirements

- Python 3.7+
- No external dependencies (uses only standard library)
- Web browser (for GUI mode)

## 🤝 Tips

1. **Start small** - Test on a single category first: `--execute --category Documents`
2. **Use dry-run** - Always preview with `--dry-run` before executing
3. **Protect important folders** - Use `--exclude` for folders you don't want touched
4. **Keep rollback files** - Don't delete them until you're sure everything is correct
5. **Use the GUI** - If you're unsure, the web interface is safer and easier

## 📄 License

MIT License - Feel free to use, modify, and distribute.
