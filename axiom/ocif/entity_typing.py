"""
Deterministic entity typing + relationship derivation for the diagram graph.

Phase 3: turns the request's flat extracted entities into a TYPED graph —
entities tagged actor / data-object / service / device / external-system /
constraint, and typed relationships (uses / depends_on / communicates_via /
stores / triggers) between them. This is what lets the Phase-4 diagram core
model how the request's entities flow through each OCIF layer, instead of a
fixed per-industry template.

Everything is deterministic and derived from THIS request's entities — no LLM,
no per-industry lookup. The classification signals and relationship rules are
named config, validated at import (invariant B7 — no scattered magic literals).
"""

from typing import Dict, List

# Entity type vocabulary.
ENTITY_TYPES = ("actor", "device", "external_system", "service", "data_object", "constraint")
_DEFAULT_TYPE = "data_object"   # neutral fallback for an unclassified concrete noun

# Relationship type vocabulary (directive-locked).
RELATIONSHIP_TYPES = ("uses", "depends_on", "communicates_via", "stores", "triggers")

# Classification signals: lowercase substrings that mark an entity as a type.
# Checked in ENTITY_TYPES order (most specific first), so a term matching several
# lands in the earliest matching type.
_TYPE_SIGNALS: Dict[str, tuple] = {
    "device": (
        "sensor", "gateway", "pump", "compressor", "valve", "motor", "actuator",
        "plc", "edge", "meter", "camera", "robot", "drone", "controller", "device",
        "turbine", "rotor", "bearing", "hvac", "chiller", "boiler",
    ),
    "external_system": (
        "scada", "erp", "crm", "sso", "provider", "payment", "third-party", "external",
        "broker", "kafka", "mqtt", "webhook", "vendor", "gateway-api", "cmms", "network",
    ),
    "service": (
        "service", "server", "engine", "processor", "scheduler", "worker", "pipeline",
        "dashboard", "portal", "application", "platform", "module", "api", "microservice",
        "queue", "cache", "orchestrator",
    ),
    "data_object": (
        "record", "reading", "alert", "ticket", "order", "invoice", "account", "ledger",
        "entry", "patient", "student", "attendance", "appointment", "result", "report",
        "log", "event", "transaction", "profile", "document", "file", "message", "menu",
        "meal", "book", "member", "loan", "encounter", "enrollment", "course", "transfer",
    ),
    "constraint": (
        "compliance", "hipaa", "gdpr", "pci", "latency", "throughput", "availability",
        "security", "privacy", "regulation", "standard", "sla", "audit",
    ),
}


def _validate() -> None:
    for t in _TYPE_SIGNALS:
        if t not in ENTITY_TYPES:
            raise ValueError(f"_TYPE_SIGNALS references unknown entity type: {t}")


_validate()


def classify_entity(name: str) -> str:
    """Deterministically type one entity by its name. Returns a value from
    ENTITY_TYPES (defaults to data_object for an unrecognised concrete noun)."""
    low = (name or "").lower()
    for etype in ENTITY_TYPES:
        if etype == "actor":
            continue  # actors come from the actor extractor, not name signals
        for sig in _TYPE_SIGNALS.get(etype, ()):  # constraint checked last per order
            if sig in low:
                return etype
    return _DEFAULT_TYPE


def build_typed_entities(entities: List[str], actors: List[str]) -> List[Dict[str, str]]:
    """Type every entity + actor. Order-preserving, de-duplicated by name."""
    typed: List[Dict[str, str]] = []
    seen = set()
    for a in actors or []:
        if a and a.lower() not in seen:
            seen.add(a.lower())
            typed.append({"name": a, "type": "actor"})
    for e in entities or []:
        if e and e.lower() not in seen:
            seen.add(e.lower())
            typed.append({"name": e, "type": classify_entity(e)})
    return typed


def derive_relationships(typed: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Derive a typed relationship graph from typed entities using standard
    engineering relations. Grounded (only names present in `typed`), deterministic,
    and non-fabricating — it connects real entities with standard relation types,
    never invents nodes.

    Rules (a primary service is the hub when one exists):
      actor            --uses-->             primary service
      device           --communicates_via--> primary service
      service          --stores-->           each data_object
      service          --depends_on-->       each external_system
      external_system  --triggers-->         primary service   (inbound events)
    """
    by_type: Dict[str, List[str]] = {t: [] for t in ENTITY_TYPES}
    for e in typed:
        by_type.setdefault(e["type"], []).append(e["name"])

    services = by_type.get("service", [])
    hub = services[0] if services else (
        by_type.get("data_object") or by_type.get("device") or [None]
    )[0]
    rels: List[Dict[str, str]] = []

    def add(src, rel, dst):
        if src and dst and src != dst:
            rels.append({"source": src, "target": dst, "type": rel})

    for actor in by_type.get("actor", []):
        add(actor, "uses", hub)
    for dev in by_type.get("device", []):
        add(dev, "communicates_via", hub)
    for ext in by_type.get("external_system", []):
        add(hub, "depends_on", ext)
        add(ext, "triggers", hub)
    for data in by_type.get("data_object", []):
        add(hub, "stores", data)

    return rels
