"""
Presentation Renderer — the new top-level orchestrator.

Superset of the existing `axiom.ocif.blueprint_pipeline.build_solution_response`:
keeps every field that response already returns (solution_blueprint,
octagonal_model, visualizations, implementation_roadmap, generated_documents
— unchanged, for backward compatibility) and adds the dashboard-first
payload the new product vision needs: `dashboard`, `documents_catalog`, and
`export_manifest`. Also caches the SolutionDocument so the on-demand
document/export endpoints can serve it by solution_id afterward.

    Solution Blueprint -> Solution Mapping Engine -> Octagonal Visualization
    Engine -> Dashboard Renderer + Document/Export catalogs -> Presentation
    Package (this module's output)
"""

from typing import Any, Dict

from ocif.blueprint_pipeline import build_solution_response
from ocif.domains import OctagonalModel
from ocif.frames import SolutionDocument
from ocif.renderers import document_types
from ocif.renderers import export as export_renderer
from ocif.renderers import solution_cache
from ocif.renderers.dashboard import build_dashboard
from ocif.roadmap import build_implementation_roadmap


class PresentationRenderer:
    """Builds the full Presentation Package for a finished solution."""

    @staticmethod
    def render(doc: SolutionDocument, markdown: str) -> Dict[str, Any]:
        package = build_solution_response(doc, markdown)

        octagonal_model = OctagonalModel(**package["octagonal_model"])
        roadmap = build_implementation_roadmap(doc.implementation_roadmap)
        documents_catalog = document_types.catalog()
        manifest = export_renderer.export_manifest()

        package["dashboard"] = build_dashboard(doc, octagonal_model, roadmap, documents_catalog, manifest)
        package["documents_catalog"] = documents_catalog
        package["export_manifest"] = manifest

        solution_cache.put(doc, markdown)
        return package
