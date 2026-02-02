#!/usr/bin/env python3
"""
File Organizer - Auto-organization prototype
Analyzes a folder and suggests a clean 3-tier structure by type and year.
Supports protected folders that won't be touched.

Usage:
    python file_organizer.py [folder_path] [--exclude "Folder Name" ...]
    python file_organizer.py --output report.json
    python file_organizer.py --dry-run
    python file_organizer.py --execute              # Actually perform moves
    python file_organizer.py --undo rollback.json   # Undo previous execution
    python file_organizer.py --server               # Start web GUI server
"""

import os
import sys
import time
import json
import logging
import re
import shutil
import argparse
import webbrowser
import threading
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import socketserver

# ============================================================================
# FILE TYPE CATEGORIES
# ============================================================================

FILE_CATEGORIES = {
    "Documents": {
        "extensions": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls",
                      ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".epub", ".mobi"],
        "icon": "📄"
    },
    "Images": {
        "extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
                      ".tiff", ".ico", ".heic", ".raw", ".psd", ".ai"],
        "icon": "🖼️"
    },
    "Videos": {
        "extensions": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
                      ".m4v", ".mpeg", ".mpg", ".3gp"],
        "icon": "🎬"
    },
    "Audio": {
        "extensions": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
                      ".aiff", ".opus"],
        "icon": "🎵"
    },
    "Code": {
        "extensions": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
                      ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php",
                      ".swift", ".kt", ".scala", ".sh", ".bash", ".zsh", ".sql",
                      ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        "icon": "💻"
    },
    "Archives": {
        "extensions": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                      ".iso", ".dmg"],
        "icon": "📦"
    },
    "Other": {
        "extensions": [],  # Catch-all
        "icon": "📁"
    }
}

# Build reverse lookup: extension -> category
EXTENSION_TO_CATEGORY = {}
for category, info in FILE_CATEGORIES.items():
    for ext in info["extensions"]:
        EXTENSION_TO_CATEGORY[ext.lower()] = category

# ============================================================================
# DEFAULT PROTECTED FOLDERS (system/config folders)
# ============================================================================

