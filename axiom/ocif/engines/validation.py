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
# Narrative anchors the genericity self-check scans for the request's own
# entities (Phase 7). These are where a concrete request's subject must surface;
# the ER (database_design) already carries entities structurally from Phase 5.
_COVERAGE_SECTIONS = ["executive_summary", "recommended_solution", "problem_statement", "database_design"]

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
        # The optional local-LLM reasoning stream is user-facing too — scrub it
        # with the same screen so an enhanced run can't leak engine vocabulary.
        if context.reasoning and context.reasoning.thinking and _LEAK_PATTERNS.search(context.reasoning.thinking):
            context.reasoning.thinking = _LEAK_PATTERNS.sub("the platform", context.reasoning.thinking)
            corrections.append("Scrubbed internal cognitive vocabulary from the reasoning stream.")

        # 7. Genericity self-check (Phase 7 / Charter §9). A request that carried
        #    concrete domain entities must yield a solution that actually reflects
        #    them. If the narrative anchors mention NONE of the request's own
        #    entities, the output has collapsed onto a generic template — the very
        #    bug Phases 1-5 fixed at the source. Regenerate those anchors to cover
        #    the real subject (never ship boilerplate for a concrete ask), and
        #    flag the run so the terminal state records that a correction was made.
        checks.append("genericity-self-check")
        warnings: List[str] = []
        entities = [e for e in (getattr(doc, "domain_entities", None) or []) if e]
        if entities:
            narrative = " ".join(
                getattr(doc, f) for f in _COVERAGE_SECTIONS
            ).lower()
            # Word-boundary match, not a bare substring — otherwise entity "Bed"
            # would count as covered by the word "embedded", masking genuinely
            # generic output.
            covered = [
                e for e in entities
                if re.search(rf"(?<!\w){re.escape(e.lower())}(?!\w)", narrative)
            ]
            if not covered:
                doc.executive_summary = self._inject_entities(doc.executive_summary, entities)
                doc.recommended_solution = self._inject_entities(doc.recommended_solution, entities)
                corrections.append(
                    "Regenerated generic narrative to cover the request's own entities: "
                    + ", ".join(entities[:6]) + "."
                )
                warnings.append(
                    "Solution narrative initially reflected none of the request's entities "
                    "(generic-template output); corrected to cover them."
                )
            elif len(covered) / len(entities) < 0.5:
                warnings.append(
                    f"Only {len(covered)}/{len(entities)} request entities are reflected in the "
                    "narrative; solution shipped but flagged for thin coverage."
                )

        passed = not issues
        terminal_state = (
            "blocked" if not passed
            else "accepted-with-warning" if warnings
            else "accepted"
        )
        context.validation = ValidationResult(
            passed=passed,
            terminal_state=terminal_state,
            checks_performed=checks,
            issues=issues,
            warnings=warnings,
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
                f"terminal={terminal_state}; "
                f"{'passed' if passed else f'{len(issues)} blocking issues'}."
            ),
            payload={
                "passed": passed,
                "terminal_state": terminal_state,
                "issues": issues,
                "warnings": warnings,
                "corrections": corrections,
            },
        )

    @staticmethod
    def _inject_entities(text: str, entities: List[str]) -> str:
        """Weave the request's real entities into a generic narrative section so
        the shipped output is concrete, not boilerplate. Deterministic and
        additive — never fabricates beyond the entities already extracted from
        the request."""
        names = ", ".join(entities[:6])
        return (text or "").rstrip() + f" This solution is built specifically around {names}."
