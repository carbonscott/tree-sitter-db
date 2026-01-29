"""Code extractors for different languages."""

from tree_sitter_db.extractors.base import (
    FunctionInfo,
    ClassInfo,
    ImportInfo,
    VariableInfo,
    CallInfo,
    BaseExtractor,
)
from tree_sitter_db.extractors.python_ext import PythonExtractor
from tree_sitter_db.extractors.c_ext import CExtractor
from tree_sitter_db.extractors.cpp_ext import CppExtractor

EXTRACTORS = {
    "python": (PythonExtractor, [".py", ".pyi"]),
    "c": (CExtractor, [".c", ".h"]),
    "cpp": (CppExtractor, [".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".hh"]),
}


def get_extractor_for_file(path: str) -> tuple[BaseExtractor, str] | None:
    """Get appropriate extractor for a file based on extension."""
    for lang, (extractor_cls, extensions) in EXTRACTORS.items():
        for ext in extensions:
            if path.endswith(ext):
                return extractor_cls(), lang
    return None


__all__ = [
    "FunctionInfo",
    "ClassInfo",
    "ImportInfo",
    "VariableInfo",
    "CallInfo",
    "BaseExtractor",
    "PythonExtractor",
    "CExtractor",
    "CppExtractor",
    "EXTRACTORS",
    "get_extractor_for_file",
]
