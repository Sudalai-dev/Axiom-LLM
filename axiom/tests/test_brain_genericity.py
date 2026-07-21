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
    Blueprint,
    CognitiveContext,
    ContextFrame,
    Diagram,
    EngineStatus,
    KnowledgeFrame,
    Plan,
    ProjectUnderstandingFrame,
    ReasoningResult,
    Risk,
    RoadmapPhase,
    SolutionDocument,
    TechChoice,
)


def _run_engine(platform, task, entities):
    engine = EngineeringIntelligenceEngine(knowledge_platform=platform)
    ctx = CognitiveContext(task=task, user_id="u1")
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


def test_phase5_entity_driven_er_diagram():
    """Diagrams (Charter §6): the ER data model's tables ARE the request's real
    entities, so two requests yield structurally different ER diagrams."""
    synth = SolutionSynthesizer()
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()

    def _db(entities):
        frame = ContextFrame(intent="solution_design", entities=entities,
                             domain_entities=entities, actors=["User"], use_cases=[])
        return synth.synthesize(
            frame, plan, kf, None, ProjectUnderstandingFrame(industry="generic_software"),
        ).database_design

    hospital = _db(["Patient", "Bed", "Ward", "Clinician"])
    library = _db(["Book", "Member", "Loan", "Author"])

    assert "PATIENT" in hospital.upper() and "BED" in hospital.upper()
    assert "BOOK" in library.upper() and "MEMBER" in library.upper()
    assert hospital != library  # structurally different ER diagrams
    # Too few entities → honest fallback to the industry pattern's ER (no invention).
    assert "erdiagram" in _db(["Widget"]).lower()


