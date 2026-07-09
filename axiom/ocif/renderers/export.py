"""
Export Renderer.

Produces downloadable artifacts from a Solution Blueprint. Formats that can
be generated honestly with pure-Python (no headless browser / rasterizer
dependency) are fully implemented: markdown, structured JSON, and a
self-contained interactive HTML page embedding the solution's octagon SVG.
PDF and PNG are declared in the manifest with `available: false` and a
clear reason — they require a rendering engine this deployment does not
bundle, and this module never fakes binary output.
"""

import json
from typing import Any, Dict, List

from ocif.documents import slugify
from ocif.frames import SolutionDocument

_AVAILABLE_FORMATS = ("svg", "mermaid", "plantuml", "json_graph", "reactflow", "markdown", "json", "html")
_UNAVAILABLE_FORMATS = {
    "pdf": "Requires a headless-browser/PDF rendering engine not bundled in this deployment.",
    "png": "Requires a rasterizer (e.g. a headless browser or cairosvg) not bundled in this deployment.",
}


def export_manifest() -> List[Dict[str, Any]]:
    """Lists every export format and whether it can actually be produced
    right now — no format claims availability it can't deliver."""
    manifest = [{"format": f, "available": True} for f in _AVAILABLE_FORMATS]
    manifest += [{"format": f, "available": False, "reason": reason} for f, reason in _UNAVAILABLE_FORMATS.items()]
    return manifest


def _escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def to_html(doc: SolutionDocument, markdown_text: str, octagon_svg: str) -> str:
    """Self-contained interactive HTML export: the solution's octagon
    diagram (fully interactive/inline SVG) plus its full report. No Python
    markdown-rendering dependency is bundled in this deployment, so the
    report body is presented as readable preformatted text rather than
    faking rich HTML formatting — the octagon diagram is the interactive
    part of this export."""
    title = doc.title or "Engineering Solution"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{_escape_html(title)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; background:#0a0e1a; color:#f1f5f9; max-width: 900px; margin: 0 auto; padding: 32px 24px; line-height: 1.6; }}
  h1 {{ color: #818cf8; }}
  .octagon {{ text-align:center; margin: 24px 0; }}
  .octagon svg {{ max-width: 100%; height: auto; }}
  .report {{ background: #1a2035; padding: 16px; border-radius: 8px; white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; overflow-x: auto; }}
</style>
</head>
<body>
<h1>{_escape_html(title)}</h1>
<div class="octagon">{octagon_svg}</div>
<div class="report">{_escape_html(markdown_text)}</div>
</body>
</html>"""


def to_json(doc: SolutionDocument) -> str:
    return json.dumps(doc.model_dump(), indent=2, default=str)


def export_filename(doc: SolutionDocument, fmt: str) -> str:
    slug = slugify(doc.title)
    ext = {"markdown": "md", "json": "json", "html": "html", "reactflow": "json", "json_graph": "json"}.get(fmt, "txt")
    return f"{slug}.{ext}"
