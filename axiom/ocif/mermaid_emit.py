"""
Deterministic mermaid emitter.

Converts a validated diagram STRUCTURE (nodes + typed edges) into valid mermaid
for a given diagram family. The local model only ever proposes structure as
JSON; mermaid syntax is ALWAYS produced here, deterministically, so broken or
injected syntax can never reach the client (invariant B4).

Node ``id`` values are the grounded entity NAMES (the guard enforces that);
this module maps them to safe internal mermaid ids and keeps the name as the
visible label.
"""

import re
from typing import Callable, Dict, List

# mermaid family -> emitter. Keys must match blueprint_config.AXIOM_DIAGRAM_TYPES.
_EMITTERS: Dict[str, Callable] = {}


def _safe_id(prefix: str, i: int) -> str:
    return f"{prefix}{i}"


def _ident(name: str, i: int, prefix: str) -> str:
    """A mermaid-safe identifier from a grounded entity name: alphanumerics only,
    never empty, never leading with a digit (both invalid in class/ER grammars)."""
    tid = re.sub(r"[^A-Za-z0-9]", "", name)
    if not tid:
        return f"{prefix}{i}"
    if tid[0].isdigit():
        return f"{prefix}{tid}"
    return tid


def _er_id(name: str, i: int) -> str:
    return _ident(name, i, "E").upper()[:24]


def _esc(label: str) -> str:
    return (label or "").replace('"', "'").strip()


def _register(*types):
    def deco(fn):
        for t in types:
            _EMITTERS[t] = fn
        return fn
    return deco


@_register("flowchart")
def _flowchart(nodes, edges, idmap) -> str:
    lines = ["flowchart LR"]
    for n in nodes:
        lines.append(f'    {idmap[n]}["{_esc(n)}"]')
    for e in edges:
        rel = _esc(e.get("type", ""))
        arrow = f'-->|{rel}|' if rel else "-->"
        lines.append(f'    {idmap[e["source"]]} {arrow} {idmap[e["target"]]}')
    return "\n".join(lines)


@_register("sequence")
def _sequence(nodes, edges, idmap) -> str:
    lines = ["sequenceDiagram"]
    for n in nodes:
        lines.append(f'    participant {idmap[n]} as {_esc(n)}')
    for e in edges:
        rel = _esc(e.get("type", "")) or "interacts"
        lines.append(f'    {idmap[e["source"]]}->>{idmap[e["target"]]}: {rel}')
    return "\n".join(lines)


@_register("state")
def _state(nodes, edges, idmap) -> str:
    lines = ["stateDiagram-v2"]
    for n in nodes:
        lines.append(f'    state "{_esc(n)}" as {idmap[n]}')
    if nodes:
        lines.append(f'    [*] --> {idmap[nodes[0]]}')
    for e in edges:
        rel = _esc(e.get("type", ""))
        suffix = f' : {rel}' if rel else ""
        lines.append(f'    {idmap[e["source"]]} --> {idmap[e["target"]]}{suffix}')
    return "\n".join(lines)


@_register("class")
def _classd(nodes, edges, idmap) -> str:
    lines = ["classDiagram"]
    for n in nodes:
        cid = idmap[n]
        lines.append(f'    class {cid} {{')
        lines.append("        +id : string")
        lines.append("        +name : string")
        lines.append("    }")
    for e in edges:
        rel = _esc(e.get("type", ""))
        suffix = f' : {rel}' if rel else ""
        lines.append(f'    {idmap[e["source"]]} --> {idmap[e["target"]]}{suffix}')
    return "\n".join(lines)


@_register("er")
def _er(nodes, edges, idmap) -> str:
    lines = ["erDiagram"]
    for n in nodes:
        lines.append(f'    {idmap[n]} {{')
        lines.append("        string id")
        lines.append("        string name")
        lines.append("    }")
    for e in edges:
        rel = re.sub(r"[^A-Za-z0-9_]", "_", e.get("type", "") or "relates")
        lines.append(f'    {idmap[e["source"]]} ||--o{{ {idmap[e["target"]]} : {rel}')
    return "\n".join(lines)


@_register("mindmap")
def _mindmap(nodes, edges, idmap) -> str:
    # mindmap is a tree; edges don't apply. Root + each grounded node as a child.
    lines = ["mindmap", "  root((Blueprint))"]
    for n in nodes:
        lines.append(f"    {_esc(n)}")
    return "\n".join(lines)


def emit_mermaid(diagram_type: str, nodes: List[str], edges: List[Dict[str, str]]) -> str:
    """Deterministically render mermaid for `diagram_type` from grounded node
    names + typed edges. Returns "" for an unknown type or no nodes (caller
    treats that as EMPTY / falls back)."""
    if diagram_type not in _EMITTERS or not nodes:
        return ""
    # Class/ER need identifier-safe ids; flowchart/sequence/state use synthetic ids.
    if diagram_type == "er":
        idmap = {name: _er_id(name, i) for i, name in enumerate(nodes)}
    elif diagram_type == "class":
        idmap = {name: _ident(name, i, "C") for i, name in enumerate(nodes)}
    else:
        idmap = {name: _safe_id("n", i) for i, name in enumerate(nodes)}
    # Drop edges that reference names not in the node set (defensive).
    node_set = set(nodes)
    edges = [e for e in edges if e.get("source") in node_set and e.get("target") in node_set]
    return _EMITTERS[diagram_type](nodes, edges, idmap)
