"""
Validation Engine (Engine 7) — fail-closed solution verification.

Checks the reasoned solution against the requirements, output completeness,
and internal consistency before it may become output. Auto-corrects what it
safely can; anything else fails the run back to the kernel for
regeneration/re-planning. A solution is never shipped as-is with a
disclaimer bolted on (Master Prompt invariant B.2.4).
"""

import re
from typing import List

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    EngineStatus,
    SolutionDocument,
    ValidationResult,
)

_TEXT_SECTIONS = [
    "executive_summary", "problem_statement", "requirements_analysis",
    "recommended_solution", "architecture_overview", "component_design",
    "database_design", "api_design", "workflow", "security_architecture",
    "deployment_architecture", "monitoring_strategy", "testing_strategy",
    "final_recommendations",
]
_LIST_SECTIONS = ["technology_stack", "implementation_roadmap", "risk_assessment", "future_enhancements"]

# Internal cognitive vocabulary that must never leak into user-facing output.
_LEAK_PATTERNS = re.compile(
    r"\b(octagonal|cognitive (framework|kernel|context|trace)|perception engine|"
    r"context engine|planning engine|knowledge engine|memory engine|reasoning engine|"
    r"validation engine|experience engine|engine trace|OCIF)\b",
    re.IGNORECASE,
)


class ValidationEngine(CognitiveEngine):
    name = EngineName.VALIDATION

    async def _run(self, context: CognitiveContext) -> EngineResult:
        reasoning = context.reasoning
        checks: List[str] = []
        issues: List[str] = []
        corrections: List[str] = []

        if reasoning is None:
            context.validation = ValidationResult(
                passed=False,
                checks_performed=["reasoning-result-present"],
                issues=["No reasoning result available to validate."],
            )
            return EngineResult(
                engine=self.name,
                status=EngineStatus.FAILED,
                summary="Validation failed: nothing to validate.",
            )

        doc = reasoning.solution_draft.model_copy(deep=True)

        # 1. Completeness — every section present and non-empty.
        checks.append("section-completeness")
        for field in _TEXT_SECTIONS:
            if not (getattr(doc, field) or "").strip():
                setattr(doc, field, "Not applicable.")
                corrections.append(f"Filled empty section '{field}' with 'Not applicable.'")
        for field in _LIST_SECTIONS:
            if not getattr(doc, field):
                issues.append(f"Structured section '{field}' is empty.")

        # 2. Confidence numeric and bounded.
        checks.append("confidence-range")
        if not (0.0 <= reasoning.confidence <= 1.0):
            issues.append(f"Confidence {reasoning.confidence} outside [0,1].")

        # 3. Source integrity — no claimed grounding without actual sources.
        checks.append("source-integrity")
        knowledge = context.knowledge
        if (not knowledge or not knowledge.knowledge_used) and re.search(
            r"grounded on \d+ internal knowledge sources", doc.final_recommendations, re.IGNORECASE
        ):
            doc.final_recommendations = re.sub(
                r"\s*The design is additionally grounded on \d+ internal knowledge\s+sources\.",
                "", doc.final_recommendations,
            )
            corrections.append("Removed unsubstantiated knowledge-grounding claim.")

        # 4. Requirements coverage — roadmap must exist to carry the FRs.
        checks.append("requirements-coverage")
        if context.plan and context.plan.functional_requirements and not doc.implementation_roadmap:
            issues.append("Functional requirements exist but the roadmap is empty.")

        # 5. Diagram sanity — mermaid fences must open and close in pairs.
        checks.append("diagram-syntax")
        full_text = "\n".join(getattr(doc, f) for f in _TEXT_SECTIONS)
        if full_text.count("```") % 2 != 0:
            issues.append("Unbalanced code fences in solution text.")

        # 6. Internal-framework leak check — the octagonal machinery is
        #    invisible to users; scrub any cognitive vocabulary that leaked in.
        checks.append("internal-leak-screen")
        for field in _TEXT_SECTIONS:
            text = getattr(doc, field)
            if _LEAK_PATTERNS.search(text):
                setattr(doc, field, _LEAK_PATTERNS.sub("the platform", text))
                corrections.append(f"Scrubbed internal cognitive vocabulary from '{field}'.")

        passed = not issues
        context.validation = ValidationResult(
            passed=passed,
            checks_performed=checks,
            issues=issues,
            corrections_made=corrections,
            corrected_solution=doc if passed else None,
        )
        if passed:
            context.reasoning.solution_draft = doc

        return EngineResult(
            engine=self.name,
            status=EngineStatus.COMPLETED if passed else EngineStatus.FAILED,
            summary=(
                f"{len(checks)} checks; {len(corrections)} corrections; "
                f"{'passed' if passed else f'{len(issues)} blocking issues'}."
            ),
            payload={"passed": passed, "issues": issues, "corrections": corrections},
        )
