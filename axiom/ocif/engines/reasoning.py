"""
Reasoning Engine (Engine 6) — the heart of Axiom.

This is the ONLY place in the platform where LLM inference happens for
solution authoring. Provider adaptation is isolated to InferenceAdapter
(ocif/inference_adapter.py, shared with the Project Understanding
classifier) so the underlying model is fully swappable (Master Prompt
invariant B.2.6).

Two reasoning paths produce the SolutionDocument draft:
  1. LLM path — the adapter asks the configured provider for the solution as
     strict JSON matching the SolutionDocument schema.
  2. SolutionSynthesizer — a deterministic engineering-reasoning fallback that
     composes a complete solution from the cognitive frames (use cases, plan,
     knowledge, memory, project understanding). It guarantees contract-valid
     output offline and is also used to fill any fields the LLM left empty.

Per-industry architecture detail (components, tech stack, ER/API/workflow
shape) lives in ocif/engines/industry_patterns.py, selected by
ProjectUnderstandingFrame.industry rather than the old narrow IT/IoT
keyword match — this file only composes those pattern fields into prose.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ocif.engine import CognitiveEngine
from ocif.engines.industry_patterns import IndustryPattern, select_pattern
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineName,
    EngineResult,
    KnowledgeFrame,
    Plan,
    ProjectUnderstandingFrame,
    ReasoningResult,
    Risk,
    RoadmapPhase,
    SolutionDocument,
    TechChoice,
)
from ocif.inference_adapter import InferenceAdapter

logger = logging.getLogger("AxiomOCIF.Reasoning")


# ---------------------------------------------------------------------------
# Deterministic solution synthesizer
# ---------------------------------------------------------------------------

class SolutionSynthesizer:
    """Composes a complete SolutionDocument from the cognitive frames."""

    def synthesize(
        self,
        frame: ContextFrame,
        plan: Plan,
        knowledge: KnowledgeFrame,
        learning: Optional[List[str]] = None,
        understanding: Optional[ProjectUnderstandingFrame] = None,
    ) -> SolutionDocument:
        pattern = select_pattern(understanding)
        title = self._title(frame)
        components = pattern.components

        doc = SolutionDocument(
            title=title,
            executive_summary=self._executive_summary(frame, pattern, understanding),
            problem_statement=self._problem_statement(frame, understanding),
            actors=list(frame.actors),
            requirements_analysis=self._requirements_analysis(frame, plan),
            recommended_solution=self._recommended_solution(pattern),
            architecture_overview=self._architecture_overview(pattern),
            technology_stack=[TechChoice(layer=l, choice=c, rationale=r) for l, c, r in pattern.stack],
            component_design=self._component_design(components),
            database_design=self._database_design(pattern),
            api_design=self._api_design(pattern),
            workflow=self._workflow(pattern),
            security_architecture=self._security_architecture(pattern),
            deployment_architecture=self._deployment_architecture(pattern),
            monitoring_strategy=self._monitoring_strategy(pattern),
            testing_strategy=self._testing_strategy(pattern),
            implementation_roadmap=self._roadmap(frame, pattern),
            risk_assessment=self._risks(pattern),
            future_enhancements=self._future(pattern),
            final_recommendations=self._final(pattern, knowledge, learning),
        )
        return doc

    # -- sections -----------------------------------------------------------

    def _title(self, frame: ContextFrame) -> str:
        subject = frame.subject.rstrip(".?! ")
        return subject[:1].upper() + subject[1:] if subject else "Engineering Solution"

    def _executive_summary(
        self, frame: ContextFrame, pattern: IndustryPattern, understanding: Optional[ProjectUnderstandingFrame]
    ) -> str:
        entities = ", ".join(frame.entities[:6]) if frame.entities else "the requested capability"
        persona = understanding.domain_expert_persona if understanding else "Solutions Architect"
        domain_line = (
            f" Prepared from the perspective of an experienced {persona} for the "
            f"{understanding.business_domain} domain." if understanding and understanding.business_domain else ""
        )
        return (
            f"This document presents a production-ready engineering solution for the stated need: "
            f"**{frame.subject}**. The recommended approach is a **{pattern.name}** built around "
            f"{entities}. The design covers the full realistic scope — primary user flows, "
            f"administration, failure handling, security, and operations — and concludes with a "
            f"phased implementation roadmap a team can execute immediately.{domain_line}"
        )

    def _problem_statement(self, frame: ContextFrame, understanding: Optional[ProjectUnderstandingFrame]) -> str:
        actors = ", ".join(frame.actors[:4])
        problem_line = (
            f"\n\n{understanding.business_problem}" if understanding and understanding.business_problem else ""
        )
        return (
            f"{frame.subject}\n\n"
            f"Stakeholders affected: {actors}. Beyond the literal request, a production system must "
            f"also handle configuration and onboarding, partial failures of dependencies, "
            f"unauthorized access attempts, and rapid diagnosis of incidents. This solution treats "
            f"those as first-class requirements rather than afterthoughts.{problem_line}"
        )

    def _requirements_analysis(self, frame: ContextFrame, plan: Plan) -> str:
        lines = [
            "The request was expanded into the complete scenario set the solution must satisfy:",
            "",
            "| # | Actor | Scenario | Expected Behavior |",
            "|---|-------|----------|-------------------|",
        ]
        for uc in frame.use_cases:
            lines.append(f"| {uc.id} | {uc.actor} | {uc.scenario} | {uc.expected_behavior} |")
        lines += [
            "",
            "**Non-functional requirements**",
            "",
            "| ID | Category | Requirement |",
            "|----|----------|-------------|",
        ]
        for nfr in plan.non_functional_requirements:
            lines.append(f"| {nfr.id} | {nfr.category} | {nfr.requirement} |")
        if plan.constraints:
            lines += ["", "**Constraints:** " + " ".join(plan.constraints)]
        if plan.assumptions:
            lines += ["", "**Assumptions:** " + " ".join(plan.assumptions)]
        return "\n".join(lines)

    _ALTERNATIVES_BY_PATTERN_KEY = {
        "industrial_iot": "a monolithic SCADA extension (poor scalability, vendor lock-in) and direct device-to-cloud HTTP polling (battery/bandwidth cost, no offline buffering)",
        "event_driven_platform": "a modular monolith (simpler initially but couples deploy cadence) and synchronous REST chaining between services (cascading failures under load)",
        "generic_software": "a microservices split (operational overhead unjustified at this scale) and a server-rendered monolith (limits interactive UX)",
        "ai_ml_platform": "fine-tuning a dedicated model (cost and staleness) and prompt-only integration without retrieval (hallucination risk on domain facts)",
        "healthcare": "a single monolithic EMR module (limits per-department scaling) and direct database access from client apps (breaks auditability/compliance)",
        "education": "a spreadsheet-based attendance process (no auditability, error-prone) and a single shared login per class (defeats individual accountability)",
        "banking_fintech": "eventual-consistency balance updates without a ledger (reconciliation nightmares) and synchronous third-party fraud calls blocking every transaction (latency/availability risk)",
    }

    def _recommended_solution(self, pattern: IndustryPattern) -> str:
        alt = self._ALTERNATIVES_BY_PATTERN_KEY.get(
            pattern.key, "simpler architectures that fail the stated non-functional requirements"
        )
        return (
            f"Adopt a **{pattern.name}**. Alternatives considered and rejected: {alt}. "
            f"The chosen pattern best balances delivery speed, operational simplicity, and the "
            f"reliability/scalability requirements derived from the scenario analysis. Each component "
            f"below is independently testable and replaceable, and the design avoids hard vendor "
            f"lock-in at every layer."
        )

    def _architecture_overview(self, pattern: IndustryPattern) -> str:
        nodes = pattern.components
        ids = [re.sub(r"[^A-Za-z0-9]", "", name)[:14] or f"C{i}" for i, (name, _) in enumerate(nodes)]
        mermaid = ["flowchart LR"]
        for (name, _), nid in zip(nodes, ids):
            mermaid.append(f'    {nid}["{name}"]')
        for a, b in zip(ids, ids[1:]):
            mermaid.append(f"    {a} --> {b}")
        narrative = "\n".join(f"- **{name}** — {desc}" for name, desc in nodes)
        return (
            f"The system is composed of the following cooperating components:\n\n{narrative}\n\n"
            "```mermaid\n" + "\n".join(mermaid) + "\n```"
        )

    def _component_design(self, components) -> str:
        lines = []
        for name, desc in components:
            lines.append(
                f"### {name}\n{desc} Exposes a narrow, typed interface; owns its configuration; "
                f"emits structured logs and metrics; fails independently without cascading."
            )
        return "\n\n".join(lines)

    def _database_design(self, pattern: IndustryPattern) -> str:
        return f"{pattern.er_notes}\n\n```mermaid\n{pattern.er_diagram}\n```"

    def _api_design(self, pattern: IndustryPattern) -> str:
        rows = [
            "| Method | Endpoint | Purpose |",
            "|--------|----------|---------|",
            "| POST | /api/v1/auth/login | Authenticate and issue JWT |",
        ] + pattern.api_rows
        return (
            "REST + JSON with OpenAPI documentation generated from typed contracts. All endpoints "
            "are versioned, authenticated (Bearer JWT), tenant-scoped, and rate-limited. Errors follow "
            "RFC 7807 problem+json.\n\n" + "\n".join(rows)
        )

    def _workflow(self, pattern: IndustryPattern) -> str:
        return f"{pattern.workflow_narrative}\n\n```mermaid\n{pattern.workflow_diagram}\n```"

    def _security_architecture(self, pattern: IndustryPattern) -> str:
        return (
            "- **Authentication:** OAuth2/JWT with short-lived access tokens and refresh rotation.\n"
            "- **Authorization:** role-based access control enforced at the API layer and row-level "
            "tenant isolation in the database.\n"
            "- **Transport:** TLS 1.2+ everywhere; internal service traffic on a private network.\n"
            "- **Secrets:** injected from a secrets manager; never committed or baked into images.\n"
            "- **Input handling:** schema validation at every boundary; parameterized queries; "
            "rate limiting and audit logging on all mutating endpoints." + pattern.security_extra
        )

    def _deployment_architecture(self, pattern: IndustryPattern) -> str:
        mermaid = (
            "flowchart TB\n"
            "    subgraph Dev[Development]\n        DC[docker-compose]\n    end\n"
            "    subgraph CI[CI/CD Pipeline]\n        T[Tests + Lint] --> B[Build Images] --> SC[Security Scan] --> RG[Registry]\n    end\n"
            "    subgraph Prod[Production Kubernetes]\n        ING[Ingress + TLS] --> SVC[Services]\n        SVC --> DB[(Managed PostgreSQL)]\n        SVC --> RD[(Redis)]\n    end\n"
            "    Dev --> CI --> Prod"
        )
        return (
            "Three environments — development (docker-compose), staging, and production (Kubernetes) — "
            "promoted through a CI/CD pipeline: tests and linting gate every merge; images are built "
            "once, scanned, and promoted immutably; production rollouts are rolling with automatic "
            "rollback on failed health checks. Configuration is environment-injected (12-factor); "
            "stateful services use managed offerings where available." + pattern.deployment_extra + "\n\n"
            "```mermaid\n" + mermaid + "\n```"
        )

    def _monitoring_strategy(self, pattern: IndustryPattern) -> str:
        return (
            "- **Metrics:** Prometheus scrapes every service (request rate, latency P50/P95/P99, error "
            "rate, queue depth, resource saturation); Grafana dashboards per component.\n"
            "- **Logs:** structured JSON logs with correlation IDs, centrally aggregated.\n"
            "- **Traces:** OpenTelemetry spans across service boundaries for end-to-end latency analysis.\n"
            "- **Alerts:** SLO-based alerting (error budget burn), paging only on user-impacting "
            "symptoms; everything else lands on a triage dashboard.\n"
            "- **Health:** liveness/readiness endpoints on every service consumed by the orchestrator."
            + pattern.monitoring_extra
        )

    def _testing_strategy(self, pattern: IndustryPattern) -> str:
        return (
            "- **Unit tests** for domain logic and pure components (fast, run on every commit).\n"
            "- **Integration tests** against real database/broker instances in containers.\n"
            "- **Contract tests** on API schemas so clients and services evolve safely.\n"
            "- **End-to-end tests** covering the primary use-case flows, including failure injection "
            "(dependency down, malformed input, unauthorized access).\n"
            "- **Performance tests** establishing baseline throughput/latency before launch; regressions "
            "gate releases.\n"
            "- CI enforces all suites plus static analysis; coverage tracked on the critical path."
            + pattern.testing_extra
        )

    def _roadmap(self, frame: ContextFrame, pattern: IndustryPattern) -> List[RoadmapPhase]:
        return [
            RoadmapPhase(phase="Phase 1 — Foundation (weeks 1-2)", items=[
                "Repository, CI/CD skeleton, environments, and coding standards.",
                "Core data model, migrations, and authentication.",
                "Walking skeleton: thinnest end-to-end slice of the primary use case deployed to staging.",
            ]),
            RoadmapPhase(phase="Phase 2 — Core capability (weeks 3-5)", items=[
                pattern.roadmap_phase2_focus,
                "Administration and configuration surfaces.",
                "Integration and contract test suites.",
            ]),
            RoadmapPhase(phase="Phase 3 — Hardening (weeks 6-7)", items=[
                "Failure handling: retries, buffering, graceful degradation, chaos tests.",
                "Security review: authorization matrix, secrets, penetration checklist.",
                "Observability: dashboards, SLOs, alert runbooks.",
            ]),
            RoadmapPhase(phase="Phase 4 — Launch & iterate (week 8+)", items=[
                "Performance baseline and capacity plan.",
                "Production rollout with rollback plan.",
                "Feedback loop: usage analytics driving the enhancement backlog.",
            ]),
        ]

    def _risks(self, pattern: IndustryPattern) -> List[Risk]:
        risks = [
            Risk(risk="Scope creep beyond the analyzed use cases", likelihood="medium", impact="medium",
                 mitigation="Change control against the requirements table; new scenarios enter the backlog, not the sprint."),
            Risk(risk="Underestimated load profile degrades latency", likelihood="medium", impact="high",
                 mitigation="Performance tests before launch; horizontal scaling designed in from Phase 1."),
            Risk(risk="Security misconfiguration in deployment", likelihood="low", impact="high",
                 mitigation="Infrastructure as code with reviewed changes; automated security scanning in CI."),
        ]
        for risk, likelihood, impact, mitigation in pattern.risks_extra:
            risks.append(Risk(risk=risk, likelihood=likelihood, impact=impact, mitigation=mitigation))
        return risks

    def _future(self, pattern: IndustryPattern) -> List[str]:
        future = [
            "Multi-region deployment for latency and disaster recovery.",
            "Self-service analytics and reporting on accumulated data.",
            "Fine-grained usage metering and cost attribution per tenant.",
        ]
        for item in reversed(pattern.future_extra):
            future.insert(0, item)
        return future

    def _final(
        self, pattern: IndustryPattern, knowledge: KnowledgeFrame,
        learning: Optional[List[str]] = None,
    ) -> str:
        grounding = (
            f" The design is additionally grounded on {len(knowledge.sources)} internal knowledge "
            f"sources." if knowledge and knowledge.knowledge_used else ""
        )
        learning_note = (
            f" This recommendation stays consistent with {len(learning)} previously validated "
            f"solution(s) to similar requests learned from past conversations."
            if learning else ""
        )
        return (
            f"Proceed with the **{pattern.name}** as specified. Start with the Phase 1 walking "
            f"skeleton to de-risk integration early, keep every component behind a typed contract so "
            f"individual choices remain replaceable, and treat the non-functional requirements as "
            f"acceptance criteria — not aspirations.{grounding}{learning_note}"
        )


# ---------------------------------------------------------------------------
# Reasoning Engine
# ---------------------------------------------------------------------------

_SOLUTION_JSON_INSTRUCTION = (
    "Respond ONLY with a JSON object matching this schema (no prose outside the JSON): "
    '{"title": str, "executive_summary": str, "problem_statement": str, '
    '"requirements_analysis": str, "recommended_solution": str, "architecture_overview": str, '
    '"technology_stack": [{"layer": str, "choice": str, "rationale": str}], '
    '"component_design": str, "database_design": str, "api_design": str, "workflow": str, '
    '"security_architecture": str, "deployment_architecture": str, "monitoring_strategy": str, '
    '"testing_strategy": str, "implementation_roadmap": [{"phase": str, "items": [str]}], '
    '"risk_assessment": [{"risk": str, "likelihood": str, "impact": str, "mitigation": str}], '
    '"future_enhancements": [str], "final_recommendations": str}. '
    "Markdown (including ```mermaid diagrams) is allowed inside string fields."
)


class ReasoningEngine(CognitiveEngine):
    name = EngineName.REASONING

    def __init__(self, inference: Optional[InferenceAdapter] = None) -> None:
        super().__init__()
        self.inference = inference or InferenceAdapter()
        self.synthesizer = SolutionSynthesizer()

    async def _run(self, context: CognitiveContext) -> EngineResult:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        learning = context.memory.learning if context.memory else []
        understanding = context.project_understanding

        # Deterministic engineering baseline — always available.
        base_doc = self.synthesizer.synthesize(frame, plan, knowledge, learning, understanding)
        provider_used = "internal-synthesizer"
        model_used = "axiom-solution-synthesizer"

        # LLM path (the only inference call site in the platform for solution authoring).
        llm_payload = await self.inference.complete(
            prompt=self._build_prompt(context), intent=context.intent
        )
        if llm_payload:
            parsed = self._extract_json(llm_payload["content"])
            if parsed:
                base_doc = self._merge(base_doc, parsed)
                provider_used = llm_payload.get("provider", "llm")
                model_used = llm_payload.get("model_used", "unknown")

        confidence = self._score_confidence(frame, knowledge, provider_used, learning)
        tradeoffs = [
            f"Chosen architecture pattern over simpler alternatives to satisfy the derived NFRs.",
            "Provider-agnostic layers preferred over managed lock-in for portability.",
            "Phased roadmap trades initial feature breadth for an early de-risked walking skeleton.",
        ]

        context.reasoning = ReasoningResult(
            solution_draft=base_doc,
            confidence=confidence,
            rationale=(
                f"Solution derived from {len(frame.use_cases)} analyzed use cases, "
                f"{len(plan.functional_requirements)} functional and "
                f"{len(plan.non_functional_requirements)} non-functional requirements"
                + (f", grounded on {len(knowledge.sources)} knowledge sources" if knowledge.knowledge_used else "")
                + "."
            ),
            tradeoffs=tradeoffs,
            provider_used=provider_used,
            model_used=model_used,
        )
        context.confidence = confidence

        return EngineResult(
            engine=self.name,
            summary=f"Solution draft composed via {provider_used} (confidence {confidence:.2f}).",
            payload={"provider": provider_used, "model": model_used, "confidence": confidence},
        )

    # -- helpers ------------------------------------------------------------

    def _build_prompt(self, context: CognitiveContext) -> str:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        memory = context.memory
        understanding = context.project_understanding

        persona = understanding.domain_expert_persona if understanding else "Solution Architect"
        parts = [
            f"You are AXIOM, an AI Engineering Solution Architecture Platform, currently acting as "
            f"an experienced {persona}. You transform engineering problems into complete, "
            f"production-ready solution blueprints written the way a specialist in this exact "
            f"industry would write them — not generic software boilerplate. You are precise, "
            f"pragmatic, and vendor-neutral.",
            f"REQUEST: {frame.subject}",
            f"INTENT: {context.intent} | ENTITIES: {', '.join(frame.entities) or 'none'}",
        ]
        if understanding:
            pu_lines = [
                f"- Industry: {understanding.industry} | Business Domain: {understanding.business_domain}",
                f"- Business Problem: {understanding.business_problem}",
                f"- Engineering Problem: {understanding.engineering_problem}",
                f"- System Type: {understanding.system_type} | Architecture Style: {understanding.architecture_style}",
                f"- Deployment Model: {understanding.deployment_model}",
            ]
            if understanding.domain_entities:
                pu_lines.append(f"- Key Domain Entities: {', '.join(understanding.domain_entities)}")
            if understanding.workflows:
                pu_lines.append(f"- Core Workflows: {', '.join(understanding.workflows)}")
            if understanding.technical_constraints or understanding.business_constraints:
                pu_lines.append(
                    "- Constraints: " + ", ".join(understanding.technical_constraints + understanding.business_constraints)
                )
            parts.append("PROJECT UNDERSTANDING:\n" + "\n".join(pu_lines))
        parts.append(
            "ANALYZED USE CASES:\n" + "\n".join(
                f"- {uc.id} [{uc.actor}] {uc.scenario} -> {uc.expected_behavior}" for uc in frame.use_cases
            )
        )
        parts.append(
            "REQUIREMENTS:\n" + "\n".join(
                f"- {r.id}: {r.requirement}" for r in plan.functional_requirements + plan.non_functional_requirements
            )
        )
        if knowledge.knowledge_used:
            parts.append("KNOWLEDGE SOURCES:\n" + "\n".join(
                f"- {s.title}: {s.excerpt[:200]}" for s in knowledge.sources
            ))
        if memory and memory.learning:
            parts.append("LEARNED FROM PAST SUCCESSFUL SOLUTIONS:\n" + "\n".join(
                f"- {entry}" for entry in memory.learning[:3]
            ))
        if memory and (memory.decisions or memory.feedback):
            parts.append("PRIOR DECISIONS/FEEDBACK:\n" + "\n".join(
                f"- {d}" for d in (memory.decisions[-3:] + memory.feedback[-3:])
            ))
        parts.append(_SOLUTION_JSON_INSTRUCTION)
        return "\n\n".join(parts)

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        candidates = re.findall(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL) or [content]
        for candidate in candidates:
            try:
                data = json.loads(candidate.strip())
                if isinstance(data, dict) and "executive_summary" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _merge(self, base: SolutionDocument, parsed: Dict[str, Any]) -> SolutionDocument:
        """LLM fields win when present and non-empty; synthesizer fills gaps."""
        data = base.model_dump()
        for key, value in parsed.items():
            if key in data and value:
                data[key] = value
        try:
            return SolutionDocument(**data)
        except Exception as exc:
            logger.warning(f"LLM solution merge failed, keeping synthesized draft: {exc}")
            return base

    def _score_confidence(
        self, frame, knowledge: KnowledgeFrame, provider: str, learning: Optional[List[str]] = None
    ) -> float:
        score = 0.62
        if frame.entities:
            score += min(0.12, 0.02 * len(frame.entities))
        if frame.use_cases:
            score += 0.06
        if knowledge.knowledge_used:
            score += 0.10 * knowledge.confidence
        if provider != "internal-synthesizer":
            score += 0.08
        if learning:
            score += min(0.06, 0.02 * len(learning))
        return round(min(score, 0.98), 2)
