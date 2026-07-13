"""
Engineering Ontology — the hierarchical semantic backbone of AXIOM.

Seeds a domain tree (Mechanical, Software, Industrial IoT, …) into the
repository's `ontology_nodes` table and offers lightweight traversal
(ancestors / descendants / expand). Traversal is deliberately simple this
increment; the persisted parent/child structure is what future graph reasoning
will build on.
"""

from typing import Dict, List, Optional
import uuid

from ecosystem.repository import EngineeringKnowledgeRepository

_ONTO_NAMESPACE = uuid.UUID("a1c1f0de-0000-4000-8000-0000000000a2")


def _node_id(domain: str, name: str) -> str:
    return str(uuid.uuid5(_ONTO_NAMESPACE, f"{domain}|{name}".lower()))


# Nested domain trees. Each top-level key is both the domain label and the
# root node. Children are nested dicts; leaves are empty dicts.
ONTOLOGY_SEED: Dict[str, dict] = {
    "Mechanical Engineering": {
        "Fluid Systems": {
            "Pump": {
                "Centrifugal Pump": {
                    "Impeller": {}, "Bearing": {}, "Seal": {},
                    "Pressure": {}, "Flow": {}, "Temperature": {},
                    "Maintenance": {"Failure Modes": {}},
                },
            },
            "Valve": {}, "Compressor": {},
        },
        "Thermal Systems": {"HVAC": {"Chiller": {}, "Air Handler": {}, "Damper": {}}},
    },
    "Software Engineering": {
        "Backend": {
            "FastAPI": {"REST": {"JWT": {}, "OAuth": {}}, "Caching": {}},
            "Database": {"PostgreSQL": {"Indexing": {}, "Replication": {}}},
        },
        "Frontend": {"SPA": {"State Management": {}, "Component Model": {}}},
    },
    "Industrial IoT": {
        "PLC": {"Modbus": {}, "OPC-UA": {}},
        "MQTT": {"Broker": {}, "QoS": {}, "Topics": {}, "Clients": {}, "Security": {}},
        "Edge Gateway": {"Store-and-Forward": {}, "Protocol Normalization": {}},
        "SCADA": {"Historian": {}, "HMI": {}},
        "Cloud": {"Time Series Database": {}, "Predictive Analytics": {}},
    },
}


class EngineeringOntology:
    def __init__(self, repository: EngineeringKnowledgeRepository) -> None:
        self.repository = repository

    def seed(self) -> int:
        """Idempotent (stable node ids). Returns node count written."""
        count = 0

        def walk(subtree: dict, domain: str, parent_id: Optional[str], level: int) -> None:
            nonlocal count
            for name, children in subtree.items():
                nid = _node_id(domain, name)
                self.repository.add_ontology_node(nid, name, parent_id, domain, level)
                count += 1
                walk(children, domain, nid, level + 1)

        for domain, tree in ONTOLOGY_SEED.items():
            root_id = _node_id(domain, domain)
            self.repository.add_ontology_node(root_id, domain, None, domain, 0)
            count += 1
            walk(tree, domain, root_id, 1)
        return count

    def _nodes(self) -> List[dict]:
        return self.repository.ontology_all()

    def children(self, term: str) -> List[str]:
        nodes = self._nodes()
        by_id = {n["node_id"]: n for n in nodes}
        matches = [n for n in nodes if n["name"].lower() == term.lower()]
        out: List[str] = []
        for m in matches:
            out.extend(n["name"] for n in nodes if n["parent_id"] == m["node_id"])
        return sorted(set(out))

    def descendants(self, term: str) -> List[str]:
        nodes = self._nodes()
        children_by_parent: Dict[str, List[dict]] = {}
        for n in nodes:
            children_by_parent.setdefault(n["parent_id"], []).append(n)
        out: List[str] = []
        seeds = [n for n in nodes if n["name"].lower() == term.lower()]
        stack = list(seeds)
        seen = set()
        while stack:
            node = stack.pop()
            for child in children_by_parent.get(node["node_id"], []):
                if child["node_id"] in seen:
                    continue
                seen.add(child["node_id"])
                out.append(child["name"])
                stack.append(child)
        return sorted(set(out))

    def ancestors(self, term: str) -> List[str]:
        nodes = self._nodes()
        by_id = {n["node_id"]: n for n in nodes}
        out: List[str] = []
        for start in [n for n in nodes if n["name"].lower() == term.lower()]:
            cur = start
            while cur.get("parent_id"):
                parent = by_id.get(cur["parent_id"])
                if not parent:
                    break
                out.append(parent["name"])
                cur = parent
        return list(dict.fromkeys(out))

    def expand(self, term: str) -> List[str]:
        """Semantic expansion: the term plus its ancestors and descendants —
        used to broaden a knowledge query beyond the literal request."""
        expanded = [term] + self.ancestors(term) + self.descendants(term)
        return list(dict.fromkeys(expanded))
