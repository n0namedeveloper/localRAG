"""
Universal code parser using tree-sitter.
Extracts functions, classes, methods, imports, and dependencies from source files.

Supports: Python, JavaScript, TypeScript, Go, Rust, Java, C++
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from tree_sitter import Language, Parser, Node, Query
from tree_sitter_languages import get_language, get_parser

from app.models.schemas import ParsedSymbol, SymbolType, DependencyEdge

logger = logging.getLogger(__name__)

# ─── Language-specific query maps ─────────────────────────────────

# Each language has AST queries to extract symbols and their dependencies.
# Format: { "capture_name": "(tree-sitter-query)" }

PYTHON_QUERIES = {
    "function_def": """
        (function_definition
            name: (identifier) @name
            parameters: (parameters) @params
            body: (block) @body
        ) @func
    """,
    "class_def": """
        (class_definition
            name: (identifier) @name
            body: (block) @body
            superclasses: (argument_list)? @parents
        ) @class
    """,
    "import": """
        (import_statement
            name: (dotted_name) @module
        ) @import
    """,
    "import_from": """
        (import_from_statement
            module_name: (dotted_name)? @module
            name: (dotted_name) @imported_name
        ) @import_from
    """,
    "decorator": """
        (decorator
            (identifier) @deco_name
        ) @decorator
    """,
}

JAVASCRIPT_QUERIES = {
    "function_def": """
        (function_declaration
            name: (identifier) @name
            parameters: (formal_parameters) @params
            body: (statement_block) @body
        ) @func
    """,
    "arrow_function": """
        (variable_declarator
            name: (identifier) @name
            value: (arrow_function
                parameters: (formal_parameters) @params
                body: (statement_block)? @body
            )
        ) @func
    """,
    "class_def": """
        (class_declaration
            name: (identifier) @name
            body: (class_body) @body
        ) @class
    """,
    "method_def": """
        (method_definition
            name: (property_identifier) @name
            parameters: (formal_parameters) @params
            body: (statement_block) @body
        ) @func
    """,
    "import": """
        (import_statement
            source: (string) @module
        ) @import
    """,
    "export": """
        (export_statement
            declaration: (_) @exported
        ) @export
    """,
}

GO_QUERIES = {
    "function_def": """
        (function_declaration
            name: (identifier) @name
            parameters: (parameter_list) @params
            body: (block)? @body
        ) @func
    """,
    "method_def": """
        (method_declaration
            receiver: (parameter_list) @receiver
            name: (field_identifier) @name
            parameters: (parameter_list) @params
            body: (block)? @body
        ) @func
    """,
    "type_def": """
        (type_declaration
            (type_spec
                name: (type_identifier) @name
                type: (struct_type) @body
            )
        ) @struct
    """,
    "import": """
        (import_declaration
            (import_spec
                path: (interpreted_string_literal) @module
            )
        ) @import
    """,
}

RUST_QUERIES = {
    "function_def": """
        (function_item
            name: (identifier) @name
            parameters: (parameters) @params
            body: (block) @body
        ) @func
    """,
    "struct_def": """
        (struct_item
            name: (type_identifier) @name
            body: (field_declaration_list) @body
        ) @struct
    """,
    "impl_block": """
        (impl_item
            type: (type_identifier) @name
            body: (declaration_list) @body
        ) @impl
    """,
    "use_decl": """
        (use_declaration
            argument: (_) @module
        ) @import
    """,
}

JAVA_QUERIES = {
    "method_def": """
        (method_declaration
            name: (identifier) @name
            parameters: (formal_parameters) @params
            body: (block) @body
        ) @func
    """,
    "class_def": """
        (class_declaration
            name: (identifier) @name
            body: (class_body) @body
        ) @class
    """,
    "import": """
        (import_declaration
            (scoped_identifier) @module
        ) @import
    """,
}

CPP_QUERIES = {
    "function_def": """
        (function_definition
            declarator: (function_declarator
                declarator: (identifier) @name
                parameters: (parameter_list) @params
            )
            body: (compound_statement) @body
        ) @func
    """,
    "class_def": """
        (class_specifier
            name: (type_identifier) @name
            body: (field_declaration_list) @body
        ) @class
    """,
    "include": """
        (preproc_include
            path: (string_literal) @module
        ) @import
    """,
}

LANGUAGE_QUERIES = {
    "python": PYTHON_QUERIES,
    "javascript": JAVASCRIPT_QUERIES,
    "typescript": JAVASCRIPT_QUERIES,  # TS shares JS grammar
    "jsx": JAVASCRIPT_QUERIES,
    "tsx": JAVASCRIPT_QUERIES,
    "go": GO_QUERIES,
    "rust": RUST_QUERIES,
    "java": JAVA_QUERIES,
    "cpp": CPP_QUERIES,
}

# Mapping from file extension to language name for tree-sitter
EXT_TO_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
}


def detect_language(file_path: Path) -> str | None:
    """Detect tree-sitter language from file extension."""
    suffix = file_path.suffix.lower()
    if suffix in (".mjs", ".cjs"):
        return "javascript"
    return EXT_TO_LANG.get(suffix)


def _generate_symbol_id(
    file_path: str, name: str, symbol_type: SymbolType, line: int
) -> str:
    """Generate a unique deterministic ID for a symbol."""
    raw = f"{file_path}:{name}:{symbol_type.value}:{line}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _safe_text(node: Node, source: bytes) -> str:
    """Extract text from node safely, returning empty string on failure."""
    try:
        return source[node.start_byte : node.end_byte].decode("utf-8")
    except Exception:
        return ""


class CodeParser:
    """
    Multi-language code parser using tree-sitter.

    Usage:
        parser = CodeParser()
        symbols = parser.parse_file("src/main.py", source_code_bytes)
    """

    def __init__(self):
        self._parsers: dict[str, Parser] = {}
        self._queries: dict[str, dict[str, Query]] = {}

    def _get_parser(self, language: str) -> Parser:
        """Get or create a tree-sitter parser for the given language."""
        if language not in self._parsers:
            try:
                self._parsers[language] = get_parser(language)
            except Exception as e:
                raise ValueError(
                    f"Unsupported language: {language}. "
                    f"Make sure the tree-sitter grammar is installed. Error: {e}"
                )
        return self._parsers[language]

    def _get_queries(self, language: str) -> dict[str, Query]:
        """Get or compile queries for the given language."""
        if language not in LANGUAGE_QUERIES:
            raise ValueError(f"No queries defined for language: {language}")

        if language not in self._queries:
            try:
                lang_obj = get_language(language)
                self._queries[language] = {}
                for query_name, query_str in LANGUAGE_QUERIES[language].items():
                    try:
                        q = lang_obj.query(query_str)
                        self._queries[language][query_name] = q
                    except Exception as e:
                        logger.warning(
                            f"Failed to compile query '{query_name}' for {language}: {e}"
                        )
            except Exception as e:
                raise ValueError(f"Cannot load language grammar for {language}: {e}")

        return self._queries[language]

    def parse_file(
        self,
        file_path: Path,
        source: bytes,
        repo_name: str = "",
        repo_url: str = "",
        branch: str = "main",
    ) -> list[ParsedSymbol]:
        """
        Parse a single source file and extract all symbols.

        Args:
            file_path: Relative or absolute path to the source file.
            source: Raw source code as bytes.
            repo_name: Name of the repository.
            repo_url: URL of the repository.
            branch: Git branch name.

        Returns:
            List of ParsedSymbol extracted from the file.
        """
        language = detect_language(file_path)
        if language is None:
            return []

        rel_path = str(file_path).replace("\\", "/")

        try:
            parser = self._get_parser(language)
            tree = parser.parse(source)
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            return []

        root = tree.root_node
        symbols: list[ParsedSymbol] = []

        try:
            queries = self._get_queries(language)
        except Exception:
            logger.warning(f"No queries for {language}, skipping {file_path}")
            return []

        source_code = source.decode("utf-8", errors="replace")

        # ── Extract functions/methods ──
        func_query = queries.get("function_def") or queries.get("method_def")
        if func_query:
            for capture_name, nodes in func_query.captures(root).items():
                if capture_name == "func":
                    for node in nodes:
                        sym = self._extract_symbol_from_node(
                            node, source, SymbolType.FUNCTION, rel_path,
                            repo_name, repo_url, branch, language,
                        )
                        if sym:
                            # Check if it's a method (has receiver or parent class context)
                            sym = self._enrich_with_context(sym, node, source, language)
                            symbols.append(sym)

        # ── Extract classes/structs ──
        class_query = queries.get("class_def") or queries.get("struct_def") or queries.get("type_def")
        if class_query:
            for capture_name, nodes in class_query.captures(root).items():
                if capture_name in ("class", "struct"):
                    for node in nodes:
                        sym = self._extract_symbol_from_node(
                            node, source, SymbolType.CLASS, rel_path,
                            repo_name, repo_url, branch, language,
                        )
                        if sym:
                            symbols.append(sym)

        # ── Extract imports ──
        import_query = (
            queries.get("import")
            or queries.get("import_from")
            or queries.get("use_decl")
            or queries.get("include")
        )
        if import_query:
            for capture_name, nodes in import_query.captures(root).items():
                if capture_name in ("import", "import_from"):
                    for node in nodes:
                        import_text = _safe_text(node, source).strip()
                        if import_text:
                            symbols.append(
                                ParsedSymbol(
                                    id=_generate_symbol_id(
                                        rel_path,
                                        import_text[:60],
                                        SymbolType.IMPORT,
                                        node.start_point[0] + 1,
                                    ),
                                    name=import_text,
                                    symbol_type=SymbolType.IMPORT,
                                    file_path=rel_path,
                                    start_line=node.start_point[0] + 1,
                                    end_line=node.end_point[0] + 1,
                                    language=language,
                                    source_code=import_text,
                                    repo_name=repo_name,
                                    repo_url=repo_url,
                                    branch=branch,
                                )
                            )

        logger.debug(f"Parsed {len(symbols)} symbols from {rel_path}")
        return symbols

    def _extract_symbol_from_node(
        self,
        node: Node,
        source: bytes,
        default_type: SymbolType,
        file_path: str,
        repo_name: str,
        repo_url: str,
        branch: str,
        language: str,
    ) -> ParsedSymbol | None:
        """Extract a ParsedSymbol from a tree-sitter node."""
        source_text = source.decode("utf-8", errors="replace")

        name_node = node.child_by_field_name("name")
        if name_node is None:
            # Try to find name in first child (some grammars differ)
            for child in node.children:
                if child.type == "identifier" or child.type == "property_identifier":
                    name_node = child
                    break
        if name_node is None:
            return None

        name = _safe_text(name_node, source).strip()
        if not name:
            return None

        body_node = node.child_by_field_name("body")
        signature = _safe_text(node, source).split("\n")[0].strip()[:200]

        source_code = _safe_text(node, source)
        docstring = self._extract_docstring(node, source, language)

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1

        # Determine symbol type more precisely
        symbol_type = default_type
        if node.type == "method_definition" or node.type == "method_declaration":
            symbol_type = SymbolType.METHOD

        return ParsedSymbol(
            id=_generate_symbol_id(file_path, name, symbol_type, start_line),
            name=name,
            symbol_type=symbol_type,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
            signature=signature,
            docstring=docstring,
            source_code=source_code,
            repo_name=repo_name,
            repo_url=repo_url,
            branch=branch,
        )

    def _enrich_with_context(
        self,
        sym: ParsedSymbol,
        node: Node,
        source: bytes,
        language: str,
    ) -> ParsedSymbol:
        """Enrich a symbol with parent class info and dependencies."""
        source_text = source.decode("utf-8", errors="replace")

        # Check for parent class (method inside a class)
        parent = node.parent
        while parent is not None:
            if parent.type in (
                "class_definition",
                "class_declaration",
                "struct_item",
                "class_specifier",
                "impl_item",
                "type_declaration",
            ):
                name_node = parent.child_by_field_name("name")
                if name_node:
                    sym.parent_class = _safe_text(name_node, source).strip()
                break
            parent = parent.parent

        # Extract decorators for Python
        if language == "python":
            current = node
            # Walk backwards through siblings for decorators
            for sibling in node.parent.children if node.parent else []:
                if sibling == node:
                    break
                if sibling.type == "decorator":
                    deco_text = _safe_text(sibling, source).strip()
                    if deco_text:
                        sym.decorators.append(deco_text)

        # Extract function calls as initial dependencies
        try:
            call_nodes = self._find_call_nodes(node, source)
            sym.dependencies = list(set(call_nodes))[:20]  # limit to top 20
        except Exception:
            pass

        return sym

    def _find_call_nodes(self, node: Node, source: bytes) -> list[str]:
        """Find function/method calls within a node (simple heuristic)."""
        deps: list[str] = []
        source_text = source.decode("utf-8", errors="replace")

        for child in node.children:
            if child.type in (
                "call",
                "call_expression",
                "method_invocation",
            ):
                # Get the function name being called
                func_node = child.child_by_field_name("function")
                if func_node is None and child.children:
                    func_node = child.children[0]
                if func_node:
                    called = _safe_text(func_node, source).strip().split("(")[0]
                    if called and len(called) > 1 and len(called) < 100:
                        deps.append(called)
            deps.extend(self._find_call_nodes(child, source))

        return deps

    def _extract_docstring(self, node: Node, source: bytes, language: str) -> str | None:
        """Try to extract a docstring/comment from a node."""
        body = node.child_by_field_name("body")
        if body is None:
            return None

        source_text = source.decode("utf-8", errors="replace")

        # Python: first expression_statement that is a string
        if language == "python":
            for child in body.children:
                if child.type == "expression_statement":
                    str_node = child.children[0] if child.children else None
                    if str_node and str_node.type == "string":
                        text = _safe_text(str_node, source).strip('"""').strip("'''")
                        text = text.strip('"').strip("'")
                        return text[:500]

        # Generic: look for comment right after the signature
        for child in body.children[:3]:
            if child.type == "comment":
                return _safe_text(child, source).strip("# ").strip("// ").strip()[:500]

        return None

    def parse_directory(
        self,
        directory: Path,
        repo_name: str = "",
        repo_url: str = "",
        branch: str = "main",
        file_patterns: list[str] | None = None,
    ) -> list[ParsedSymbol]:
        """
        Recursively parse all supported source files in a directory.

        Args:
            directory: Root directory of the repository.
            repo_name: Repository name.
            repo_url: Repository URL.
            branch: Git branch.
            file_patterns: Optional glob patterns to filter files.

        Returns:
            Flat list of all ParsedSymbols found.
        """
        if file_patterns is None:
            file_patterns = ["**/*"]

        all_symbols: list[ParsedSymbol] = []
        patterns_set = set(EXT_TO_LANG.keys())

        for ext in patterns_set:
            for file_path in directory.rglob(f"*{ext}"):
                # Skip hidden dirs and common non-source dirs
                parts = file_path.parts
                if any(p.startswith(".") for p in parts):
                    continue
                if any(
                    skip in parts
                    for skip in (
                        "node_modules",
                        "__pycache__",
                        "venv",
                        ".venv",
                        "dist",
                        "build",
                        "target",
                        ".git",
                    )
                ):
                    continue

                try:
                    source = file_path.read_bytes()
                except Exception as e:
                    logger.warning(f"Cannot read {file_path}: {e}")
                    continue

                symbols = self.parse_file(
                    file_path, source, repo_name, repo_url, branch
                )
                all_symbols.extend(symbols)

        logger.info(
            f"Parsed {len(all_symbols)} symbols from directory {directory}"
        )
        return all_symbols