def test_phase6_recall_reuses_prior_design():
    """Learning loop (Charter §8): a recalled prior validated solution is
    genuinely REUSED — named in the recommendation, reconciled as a roadmap
    deliverable, and its trade-offs carried into the risk register — so a second
    similar request measurably differs from the same request seen cold."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["patient", "record"],
                         actors=["Clinician"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()
    understanding = ProjectUnderstandingFrame(industry="healthcare")

    cold = synth.synthesize(frame, plan, kf, None, understanding)
    recalled = [{
        "title": "Patient Records Portal",
        "intent": "solution_design",
        "confidence": 0.91,
        "entities": ["patient", "record"],
        "tradeoffs": ["Chose Postgres over Mongo for transactional integrity."],
    }]
    warm = synth.synthesize(frame, plan, kf, None, understanding, recalled=recalled)

    # The prior design is named and reused, not re-derived from the pattern.
    assert "Patient Records Portal" in warm.recommended_solution
    assert "reuses and adapts" in warm.recommended_solution.lower()
    assert "Patient Records Portal" not in cold.recommended_solution
    # Reconcile-with-prior is an explicit Phase-1 roadmap deliverable.
    p1_items = warm.implementation_roadmap[0].items
    assert any("Patient Records Portal" in it for it in p1_items)
    # The prior trade-off is carried into the risk register as a known decision.
    warm_risks = " ".join(r.risk for r in warm.risk_assessment)
    assert "Postgres" in warm_risks
    # Cold vs warm are measurably different.
    assert warm.recommended_solution != cold.recommended_solution
    assert len(warm.risk_assessment) > len(cold.risk_assessment)


def test_phase6_recall_without_entity_overlap_is_not_falsely_reused():
    """`find_similar` can return a same-intent recall with ZERO entity overlap
    (two unrelated projects sharing the 'solution_design' intent). Such a recall
    must NOT be presented as 'reused and adapted' — that would be a false claim."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["turbine", "rotor"],
                         actors=["Engineer"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()
    understanding = ProjectUnderstandingFrame(industry="generic_software")

    unrelated = [{
        "title": "Cafeteria Menu Board",
        "intent": "solution_design",
        "confidence": 0.88,
        "entities": ["menu", "meal"],   # no overlap with turbine/rotor
        "tradeoffs": ["Chose static hosting."],
    }]
    doc = synth.synthesize(frame, plan, kf, None, understanding, recalled=unrelated)
    assert "Cafeteria Menu Board" not in doc.recommended_solution
    assert "reuses and adapts" not in doc.recommended_solution.lower()


def test_phase5_degenerate_entities_fall_back_without_crashing():
    """Two 'entities' that sanitize to no valid table name must not crash the ER
    builder (no IndexError on the hub); the data model falls back to the pattern
    ER honestly rather than emitting a degenerate diagram."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["!!!", "@@@"],
                         domain_entities=["!!!", "@@@"], actors=["User"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    doc = synth.synthesize(frame, plan, KnowledgeFrame(), None,
                           ProjectUnderstandingFrame(industry="generic_software"))
    assert "erdiagram" in doc.database_design.lower()   # valid fallback ER, no crash
    assert SolutionSynthesizer._entity_er_mermaid(["!!!", "@@@"]) == ""


def test_phase6_feedback_shifts_output():
    """Explicit user feedback must shift the next solution: each note lands on
    the risk register as a must-address item (negative → high likelihood)."""
    synth = SolutionSynthesizer()
    frame = ContextFrame(intent="solution_design", entities=["portal"], actors=["User"], use_cases=[])
    plan = Plan(functional_requirements=[], non_functional_requirements=[])
    kf = KnowledgeFrame()
    understanding = ProjectUnderstandingFrame(industry="generic_software")

    base = synth.synthesize(frame, plan, kf, None, understanding)
    feedback = [{"rating": -1, "note": "The previous roadmap underestimated data migration effort."}]
    shifted = synth.synthesize(frame, plan, kf, None, understanding, feedback_signals=feedback)

    base_risks = " ".join(r.risk for r in base.risk_assessment)
    shifted_risks = [r for r in shifted.risk_assessment if "data migration effort" in r.risk]
    assert "data migration effort" not in base_risks
    assert len(shifted_risks) == 1
    assert shifted_risks[0].likelihood == "high"  # negative feedback → urgent


def test_phase6_learning_loop_end_to_end(tmp_path):
    """Full loop through the kernel: the same request run twice against a durable
    store must, on the SECOND run, recall and reuse the first's validated design
    (the first run had nothing to recall)."""
    from memory.learning_store import LearningStore
    from ocif import OctagonalKernel
    from ocif.engines.memory import MemoryEngine

    store = LearningStore(db_path=str(tmp_path / "learn.db"))
    kernel = OctagonalKernel(memory=MemoryEngine(learning_store=store))
    req = ("Design a hospital patient records portal that stores medication history "
           "for clinicians with appointment scheduling")

    first = asyncio.run(kernel.process(req, user_id="t9", project="p9", conversation_id="c1"))
    second = asyncio.run(kernel.process(req, user_id="t9", project="p9", conversation_id="c2"))

    assert not first.is_conversational and not second.is_conversational
    first_rec = first.solution_json["recommended_solution"].lower()
    second_rec = second.solution_json["recommended_solution"].lower()
    assert "reuses and adapts" not in first_rec   # nothing to recall yet
    assert "reuses and adapts" in second_rec       # second reuses the first


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


# ---------------------------------------------------------------------------
# Phase 7 — Self-check (Charter §9): the Validation engine rejects/repairs
# generic-template output for a concrete request, and passes a genuinely
# generic one cleanly.
# ---------------------------------------------------------------------------

def _validate_draft(draft: SolutionDocument, task: str):
    from ocif.engines.validation import ValidationEngine

    ctx = CognitiveContext(task=task)
    ctx.reasoning = ReasoningResult(solution_draft=draft, confidence=0.8)
    asyncio.run(ValidationEngine()._run(ctx))
    return ctx.validation, ctx.reasoning.solution_draft


def _complete_draft(**overrides) -> SolutionDocument:
    """A structurally complete draft (all list sections filled) so only the
    genericity self-check under test drives the verdict."""
    base = dict(
        title="Solution",
        executive_summary="This document presents a production-ready engineering solution.",
        problem_statement="Build a system that satisfies the stated requirements.",
        recommended_solution="Adopt a standard layered architecture with typed contracts.",
        database_design="A normalized relational store with audit columns.",
        technology_stack=[TechChoice(layer="API", choice="FastAPI", rationale="typed, async")],
        implementation_roadmap=[RoadmapPhase(phase="Phase 1", items=["Foundation"])],
        risk_assessment=[Risk(risk="Scope creep", mitigation="Change control")],
        future_enhancements=["Multi-region deployment"],
    )
    base.update(overrides)
    return SolutionDocument(**base)


def test_phase7_generic_output_for_concrete_request_is_flagged_and_covered():
    """A concrete request (real entities) whose draft mentions none of them has
    collapsed onto a generic template. The self-check must repair the narrative
    to cover the entities and record an `accepted-with-warning` terminal state."""
    draft = _complete_draft(domain_entities=["Turbine", "Rotor", "Bearing"])
    verdict, covered = _validate_draft(draft, task="Design a turbine condition monitor")

    assert verdict.passed                       # repaired, not fail-looped
    assert verdict.terminal_state == "accepted-with-warning"
    assert verdict.warnings
    # The real entities now surface in the narrative anchors.
    assert "Turbine" in covered.executive_summary
    assert "Turbine" in covered.recommended_solution


def test_phase7_generic_request_passes_clean():
    """A genuinely generic request (no concrete entities) has nothing to cover —
    it must pass with a clean `accepted` state and no warnings."""
    draft = _complete_draft(domain_entities=[])
    verdict, _ = _validate_draft(draft, task="Please build a system.")

    assert verdict.passed
    assert verdict.terminal_state == "accepted"
    assert not verdict.warnings


def test_phase7_covered_concrete_request_is_not_flagged():
    """A concrete request whose draft ALREADY reflects its entities must pass
    clean — the self-check only fires on genuine genericity, never as noise."""
    draft = _complete_draft(
        domain_entities=["Patient", "Appointment"],
        executive_summary="A portal managing Patient records and Appointment scheduling.",
        recommended_solution="Adopt a layered architecture around Patient and Appointment domains.",
    )
    verdict, _ = _validate_draft(draft, task="Design a patient appointment portal")

    assert verdict.passed
    assert verdict.terminal_state == "accepted"
    assert not verdict.warnings


# ---------------------------------------------------------------------------
# Phase 5 (diagram-only directive) — Validation's DIAGRAM self-check. The
# primary output is the Blueprint, so validation must guard diagram grounding:
# never ship a RENDERED-but-ungrounded diagram, and flag a concrete request
# whose diagrams reflect none of its entities. Fail-soft (warn/correct, never
# hard-block), mirroring the prose self-check above.
# ---------------------------------------------------------------------------

def _validate_with_blueprint(draft: SolutionDocument, blueprint: Blueprint, task: str):
    from ocif.engines.validation import ValidationEngine

    ctx = CognitiveContext(task=task)
    ctx.reasoning = ReasoningResult(solution_draft=draft, confidence=0.8)
    ctx.metadata["blueprint"] = blueprint.model_dump()
    asyncio.run(ValidationEngine()._run(ctx))
    return ctx.validation, ctx.metadata["blueprint"]


def test_phase5_ungrounded_rendered_diagram_demoted_to_empty():
    """A diagram marked RENDERED but not grounded must never ship — the
    self-check demotes it to an honest EMPTY and records the correction."""
    bp = Blueprint(diagrams=[
        Diagram(view="reasoning", label="Reasoning", diagram_type="class",
                code="classDiagram\n    class Foo", nodes=["Foo"],
                provider_used="local-llm:x", grounded=False, status="RENDERED"),
    ])
    draft = _complete_draft(domain_entities=[])   # isolate: no prose check noise
    verdict, out = _validate_with_blueprint(draft, bp, task="Design a system")

    assert verdict.passed                                  # fail-soft, not blocked
    assert verdict.terminal_state == "accepted-with-warning"
    assert any("dropped to EMPTY" in w for w in verdict.warnings)
    assert out["diagrams"][0]["status"] == "EMPTY"
    assert out["diagrams"][0]["code"] == ""


def test_phase5_concrete_request_with_no_entity_grounding_is_flagged():
    """A concrete request whose diagrams ground only on generic primitives (no
    real entity) has collapsed onto generic diagrams — flag it (accepted-with-
    warning), even though the prose narrative covers the entities cleanly."""
    bp = Blueprint(diagrams=[
        Diagram(view="planning", label="Planning", diagram_type="flowchart",
                code="flowchart LR\n    n0[\"System\"]", nodes=["System"],
                provider_used="internal-builder", grounded=True, status="RENDERED"),
    ])
    draft = _complete_draft(
        domain_entities=["Turbine", "Rotor"],
        executive_summary="A monitor for the Turbine and its Rotor.",
        recommended_solution="A layered design around the Turbine and Rotor.",
    )
    verdict, _ = _validate_with_blueprint(draft, bp, task="Design a turbine monitor")

    assert verdict.passed
    assert verdict.terminal_state == "accepted-with-warning"
    assert any("reflected none of the request's entities" in w for w in verdict.warnings)


def test_phase5_entity_grounded_diagrams_pass_clean():
    """A concrete request whose diagrams ground in its real entities passes
    clean — the diagram self-check fires only on genuine genericity."""
    bp = Blueprint(diagrams=[
        Diagram(view="knowledge", label="Knowledge", diagram_type="er",
                code="erDiagram\n    PATIENT {\n        string id\n    }", nodes=["Patient"],
                provider_used="internal-builder", grounded=True, status="RENDERED"),
    ])
    draft = _complete_draft(
        domain_entities=["Patient", "Record"],
        executive_summary="A portal for Patient and Record management.",
        recommended_solution="A layered design around Patient and Record domains.",
    )
    verdict, _ = _validate_with_blueprint(draft, bp, task="Design a patient records portal")

    assert verdict.passed
    assert verdict.terminal_state == "accepted"
    assert not verdict.warnings
