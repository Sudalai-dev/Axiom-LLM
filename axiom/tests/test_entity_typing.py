"""Phase 3 — typed entities + relationships.

Each request yields a typed entity graph (actor/device/external_system/service/
data_object/constraint) and typed relationships, derived deterministically from
the request's OWN entities — so two same-industry requests produce materially
different typed node + edge sets (invariant B8).
"""

import asyncio

from ocif.engines.context import ContextEngine
from ocif.entity_typing import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    build_typed_entities,
    classify_entity,
    derive_relationships,
)
from ocif.frames import CognitiveContext, PerceptionFrame


def _typed(text):
    ctx = CognitiveContext(task=text)
    ctx.perception = PerceptionFrame(raw_text=text, normalized_text=text)
    asyncio.run(ContextEngine()._run(ctx))
    return ctx.context


def test_classify_entity_types_are_in_vocabulary():
    assert classify_entity("Vibration Sensor") == "device"
    assert classify_entity("Payment Provider") == "external_system"
    assert classify_entity("Patient Record") == "data_object"
    assert classify_entity("Scheduler Service") == "service"
    assert classify_entity("HIPAA Compliance") == "constraint"
    # Everything resolves to a known type.
    for name in ("Widget", "Frobnicator", "Xyz"):
        assert classify_entity(name) in ENTITY_TYPES


def test_derived_relationships_are_typed_and_grounded():
    typed = build_typed_entities(["Telemetry Service", "Vibration Sensor", "Alert Record"], ["Operator"])
    names = {t["name"] for t in typed}
    rels = derive_relationships(typed)
    assert rels  # non-empty for a request with actors/devices/services
    for r in rels:
        assert r["type"] in RELATIONSHIP_TYPES
        assert r["source"] in names and r["target"] in names   # grounded, no invented nodes


def test_context_engine_populates_typed_graph():
    frame = _typed("A hospital patient records portal where clinicians manage appointments and PHI.")
    assert frame.typed_entities
    assert {t["type"] for t in frame.typed_entities} <= set(ENTITY_TYPES)
    # The actor is typed as an actor.
    assert any(t["type"] == "actor" for t in frame.typed_entities)


def test_two_same_industry_requests_have_different_typed_graphs():
    a = _typed("A hospital patient records portal storing PHI, appointments and lab results for clinicians.")
    b = _typed("A hospital cafeteria menu board showing daily meals and prices to visitors.")
    a_nodes = {t["name"].lower() for t in a.typed_entities}
    b_nodes = {t["name"].lower() for t in b.typed_entities}
    assert a_nodes != b_nodes
    # Edge sets differ too (grounded in different entities).
    a_edges = {(r["source"].lower(), r["type"], r["target"].lower()) for r in a.relationships}
    b_edges = {(r["source"].lower(), r["type"], r["target"].lower()) for r in b.relationships}
    assert a_edges != b_edges


def test_trivial_request_has_no_typed_graph():
    frame = _typed("hello")
    assert frame.typed_entities == []
    assert frame.relationships == []
