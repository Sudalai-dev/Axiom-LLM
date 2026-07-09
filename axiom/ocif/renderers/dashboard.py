"""
Dashboard Renderer.

Assembles the lightweight "Solution Dashboard" payload — the primary,
text-reduced response a client should render first: a short executive
summary, octagon navigation metadata (label/summary/counts per domain, not
full artifact content), a roadmap overview, and lightweight catalogs of
what's available to download on demand. Full artifact/diagram content stays
in `octagonal_model`/`visualizations` (already returned) and full documents
are rendered only when explicitly requested — the dashboard itself stays
small regardless of how much the underlying solution contains.
"""

from typing import Any, Dict, List

from ocif.domains import OctagonalModel
from ocif.frames import SolutionDocument
from ocif.roadmap import ImplementationRoadmap


def build_dashboard(
    doc: SolutionDocument,
    octagonal_model: OctagonalModel,
    roadmap: ImplementationRoadmap,
    documents_catalog: List[Dict[str, Any]],
    export_manifest: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "title": doc.title,
        "executive_summary": doc.executive_summary,
        "octagon_navigation": [
            {
                "domain": node.domain,
                "label": node.label,
                "description": node.description,
                "summary": node.summary,
                "artifact_count": len(node.artifacts),
                "diagram_count": len(node.diagrams),
            }
            for node in octagonal_model.nodes
        ],
        "roadmap_overview": {
            "phase_count": len(roadmap.phases),
            "phases": [
                {"phase": p.phase, "timeline": p.timeline, "task_count": len(p.tasks), "depends_on": p.depends_on}
                for p in roadmap.phases
            ],
        },
        "document_catalog": documents_catalog,
        "download_center": export_manifest,
    }
