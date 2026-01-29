"""SQLite schema for code knowledge database."""

import sqlite3
from pathlib import Path

SCHEMA = """
-- Files indexed
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Functions and methods
CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER,
    signature TEXT,
    class_name TEXT,
    docstring TEXT
);

-- Classes (Python) / Structs (C/C++)
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER,
    bases TEXT,
    docstring TEXT
);

-- Imports / Includes
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    module TEXT NOT NULL,
    alias TEXT,
    line INTEGER NOT NULL
);

-- Global/class-level variables
CREATE TABLE IF NOT EXISTS variables (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    line INTEGER NOT NULL,
    scope TEXT NOT NULL,
    class_name TEXT,
    type_hint TEXT
);

-- Function calls (for call graph)
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    caller_function TEXT,
    callee_name TEXT NOT NULL,
    line INTEGER NOT NULL
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name);
CREATE INDEX IF NOT EXISTS idx_functions_class ON functions(class_name);
CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);
CREATE INDEX IF NOT EXISTS idx_imports_module ON imports(module);
CREATE INDEX IF NOT EXISTS idx_variables_name ON variables(name);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name);
CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_function);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    return conn


def clear_file_data(conn: sqlite3.Connection, file_id: int) -> None:
    """Clear all data for a file (for re-indexing)."""
    conn.execute("DELETE FROM functions WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM classes WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM imports WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM variables WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM calls WHERE file_id = ?", (file_id,))
