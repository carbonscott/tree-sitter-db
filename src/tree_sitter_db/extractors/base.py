"""Base extractor class and data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

import tree_sitter


@dataclass
class FunctionInfo:
    """Information about a function or method."""
    name: str
    line_start: int
    line_end: int
    signature: str
    class_name: str | None = None
    docstring: str | None = None


@dataclass
class ClassInfo:
    """Information about a class or struct."""
    name: str
    line_start: int
    line_end: int
    bases: str | None = None
    docstring: str | None = None


@dataclass
class ImportInfo:
    """Information about an import or include."""
    module: str
    line: int
    alias: str | None = None


@dataclass
class VariableInfo:
    """Information about a variable."""
    name: str
    line: int
    scope: str  # 'global', 'class'
    class_name: str | None = None
    type_hint: str | None = None


@dataclass
class CallInfo:
    """Information about a function call."""
    callee_name: str
    line: int
    caller_function: str | None = None


class BaseExtractor(ABC):
    """Abstract base class for language-specific extractors."""

    @abstractmethod
    def parse(self, source: bytes) -> tree_sitter.Tree:
        """Parse source code and return syntax tree."""
        pass

    @abstractmethod
    def extract_functions(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[FunctionInfo]:
        """Extract all function definitions."""
        pass

    @abstractmethod
    def extract_classes(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ClassInfo]:
        """Extract all class definitions."""
        pass

    @abstractmethod
    def extract_imports(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ImportInfo]:
        """Extract all import statements."""
        pass

    @abstractmethod
    def extract_variables(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[VariableInfo]:
        """Extract global and class-level variables."""
        pass

    @abstractmethod
    def extract_calls(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[CallInfo]:
        """Extract function calls."""
        pass


def walk_tree(node: tree_sitter.Node) -> Iterator[tree_sitter.Node]:
    """Walk all nodes in a tree depth-first."""
    cursor = node.walk()
    visited = False

    while True:
        if not visited:
            yield cursor.node
            if cursor.goto_first_child():
                continue
        visited = False
        if cursor.goto_next_sibling():
            continue
        if not cursor.goto_parent():
            break
        visited = True


def get_node_text(node: tree_sitter.Node, source: bytes) -> str:
    """Get the text content of a node."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
