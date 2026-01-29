"""Main indexing logic for tree-sitter-db."""

import fnmatch
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable

from tree_sitter_db.extractors import get_extractor_for_file
from tree_sitter_db.schema import init_db, clear_file_data


def index_repository(
    repo_path: Path,
    db_path: Path,
    exclude_patterns: list[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict:
    """Index a repository and store results in SQLite.

    Args:
        repo_path: Path to repository root
        db_path: Path to output SQLite database
        exclude_patterns: Glob patterns to exclude (e.g., "**/test/**")
        progress_callback: Optional callback for progress updates

    Returns:
        Statistics about what was indexed
    """
    if exclude_patterns is None:
        exclude_patterns = ["**/__pycache__/**", "**/build/**", "**/.git/**"]

    conn = init_db(db_path)
    stats = {
        "files": 0,
        "functions": 0,
        "classes": 0,
        "imports": 0,
        "variables": 0,
        "calls": 0,
    }

    # Find all source files
    source_files = list(_find_source_files(repo_path, exclude_patterns))

    for file_path in source_files:
        result = get_extractor_for_file(str(file_path))
        if not result:
            continue

        extractor, language = result

        if progress_callback:
            progress_callback(f"Indexing {file_path.relative_to(repo_path)}")

        try:
            source = file_path.read_bytes()
        except (IOError, OSError) as e:
            if progress_callback:
                progress_callback(f"  Error reading file: {e}")
            continue

        try:
            tree = extractor.parse(source)
        except Exception as e:
            if progress_callback:
                progress_callback(f"  Parse error: {e}")
            continue

        # Insert or update file record
        rel_path = str(file_path.relative_to(repo_path))
        cursor = conn.execute(
            "INSERT OR REPLACE INTO files (path, language, indexed_at) VALUES (?, ?, ?)",
            (rel_path, language, datetime.now().isoformat()),
        )
        file_id = cursor.lastrowid

        # Clear old data for this file
        clear_file_data(conn, file_id)

        # Extract and insert functions
        for func in extractor.extract_functions(tree, source):
            conn.execute(
                """INSERT INTO functions
                   (file_id, name, line_start, line_end, signature, class_name, docstring)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (file_id, func.name, func.line_start, func.line_end,
                 func.signature, func.class_name, func.docstring),
            )
            stats["functions"] += 1

        # Extract and insert classes
        for cls in extractor.extract_classes(tree, source):
            conn.execute(
                """INSERT INTO classes
                   (file_id, name, line_start, line_end, bases, docstring)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_id, cls.name, cls.line_start, cls.line_end,
                 cls.bases, cls.docstring),
            )
            stats["classes"] += 1

        # Extract and insert imports
        for imp in extractor.extract_imports(tree, source):
            conn.execute(
                """INSERT INTO imports (file_id, module, alias, line)
                   VALUES (?, ?, ?, ?)""",
                (file_id, imp.module, imp.alias, imp.line),
            )
            stats["imports"] += 1

        # Extract and insert variables
        for var in extractor.extract_variables(tree, source):
            conn.execute(
                """INSERT INTO variables
                   (file_id, name, line, scope, class_name, type_hint)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_id, var.name, var.line, var.scope,
                 var.class_name, var.type_hint),
            )
            stats["variables"] += 1

        # Extract and insert calls
        for call in extractor.extract_calls(tree, source):
            conn.execute(
                """INSERT INTO calls (file_id, caller_function, callee_name, line)
                   VALUES (?, ?, ?, ?)""",
                (file_id, call.caller_function, call.callee_name, call.line),
            )
            stats["calls"] += 1

        stats["files"] += 1
        conn.commit()

    conn.close()
    return stats


def _find_source_files(
    repo_path: Path, exclude_patterns: list[str]
) -> list[Path]:
    """Find all source files in repository."""
    extensions = {".py", ".pyi", ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"}

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.suffix not in extensions:
            continue

        # Check exclude patterns
        rel_path = str(file_path.relative_to(repo_path))
        excluded = False
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                excluded = True
                break

        if not excluded:
            yield file_path


