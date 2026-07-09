"""
Presentation Engine — the final assembly stage of the new output pipeline.

    Solution Blueprint Builder -> Solution Mapping Engine ->
    Octagonal Visualization Engine -> Presentation Engine -> API response

Assembles the backend response model the mission specifies:

    {
      "solution_blueprint": {...},
      "octagonal_model": {...},
      "visualizations": {"svg", "mermaid", "plantuml", "json_graph", "reactflow"},
      "implementation_roadmap": {...},
      "generated_documents": [...]
    }

Takes only already-public data (SolutionDocument + its derived domain model,
visualizations, roadmap, and documents) — never internal reasoning frames.
"""

from typing import Any, Dict, List

from ocif.documents import GeneratedDocument
from ocif.domains import OctagonalModel
from ocif.roadmap import ImplementationRoadmap


class PresentationEngine:
    """Assembles the mission's response schema from already-built parts."""

    @staticmethod
    def assemble(
        solution_blueprint: Dict[str, Any],
        octagonal_model: OctagonalModel,
        visualizations: Dict[str, Any],
        implementation_roadmap: ImplementationRoadmap,
        generated_documents: List[GeneratedDocument],
    ) -> Dict[str, Any]:
        return {
            "solution_blueprint": solution_blueprint,
            "octagonal_model": octagonal_model.model_dump(),
            "visualizations": visualizations,
            "implementation_roadmap": implementation_roadmap.model_dump(),
            "generated_documents": [d.model_dump() for d in generated_documents],
        }
