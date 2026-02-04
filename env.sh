# tree-sitter-db environment setup
# Source this file before running tree-sitter-db:
#   source /sdf/group/lcls/ds/dm/apps/dev/tools/tree-sitter-db/env.sh

# Add shared uv to PATH (needed for Slurm nodes and users without personal uv)
export PATH="/sdf/group/lcls/ds/dm/apps/dev/bin:$PATH"

# Auto-detect project directory from this script's location
export TREE_SITTER_DB_APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default data directory for indexed databases (override in env.local)
# Note: For on-demand indexing, databases are typically created in /tmp or user-specified locations
export TREE_SITTER_DB_DATA_DIR="${TREE_SITTER_DB_DATA_DIR:-/tmp}"

# Source local overrides if present
if [[ -f "$TREE_SITTER_DB_APP_DIR/env.local" ]]; then
    source "$TREE_SITTER_DB_APP_DIR/env.local"
fi

# UV cache directory (persistent across sessions)
export UV_CACHE_DIR="$TREE_SITTER_DB_APP_DIR/.uv-cache"

# Convenience wrapper for tree-sitter-db
# Usage: tsdb <repo_path> [--db path] [--exclude pattern] [--verbose]
tsdb() {
    local cmd="${1:-}"
    if [[ -z "$cmd" ]]; then
        uv run --project "$TREE_SITTER_DB_APP_DIR" tree-sitter-db --help
        return
    fi
    shift
    uv run --project "$TREE_SITTER_DB_APP_DIR" tree-sitter-db "$cmd" "$@"
}
