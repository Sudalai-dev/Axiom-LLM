"""DocumentRenderer, ExportRenderer, DashboardRenderer, solution cache, and
the PresentationRenderer that orchestrates them — each renderer must consume
only the Solution Blueprint (or things derived from it)."""

import inspect
import json

from ocif.domains import OctagonalModel
from ocif.frames import RoadmapPhase, Risk, SolutionDocument, TechChoice
from ocif.renderers import PresentationRenderer, document_types, export, solution_cache
from ocif.renderers.dashboard import build_dashboard
from ocif.roadmap import build_implementation_roadmap
from ocif.solution_mapping import SolutionMappingEngine


def make_document() -> SolutionDocument:
    return SolutionDocument(
        title="Order Processing Pipeline",
        executive_summary="Short summary.",
        technology_stack=[TechChoice(layer="Backend", choice="FastAPI", rationale="Async")],
        implementation_roadmap=[RoadmapPhase(phase="Phase 1 (weeks 1-2)", items=["Setup"])],
        risk_assessment=[Risk(risk="Load", likelihood="medium", impact="high", mitigation="Autoscale")],
        api_design=(
            "Table:\n\n| Method | Endpoint | Purpose |\n|---|---|---|\n"
            "| GET | /api/v1/orders | List orders |\n| POST | /api/v1/orders | Create order |\n"
            "| WS | /api/v1/stream | Real-time updates |"
        ),
    )


# -- Document Renderer --------------------------------------------------------

def test_document_catalog_lists_fifteen_types_including_openapi():
    catalog = document_types.catalog()
    keys = {d["type"] for d in catalog}
    assert "openapi" in keys
    assert len(catalog) == 15
    for entry in catalog:
        assert entry["title"]
        assert entry["format"] in ("markdown", "json")


def test_document_renderer_takes_only_solution_document():
    sig = inspect.signature(document_types.render)
    params = list(sig.parameters.values())
    assert params[0].annotation is SolutionDocument


def test_render_every_catalog_entry_succeeds():
    doc = make_document()
    for entry in document_types.catalog():
        rendered = document_types.render(doc, entry["type"])
        assert rendered.content
        assert rendered.type == entry["type"]


def test_unknown_document_type_raises_keyerror():
    doc = make_document()
    try:
        document_types.render(doc, "does-not-exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_openapi_is_valid_json_with_real_endpoints_and_excludes_websocket():
    doc = make_document()
    rendered = document_types.render(doc, "openapi")
    spec = json.loads(rendered.content)
    assert spec["openapi"].startswith("3.")
    assert "/api/v1/orders" in spec["paths"]
    assert "get" in spec["paths"]["/api/v1/orders"]
    assert "post" in spec["paths"]["/api/v1/orders"]
    # WS is not a valid OpenAPI HTTP operation — must never be fabricated as one.
    assert "/api/v1/stream" not in spec["paths"]


def test_document_never_fabricates_content_beyond_blueprint():
    """Every document is built ONLY from SolutionDocument fields — an empty
    blueprint must render 'Not applicable.' placeholders, never invented text."""
    empty = SolutionDocument(title="Empty")
    rendered = document_types.render(empty, "hld")
    assert "Not applicable." in rendered.content


# -- Export Renderer -----------------------------------------------------------

def test_export_manifest_marks_pdf_and_png_unavailable_with_reason():
    manifest = export.export_manifest()
    by_format = {m["format"]: m for m in manifest}
    assert by_format["pdf"]["available"] is False
    assert by_format["pdf"]["reason"]
    assert by_format["png"]["available"] is False
    for real in ("svg", "mermaid", "plantuml", "json_graph", "reactflow", "markdown", "json", "html"):
        assert by_format[real]["available"] is True


def test_html_export_is_self_contained_and_escapes_content():
    doc = make_document()
    html = export.to_html(doc, "Some <script>evil()</script> text", "<svg>diagram</svg>")
    assert html.startswith("<!doctype html>")
    assert "<svg>diagram</svg>" in html
    assert "<script>evil()</script>" not in html  # must be escaped, not executed
    assert "&lt;script&gt;" in html


# -- Dashboard Renderer ----------------------------------------------------------

def test_dashboard_is_lightweight_not_full_content():
    doc = make_document()
    model = SolutionMappingEngine().map(doc)
    roadmap = build_implementation_roadmap(doc.implementation_roadmap)
    dashboard = build_dashboard(doc, model, roadmap, document_types.catalog(), export.export_manifest())

    assert dashboard["executive_summary"] == doc.executive_summary
    assert len(dashboard["octagon_navigation"]) == 8
    for nav in dashboard["octagon_navigation"]:
        assert "summary" in nav and "artifact_count" in nav and "diagram_count" in nav
        # The dashboard nav is metadata only — no full artifact/diagram payloads.
        assert "artifacts" not in nav
        assert "diagrams" not in nav
    assert dashboard["roadmap_overview"]["phase_count"] == 1
    assert dashboard["document_catalog"]
    assert dashboard["download_center"]


# -- Solution cache --------------------------------------------------------------

def test_solution_cache_round_trip():
    solution_cache.clear()
    doc = make_document()
    solution_cache.put(doc, "# markdown")
    cached = solution_cache.get(doc.solution_id)
    assert cached is not None
    cached_doc, cached_markdown = cached
    assert cached_doc.solution_id == doc.solution_id
    assert cached_markdown == "# markdown"
    assert solution_cache.get("nonexistent") is None


# -- Presentation Renderer (orchestrator) -----------------------------------------

def test_presentation_renderer_is_superset_of_existing_blueprint_pipeline():
    """Backward compatibility guarantee: every field the OLD pipeline
    returned must still be present, unchanged in shape, alongside the new
    dashboard-first fields."""
    doc = make_document()
    package = PresentationRenderer.render(doc, "# markdown body")

    for legacy_key in ("solution_blueprint", "octagonal_model", "visualizations", "implementation_roadmap", "generated_documents"):
        assert legacy_key in package

    for new_key in ("dashboard", "documents_catalog", "export_manifest"):
        assert new_key in package

    assert isinstance(package["octagonal_model"], dict)
    OctagonalModel(**package["octagonal_model"])  # must round-trip through the real model

    # Rendering also populates the on-demand cache.
    assert solution_cache.get(doc.solution_id) is not None
