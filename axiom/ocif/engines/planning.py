"""
Planning Engine (Engine 3) — decomposes the problem into an ordered plan.

Derives objectives, solution steps, the specialist agents required (Part E),
whether knowledge retrieval is needed, and the requirement set (FR/NFR,
constraints, assumptions) the solution will be validated against.

Reads context.project_understanding (populated upstream by
ocif/engines/project_understanding.py) alongside the shallower
ContextFrame intent/entities — industry-aware agent assignment and NFRs
come from there rather than only the narrow IT/IoT keyword lexicon.
"""

from typing import List, Optional, Tuple

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    Intent,
    Plan,
    ProjectUnderstandingFrame,
    Requirement,
    SpecialistAgent,
)

_AGENTS_BY_INTENT = {
    Intent.SOLUTION_DESIGN: [
        SpecialistAgent.ARCHITECTURE, SpecialistAgent.BACKEND, SpecialistAgent.DATABASE,
        SpecialistAgent.SECURITY, SpecialistAgent.DEVOPS, SpecialistAgent.TESTING,
    ],
    Intent.CODE_GENERATION: [
        SpecialistAgent.BACKEND, SpecialistAgent.TESTING, SpecialistAgent.DOCUMENTATION,
    ],
    Intent.DOCUMENTATION: [
        SpecialistAgent.DOCUMENTATION, SpecialistAgent.ARCHITECTURE,
    ],
    Intent.AIOT_ENGINEERING: [
        SpecialistAgent.IOT, SpecialistAgent.ARCHITECTURE, SpecialistAgent.BACKEND,
        SpecialistAgent.SECURITY, SpecialistAgent.DEVOPS, SpecialistAgent.TESTING,
    ],
    Intent.REVIEW: [
        SpecialistAgent.ARCHITECTURE, SpecialistAgent.SECURITY, SpecialistAgent.OPTIMIZATION,
    ],
    Intent.GENERAL_ENGINEERING: [
        SpecialistAgent.ARCHITECTURE, SpecialistAgent.BACKEND, SpecialistAgent.TESTING,
    ],
}

_ENTITY_AGENT_RULES = [
    ({"React", "TypeScript"}, SpecialistAgent.FRONTEND),
    ({"PostgreSQL", "MySQL", "MongoDB", "SQLite", "Database", "TimescaleDB", "InfluxDB"}, SpecialistAgent.DATABASE),
    ({"Docker", "Kubernetes", "CI/CD", "Terraform", "AWS", "Azure", "GCP"}, SpecialistAgent.DEVOPS),
    ({"MQTT", "OPC-UA", "Modbus", "IoT", "AIoT", "Sensors", "Edge Computing"}, SpecialistAgent.IOT),
    ({"OAuth2", "JWT", "TLS", "RBAC", "SSO"}, SpecialistAgent.SECURITY),
]

# Extra specialist agents by classified industry — mapped onto the existing
# closed SpecialistAgent enum (no new agent types), so e.g. a hospital or
# banking request pulls in Security/Documentation/Database attention that
# the narrow tech-keyword lexicon alone would never trigger.
_INDUSTRY_AGENT_RULES = {
    "industrial_iot": [SpecialistAgent.IOT],
    "healthcare": [SpecialistAgent.SECURITY, SpecialistAgent.DOCUMENTATION],
    "education": [SpecialistAgent.SECURITY],
    "banking_fintech": [SpecialistAgent.SECURITY, SpecialistAgent.DATABASE],
    "automotive": [SpecialistAgent.IOT],
    "agriculture": [SpecialistAgent.IOT],
    "construction": [SpecialistAgent.DOCUMENTATION],
    "retail_ecommerce": [SpecialistAgent.DATABASE],
    "logistics_supply_chain": [SpecialistAgent.DATABASE],
    "ai_ml_platform": [SpecialistAgent.RESEARCH],
}

# Extra NFRs by classified industry, appended to the 5 baseline NFRs —
# keeps compliance/domain concerns from being silently generic.
_INDUSTRY_NFR_EXTRA = {
    "healthcare": [("Compliance", "Patient-identifiable data is encrypted at rest/in transit and every access is audit-logged (HIPAA-style compliance).")],
    "education": [("Privacy", "Student records are visible only to their own faculty and guardians (FERPA-style data minimization).")],
    "banking_fintech": [("Financial Integrity", "Money-movement operations are idempotent and reconciled against an append-only ledger; AML/KYC checks are enforced, not advisory.")],
    "industrial_iot": [("Reliability", "Edge devices buffer telemetry under intermittent connectivity with at-least-once, deduplicated delivery.")],
    "construction": [("Compliance", "Site safety inspection and incident records are immutable once logged, supporting regulatory audit.")],
}


