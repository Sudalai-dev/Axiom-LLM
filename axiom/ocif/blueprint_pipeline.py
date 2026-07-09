"""
The new post-reasoning output pipeline, entirely outside the internal
cognitive kernel:

    Solution Blueprint (SolutionDocument)
        -> Solution Mapping Engine        (classify content into 8 domains)
        -> Octagonal Visualization Engine (SVG / Mermaid / PlantUML / JSON graph / ReactFlow)
        -> Presentation Engine            (assemble the API response)

Every stage takes and returns already-public data. None of them ever see
CognitiveContext, EngineResult, or any internal reasoning frame — the
Octagonal Cognitive Framework's execution remains fully internal regardless
of how this pipeline is wired into a route.
"""

from typing import Any, Dict

from ocif.documents import build_generated_documents
from ocif.frames import SolutionDocument
from ocif.presentation import PresentationEngine
from ocif.roadmap import build_implementation_roadmap
from ocif.solution_mapping import SolutionMappingEngine
from ocif.visualization import OctagonalVisualizationEngine

_mapping_engine = SolutionMappingEngine()
_visualization_engine = OctagonalVisualizationEngine()


def build_solution_response(doc: SolutionDocument, markdown: str) -> Dict[str, Any]:
    """Runs the finished Solution Blueprint through Mapping -> Visualization
    -> Presentation and returns the mission's response schema (minus the
    envelope fields — session_id/citations/developer — added by the route)."""
    octagonal_model = _mapping_engine.map(doc)
    visualizations = _visualization_engine.generate(octagonal_model)
    implementation_roadmap = build_implementation_roadmap(doc.implementation_roadmap)
    generated_documents = build_generated_documents(doc, markdown)

    return PresentationEngine.assemble(
        solution_blueprint=doc.model_dump(),
        octagonal_model=octagonal_model,
        visualizations=visualizations,
        implementation_roadmap=implementation_roadmap,
        generated_documents=generated_documents,
    )
