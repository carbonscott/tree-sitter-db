"""C++ code extractor using tree-sitter."""

from typing import Iterator

import tree_sitter
import tree_sitter_cpp as tscpp
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

CPP_LANGUAGE = Language(tscpp.language())


class CppExtractor(BaseExtractor):
    """Extract code entities from C++ source files."""

    def __init__(self):
        self.parser = Parser(CPP_LANGUAGE)

    def parse(self, source: bytes) -> tree_sitter.Tree:
        return self.parser.parse(source)

    def extract_functions(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[FunctionInfo]:
        """Extract function and method definitions."""
        for node in walk_tree(tree.root_node):
            if node.type == "function_definition":
                info = self._extract_function(node, source)
                if info:
                    yield info

    def _extract_function(self, node: tree_sitter.Node, source: bytes) -> FunctionInfo | None:
        """Extract info from a function_definition node."""
        type_node = node.child_by_field_name("type")
        declarator = node.child_by_field_name("declarator")

        if not declarator:
            return None

        name, params = self._extract_declarator_info(declarator, source)
        if not name:
            return None

        return_type = get_node_text(type_node, source) if type_node else "void"

        # Check if this is a method (Class::method)
        class_name = None
        if "::" in name:
            parts = name.rsplit("::", 1)
            if len(parts) == 2:
                class_name = parts[0]
                name = parts[1]

        signature = f"{return_type} {name}{params}"

        return FunctionInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            class_name=class_name,
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
                elif decl.type == "qualified_identifier":
                    return get_node_text(decl, source), params
                elif decl.type == "field_identifier":
                    return get_node_text(decl, source), params
                else:
                    name, _ = self._extract_declarator_info(decl, source)
                    return name, params

        elif node.type == "pointer_declarator":
            decl = node.child_by_field_name("declarator")
            if decl:
                return self._extract_declarator_info(decl, source)

        elif node.type == "reference_declarator":
            for child in node.children:
                if child.type not in ("&", "&&"):
                    return self._extract_declarator_info(child, source)

        elif node.type in ("identifier", "qualified_identifier", "field_identifier"):
            return get_node_text(node, source), "()"

        elif node.type == "parenthesized_declarator":
            for child in node.children:
                if child.type not in ("(", ")"):
                    return self._extract_declarator_info(child, source)

        return None, "()"

    def extract_classes(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ClassInfo]:
        """Extract class and struct definitions."""
        for node in walk_tree(tree.root_node):
            if node.type in ("class_specifier", "struct_specifier"):
                info = self._extract_class(node, source)
                if info:
                    yield info

    def _extract_class(self, node: tree_sitter.Node, source: bytes) -> ClassInfo | None:
        """Extract info from class_specifier or struct_specifier."""
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")

        if not name_node:
            return None

        name = get_node_text(name_node, source)

        # Extract base classes
        bases = []
        for child in node.children:
            if child.type == "base_class_clause":
                for base in child.children:
                    if base.type == "type_identifier":
                        bases.append(get_node_text(base, source))
                    elif base.type == "qualified_identifier":
                        bases.append(get_node_text(base, source))

        return ClassInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1 if body_node else node.start_point[0] + 1,
            bases=", ".join(bases) if bases else None,
        )

    def extract_imports(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ImportInfo]:
        """Extract #include directives."""
        for node in walk_tree(tree.root_node):
            if node.type == "preproc_include":
                path_node = node.child_by_field_name("path")
                if path_node:
                    path = get_node_text(path_node, source)
                    path = path.strip('"<>')
                    yield ImportInfo(module=path, line=node.start_point[0] + 1)

    def extract_variables(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[VariableInfo]:
        """Extract global and class-level variable declarations."""
        for node in walk_tree(tree.root_node):
            if node.type == "declaration":
                parent = node.parent
                if parent and parent.type == "translation_unit":
                    yield from self._extract_declaration(node, source, "global", None)
            elif node.type == "field_declaration":
                # Class member
                class_name = self._get_parent_class(node, source)
                if class_name:
                    yield from self._extract_field(node, source, class_name)

    def _get_parent_class(self, node: tree_sitter.Node, source: bytes) -> str | None:
        """Find parent class name."""
        parent = node.parent
        while parent:
            if parent.type in ("class_specifier", "struct_specifier"):
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return get_node_text(name_node, source)
            parent = parent.parent
        return None

    def _extract_declaration(
        self, node: tree_sitter.Node, source: bytes, scope: str, class_name: str | None
    ) -> Iterator[VariableInfo]:
        """Extract variables from declaration."""
        type_node = node.child_by_field_name("type")
        type_str = get_node_text(type_node, source) if type_node else None

        declarator = node.child_by_field_name("declarator")
        if declarator:
            name = self._get_var_name(declarator, source)
            if name:
                yield VariableInfo(
                    name=name,
                    line=node.start_point[0] + 1,
                    scope=scope,
                    class_name=class_name,
                    type_hint=type_str,
                )

    def _extract_field(
        self, node: tree_sitter.Node, source: bytes, class_name: str
    ) -> Iterator[VariableInfo]:
        """Extract class field."""
        type_node = node.child_by_field_name("type")
        type_str = get_node_text(type_node, source) if type_node else None

        declarator = node.child_by_field_name("declarator")
        if declarator:
            name = self._get_var_name(declarator, source)
            if name:
                yield VariableInfo(
                    name=name,
                    line=node.start_point[0] + 1,
                    scope="class",
                    class_name=class_name,
                    type_hint=type_str,
                )

    def _get_var_name(self, node: tree_sitter.Node, source: bytes) -> str | None:
        """Extract variable name from declarator."""
        if node.type in ("identifier", "field_identifier"):
            return get_node_text(node, source)
        elif node.type in ("init_declarator", "pointer_declarator", "array_declarator"):
            decl = node.child_by_field_name("declarator")
            if decl:
                return self._get_var_name(decl, source)
            for child in node.children:
                if child.type in ("identifier", "field_identifier"):
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
                        # Strip class prefix for matching
                        if "::" in name:
                            name = name.rsplit("::", 1)[1]
                        func_ranges.append((node.start_byte, node.end_byte, name))

        # Find calls
        for node in walk_tree(tree.root_node):
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if not func_node:
                    continue

                callee = None
                if func_node.type == "identifier":
                    callee = get_node_text(func_node, source)
                elif func_node.type == "qualified_identifier":
                    callee = get_node_text(func_node, source)
                elif func_node.type == "field_expression":
                    # obj.method() or obj->method()
                    field = func_node.child_by_field_name("field")
                    if field:
                        callee = get_node_text(field, source)

                if callee:
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