class PlanningEngine(CognitiveEngine):
    name = EngineName.PLANNING

    async def _run(self, context: CognitiveContext) -> EngineResult:
        frame = context.context
        intent = frame.intent
        entities = frame.entities
        understanding = context.project_understanding
        revision = (context.plan.revision + 1) if context.plan else 0

        objectives = self._derive_objectives(frame.subject, intent, entities, understanding)
        steps = self._derive_steps(intent)
        agents = self._assign_agents(intent, entities, understanding)
        # Knowledge retrieval is optional; reasoning is not. Retrieval is
        # required when the request names concrete technologies, references
        # prior documents/attachments worth grounding against, or when the
        # request was classified into a real industry (not the generic
        # fallback) — a hospital/school request has zero tech-keyword
        # entities but still benefits from grounding against any
        # user-uploaded domain documents, so it must not be silently
        # skipped the way it was before project understanding existed.
        required_knowledge = (
            bool(entities)
            or bool(context.perception and context.perception.attachments)
            or bool(understanding and understanding.industry not in ("generic_software", ""))
        )
        if required_knowledge and SpecialistAgent.RESEARCH not in agents:
            agents.append(SpecialistAgent.RESEARCH)
        agents.append(SpecialistAgent.VALIDATION)

        frs, nfrs = self._derive_requirements(frame, understanding)

        context.plan = Plan(
            objectives=objectives,
            steps=steps,
            required_agents=agents,
            required_knowledge=required_knowledge,
            functional_requirements=frs,
            non_functional_requirements=nfrs,
            constraints=[
                "Solution must be production-ready, not a prototype sketch.",
                "Technology choices must be justified against alternatives.",
                "Multi-environment deployment (dev/staging/prod) must be supported.",
            ],
            assumptions=[
                "Greenfield implementation unless the request references an existing system.",
                "Team is proficient in the recommended stack or willing to adopt it.",
                "Cloud or on-prem container hosting is available.",
            ],
            revision=revision,
        )

        return EngineResult(
            engine=self.name,
            summary=(
                f"Plan rev {revision}: {len(steps)} steps, {len(agents)} agents, "
                f"knowledge {'required' if required_knowledge else 'not required'}."
            ),
            payload={
                "steps": steps,
                "agents": [a.value for a in agents],
                "required_knowledge": required_knowledge,
                "revision": revision,
            },
        )

    # -- helpers ------------------------------------------------------------

    def _derive_objectives(
        self, subject: str, intent: Intent, entities: List[str],
        understanding: Optional[ProjectUnderstandingFrame] = None,
    ) -> List[str]:
        objectives = [f"Deliver a complete, implementation-ready solution for: {subject}"]
        if entities:
            objectives.append(
                f"Integrate correctly with the named technologies: {', '.join(entities[:8])}."
            )
        objectives += [
            "Cover the full expanded use-case scope, including failure, security, and operations scenarios.",
            "Provide phased implementation guidance a team can execute immediately.",
        ]
        if intent == Intent.AIOT_ENGINEERING:
            objectives.append("Ensure industrial-grade reliability for edge/device connectivity.")
        if understanding and understanding.business_problem and understanding.industry not in ("generic_software", ""):
            objectives.append(
                f"Address the classified {understanding.business_domain or understanding.industry} "
                f"business problem: {understanding.business_problem}"
            )
        return objectives

    def _derive_steps(self, intent: Intent) -> List[str]:
        base = [
            "Analyze the expanded use cases and derive functional and non-functional requirements.",
            "Select the architecture pattern and justify trade-offs against alternatives.",
            "Design components, data model, and API contracts.",
            "Define security, deployment, monitoring, and testing strategies.",
            "Assemble the phased implementation roadmap and risk assessment.",
        ]
        if intent == Intent.CODE_GENERATION:
            base.insert(2, "Produce implementation code aligned with the component design.")
        if intent == Intent.DOCUMENTATION:
            base.insert(1, "Map the requested document type to its canonical structure.")
        return base

    def _assign_agents(
        self, intent: Intent, entities: List[str],
        understanding: Optional[ProjectUnderstandingFrame] = None,
    ) -> List[SpecialistAgent]:
        agents = list(_AGENTS_BY_INTENT.get(intent, _AGENTS_BY_INTENT[Intent.GENERAL_ENGINEERING]))
        entity_set = set(entities)
        for triggers, agent in _ENTITY_AGENT_RULES:
            if triggers & entity_set and agent not in agents:
                agents.append(agent)
        if understanding:
            for agent in _INDUSTRY_AGENT_RULES.get(understanding.industry, []):
                if agent not in agents:
                    agents.append(agent)
        return agents

    def _derive_requirements(self, frame, understanding: Optional[ProjectUnderstandingFrame] = None) -> Tuple[list, list]:
        frs = [
            Requirement(
                id=f"FR-{i + 1}",
                category="functional",
                requirement=f"[{uc.id}] As {uc.actor}: {uc.scenario} — {uc.expected_behavior}",
            )
            for i, uc in enumerate(frame.use_cases)
        ]
        nfrs = [
            Requirement(id="NFR-1", category="Reliability",
                        requirement="Core flows survive single-component failure with graceful degradation."),
            Requirement(id="NFR-2", category="Security",
                        requirement="All access authenticated and authorized (least privilege); data encrypted in transit and at rest."),
            Requirement(id="NFR-3", category="Scalability",
                        requirement="Horizontal scaling of stateless services; load growth handled without redesign."),
            Requirement(id="NFR-4", category="Observability",
                        requirement="Metrics, structured logs, and distributed traces for every service; actionable alerting."),
            Requirement(id="NFR-5", category="Maintainability",
                        requirement="Modular components with typed contracts, automated tests, and CI/CD gates."),
        ]
        if understanding:
            for i, (category, requirement) in enumerate(_INDUSTRY_NFR_EXTRA.get(understanding.industry, [])):
                nfrs.append(Requirement(id=f"NFR-{6 + i}", category=category, requirement=requirement))
        return frs, nfrs
