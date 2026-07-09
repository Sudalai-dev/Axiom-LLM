"""
Planning Engine (Engine 3) — decomposes the problem into an ordered plan.

Derives objectives, solution steps, the specialist agents required (Part E),
whether knowledge retrieval is needed, and the requirement set (FR/NFR,
constraints, assumptions) the solution will be validated against.
"""

from typing import List

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    Intent,
    Plan,
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


class PlanningEngine(CognitiveEngine):
    name = EngineName.PLANNING

    async def _run(self, context: CognitiveContext) -> EngineResult:
        frame = context.context
        intent = frame.intent
        entities = frame.entities
        revision = (context.plan.revision + 1) if context.plan else 0

        objectives = self._derive_objectives(frame.subject, intent, entities)
        steps = self._derive_steps(intent)
        agents = self._assign_agents(intent, entities)
        # Knowledge retrieval is optional; reasoning is not. Retrieval is
        # required when the request names concrete technologies or references
        # prior documents/attachments worth grounding against.
        required_knowledge = bool(entities) or bool(
            context.perception and context.perception.attachments
        )
        if required_knowledge and SpecialistAgent.RESEARCH not in agents:
            agents.append(SpecialistAgent.RESEARCH)
        agents.append(SpecialistAgent.VALIDATION)

        frs, nfrs = self._derive_requirements(frame)

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

    def _derive_objectives(self, subject: str, intent: Intent, entities: List[str]) -> List[str]:
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

    def _assign_agents(self, intent: Intent, entities: List[str]) -> List[SpecialistAgent]:
        agents = list(_AGENTS_BY_INTENT.get(intent, _AGENTS_BY_INTENT[Intent.GENERAL_ENGINEERING]))
        entity_set = set(entities)
        for triggers, agent in _ENTITY_AGENT_RULES:
            if triggers & entity_set and agent not in agents:
                agents.append(agent)
        return agents

    def _derive_requirements(self, frame) -> tuple:
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
        return frs, nfrs
