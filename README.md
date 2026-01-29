# tree-sitter-db

Extract code knowledge from repositories into SQLite using tree-sitter.

## What it does

Parses source code and stores structured information in an SQLite database:
- Functions and methods (with signatures, docstrings, line numbers)
- Classes and structs (with inheritance info)
- Imports and includes
- Global/class-level variables
- Function call graph

**Supported languages:** Python, C, C++

## Usage

Run with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv run tree-sitter-db <repository-path> [--db code.db] [--exclude "pattern"] [--verbose]
```

**Examples:**
```bash
# Index current directory
uv run tree-sitter-db .

# Custom output path
uv run tree-sitter-db /path/to/repo --db my_code.db

# Exclude test directories
uv run tree-sitter-db . --exclude "**/test/**" --exclude "**/tests/**"

# Show progress
uv run tree-sitter-db . --verbose
```

Default excludes: `**/__pycache__/**`, `**/build/**`, `**/.git/**`

## Database Schema

### files
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| path | TEXT | Relative file path (unique) |
| language | TEXT | python, c, or cpp |
| indexed_at | TIMESTAMP | When file was indexed |

### functions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| name | TEXT | Function name |
| line_start | INTEGER | Starting line number |
| line_end | INTEGER | Ending line number |
| signature | TEXT | Full signature (e.g., `def foo(x: int) -> str`) |
| class_name | TEXT | Containing class (NULL if top-level) |
| docstring | TEXT | Docstring content |

### classes
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| name | TEXT | Class/struct name |
| line_start | INTEGER | Starting line number |
| line_end | INTEGER | Ending line number |
| bases | TEXT | Base classes (comma-separated) |
| docstring | TEXT | Docstring content |

### imports
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| module | TEXT | Imported module/header |
| alias | TEXT | Import alias (e.g., `np` for numpy) |
| line | INTEGER | Line number |

### variables
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| name | TEXT | Variable name |
| line | INTEGER | Line number |
| scope | TEXT | global or class |
| class_name | TEXT | Containing class (if class scope) |
| type_hint | TEXT | Type annotation |

### calls
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| file_id | INTEGER | FK to files |
| caller_function | TEXT | Function containing the call (NULL if module-level) |
| callee_name | TEXT | Name of called function |
| line | INTEGER | Line number |

### Indexes
- `idx_functions_name` on functions(name)
- `idx_functions_class` on functions(class_name)
- `idx_classes_name` on classes(name)
- `idx_imports_module` on imports(module)
- `idx_variables_name` on variables(name)
- `idx_calls_callee` on calls(callee_name)
- `idx_calls_caller` on calls(caller_function)

## Example Queries

```sql
-- Database statistics
SELECT 'files' as type, COUNT(*) as count FROM files
UNION ALL SELECT 'functions', COUNT(*) FROM functions
UNION ALL SELECT 'classes', COUNT(*) FROM classes
UNION ALL SELECT 'imports', COUNT(*) FROM imports
UNION ALL SELECT 'variables', COUNT(*) FROM variables
UNION ALL SELECT 'calls', COUNT(*) FROM calls;

-- Files by language
SELECT language, COUNT(*) as count FROM files GROUP BY language;

-- Find functions by name pattern
SELECT f.path, fn.name, fn.line_start, fn.signature
FROM functions fn
JOIN files f ON fn.file_id = f.id
WHERE fn.name LIKE '%parse%';

-- Find all callers of a function
SELECT f.path, c.caller_function, c.line
FROM calls c
JOIN files f ON c.file_id = f.id
WHERE c.callee_name = 'process_data';

-- Find what a function calls
SELECT DISTINCT c.callee_name, f.path, c.line
FROM calls c
JOIN files f ON c.file_id = f.id
WHERE c.caller_function = 'main';

-- Classes with their methods
SELECT c.name as class, fn.name as method, fn.signature
FROM classes c
JOIN files f ON c.file_id = f.id
JOIN functions fn ON fn.file_id = f.id AND fn.class_name = c.name
ORDER BY c.name, fn.line_start;

-- Find classes that inherit from a base
SELECT f.path, c.name, c.bases
FROM classes c
JOIN files f ON c.file_id = f.id
WHERE c.bases LIKE '%BaseClass%';

-- All imports of a module
SELECT f.path, i.module, i.alias, i.line
FROM imports i
JOIN files f ON i.file_id = f.id
WHERE i.module LIKE '%numpy%';
```

## Querying the Database

```bash
sqlite3 code.db
```

Or use any SQLite client (DB Browser for SQLite, DBeaver, etc.).
