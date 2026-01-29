"""C code extractor using tree-sitter."""

from typing import Iterator

import tree_sitter
import tree_sitter_c as tsc
from tree_sitter import Language, Parser

from tree_sitter_db.extractors.base import (
    BaseExtractor,
    FunctionInfo,
    ClassInfo,
    ImportInfo,
    VariableInfo,
    CallInfo,
    walk_tree,
    get_node_text,
)

C_LANGUAGE = Language(tsc.language())


class CExtractor(BaseExtractor):
    """Extract code entities from C source files."""

    def __init__(self):
        self.parser = Parser(C_LANGUAGE)

    def parse(self, source: bytes) -> tree_sitter.Tree:
        return self.parser.parse(source)

    def extract_functions(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[FunctionInfo]:
        """Extract function definitions."""
        for node in walk_tree(tree.root_node):
            if node.type == "function_definition":
                info = self._extract_function(node, source)
                if info:
                    yield info

    def _extract_function(self, node: tree_sitter.Node, source: bytes) -> FunctionInfo | None:
        """Extract info from a function_definition node."""
        # C function structure: type declarator body
        # declarator can be: function_declarator or pointer_declarator containing function_declarator
        type_node = node.child_by_field_name("type")
        declarator = node.child_by_field_name("declarator")

        if not declarator:
            return None

        # Find the function name and parameters
        name, params = self._extract_declarator_info(declarator, source)
        if not name:
            return None

        return_type = get_node_text(type_node, source) if type_node else "void"
        signature = f"{return_type} {name}{params}"

        return FunctionInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
        )

    def _extract_declarator_info(
        self, node: tree_sitter.Node, source: bytes
    ) -> tuple[str | None, str]:
        """Recursively extract function name and parameters from declarator."""
        if node.type == "function_declarator":
            decl = node.child_by_field_name("declarator")
            params_node = node.child_by_field_name("parameters")
            params = get_node_text(params_node, source) if params_node else "()"

            if decl:
                if decl.type == "identifier":
                    return get_node_text(decl, source), params
                else:
                    name, _ = self._extract_declarator_info(decl, source)
                    return name, params

        elif node.type == "pointer_declarator":
            decl = node.child_by_field_name("declarator")
            if decl:
                return self._extract_declarator_info(decl, source)

        elif node.type == "identifier":
            return get_node_text(node, source), "()"

        elif node.type == "parenthesized_declarator":
            for child in node.children:
                if child.type not in ("(", ")"):
                    return self._extract_declarator_info(child, source)

        return None, "()"

    def extract_classes(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ClassInfo]:
        """Extract struct definitions (C doesn't have classes)."""
        for node in walk_tree(tree.root_node):
            if node.type == "struct_specifier":
                info = self._extract_struct(node, source)
                if info:
                    yield info

    def _extract_struct(self, node: tree_sitter.Node, source: bytes) -> ClassInfo | None:
        """Extract info from struct_specifier."""
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")

        # Skip anonymous structs or forward declarations without body
        if not name_node:
            return None

        name = get_node_text(name_node, source)

        return ClassInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1 if body_node else node.start_point[0] + 1,
        )

    def extract_imports(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ImportInfo]:
        """Extract #include directives."""
        for node in walk_tree(tree.root_node):
            if node.type == "preproc_include":
                path_node = node.child_by_field_name("path")
                if path_node:
                    path = get_node_text(path_node, source)
                    # Remove quotes or angle brackets
                    path = path.strip('"<>')
                    yield ImportInfo(module=path, line=node.start_point[0] + 1)

    def extract_variables(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[VariableInfo]:
        """Extract global variable declarations."""
        for node in walk_tree(tree.root_node):
            if node.type == "declaration":
                parent = node.parent
                # Only global declarations (direct children of translation_unit)
                if parent and parent.type == "translation_unit":
                    yield from self._extract_declaration(node, source)

    def _extract_declaration(
        self, node: tree_sitter.Node, source: bytes
    ) -> Iterator[VariableInfo]:
        """Extract variables from a declaration."""
        type_node = node.child_by_field_name("type")
        type_str = get_node_text(type_node, source) if type_node else None

        declarator = node.child_by_field_name("declarator")
        if declarator:
            name = self._get_var_name(declarator, source)
            if name:
                yield VariableInfo(
                    name=name,
                    line=node.start_point[0] + 1,
                    scope="global",
                    type_hint=type_str,
                )

    def _get_var_name(self, node: tree_sitter.Node, source: bytes) -> str | None:
        """Extract variable name from declarator."""
        if node.type == "identifier":
            return get_node_text(node, source)
        elif node.type in ("init_declarator", "pointer_declarator", "array_declarator"):
            decl = node.child_by_field_name("declarator")
            if decl:
                return self._get_var_name(decl, source)
            # Try first child
            for child in node.children:
                if child.type == "identifier":
                    return get_node_text(child, source)
        return None

    def extract_calls(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[CallInfo]:
        """Extract function calls."""
        # Build function position map
        func_ranges: list[tuple[int, int, str]] = []
        for node in walk_tree(tree.root_node):
            if node.type == "function_definition":
                declarator = node.child_by_field_name("declarator")
                if declarator:
                    name, _ = self._extract_declarator_info(declarator, source)
                    if name:
                        func_ranges.append((node.start_byte, node.end_byte, name))

        # Find calls
        for node in walk_tree(tree.root_node):
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and func_node.type == "identifier":
                    callee = get_node_text(func_node, source)

                    # Find caller
                    caller = None
                    call_pos = node.start_byte
                    for start, end, name in func_ranges:
                        if start <= call_pos <= end:
                            caller = name
                            break

                    yield CallInfo(
                        callee_name=callee,
                        line=node.start_point[0] + 1,
                        caller_function=caller,
                    )
