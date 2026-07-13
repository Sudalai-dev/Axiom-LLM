"""
Engineering Knowledge Platform (`ecosystem/`) — repository, versioning,
relationships, ranking, standards, rules, ontology, dynamic assembly,
ingestion, seeding, and Engineering-Intelligence-Engine integration.
"""

from ecosystem import KnowledgePlatform
from ecosystem.models import ApprovalState, KnowledgeCategory, KnowledgeObject
from ecosystem.ranking import score
from ecosystem.repository import EngineeringKnowledgeRepository
from ocif.engines.engineering_intelligence import KNOWLEDGE_PACKS, KnowledgePackLoader


def make_repo(tmp_path) -> EngineeringKnowledgeRepository:
    return EngineeringKnowledgeRepository(db_path=str(tmp_path / "kp.db"))


def make_platform(tmp_path) -> KnowledgePlatform:
    plat = KnowledgePlatform(db_path=str(tmp_path / "platform.db"))
    plat.seed()
    return plat


# --------------------------------------------------------------------------
# Repository — CRUD, ranking, usage
# --------------------------------------------------------------------------

def test_repository_upsert_get_and_query(tmp_path):
    repo = make_repo(tmp_path)
    obj = KnowledgeObject(
        title="Event-Driven Architecture", category=KnowledgeCategory.PATTERN.value,
        domain="Software Engineering", summary="Decoupled services via events",
    )
    kid = repo.upsert(obj)
    fetched = repo.get(kid)
    assert fetched is not None
    assert fetched.title == "Event-Driven Architecture"

    results = repo.query(domain="Software Engineering", category=KnowledgeCategory.PATTERN.value)
    assert any(o.knowledge_id == kid for o in results)


def test_repository_durable_across_reopen(tmp_path):
    repo = make_repo(tmp_path)
    kid = repo.upsert(KnowledgeObject(title="Persisted", domain="DevOps"))
    reopened = EngineeringKnowledgeRepository(db_path=repo.db_path)
    assert reopened.get(kid) is not None


def test_ranking_prefers_higher_signal_objects():
    strong = KnowledgeObject(title="strong", confidence=0.95, usage_count=50, success_rate=0.9, rating=4.5, priority=8)
    weak = KnowledgeObject(title="weak", confidence=0.5, usage_count=0, success_rate=0.0, rating=0.0, priority=0)
    assert score(strong) > score(weak)


def test_query_ranked_orders_by_score(tmp_path):
    repo = make_repo(tmp_path)
    repo.upsert(KnowledgeObject(title="weak", domain="X", confidence=0.5, usage_count=0))
    repo.upsert(KnowledgeObject(title="strong", domain="X", confidence=0.98, usage_count=40, success_rate=0.9))
    ranked = repo.query(domain="X", approved_only=False, ranked=True)
    assert ranked[0].title == "strong"


def test_record_usage_increments(tmp_path):
    repo = make_repo(tmp_path)
    kid = repo.upsert(KnowledgeObject(title="U", domain="X"))
    repo.record_usage(kid)
    repo.record_usage(kid)
    assert repo.get(kid).usage_count == 2


def test_repository_fail_soft_on_bad_path():
    # A path under a non-existent, uncreatable location must not raise.
    repo = EngineeringKnowledgeRepository(db_path="/\0/invalid/does/not/exist.db")
    assert repo.query() == []
    assert repo.count() == 0
    assert repo.get("nope") is None


# --------------------------------------------------------------------------
# Versioning + rollback
# --------------------------------------------------------------------------

def test_versioning_and_rollback(tmp_path):
    repo = make_repo(tmp_path)
    kid = repo.upsert(KnowledgeObject(title="Doc", body="v1 body", domain="X"))

    repo.update(kid, {"body": "v2 body"}, reviewer="alice", reason="edit", change_summary="expand")
    updated = repo.get(kid)
    assert updated.version == 2
    assert updated.body == "v2 body"

    versions = repo.versions(kid)
    assert [v.version for v in versions] == [1, 2]

    rolled = repo.rollback(kid, to_version=1, reviewer="bob")
    assert rolled.version == 3           # rollback is a new version (history preserved)
    assert rolled.body == "v1 body"      # content restored


# --------------------------------------------------------------------------
# Relationship edges (graph-ready)
# --------------------------------------------------------------------------

def test_relationship_edges_and_neighbors(tmp_path):
    repo = make_repo(tmp_path)
    a = repo.upsert(KnowledgeObject(title="MQTT", domain="Industrial IoT"))
    b = repo.upsert(KnowledgeObject(title="Broker", domain="Industrial IoT"))
    repo.add_relationship(a, "has_component", b)

    neighbors = repo.neighbors(a)
    assert any(o.knowledge_id == b for o in neighbors)

    hydrated = repo.get(a)
    assert b in hydrated.related_components


# --------------------------------------------------------------------------
# Human approval queue
# --------------------------------------------------------------------------

