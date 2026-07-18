"""Brain genericity (Phase 2/3) — the deterministic synthesizer must produce
REQUEST-SPECIFIC output, not a frozen per-industry template.

Two requests that resolve to the same industry but fire different engineering
rules must differ in the sections those rules feed (security, recommended
solution, risk), while a request with no platform knowledge must fall back to
exactly the prior industry-pattern behaviour (backward compatibility).
"""

import asyncio

from ecosystem import KnowledgePlatform
from ocif.engines.context import ContextEngine
from ocif.engines.engineering_intelligence import (
    EngineeringIntelligenceEngine,
    SolutionSynthesizer,
)
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineStatus,
    KnowledgeFrame,
    Plan,
    ProjectUnderstandingFrame,
)


def _run_engine(platform, task, entities):
    engine = EngineeringIntelligenceEngine(knowledge_platform=platform)
    ctx = CognitiveContext(task=task, tenant_id="t1", user_id="u1")
    ctx.context = ContextFrame(intent="solution_design", entities=entities, actors=["User"], use_cases=[])
    ctx.plan = Plan(functional_requirements=[], non_functional_requirements=[])
    ctx.project_understanding = ProjectUnderstandingFrame(
        industry="healthcare",
        business_domain="Healthcare System",
        domain_expert_persona="Healthcare Solutions Architect",
    )
    asyncio.run(engine._run(ctx))
    return ctx.reasoning.solution_draft


def _entity_set(text):
    return {e.lower() for e in ContextEngine()._extract_entities(text.lower())}


def test_phase1_domain_entities_differentiate():
    """Comprehension (Charter §3): two same-industry requests must yield
    materially different entity sets — target Jaccard < 0.5 — because the
    concrete domain nouns are now harvested, not just shared tech keywords."""
    a = _entity_set("A hospital patient records portal storing medication history for clinicians.")
    b = _entity_set("A cafeteria menu board showing daily meals and prices to campus visitors.")
    assert a and b
    jaccard = len(a & b) / len(a | b)
    assert jaccard < 0.5, f"entity sets too similar (Jaccard={jaccard:.2f}): {a} vs {b}"
    # The concrete domain nouns are actually captured (not just tech terms).
    assert "patient" in a
    assert "cafeteria" in b or "menu" in b


def test_phase1_generic_request_stays_generic():
    """A request with no concrete nouns must not manufacture entities from
    generic filler (Charter §9: don't force unsupported variation)."""
    ents = _entity_set("Please help me build a system.")
    assert ents == set()  # 'help/build/system' are all stopwords → no fake entities


def test_same_industry_requests_diverge(tmp_path):
    platform = KnowledgePlatform(db_path=str(tmp_path / "kp.db"))
    platform.seed()

    # Both are "healthcare", but only A carries PHI/payment signals that fire the
    # encryption + OWASP rules and pull in HIPAA/PCI compliance.
    phi = _run_engine(
        platform,
        "A patient records portal that stores PHI and payment card details for clinicians.",
        entities=["PHI", "patient", "payment"],
    )
    menu = _run_engine(
        platform,
        "A cafeteria menu board that displays today's meals to visitors.",
        entities=["menu", "meal"],
    )

    # The rule-fed sections must differ between the two requests.
    assert phi.security_architecture != menu.security_architecture
    assert phi.recommended_solution != menu.recommended_solution
    assert phi.risk_assessment != menu.risk_assessment

    # And the PHI request must actually contain the fired-rule / compliance content.
    assert "encrypt" in phi.security_architecture.lower()
    risk_text = " ".join(r.risk for r in phi.risk_assessment).lower()
    assert "compliance" in risk_text or "hipaa" in risk_text or "pci" in risk_text


def test_no_platform_knowledge_is_backward_compatible():
    """With no standards/rules supplied, every section equals the pre-Phase-2
    industry-pattern output (empty enrichment adds nothing)."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["widget"], actors=["User"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()
    understanding = ProjectUnderstandingFrame(industry="generic_software")

    baseline = synth.synthesize(frame, plan, kf, None, understanding)
    enriched_empty = synth.synthesize(
        frame, plan, kf, None, understanding,
        platform_standards=[], rules_applied=[], domains=["Software Engineering"],
    )
    # Passing empty knowledge must not change any rule-fed section.
    assert baseline.security_architecture == enriched_empty.security_architecture
    assert baseline.recommended_solution == enriched_empty.recommended_solution
    assert baseline.risk_assessment == enriched_empty.risk_assessment
    assert baseline.architecture_overview == enriched_empty.architecture_overview


def test_fired_rules_reach_sections_directly():
    """A hand-built security rule + mandatory standard must surface in the
    security, risk, and recommendation sections."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["PHI"], actors=["Clinician"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()
    understanding = ProjectUnderstandingFrame(industry="healthcare")

    rules = [{
        "name": "Sensitive data must be encrypted at rest",
        "domain": "Cybersecurity",
        "then": "Encrypt sensitive data at rest (AES-256) and in transit (TLS 1.2+).",
        "rationale": "HIPAA mandates encryption for PHI.",
        "standards": ["HIPAA", "PCI-DSS 4.0"],
    }]
    standards = [{"name": "HIPAA", "compliance_level": "mandatory", "domains": ["Cybersecurity"]}]

    doc = synth.synthesize(
        frame, plan, kf, None, understanding,
        platform_standards=standards, rules_applied=rules, domains=["Cybersecurity"],
    )
    assert "encrypted at rest" in doc.security_architecture.lower() or "aes-256" in doc.security_architecture.lower()
    assert "HIPAA" in doc.recommended_solution
    risk_text = " ".join(r.risk for r in doc.risk_assessment)
    assert "HIPAA" in risk_text and "PCI-DSS 4.0" in risk_text


def test_phase4_human_gated_rule_growth(tmp_path):
    """A proposed rule must NOT fire until approved; once approved it fires on
    the next request with no restart (Phase 4 / Charter §1.3)."""
    platform = KnowledgePlatform(db_path=str(tmp_path / "kp.db"))
    platform.seed()

    msg = "Design a widget-tracking service for our loomweaver assembly line."
    domains, entities = ["Software Engineering"], ["loomweaver", "widget"]

    # Baseline: the novel term fires nothing.
    assert platform.rules_for(msg, domains, "", entities) == []

    # Propose a rule keyed on the novel term → it goes to the pending queue and
    # STILL does not fire (human-gated).
    pending_id = platform.rules.propose(
        name="Loomweaver lines need vibration monitoring",
        when=["loomweaver"],
        then="Attach vibration sensors and stream to a time-series store.",
        rationale="Loomweaver bearings fail silently without trend monitoring.",
        domain="Industrial IoT",
        standards=["ISA-95"],
    )
    assert pending_id
    assert platform.rules_for(msg, domains, "", entities) == []  # not yet approved

    # Approve it → it must now fire immediately.
    obj = platform.repository.approve_pending(pending_id, reviewer="admin")
    assert obj is not None
    fired = platform.rules_for(msg, domains, "", entities)
    names = [r["name"] for r in fired]
    assert "Loomweaver lines need vibration monitoring" in names

    # And it must reach the composed solution's architecture (design rule).
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=entities, actors=["Operator"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    doc = synth.synthesize(
        frame, plan, KnowledgeFrame(), None,
        ProjectUnderstandingFrame(industry="manufacturing"),
        platform_standards=[], rules_applied=fired, domains=domains,
    )
    assert "vibration" in doc.architecture_overview.lower()
