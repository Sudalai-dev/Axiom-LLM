"""
Experience Engine (Engine 8) — output formatting and delivery.

Renders the validated SolutionDocument as the user-facing markdown document
(the ONLY artifact a normal user ever sees) and assembles the machine-readable
solution JSON plus the developer-mode-only CognitiveTrace.

The octagonal machinery never appears in the user-facing markdown.
"""

from typing import Any, Dict

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    CognitiveTrace,
    EngineName,
    EngineResult,
    SolutionDocument,
)
from ocif.octagon import build_octagon_svg


class ExperienceEngine(CognitiveEngine):
    name = EngineName.EXPERIENCE

    async def _run(self, context: CognitiveContext) -> EngineResult:
        doc = context.reasoning.solution_draft
        markdown = self.render_markdown(doc)

        context.execution_state["solution_markdown"] = markdown
        context.execution_state["solution_json"] = doc.model_dump()

        return EngineResult(
            engine=self.name,
            summary=f"Rendered solution document '{doc.title}' ({len(markdown)} chars).",
            payload={"solution_id": doc.solution_id, "title": doc.title},
        )

    # -- rendering ------------------------------------------------------------

    @staticmethod
    def render_markdown(doc: SolutionDocument) -> str:
        stack_rows = "\n".join(
            f"| {t.layer} | {t.choice} | {t.rationale} |" for t in doc.technology_stack
        )
        roadmap = "\n\n".join(
            f"**{p.phase}**\n" + "\n".join(f"- {item}" for item in p.items)
            for p in doc.implementation_roadmap
        )
        risks = "\n".join(
            f"| {r.risk} | {r.likelihood} | {r.impact} | {r.mitigation} |"
            for r in doc.risk_assessment
        )
        future = "\n".join(f"- {item}" for item in doc.future_enhancements)

        return f"""# {doc.title}

## Executive Summary
{doc.executive_summary}

## Problem Statement
{doc.problem_statement}

## Requirements Analysis
{doc.requirements_analysis}

## Recommended Solution
{doc.recommended_solution}

## Architecture Overview
{doc.architecture_overview}

## Technology Stack
| Layer | Choice | Rationale |
|-------|--------|-----------|
{stack_rows}

## Component Design
{doc.component_design}

## Database Design
{doc.database_design}

## API Design
{doc.api_design}

## Workflow
{doc.workflow}

## Security Architecture
{doc.security_architecture}

## Deployment Architecture
{doc.deployment_architecture}

## Monitoring Strategy
{doc.monitoring_strategy}

## Testing Strategy
{doc.testing_strategy}

## Implementation Roadmap
{roadmap}

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
{risks}

## Future Enhancements
{future}

## Final Recommendations
{doc.final_recommendations}
"""

    # -- developer-mode trace ---------------------------------------------------

    @staticmethod
    def build_trace(context: CognitiveContext) -> CognitiveTrace:
        """Assembles the developer/admin-only cognitive execution trace,
        including the octagon visualization of the 8-engine execution."""
        return CognitiveTrace(
            correlation_id=context.correlation_id,
            engine_timeline=list(context.engine_trace),
            intent=context.intent,
            entities=list(context.entities),
            use_cases=list(context.context.use_cases) if context.context else [],
            plan=context.plan,
            knowledge_sources=list(context.knowledge.sources) if context.knowledge else [],
            validation_report=context.validation,
            confidence=context.confidence,
            reasoning_rationale=context.reasoning.rationale if context.reasoning else "",
            reasoning_thinking=context.reasoning.thinking if context.reasoning else "",
            tradeoffs=list(context.reasoning.tradeoffs) if context.reasoning else [],
            provider_used=context.reasoning.provider_used if context.reasoning else "",
            octagon_svg=build_octagon_svg(context.engine_trace, confidence=context.confidence),
            diagram_usage=list(context.metadata.get("diagram_usage", [])),
            project_understanding=context.project_understanding,
            engineering_intelligence=dict(context.metadata.get("engineering_intelligence", {})),
        )