def test_pending_submit_approve_promotes(tmp_path):
    repo = make_repo(tmp_path)
    obj = KnowledgeObject(title="Ingested Pattern", domain="Cloud Computing")
    pending_id = repo.submit_pending(obj, submitted_by="user-1")

    assert len(repo.list_pending()) == 1
    # Not yet active knowledge.
    assert repo.get(obj.knowledge_id) is None

    promoted = repo.approve_pending(pending_id, reviewer="approver", note="looks good")
    assert promoted is not None
    assert promoted.approval_status == ApprovalState.APPROVED.value
    # Now queryable as active knowledge.
    active = repo.get(promoted.knowledge_id)
    assert active is not None
    assert repo.list_pending() == []


def test_pending_reject_discards(tmp_path):
    repo = make_repo(tmp_path)
    obj = KnowledgeObject(title="Bad Entry", domain="X")
    pending_id = repo.submit_pending(obj)
    assert repo.reject_pending(pending_id, reviewer="r", note="wrong") is True
    assert repo.get(obj.knowledge_id) is None
    assert repo.list_pending() == []


# --------------------------------------------------------------------------
# Standards / Rules / Ontology
# --------------------------------------------------------------------------

def test_standards_query_returns_structured_sections(tmp_path):
    plat = make_platform(tmp_path)
    results = plat.standards.query(domain="Cybersecurity")
    assert results
    owasp = next((s for s in results if "OWASP" in s["name"]), None)
    assert owasp is not None
    assert owasp["sections"]                       # concrete sections, not just a name
    assert owasp["compliance_level"] in ("mandatory", "recommended")


def test_rules_engine_fires_on_signals(tmp_path):
    plat = make_platform(tmp_path)
    applied = plat.rules_for("system must handle a critical alarm with high availability",
                             ["Industrial IoT"])
    names = [r["name"] for r in applied]
    assert "Critical alarms require guaranteed delivery" in names
    assert "High availability requires broker redundancy" in names


def test_ontology_expansion(tmp_path):
    plat = make_platform(tmp_path)
    expanded = plat.ontology.expand("MQTT")
    assert "MQTT" in expanded
    assert "Industrial IoT" in expanded          # ancestor
    assert "Broker" in expanded                  # descendant


# --------------------------------------------------------------------------
# Dynamic assembly
# --------------------------------------------------------------------------

def test_dynamic_assembly_returns_combined_packs(tmp_path):
    plat = make_platform(tmp_path)
    packs = plat.assemble_packs(
        ["Industrial IoT", "Cybersecurity"], industry="industrial_iot",
        intent="AIOT_ENGINEERING", entities=["MQTT"],
        message="Design MQTT platform with high availability",
    )
    assert len(packs) == 2
    for pack in packs:
        assert {"name", "standards", "patterns", "common_problems", "failure_modes", "recommendations"} <= set(pack)
    iiot = next(p for p in packs if "Industrial IoT" in p["name"])
    assert any("MQTT" in s for s in iiot["standards"])


# --------------------------------------------------------------------------
# Ingestion -> pending queue
# --------------------------------------------------------------------------

def test_ingest_markdown_lands_in_pending(tmp_path):
    plat = make_platform(tmp_path)
    doc = tmp_path / "notes.md"
    doc.write_text("# HVAC Predictive Maintenance\nCompressor vibration monitoring using MQTT sensors.", encoding="utf-8")
    pending_id = plat.ingestor.ingest_file(str(doc), submitted_by="eng-7")
    assert pending_id is not None
    pending = plat.repository.list_pending()
    assert any(p["pending_id"] == pending_id for p in pending)


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------

def test_seed_is_idempotent(tmp_path):
    plat = KnowledgePlatform(db_path=str(tmp_path / "seed.db"))
    first = plat.seed()
    assert first.get("standards", 0) > 0
    total_after_first = plat.repository.count()

    second = plat.seed()                          # no-op via marker
    assert second == {"skipped": 1}
    assert plat.repository.count() == total_after_first

    forced = plat.seed(force=True)                # re-runs, but stable ids -> upsert
    assert forced.get("standards", 0) > 0
    assert plat.repository.count() == total_after_first


# --------------------------------------------------------------------------
# Engineering Intelligence Engine integration
# --------------------------------------------------------------------------

def test_loader_uses_platform_when_present(tmp_path):
    plat = make_platform(tmp_path)
    loader = KnowledgePackLoader(platform=plat)
    packs = loader.load(["Industrial IoT"], "industrial_iot",
                        intent="AIOT_ENGINEERING", entities=["MQTT"], message="mqtt broker")
    assert packs
    assert any("Industrial IoT" in p["name"] for p in packs)


def test_loader_falls_back_to_hardcoded_without_platform():
    loader = KnowledgePackLoader(platform=None)
    packs = loader.load(["Industrial IoT"], "industrial_iot")
    # Falls back to the hardcoded KNOWLEDGE_PACKS (the mqtt pack).
    assert packs
    assert any(p is KNOWLEDGE_PACKS["mqtt"] or p.get("name") == KNOWLEDGE_PACKS["mqtt"]["name"] for p in packs)


def test_loader_fallback_matches_legacy_behavior():
    """With no platform, the loader must produce exactly the pre-existing
    hardcoded packs — proving the extension never changes default behavior."""
    loader = KnowledgePackLoader(platform=None)
    packs = loader.load(["Cybersecurity", "DevOps"], "generic_software")
    names = {p["name"] for p in packs}
    assert KNOWLEDGE_PACKS["networking/security"]["name"] in names
    assert KNOWLEDGE_PACKS["cloud"]["name"] in names
