"""
Renderers — each consumes ONLY the Solution Blueprint (SolutionDocument) or
things derived from it, and produces one facet of the Presentation Package:

- dashboard.py        -> DashboardRenderer (build_dashboard): the lightweight, text-reduced primary view
- document_types.py   -> DocumentRenderer (catalog/render): BRD/PRD/SRS/HLD/LLD/... + OpenAPI, on demand
- export.py           -> ExportRenderer (export_manifest/to_html/to_json): downloadable formats
- solution_cache.py   -> ephemeral solution_id -> (SolutionDocument, markdown) lookup for on-demand rendering
- presentation.py     -> PresentationRenderer: orchestrates all of the above into the final response
"""

from ocif.renderers.presentation import PresentationRenderer

__all__ = ["PresentationRenderer"]
