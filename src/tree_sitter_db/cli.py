"""CLI for tree-sitter-db."""

import argparse
import sys
from pathlib import Path

from tree_sitter_db.indexer import index_repository


def main():
    parser = argparse.ArgumentParser(
        description="Extract code knowledge from repositories into SQLite."
    )
    parser.add_argument("repo_path", type=Path, help="Path to repository to index")
    parser.add_argument(
        "--db", "-d", type=Path, default=Path("code.db"), help="Output database path"
    )
    parser.add_argument(
        "--exclude", "-e", action="append", help="Glob patterns to exclude"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress")

    args = parser.parse_args()

    if not args.repo_path.exists():
        print(f"Error: {args.repo_path} does not exist", file=sys.stderr)
        sys.exit(1)

    if not args.repo_path.is_dir():
        print(f"Error: {args.repo_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    patterns = args.exclude or ["**/__pycache__/**", "**/build/**", "**/.git/**"]

    def progress(msg: str):
        if args.verbose:
            print(msg)

    print(f"Indexing {args.repo_path} -> {args.db}")
    stats = index_repository(args.repo_path, args.db, patterns, progress)

    print(f"\nIndexed:")
    print(f"  {stats['files']} files")
    print(f"  {stats['functions']} functions")
    print(f"  {stats['classes']} classes")
    print(f"  {stats['imports']} imports")
    print(f"  {stats['variables']} variables")
    print(f"  {stats['calls']} calls")


if __name__ == "__main__":
    main()
