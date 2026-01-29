"""Python code extractor using tree-sitter."""

from typing import Iterator

import tree_sitter
import tree_sitter_python as tspython
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

PY_LANGUAGE = Language(tspython.language())


class PythonExtractor(BaseExtractor):
    """Extract code entities from Python source files."""

    def __init__(self):
        self.parser = Parser(PY_LANGUAGE)

    def parse(self, source: bytes) -> tree_sitter.Tree:
        return self.parser.parse(source)

    def extract_functions(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[FunctionInfo]:
        """Extract function and method definitions."""
        for node in walk_tree(tree.root_node):
            if node.type == "function_definition":
                yield self._extract_function(node, source)

    def _extract_function(self, node: tree_sitter.Node, source: bytes) -> FunctionInfo:
        """Extract info from a function_definition node."""
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")
        return_node = node.child_by_field_name("return_type")
        body_node = node.child_by_field_name("body")

        name = get_node_text(name_node, source) if name_node else "<unknown>"
        params = get_node_text(params_node, source) if params_node else "()"
        return_type = get_node_text(return_node, source) if return_node else ""

        signature = f"def {name}{params}"
        if return_type:
            signature += f" -> {return_type}"

        # Check if this is a method (inside a class)
        class_name = self._get_parent_class(node, source)

        # Extract docstring
        docstring = self._extract_docstring(body_node, source)

        return FunctionInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            class_name=class_name,
            docstring=docstring,
        )

    def _get_parent_class(self, node: tree_sitter.Node, source: bytes) -> str | None:
        """Find the parent class name if node is inside a class."""
        parent = node.parent
        while parent:
            if parent.type == "class_definition":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    return get_node_text(name_node, source)
            parent = parent.parent
        return None

    def _extract_docstring(self, body_node: tree_sitter.Node | None, source: bytes) -> str | None:
        """Extract docstring from function/class body."""
        if not body_node:
            return None

        # First statement in body might be a docstring
        for child in body_node.children:
            if child.type == "expression_statement":
                expr = child.child(0)
                if expr and expr.type == "string":
                    text = get_node_text(expr, source)
                    # Remove quotes
                    if text.startswith('"""') or text.startswith("'''"):
                        return text[3:-3].strip()
                    elif text.startswith('"') or text.startswith("'"):
                        return text[1:-1].strip()
            elif child.type not in ("comment",):
                break
        return None

    def extract_classes(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ClassInfo]:
        """Extract class definitions."""
        for node in walk_tree(tree.root_node):
            if node.type == "class_definition":
                yield self._extract_class(node, source)

    def _extract_class(self, node: tree_sitter.Node, source: bytes) -> ClassInfo:
        """Extract info from a class_definition node."""
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")

        name = get_node_text(name_node, source) if name_node else "<unknown>"

        # Extract base classes
        bases = []
        for child in node.children:
            if child.type == "argument_list":
                # This is the inheritance list: class Foo(Bar, Baz)
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(get_node_text(arg, source))
                    elif arg.type == "attribute":
                        bases.append(get_node_text(arg, source))

        docstring = self._extract_docstring(body_node, source)

        return ClassInfo(
            name=name,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            bases=", ".join(bases) if bases else None,
            docstring=docstring,
        )

    def extract_imports(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[ImportInfo]:
        """Extract import statements."""
        for node in walk_tree(tree.root_node):
            if node.type == "import_statement":
                yield from self._extract_import(node, source)
            elif node.type == "import_from_statement":
                yield from self._extract_from_import(node, source)

    def _extract_import(self, node: tree_sitter.Node, source: bytes) -> Iterator[ImportInfo]:
        """Extract 'import x' or 'import x as y'."""
        for child in node.children:
            if child.type == "dotted_name":
                module = get_node_text(child, source)
                yield ImportInfo(module=module, line=node.start_point[0] + 1)
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    module = get_node_text(name_node, source)
                    alias = get_node_text(alias_node, source) if alias_node else None
                    yield ImportInfo(module=module, line=node.start_point[0] + 1, alias=alias)

    def _extract_from_import(self, node: tree_sitter.Node, source: bytes) -> Iterator[ImportInfo]:
        """Extract 'from x import y' statements."""
        module_node = node.child_by_field_name("module_name")
        module = get_node_text(module_node, source) if module_node else ""

        for child in node.children:
            if child.type == "dotted_name" and child != module_node:
                item = get_node_text(child, source)
                yield ImportInfo(
                    module=f"{module}.{item}" if module else item,
                    line=node.start_point[0] + 1,
                )
            elif child.type == "aliased_import":
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                if name_node:
                    item = get_node_text(name_node, source)
                    alias = get_node_text(alias_node, source) if alias_node else None
                    yield ImportInfo(
                        module=f"{module}.{item}" if module else item,
                        line=node.start_point[0] + 1,
                        alias=alias,
                    )

    def extract_variables(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[VariableInfo]:
        """Extract global and class-level variables."""
        for node in walk_tree(tree.root_node):
            if node.type == "assignment":
                yield from self._extract_assignment(node, source)
            elif node.type == "annotated_assignment":
                yield from self._extract_annotated_assignment(node, source)

    def _extract_assignment(self, node: tree_sitter.Node, source: bytes) -> Iterator[VariableInfo]:
        """Extract variable from assignment."""
        # Only extract module-level or class-level assignments
        parent = node.parent
        if parent and parent.type == "expression_statement":
            grandparent = parent.parent
            if grandparent:
                if grandparent.type == "module":
                    scope = "global"
                    class_name = None
                elif grandparent.type == "block":
                    # Check if inside class body
                    class_name = self._get_parent_class(node, source)
                    if class_name:
                        scope = "class"
                    else:
                        return  # Inside a function, skip
                else:
                    return

                left = node.child_by_field_name("left")
                if left and left.type == "identifier":
                    name = get_node_text(left, source)
                    yield VariableInfo(
                        name=name,
                        line=node.start_point[0] + 1,
                        scope=scope,
                        class_name=class_name,
                    )

    def _extract_annotated_assignment(
        self, node: tree_sitter.Node, source: bytes
    ) -> Iterator[VariableInfo]:
        """Extract variable from annotated assignment (x: int = 5)."""
        parent = node.parent
        if parent and parent.type in ("module", "block"):
            if parent.type == "module":
                scope = "global"
                class_name = None
            else:
                class_name = self._get_parent_class(node, source)
                if class_name:
                    scope = "class"
                else:
                    return

            name_node = node.child_by_field_name("name")
            type_node = node.child_by_field_name("type")

            if name_node and name_node.type == "identifier":
                name = get_node_text(name_node, source)
                type_hint = get_node_text(type_node, source) if type_node else None
                yield VariableInfo(
                    name=name,
                    line=node.start_point[0] + 1,
                    scope=scope,
                    class_name=class_name,
                    type_hint=type_hint,
                )

    def extract_calls(self, tree: tree_sitter.Tree, source: bytes) -> Iterator[CallInfo]:
        """Extract function calls."""
        # First, build a map of function positions to names
        func_ranges: list[tuple[int, int, str]] = []
        for node in walk_tree(tree.root_node):
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_ranges.append(
                        (node.start_byte, node.end_byte, get_node_text(name_node, source))
                    )

        # Now find all calls
        for node in walk_tree(tree.root_node):
            if node.type == "call":
                func_node = node.child_by_field_name("function")
                if not func_node:
                    continue

                # Get callee name
                if func_node.type == "identifier":
                    callee = get_node_text(func_node, source)
                elif func_node.type == "attribute":
                    # method call: obj.method()
                    attr_node = func_node.child_by_field_name("attribute")
                    if attr_node:
                        callee = get_node_text(attr_node, source)
                    else:
                        continue
                else:
                    continue

                # Find which function contains this call
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