DEFAULT_PROTECTED = {
    # Hidden/system folders
    ".git", ".svn", ".hg",
    ".vscode", ".idea", ".eclipse",
    ".npm", ".nvm", ".bun", ".yarn",
    ".pyenv", ".conda", ".virtualenv",
    ".config", ".local", ".cache",
    ".ssh", ".gnupg",
    ".Trash", ".DS_Store",
    "node_modules", "__pycache__", ".pytest_cache",
    "venv", "env", ".env",
    # Common app folders
    "Library", "Applications",
    ".claude", ".gemini", ".ollama",
    ".oh-my-zsh", ".zsh_sessions",
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_file_category(filepath: Path) -> str:
    """Determine the category of a file based on its extension."""
    ext = filepath.suffix.lower()
    return EXTENSION_TO_CATEGORY.get(ext, "Other")

def get_file_year(filepath: Path) -> str:
    """Get the year from file's modification time."""
    try:
        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y")
    except (OSError, ValueError):
        return "Unknown"

def clean_filename(filename: str) -> str:
    """Suggest a cleaner filename."""
    name, ext = os.path.splitext(filename)

    # Remove leading/trailing spaces and dots
    name = name.strip(" .")

    # Replace multiple spaces/underscores with single space
    name = re.sub(r'[\s_]+', ' ', name)

    # Remove or replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)

    # Trim if too long (keep under 100 chars)
    if len(name) > 100:
        name = name[:97] + "..."

    return name + ext

def should_skip_folder(folder_name: str, protected_folders: Set[str]) -> bool:
    """Check if a folder should be skipped (protected or system)."""
    # Skip hidden folders by default
    if folder_name.startswith('.'):
        return True
    # Skip if in protected list
    if folder_name in protected_folders:
        return True
    return False

def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    """Call in a loop to create terminal progress bar"""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')

def setup_logging(verbose: bool = False, log_file: str = None):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    handlers = []
    
    # Console handler (only warnings/errors unless verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level if verbose else logging.WARNING)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    handlers.append(console_handler)
    
    # File handler (always debug if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        handlers.append(file_handler)
        
    logging.basicConfig(level=logging.DEBUG if log_file else level, handlers=handlers, force=True)

# Global task status for Web GUI
TASK_STATUS = {
    "status": "idle",
    "operation": None,
    "progress": 0,
    "total": 0,
    "current": 0,
    "message": "",
    "error": None
}

def update_task_status(op, current, total, msg, status="running"):
    TASK_STATUS.update({
        "status": status,
        "operation": op,
        "current": current,
        "total": total,
        "progress": int((current / total) * 100) if total > 0 else 0,
        "message": msg
    })

# ============================================================================
# MAIN ANALYZER CLASS
# ============================================================================

class FileOrganizer:
    def __init__(self, root_path: str, protected_folders: Optional[List[str]] = None, group_old_files: bool = False):
        self.root_path = Path(root_path).resolve()
        self.protected_folders: Set[str] = set(protected_folders or [])
        self.protected_folders.update(DEFAULT_PROTECTED)

        # Results
        self.files_analyzed: List[Dict] = []
        self.suggestions: List[Dict] = []
        self.category_stats: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "size": 0})
        self.year_stats: Dict[str, int] = defaultdict(int)
        self.protected_found: List[str] = []
        self.seen_inodes: Set[Tuple[int, int]] = set()
        self.group_old_files = group_old_files

    def analyze(self, max_depth: int = 10, progress_callback=None) -> Dict:
        """Analyze the folder and generate organization suggestions."""
        self.progress_callback = progress_callback
        print(f"🔍 Analyzing: {self.root_path}")
        print(f"🔒 Protected folders: {len(self.protected_folders)}")

        self._scan_directory(self.root_path, depth=0, max_depth=max_depth)
        print()  # Newline after scanning progress
        self._generate_suggestions()

        return self._build_report()

    def _scan_directory(self, path: Path, depth: int, max_depth: int, rel_prefix: str = ""):
        """Recursively scan directory for files."""
        if depth > max_depth:
            return

        try:
            entries = list(path.iterdir())
        except PermissionError:
            logging.warning(f"Permission denied: {path}")
            return
        except OSError as e:
            logging.error(f"Error reading directory {path}: {e}")
            return

        for entry in entries:
            rel_path = os.path.join(rel_prefix, entry.name) if rel_prefix else entry.name

            try:
                is_dir = entry.is_dir()
            except (PermissionError, OSError):
                continue  # Skip entries we can't access

            if is_dir:
                # Check if this folder is protected
                folder_name = entry.name

                # Check tier 1 protection (top-level)
                if depth == 0 and folder_name in self.protected_folders:
                    self.protected_found.append(rel_path)
                    continue

                # Check tier 2 protection (second-level, format: "Parent/Child")
                if depth == 1:
                    parent_name = path.name
                    full_tier2_name = f"{parent_name}/{folder_name}"
                    if full_tier2_name in self.protected_folders:
                        self.protected_found.append(rel_path)
                        continue

                # Skip system/hidden folders
                if should_skip_folder(folder_name, self.protected_folders):
                    continue

                # Recurse into subdirectory
                self._scan_directory(entry, depth + 1, max_depth, rel_path)

            elif not is_dir:  # It's a file
                # Skip hidden files
                if entry.name.startswith('.'):
                    continue

                self._analyze_file(entry, rel_path)

    def _analyze_file(self, filepath: Path, rel_path: str):
        """Analyze a single file."""
        try:
            # Use lstat to check for symlinks and ignore their "target" size
            stat = filepath.lstat()
            is_symlink = filepath.is_symlink()
            
            if is_symlink:
                # Symlinks take negligible space, avoid double counting target
                size = 0
                effective_size = 0
            else:
                size = stat.st_size
                
                # Check for hard links to avoid double counting
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key in self.seen_inodes:
                    effective_size = 0
                else:
                    self.seen_inodes.add(inode_key)
                    effective_size = size
                    
        except OSError:
            size = 0
            effective_size = 0
            is_symlink = False

        category = get_file_category(filepath)
        year = get_file_year(filepath)
        
        # Group old files by decade if requested
        if self.group_old_files and year != "Unknown":
            try:
                y_int = int(year)
                current_year = datetime.now().year
                if current_year - y_int >= 5: # Group files older than 5 years
                    decade = (y_int // 10) * 10
                    year = f"{decade}s"
            except ValueError:
                pass

        file_info = {
            "name": filepath.name,
            "path": str(filepath),
            "rel_path": rel_path,
            "category": category,
            "year": year,
            "size": size,
            "size_formatted": format_size(size),
            "extension": filepath.suffix.lower(),
            "is_symlink": is_symlink
        }

        self.files_analyzed.append(file_info)
        self.category_stats[category]["count"] += 1
        self.category_stats[category]["size"] += effective_size
        self.year_stats[year] += 1
        
        # Show scanning progress
        count = len(self.files_analyzed)
        if count % 10 == 0:  # Update every 10 files to avoid flicker/slowdown
            sys.stdout.write(f"\rScanning... {count} files found")
            sys.stdout.flush()
            
        if self.progress_callback and count % 5 == 0:
            self.progress_callback(count, 0, f"Scanning: {filepath.name}")

    def _generate_suggestions(self):
        """Generate move/rename suggestions for each file."""
        for file_info in self.files_analyzed:
            category = file_info["category"]
            year = file_info["year"]
            original_name = file_info["name"]

            # Proposed new structure: Category/Year/filename
            new_rel_path = f"{category}/{year}/{original_name}"

            # Check if rename is suggested
            cleaned_name = clean_filename(original_name)
            rename_suggested = cleaned_name != original_name

            if rename_suggested:
                new_rel_path = f"{category}/{year}/{cleaned_name}"

            suggestion = {
                "original_path": file_info["rel_path"],
                "original_name": original_name,
                "suggested_path": new_rel_path,
                "suggested_name": cleaned_name if rename_suggested else original_name,
                "category": category,
                "year": year,
                "size": file_info["size"],
                "size_formatted": file_info["size_formatted"],
                "rename_suggested": rename_suggested,
                "move_required": file_info["rel_path"] != new_rel_path,
            }

            self.suggestions.append(suggestion)

    def _build_report(self) -> Dict:
        """Build the final report."""
        # Sort suggestions by category, then year
        self.suggestions.sort(key=lambda x: (x["category"], x["year"], x["original_name"]))

        # Build proposed structure tree
        proposed_structure = self._build_proposed_tree()

        # Category summary with icons
        category_summary = {}
        for cat, stats in self.category_stats.items():
            category_summary[cat] = {
                "count": stats["count"],
                "size": stats["size"],
                "size_formatted": format_size(stats["size"]),
                "icon": FILE_CATEGORIES.get(cat, {}).get("icon", "📁")
            }

        report = {
            "root_path": str(self.root_path),
            "scan_time": datetime.now().isoformat(),
            "summary": {
                "total_files": len(self.files_analyzed),
                "total_size": sum(f["size"] for f in self.files_analyzed),
                "total_size_formatted": format_size(sum(f["size"] for f in self.files_analyzed)),
                "categories_found": len(self.category_stats),
                "years_found": len(self.year_stats),
                "moves_suggested": sum(1 for s in self.suggestions if s["move_required"]),
                "renames_suggested": sum(1 for s in self.suggestions if s["rename_suggested"]),
            },
            "protected_folders": list(self.protected_folders),
            "protected_folders_found": self.protected_found,
            "category_stats": category_summary,
            "year_stats": dict(sorted(self.year_stats.items())),
            "proposed_structure": proposed_structure,
            "suggestions": self.suggestions,
        }

        return report

    def _build_proposed_tree(self) -> Dict:
        """Build a tree representation of the proposed structure."""
        tree = {}

        for suggestion in self.suggestions:
            category = suggestion["category"]
            year = suggestion["year"]
            filename = suggestion["suggested_name"]

            if category not in tree:
                tree[category] = {"icon": FILE_CATEGORIES.get(category, {}).get("icon", "📁"), "years": {}}

            if year not in tree[category]["years"]:
                tree[category]["years"][year] = []

            tree[category]["years"][year].append({
                "name": filename,
                "original": suggestion["original_path"],
                "size": suggestion["size_formatted"]
            })

        return tree


# ============================================================================
# FILE EXECUTOR CLASS - Actually performs the moves
# ============================================================================

class FileExecutor:
    """Executes file organization with safety features and rollback support."""

    def __init__(self, root_path: Path, suggestions: List[Dict]):
        self.root_path = root_path
        self.suggestions = suggestions
        self.executed_moves: List[Dict] = []
        self.failed_moves: List[Dict] = []
        self.skipped_moves: List[Dict] = []

    def execute(self, confirm: bool = True, category_filter: str = None,
                year_filter: str = None, progress_callback=None) -> Dict:
        """
        Execute the suggested moves.

        Args:
            confirm: If True, ask for confirmation before each batch
            category_filter: Only move files in this category
            year_filter: Only move files from this year

        Returns:
            Execution report with success/failure counts
        """
        # Filter suggestions if needed
        to_execute = self.suggestions
        if category_filter:
            to_execute = [s for s in to_execute if s["category"] == category_filter]
        if year_filter:
            to_execute = [s for s in to_execute if s["year"] == year_filter]

        # Only process files that actually need moving
        to_execute = [s for s in to_execute if s["move_required"]]

        if not to_execute:
            print("⚠️  No files to move with current filters.")
            return {"executed": 0, "failed": 0, "skipped": 0}

        # Show summary and ask for confirmation
        print(f"\n{'='*60}")
        print("📋 EXECUTION PLAN")
        print(f"{'='*60}")
        print(f"📁 Root: {self.root_path}")
        print(f"📄 Files to move: {len(to_execute)}")
        print(f"💾 Total size: {format_size(sum(s['size'] for s in to_execute))}")

        # Show category breakdown
        cat_counts = defaultdict(int)
        for s in to_execute:
            cat_counts[s["category"]] += 1
        print("\n📂 By category:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            icon = FILE_CATEGORIES.get(cat, {}).get("icon", "📁")
            print(f"   {icon} {cat}: {count} files")

        # Show sample moves
        print("\n📝 Sample moves (first 5):")
        for s in to_execute[:5]:
            print(f"   {s['original_path']}")
            print(f"   → {s['suggested_path']}")
            print()

        if len(to_execute) > 5:
            print(f"   ... and {len(to_execute) - 5} more files\n")

        # Confirmation
        if confirm:
            print("⚠️  This will MOVE files to new locations.")
            print("   A rollback file will be created to undo changes.")
            response = input("\n🔑 Type 'yes' to proceed, anything else to cancel: ")
            if response.lower() != 'yes':
                print("❌ Cancelled by user.")
                return {"executed": 0, "failed": 0, "skipped": len(to_execute)}

        # Execute moves
        print(f"\n{'='*60}")
        print("🚀 EXECUTING MOVES")
        print(f"{'='*60}")

        start_time = time.time()
        total_moves = len(to_execute)

        for i, suggestion in enumerate(to_execute, 1):
            # Calculate ETA
            elapsed = time.time() - start_time
            if i > 1:
                avg_time = elapsed / (i - 1)
                remaining = total_moves - i
                eta = remaining * avg_time
                eta_str = f"ETA: {int(eta)}s"
            else:
                eta_str = "ETA: --"

            # Print progress bar
            short_name = (suggestion['original_name'][:15] + '..') if len(suggestion['original_name']) > 15 else suggestion['original_name']
            print_progress_bar(i, total_moves, prefix='Progress:', suffix=f'({i}/{total_moves}) {eta_str} {short_name}', length=30)
            
            if progress_callback:
                progress_callback(i, total_moves, f"Moving: {suggestion['original_name']}")
            
            self._execute_single_move(suggestion, i, total_moves)

        # Save rollback file
        rollback_file = self._save_rollback()

        # Print summary
        print(f"\n{'='*60}")
        print("✅ EXECUTION COMPLETE")
        print(f"{'='*60}")
        print(f"✓ Moved: {len(self.executed_moves)} files")
        print(f"✗ Failed: {len(self.failed_moves)} files")
        print(f"⊘ Skipped: {len(self.skipped_moves)} files")
        print(f"\n💾 Rollback file: {rollback_file}")
        print(f"   To undo: python file_organizer.py --undo {rollback_file}")

        return {
            "executed": len(self.executed_moves),
            "failed": len(self.failed_moves),
            "skipped": len(self.skipped_moves),
            "rollback_file": str(rollback_file)
        }

    def _execute_single_move(self, suggestion: Dict, index: int, total: int):
        """Execute a single file move."""
        original_abs = self.root_path / suggestion["original_path"]
        target_abs = self.root_path / suggestion["suggested_path"]

        # Check if source exists
        if not original_abs.exists():
            # Clear line to avoid messing up progress bar
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            print(f"⊘ SKIP (not found): {suggestion['original_path']}")
            self.skipped_moves.append({**suggestion, "reason": "source_not_found"})
            return

        # Check if target already exists
        if target_abs.exists():
            # Add number suffix to avoid overwrite
            target_abs = self._get_unique_path(target_abs)
            suggestion["final_path"] = str(target_abs.relative_to(self.root_path))

        # Create target directory if needed
        try:
            target_abs.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            print(f"✗ FAIL (can't create dir): {suggestion['original_path']}")
            self.failed_moves.append({**suggestion, "error": str(e)})
            return

        # Perform the move with retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                shutil.move(str(original_abs), str(target_abs))
                
                # Record for rollback
                self.executed_moves.append({
                    "original_path": suggestion["original_path"],
                    "new_path": str(target_abs.relative_to(self.root_path)),
                    "original_abs": str(original_abs),
                    "new_abs": str(target_abs),
                    "size": suggestion["size"],
                    "timestamp": datetime.now().isoformat()
                })
                break # Success, exit retry loop

            except OSError as e:
                # If it's the last attempt, fail
                if attempt == max_retries - 1:
                    sys.stdout.write('\r' + ' ' * 80 + '\r')
                    print(f"✗ FAIL: {suggestion['original_path']} - {e}")
                    logging.error(f"Failed to move {suggestion['original_path']}: {e}")
                    self.failed_moves.append({**suggestion, "error": str(e)})
                else:
                    # Wait and retry
                    logging.debug(f"Retry {attempt+1}/{max_retries} for {suggestion['original_path']} due to: {e}")
                    time.sleep(0.5)

    def interactive_review(self, category_filter: str = None, year_filter: str = None) -> bool:
        """Run an interactive CLI review session."""
        
        # Filter suggestions initially for display
        filtered = self.suggestions
        if category_filter:
            filtered = [s for s in filtered if s["category"] == category_filter]
        if year_filter:
            filtered = [s for s in filtered if s["year"] == year_filter]
            
        # Add temporary ID for interactive session
        for i, s in enumerate(filtered, 1):
            s["_id"] = i

        while True:
            # Count active moves
            to_move = [s for s in filtered if s["move_required"]]
            
            print(f"\n{'-'*60}")
            print(f"🤖 INTERACTIVE REVIEW MODE")
            print(f"{'-'*60}")
            print(f"Total files in scope: {len(filtered)}")
            print(f"Set to move: {len(to_move)}")
            print(f"Skipped: {len(filtered) - len(to_move)}")
            print(f"{'-'*60}")
            print("Commands:")
            print("  [l] List all files")
            print("  [c] List by Category")
            print("  [s <ID>] Skip/Unskip file (toggle)")
            print("  [r <ID> <NAME>] Rename file")
            print("  [run] Execute moves")
            print("  [q] Quit")
            
            choice = input("\nEnter command: ").strip().split()
            if not choice:
                continue
                
            cmd = choice[0].lower()
            
            if cmd == 'q':
                print("Aborted.")
                return False
                
            elif cmd == 'run':
                if not to_move:
                    print("No files to move!")
                    continue
                return True
                
            elif cmd == 'l':
                print("\n📄 FILES LIST:")
                for s in filtered:
                    status = "[x]" if s["move_required"] else "[ ]"
                    print(f"  {s['_id']}. {status} {s['original_name']} -> {s['category']}/{s['year']}/{s['suggested_name']}")
            
            elif cmd == 'c':
                cats = defaultdict(list)
                for s in filtered:
                    cats[s['category']].append(s)
                
                for cat, items in cats.items():
                    print(f"\n📁 {cat}:")
                    for s in items:
                        status = "[x]" if s["move_required"] else "[ ]"
                        print(f"  {s['_id']}. {status} {s['original_name']} -> {s['year']}/{s['suggested_name']}")

            elif cmd == 's':
                if len(choice) < 2:
                    print("Usage: s <ID>")
                    continue
                try:
                    idx = int(choice[1])
                    target = next((s for s in filtered if s["_id"] == idx), None)
                    if target:
                        target["move_required"] = not target["move_required"]
                        print(f"Toggled file #{idx}: {'Moving' if target['move_required'] else 'Skipped'}")
                    else:
                        print("Invalid ID")
                except ValueError:
                    print("Invalid ID number")

            elif cmd == 'r':
                if len(choice) < 3:
                    print("Usage: r <ID> <NEW_NAME>")
                    continue
                try:
                    idx = int(choice[1])
                    new_name = " ".join(choice[2:])
                    target = next((s for s in filtered if s["_id"] == idx), None)
                    if target:
                        target["suggested_name"] = new_name
                        target["suggested_path"] = f"{target['category']}/{target['year']}/{new_name}"
                        target["rename_suggested"] = True
                        print(f"Renamed file #{idx} to: {new_name}")
                    else:
                        print("Invalid ID")
                except ValueError:
                    print("Invalid ID number")
            
            else:
                print("Unknown command")

    def _get_unique_path(self, path: Path) -> Path:
        """Get a unique path by adding a number suffix if file exists."""
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

    def _save_rollback(self) -> Path:
        """Save rollback information to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rollback_file = self.root_path / f"organizer_rollback_{timestamp}.json"

        rollback_data = {
            "created": datetime.now().isoformat(),
            "root_path": str(self.root_path),
            "total_moves": len(self.executed_moves),
            "moves": self.executed_moves,
            "failed": self.failed_moves,
            "skipped": self.skipped_moves
        }

        with open(rollback_file, 'w', encoding='utf-8') as f:
            json.dump(rollback_data, f, indent=2, ensure_ascii=False)

        return rollback_file


def undo_moves(rollback_file: str) -> Dict:
    """Undo moves from a rollback file."""
    rollback_path = Path(rollback_file)

    if not rollback_path.exists():
        print(f"❌ Rollback file not found: {rollback_file}")
        return {"success": False, "error": "file_not_found"}

    with open(rollback_path, 'r', encoding='utf-8') as f:
        rollback_data = json.load(f)

    moves = rollback_data.get("moves", [])
    root_path = Path(rollback_data.get("root_path", "."))

    if not moves:
        print("⚠️  No moves to undo in this rollback file.")
        return {"success": True, "undone": 0}

    print(f"\n{'='*60}")
    print("🔄 UNDO OPERATION")
    print(f"{'='*60}")
    print(f"📁 Root: {root_path}")
    print(f"📄 Moves to undo: {len(moves)}")
    print(f"📅 Original execution: {rollback_data.get('created', 'unknown')}")

    # Confirmation
    response = input("\n🔑 Type 'yes' to undo all moves: ")
    if response.lower() != 'yes':
        print("❌ Cancelled by user.")
        return {"success": False, "error": "cancelled"}

    # Undo in reverse order
    undone = 0
    failed = 0

    for move in reversed(moves):
        new_abs = Path(move["new_abs"])
        original_abs = Path(move["original_abs"])

        if not new_abs.exists():
            print(f"⊘ SKIP (already moved): {move['new_path']}")
            continue

        try:
            # Recreate original directory if needed
            original_abs.parent.mkdir(parents=True, exist_ok=True)

            # Move back
            shutil.move(str(new_abs), str(original_abs))
            print(f"✓ {move['new_path']} → {move['original_path']}")
            undone += 1

        except OSError as e:
            print(f"✗ FAIL: {move['new_path']} - {e}")
            failed += 1

    # Clean up empty directories
    print("\n🧹 Cleaning up empty directories...")
    _cleanup_empty_dirs(root_path)

    print(f"\n{'='*60}")
    print("✅ UNDO COMPLETE")
    print(f"{'='*60}")
    print(f"✓ Undone: {undone} moves")
    print(f"✗ Failed: {failed} moves")

    return {"success": True, "undone": undone, "failed": failed}


def _cleanup_empty_dirs(root_path: Path):
    """Remove empty directories created during organization."""
    # Categories that might have been created
    categories = list(FILE_CATEGORIES.keys())

    for category in categories:
        cat_path = root_path / category
        if cat_path.exists() and cat_path.is_dir():
            try:
                # Walk bottom-up to remove empty dirs
                for dirpath, dirnames, filenames in os.walk(str(cat_path), topdown=False):
                    dir_path = Path(dirpath)
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        print(f"   Removed empty: {dir_path.relative_to(root_path)}")
            except OSError:
                pass


# ============================================================================
# WEB SERVER FOR GUI
# ============================================================================

class OrganizerAPIHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the web GUI API."""

    # Class-level state
    server_root = None
    protected_folders = []
    current_report = None

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # API endpoints
        if path == '/api/status':
            self._send_json({
                "status": "running",
                "root_path": str(OrganizerAPIHandler.server_root),
                "protected_folders": OrganizerAPIHandler.protected_folders
            })
        elif path == '/api/analyze':
            self._handle_analyze(parse_qs(parsed.query))
        elif path == '/api/folders':
            self._handle_list_folders()
        elif path == '/api/rollbacks':
            self._handle_list_rollbacks()
        elif path == '/api/progress':
            self._send_json(TASK_STATUS)
        elif path == '/api/report':
            if OrganizerAPIHandler.current_report:
                self._send_json(OrganizerAPIHandler.current_report)
            else:
                self._send_json({"error": "No report available"}, 404)
        elif path == '/':
            # Serve the HTML file
            self._serve_html()
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Read POST body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == '/api/analyze':
            self._handle_analyze_post(data)
        elif path == '/api/execute':
            self._handle_execute(data)
        elif path == '/api/undo':
            self._handle_undo(data)
        elif path == '/api/protected':
            self._handle_update_protected(data)
        else:
            self._send_json({"error": "Unknown endpoint"}, 404)

    def _send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _serve_html(self):
        """Serve the main HTML interface."""
        html_path = OrganizerAPIHandler.server_root / 'organizer_preview.html'
        if html_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(html_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self._send_json({"error": "HTML file not found"}, 404)

    def _handle_list_folders(self):
        """List top-level folders in root path."""
        try:
            folders = []
            for entry in OrganizerAPIHandler.server_root.iterdir():
                if entry.is_dir() and not entry.name.startswith('.'):
                    folders.append(entry.name)
            self._send_json({"folders": sorted(folders)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_list_rollbacks(self):
        """List available rollback files."""
        try:
            rollbacks = []
            for f in OrganizerAPIHandler.server_root.glob('organizer_rollback_*.json'):
                stat = f.stat()
                rollbacks.append({
                    "name": f.name,
                    "path": str(f),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
            rollbacks.sort(key=lambda x: x["created"], reverse=True)
            self._send_json({"rollbacks": rollbacks})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_analyze(self, params):
        """Handle analyze GET request."""
        depth = int(params.get('depth', [3])[0])
        self._run_analysis(depth)

    def _handle_analyze_post(self, data):
        """Handle analyze POST request (Async)."""
        depth = data.get('depth', 3)
        protected = data.get('protected_folders', [])
        OrganizerAPIHandler.protected_folders = protected
        
        # Set status synchronously to avoid race condition with polling
        update_task_status("analyze", 0, 0, "Starting analysis...", status="running")
        threading.Thread(target=self._run_analysis_thread, args=(depth, protected)).start()
        self._send_json({"status": "analyzing"})

    def _run_analysis_thread(self, depth, protected):
        """Run analysis in a separate thread."""
        try:
            if protected is None:
                protected = OrganizerAPIHandler.protected_folders

            organizer = FileOrganizer(
                str(OrganizerAPIHandler.server_root),
                protected_folders=protected
            )
            
            def progress(c, t, m):
                update_task_status("analyze", c, t, m)
                
            report = organizer.analyze(max_depth=depth, progress_callback=progress)
            OrganizerAPIHandler.current_report = report
            update_task_status("analyze", 0, 0, "Analysis complete", status="complete")
        except Exception as e:
            update_task_status("analyze", 0, 0, str(e), status="error")
            TASK_STATUS["error"] = str(e)

    def _run_analysis(self, depth=3, protected=None):
        """Legacy synchronous analysis (kept for GET compatibility if needed, though broken now by threaded model)"""
        # For now, redirect to thread but block? No, simpler to just leave it or deprecate.
        pass

    def _handle_execute(self, data):
        """Handle execute request (Async)."""
        if not OrganizerAPIHandler.current_report:
            self._send_json({"error": "No analysis report. Run analyze first."}, 400)
            return

        # Set status synchronously
        update_task_status("execute", 0, 0, "Preparing to move...", status="running")
        threading.Thread(target=self._run_execute_thread, args=(data,)).start()
        self._send_json({"status": "executing"})

    def _run_execute_thread(self, data):
        """Run execution in a separate thread."""
        try:
            category_filter = data.get('category')
            year_filter = data.get('year')
            custom_suggestions = data.get('suggestions')
            
            # Use custom suggestions if provided (editable mode), otherwise default to report
            if custom_suggestions:
                suggestions_to_use = custom_suggestions
                # If custom suggestions are passed, we assume filtering is already done or irrelevant, 
                # but we can still apply filters if strictness is needed. 
                # For now, let's treat custom_suggestions as the final list to execute (except for validation).
            else:
                suggestions_to_use = OrganizerAPIHandler.current_report["suggestions"]

            executor = FileExecutor(
                OrganizerAPIHandler.server_root,
                suggestions_to_use
            )

            def progress(c, t, m):
                update_task_status("execute", c, t, m)

            # Execute without terminal confirmation
            result = executor.execute(
                confirm=False,
                category_filter=category_filter,
                year_filter=year_filter,
                progress_callback=progress
            )
            
            # We could store result in TASK_STATUS if needed
            TASK_STATUS["result"] = result
            update_task_status("execute", 0, 0, "Execution complete", status="complete")
            
        except Exception as e:
            update_task_status("execute", 0, 0, str(e), status="error")
            TASK_STATUS["error"] = str(e)

    def _handle_undo(self, data):
        """Handle undo request."""
        try:
            rollback_file = data.get('rollback_file')
            if not rollback_file:
                self._send_json({"error": "No rollback file specified"}, 400)
                return

            rollback_path = Path(rollback_file)
            if not rollback_path.is_absolute():
                rollback_path = OrganizerAPIHandler.server_root / rollback_file

            if not rollback_path.exists():
                self._send_json({"error": f"Rollback file not found: {rollback_file}"}, 404)
                return

            # Load rollback data
            with open(rollback_path, 'r', encoding='utf-8') as f:
                rollback_data = json.load(f)

            moves = rollback_data.get("moves", [])
            root_path = Path(rollback_data.get("root_path", "."))

            undone = 0
            failed = 0
            errors = []

            for move in reversed(moves):
                new_abs = Path(move["new_abs"])
                original_abs = Path(move["original_abs"])

                if not new_abs.exists():
                    continue

                try:
                    original_abs.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(new_abs), str(original_abs))
                    undone += 1
                except OSError as e:
                    failed += 1
                    errors.append(str(e))

            # Clean up empty directories
            _cleanup_empty_dirs(root_path)

            self._send_json({
                "success": True,
                "undone": undone,
                "failed": failed,
                "errors": errors[:5]  # Limit error messages
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_update_protected(self, data):
        """Update protected folders list."""
        OrganizerAPIHandler.protected_folders = data.get('folders', [])
        self._send_json({"success": True, "protected_folders": OrganizerAPIHandler.protected_folders})

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_server(root_path: Path, port: int = 8765, open_browser: bool = True):
    """Start the web server for the GUI."""
    OrganizerAPIHandler.server_root = root_path

    # Change to root directory for serving files
    os.chdir(root_path)

    with socketserver.TCPServer(("", port), OrganizerAPIHandler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\n{'='*60}")
        print("🌐 FILE ORGANIZER WEB GUI")
        print(f"{'='*60}")
        print(f"📁 Root folder: {root_path}")
        print(f"🔗 Open in browser: {url}")
        print(f"\n   Press Ctrl+C to stop the server")
        print(f"{'='*60}\n")

        if open_browser:
            # Open browser after a short delay
            def open_delayed():
                import time
                time.sleep(0.5)
                webbrowser.open(url)
            threading.Thread(target=open_delayed, daemon=True).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped.")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="File Organizer - Analyze and suggest folder organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python file_organizer.py ~/Downloads
  python file_organizer.py ~/Documents --exclude "Work Projects" --exclude "Personal/Private"
  python file_organizer.py . --output report.json

Web GUI (recommended for beginners):
  python file_organizer.py --server
  python file_organizer.py ~/Downloads --server --port 8080

Execute mode (actually move files):
  python file_organizer.py ~/Downloads --execute
  python file_organizer.py . --execute --category Documents
  python file_organizer.py . --execute --year 2024 --no-confirm

Undo previous execution:
  python file_organizer.py --undo organizer_rollback_20240115_143022.json
        """
    )

    parser.add_argument("path", nargs="?", default=".",
                       help="Folder to analyze (default: current directory)")
    parser.add_argument("-e", "--exclude", action="append", default=[],
                       help="Folders to protect/exclude (can be used multiple times)")
    parser.add_argument("-o", "--output", default=None,
                       help="Output JSON file for the report")
    parser.add_argument("-d", "--depth", type=int, default=10,
                       help="Maximum depth to scan (default: 10)")
    parser.add_argument("--group-old", action="store_true",
                       help="Group files older than 5 years into decades (e.g. 2010s)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Just show summary, don't output full report")

    # Execute mode arguments
    parser.add_argument("--execute", action="store_true",
                       help="Actually perform the suggested moves")
    parser.add_argument("--category", default=None,
                       help="Only move files in this category (use with --execute)")
    parser.add_argument("--year", default=None,
                       help="Only move files from this year (use with --execute)")
    parser.add_argument("--no-confirm", action="store_true",
                       help="Skip confirmation prompt (use with caution!)")
    parser.add_argument("-i", "--interactive", action="store_true",
                       help="Review changes interactively before execution")

    # Undo mode
    parser.add_argument("--undo", default=None, metavar="ROLLBACK_FILE",
                       help="Undo moves from a rollback JSON file")

    # Web server mode
    parser.add_argument("--server", action="store_true",
                       help="Start web GUI server (recommended for beginners)")
    parser.add_argument("--port", type=int, default=8765,
                       help="Port for web server (default: 8765)")
    parser.add_argument("--no-browser", action="store_true",
                       help="Don't auto-open browser when starting server")

    # Logging options
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--log", default=None, metavar="LOG_FILE",
                       help="Save log to file")

    args = parser.parse_args()
    
    setup_logging(args.verbose, args.log)

    # Handle undo mode
    if args.undo:
        result = undo_moves(args.undo)
        sys.exit(0 if result.get("success") else 1)

    # Handle server mode
    if args.server:
        root_path = Path(args.path).resolve()
        start_server(root_path, port=args.port, open_browser=not args.no_browser)
        sys.exit(0)

    # Run analyzer
    organizer = FileOrganizer(args.path, protected_folders=args.exclude, group_old_files=args.group_old)
    report = organizer.analyze(max_depth=args.depth)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"📁 Root: {report['root_path']}")
    print(f"📄 Total files: {report['summary']['total_files']}")
    print(f"💾 Total size: {report['summary']['total_size_formatted']}")
    print(f"📂 Categories: {report['summary']['categories_found']}")
    print(f"📅 Years: {report['summary']['years_found']}")
    print(f"➡️  Moves suggested: {report['summary']['moves_suggested']}")
    print(f"✏️  Renames suggested: {report['summary']['renames_suggested']}")

    print("\n📂 FILES BY CATEGORY:")
    for cat, stats in sorted(report['category_stats'].items(), key=lambda x: -x[1]['count']):
        print(f"   {stats['icon']} {cat}: {stats['count']} files ({stats['size_formatted']})")

    print("\n📅 FILES BY YEAR:")
    for year, count in sorted(report['year_stats'].items(), reverse=True):
        print(f"   {year}: {count} files")

    if report['protected_folders_found']:
        print(f"\n🔒 PROTECTED FOLDERS FOUND ({len(report['protected_folders_found'])}):")
        for folder in report['protected_folders_found'][:5]:
            print(f"   - {folder}")
        if len(report['protected_folders_found']) > 5:
            print(f"   ... and {len(report['protected_folders_found']) - 5} more")

    # Execute mode - actually perform the moves
    # Execute mode - actually perform the moves
    if args.execute or args.interactive:
        executor = FileExecutor(organizer.root_path, report["suggestions"])
        
        should_run = True
        confirm_needed = not args.no_confirm

        if args.interactive:
            should_run = executor.interactive_review(args.category, args.year)
            confirm_needed = False # Already confirmed by 'run' command in interactive mode
        
        if should_run:
            result = executor.execute(
                confirm=confirm_needed,
                category_filter=args.category,
                year_filter=args.year
            )
            return result
        else:
            print("Cancelled.")
            return

    # Output to file if requested
    if args.output and not args.dry_run:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Report saved to: {output_path}")
    elif not args.dry_run:
        # Print JSON to stdout if no output file specified
        print("\n" + "=" * 60)
        print("📋 FULL REPORT (JSON)")
        print("=" * 60)
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return report


if __name__ == "__main__":
    main()
