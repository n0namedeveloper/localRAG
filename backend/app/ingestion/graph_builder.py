"""
Dependency graph builder.

Constructs a directed graph (networkx) from parsed symbols:
  - import edges: file A imports file B (via import statements)
  - call edges: function X calls function Y
  - inheritance edges: class C extends class D

Used during retrieval to traverse +1 hop for context enrichment.
"""

import logging
from collections import defaultdict

import networkx as nx

from app.models.schemas import ParsedSymbol, DependencyEdge, SymbolType, DependencyType

logger = logging.getLogger(__name__)


class DependencyGraph:
    """
    Wraps a networkx directed graph for code dependency traversal.

    Nodes: symbol IDs (str)
    Edges: DependencyEdge metadata in edge attributes
    """

    def __init__(self):
        self.graph = nx.DiGraph()

    def build(
        self,
        symbols: list[ParsedSymbol],
    ) -> nx.DiGraph:
        """
        Build the dependency graph from a flat list of parsed symbols.

        Steps:
          1. Add all symbols as nodes
          2. Build a lookup: name → list of definitions (handle overloads)
          3. Add call edges by matching dependencies against the lookup
          4. Add import edges as file→file connections
          5. Add inheritance edges for classes
        """
        self.graph.clear()

        # ── 1. Add nodes ──
        for sym in symbols:
            self.graph.add_node(
                sym.id,
                name=sym.name,
                symbol_type=sym.symbol_type.value,
                file_path=sym.file_path,
                parent_class=sym.parent_class,
            )

        # ── 2. Build lookup: name → [symbol_ids] ──
        name_index: dict[str, list[str]] = defaultdict(list)
        for sym in symbols:
            if sym.symbol_type in (
                SymbolType.FUNCTION,
                SymbolType.METHOD,
                SymbolType.CLASS,
            ):
                name_index[sym.name.lower()].append(sym.id)

        # ── 3. Call edges ──
        for sym in symbols:
            if sym.symbol_type == SymbolType.IMPORT:
                continue
            for dep_name in sym.dependencies:
                dep_lower = dep_name.lower()
                if dep_lower in name_index:
                    for target_id in name_index[dep_lower]:
                        if target_id != sym.id:
                            self.graph.add_edge(
                                sym.id,
                                target_id,
                                dep_type=DependencyType.CALL.value,
                                from_file=sym.file_path,
                                to_file=self.graph.nodes[target_id].get(
                                    "file_path", ""
                                ),
                                weight=0.8,
                            )

        # ── 4. Inheritance edges ──
        # When class C extends class D (via parent_class field on child methods)
        for sym in symbols:
            if sym.parent_class:
                parent_lower = sym.parent_class.lower()
                if parent_lower in name_index:
                    for parent_id in name_index[parent_lower]:
                        if parent_id != sym.id:
                            self.graph.add_edge(
                                sym.id,
                                parent_id,
                                dep_type=DependencyType.INHERITANCE.value,
                                from_file=sym.file_path,
                                to_file=self.graph.nodes[parent_id].get(
                                    "file_path", ""
                                ),
                                weight=0.6,
                            )

        # ── 5. File-level import edges ──
        file_symbols: dict[str, list[str]] = defaultdict(list)
        for sym in symbols:
            file_symbols[sym.file_path].append(sym.id)

        for sym in symbols:
            if sym.symbol_type == SymbolType.IMPORT:
                # Try to match import name to known files
                import_name = sym.name.lower().replace(".", "/").replace("from ", "")
                for file_path, node_ids in file_symbols.items():
                    if file_path.replace(".py", "").replace(".js", "").endswith(
                        import_name
                    ) or import_name in file_path.lower():
                        for target_id in node_ids:
                            self.graph.add_edge(
                                sym.id,
                                target_id,
                                dep_type=DependencyType.IMPORT.value,
                                from_file=sym.file_path,
                                to_file=file_path,
                                weight=0.3,
                            )

        logger.info(
            f"Built dependency graph: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )
        return self.graph

    def get_neighbors(
        self, symbol_id: str, hops: int = 1, direction: str = "both"
    ) -> list[str]:
        """
        Get neighboring symbol IDs within N hops.

        Args:
            symbol_id: The starting symbol's ID.
            hops: Number of graph hops (default 1).
            direction: "out" (dependents), "in" (dependencies), "both".

        Returns:
            List of symbol IDs reachable within the hop limit.
        """
        if symbol_id not in self.graph:
            return []

        neighbors: set[str] = set()
        current = {symbol_id}

        for _ in range(hops):
            next_level: set[str] = set()
            for node in current:
                if direction in ("out", "both"):
                    for _, target in self.graph.out_edges(node):
                        next_level.add(target)
                if direction in ("in", "both"):
                    for source, _ in self.graph.in_edges(node):
                        next_level.add(source)
            neighbors.update(next_level)
            current = next_level

        return list(neighbors)

    def get_dependency_chain(
        self, symbol_id: str, max_depth: int = 3
    ) -> list[list[str]]:
        """
        Get dependency chains (paths) for explanation.

        Returns list of paths (each path is a list of symbol IDs).
        """
        chains: list[list[str]] = []
        if symbol_id not in self.graph:
            return chains

        # Simple BFS path enumeration limited by depth
        def dfs(node: str, visited: set[str], depth: int, path: list[str]):
            if depth > max_depth:
                return
            for _, target in self.graph.out_edges(node):
                if target not in visited:
                    new_path = path + [target]
                    chains.append(new_path)
                    new_visited = visited | {target}
                    dfs(target, new_visited, depth + 1, new_path)

        dfs(symbol_id, {symbol_id}, 1, [symbol_id])
        return chains

    def get_symbol_file(self, symbol_id: str) -> str | None:
        """Get file path for a symbol."""
        if symbol_id in self.graph:
            return self.graph.nodes[symbol_id].get("file_path")
        return None

    def get_symbol_name(self, symbol_id: str) -> str | None:
        """Get symbol name for an ID."""
        if symbol_id in self.graph:
            return self.graph.nodes[symbol_id].get("name")
        return None

    def get_incoming_calls(self, symbol_id: str) -> list[str]:
        """Get all symbols that call this symbol."""
        if symbol_id not in self.graph:
            return []
        callers = []
        for source, _, data in self.graph.in_edges(symbol_id, data=True):
            if data.get("dep_type") == DependencyType.CALL.value:
                callers.append(source)
        return callers

    def get_outgoing_calls(self, symbol_id: str) -> list[str]:
        """Get all symbols that this symbol calls."""
        if symbol_id not in self.graph:
            return []
        callees = []
        for _, target, data in self.graph.out_edges(symbol_id, data=True):
            if data.get("dep_type") == DependencyType.CALL.value:
                callees.append(target)
        return callees

    def to_export_format(self, repo_name: str | None = None) -> dict:
        """
        Export graph as nodes/edges for frontend visualization.
        """
        nodes = []
        edges = []
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            nodes.append({
                "id": node_id,
                "data": {
                    "name": node_data.get("name", ""),
                    "symbol_type": node_data.get("symbol_type", "unknown"),
                    "file_path": node_data.get("file_path", ""),
                    "parent_class": node_data.get("parent_class"),
                }
            })
        for source, target, edge_data in self.graph.edges(data=True):
            dep_type = edge_data.get("dep_type", "unknown")
            edges.append({
                "id": f"{source}__{target}",
                "source": source,
                "target": target,
                "label": dep_type,
                "weight": edge_data.get("weight", 1.0),
            })
        return {"repo_name": repo_name or "unknown", "nodes": nodes, "edges": edges}
