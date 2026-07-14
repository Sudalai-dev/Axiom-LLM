"""
Dynamic Planning Engine — Phase 5.

Decides WHAT should be generated before generation begins, by reading the
Project Intelligence Model (ProjectUnderstandingFrame) and the selected
IndustryPattern (ocif/engines/industry_patterns.py) — never raw user text.

This is deliberately additive/advisory, not a gate: the existing fixed
document catalog (ocif/renderers/document_types.py, 15 types) and the 8
project-specific diagrams (ocif/project_diagrams.py, Phase 3) stay complete
and predictable for every request — CLAUDE.md documents this as a standing
invariant ("documents/exports are rendered on demand... every response
carries only catalogs"). GenerationPlan instead prioritizes/recommends
within that fixed surface, and — like the rest of the pre-inference
pipeline's provenance (domains/experts/standards) — is surfaced only in the
developer-mode CognitiveTrace, never in normal user-facing output.

Covers the five planner responsibilities from the request:
  - Document Planner   -> document_focus   (from recommended_documents)
  - Diagram Planner     -> diagram_focus    (from recommended_diagrams;
                           DiagramPlanner in this same module already covers
                           the "which diagram names to ask the LLM for" half)
  - Report Planner      -> report_plan      (from required_reports)
  - Image Planner       -> image_plan       (from required_images — no image
                           generation engine exists yet, so this stays
                           descriptive/advisory, not a fabricated capability)
  - Architecture Planner -> architecture_plan (style/deployment/components
                           from the selected IndustryPattern)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ocif.engines.industry_patterns import IndustryPattern
from ocif.frames import ProjectUnderstandingFrame


@dataclass
class GenerationPlan:
    document_focus: List[str] = field(default_factory=list)
    diagram_focus: List[str] = field(default_factory=list)
    report_plan: List[str] = field(default_factory=list)
    image_plan: List[str] = field(default_factory=list)
    architecture_plan: Dict[str, Any] = field(default_factory=dict)


class GenerationPlanner:
    """Builds a GenerationPlan from already-computed Project Intelligence."""

    def plan(
        self,
        understanding: Optional[ProjectUnderstandingFrame],
        pattern: IndustryPattern,
    ) -> GenerationPlan:
        image_plan = [
            f"{image} (descriptive only — no image-generation engine is wired yet)"
            for image in (understanding.required_images if understanding else [])
        ]
        return GenerationPlan(
            document_focus=list(understanding.recommended_documents) if understanding else [],
            diagram_focus=list(understanding.recommended_diagrams) if understanding else [],
            report_plan=list(understanding.required_reports) if understanding else [],
            image_plan=image_plan,
            architecture_plan={
                "architecture_style": understanding.architecture_style if understanding else "",
                "deployment_model": understanding.deployment_model if understanding else "",
                "system_type": understanding.system_type if understanding else "",
                "key_components": [name for name, _ in pattern.components[:6]],
            },
        )
