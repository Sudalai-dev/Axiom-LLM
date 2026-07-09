"""
Document Renderer.

"Solution Blueprint -> Document Renderer -> {HLD, LLD, BRD, PRD, SRS, ...}"

Every enterprise document type is a different lens over the SAME
SolutionDocument — no document is ever generated independently of the
blueprint, and no new content is invented: each template just re-arranges
already-validated fields into the section order a reader of that document
type would expect. This mirrors how these documents overlap in practice.

Documents are rendered on demand (see axiom.api.routes.documents), not
eagerly on every solution response — the catalog (see catalog()) is cheap
metadata; render() does the actual formatting.
"""

import json
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ocif.documents import GeneratedDocument, slugify
from ocif.frames import SolutionDocument
from ocif.roadmap import ImplementationRoadmap, build_implementation_roadmap

SectionFn = Callable[[SolutionDocument], str]


def _field(name: str) -> SectionFn:
    return lambda doc: getattr(doc, name) or "Not applicable."


def _tech_stack_table(doc: SolutionDocument) -> str:
    if not doc.technology_stack:
        return "Not applicable."
    rows = [f"| {t.layer} | {t.choice} | {t.rationale} |" for t in doc.technology_stack]
    return "| Layer | Choice | Rationale |\n|-------|--------|-----------|\n" + "\n".join(rows)


def _risk_table(doc: SolutionDocument) -> str:
    if not doc.risk_assessment:
        return "Not applicable."
    rows = [f"| {r.risk} | {r.likelihood} | {r.impact} | {r.mitigation} |" for r in doc.risk_assessment]
    return "| Risk | Likelihood | Impact | Mitigation |\n|------|-----------|--------|------------|\n" + "\n".join(rows)


def _actors_list(doc: SolutionDocument) -> str:
    return "\n".join(f"- {a}" for a in doc.actors) or "Not applicable."


def _roadmap_detailed(doc: SolutionDocument) -> str:
    roadmap = build_implementation_roadmap(doc.implementation_roadmap)
    if not roadmap.phases:
        return "Not applicable."
    lines = []
    for phase in roadmap.phases:
        timeline = f" ({phase.timeline})" if phase.timeline else ""
        depends = f" — depends on: {', '.join(phase.depends_on)}" if phase.depends_on else ""
        lines.append(f"**{phase.phase}**{timeline}{depends}")
        lines += [f"- {t.name}" for t in phase.tasks]
    return "\n".join(lines)


def _future_list(doc: SolutionDocument) -> str:
    return "\n".join(f"- {f}" for f in doc.future_enhancements) or "Not applicable."


@dataclass
class DocumentTemplate:
    key: str
    title: str
    description: str
    sections: List[Tuple[str, SectionFn]]


DOCUMENT_TEMPLATES: List[DocumentTemplate] = [
    DocumentTemplate("brd", "Business Requirements Document", "Business objective, problem, scope, and stakeholders.", [
        ("Business Objective", _field("executive_summary")),
        ("Business Problem", _field("problem_statement")),
        ("Stakeholders", _actors_list),
        ("Business Requirements & Scope", _field("requirements_analysis")),
        ("Success Criteria", _field("final_recommendations")),
    ]),
    DocumentTemplate("prd", "Product Requirements Document", "Product vision, requirements, and roadmap.", [
        ("Overview", _field("executive_summary")),
        ("Problem Statement", _field("problem_statement")),
        ("Requirements", _field("requirements_analysis")),
        ("Recommended Approach", _field("recommended_solution")),
        ("Future Enhancements", _future_list),
    ]),
    DocumentTemplate("srs", "Software Requirements Specification", "Functional/non-functional requirements and interfaces.", [
        ("Requirements Analysis", _field("requirements_analysis")),
        ("Interface Requirements (API)", _field("api_design")),
        ("Data Requirements", _field("database_design")),
        ("Security Requirements", _field("security_architecture")),
        ("Verification (Testing Strategy)", _field("testing_strategy")),
    ]),
    DocumentTemplate("hld", "High-Level Design", "Architecture, stack, and deployment topology.", [
        ("Architecture Overview", _field("architecture_overview")),
        ("Technology Stack", _tech_stack_table),
        ("Component Design", _field("component_design")),
        ("Deployment Architecture", _field("deployment_architecture")),
    ]),
    DocumentTemplate("lld", "Low-Level Design", "Component internals, APIs, data model, and workflow.", [
        ("Component Design", _field("component_design")),
        ("API Design", _field("api_design")),
        ("Database Design", _field("database_design")),
        ("Workflow", _field("workflow")),
    ]),
    DocumentTemplate("architecture", "Architecture Document", "Full architecture, stack, data, deployment, and security.", [
        ("Architecture Overview", _field("architecture_overview")),
        ("Technology Stack", _tech_stack_table),
        ("Component Design", _field("component_design")),
        ("Database Design", _field("database_design")),
        ("Deployment Architecture", _field("deployment_architecture")),
        ("Security Architecture", _field("security_architecture")),
    ]),
    DocumentTemplate("api_documentation", "API Documentation", "Endpoint reference and conventions.", [
        ("API Design", _field("api_design")),
    ]),
    DocumentTemplate("deployment_guide", "Deployment Guide", "How to deploy, configure, and validate a release.", [
        ("Deployment Architecture", _field("deployment_architecture")),
        ("Monitoring Strategy", _field("monitoring_strategy")),
        ("Security Considerations", _field("security_architecture")),
        ("Post-Deployment Validation (Testing Strategy)", _field("testing_strategy")),
    ]),
    DocumentTemplate("user_manual", "User Manual", "How end users interact with the delivered solution.", [
        ("Overview", _field("executive_summary")),
        ("How It Works (Workflow)", _field("workflow")),
        ("API Reference", _field("api_design")),
        ("Recommendations", _field("final_recommendations")),
    ]),
    DocumentTemplate("developer_guide", "Developer Guide", "Architecture, components, and how to extend the system.", [
        ("Architecture Overview", _field("architecture_overview")),
        ("Component Design", _field("component_design")),
        ("Technology Stack", _tech_stack_table),
        ("API Design", _field("api_design")),
        ("Testing Strategy", _field("testing_strategy")),
    ]),
    DocumentTemplate("test_plan", "Test Plan", "Testing strategy, acceptance criteria, and risk-driven test focus.", [
        ("Testing Strategy", _field("testing_strategy")),
        ("Acceptance Criteria (Requirements)", _field("requirements_analysis")),
        ("Risk-Driven Test Focus", _risk_table),
    ]),
    DocumentTemplate("migration_plan", "Migration Plan", "Phased migration roadmap and risk mitigation.", [
        ("Migration Roadmap", _roadmap_detailed),
        ("Risks & Mitigations", _risk_table),
        ("Target Deployment Architecture", _field("deployment_architecture")),
    ]),
    DocumentTemplate("support_manual", "Support Manual", "Operating the solution and handling known issues.", [
        ("Monitoring Strategy", _field("monitoring_strategy")),
        ("Deployment Architecture", _field("deployment_architecture")),
        ("Known Risks & Mitigations", _risk_table),
        ("Recommendations", _field("final_recommendations")),
    ]),
    DocumentTemplate("runbook", "Runbook", "Operational procedures and incident response.", [
        ("Operational Monitoring", _field("monitoring_strategy")),
        ("Deployment Topology", _field("deployment_architecture")),
        ("Incident Response (Risk Mitigations)", _risk_table),
    ]),
]

_TEMPLATES_BY_KEY = {t.key: t for t in DOCUMENT_TEMPLATES}

# OpenAPI/Swagger is structurally different (JSON, not a markdown template).
_OPENAPI_KEY = "openapi"
_API_ROW = re.compile(r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", re.IGNORECASE | re.MULTILINE)


def catalog() -> List[dict]:
    """Lightweight metadata for every available document type — cheap to
    include in every response; no content is rendered until requested."""
    entries = [{"type": t.key, "title": t.title, "description": t.description, "format": "markdown"} for t in DOCUMENT_TEMPLATES]
    entries.append({"type": _OPENAPI_KEY, "title": "OpenAPI Specification", "description": "Machine-readable API contract derived from the API Design section.", "format": "json"})
    return entries


def render(doc: SolutionDocument, document_type: str) -> GeneratedDocument:
    """Renders one document type from the blueprint. Raises KeyError for an
    unknown type (the route layer turns that into a 404)."""
    if document_type == _OPENAPI_KEY:
        return _render_openapi(doc)

    template = _TEMPLATES_BY_KEY.get(document_type)
    if template is None:
        raise KeyError(document_type)

    body_parts = [f"# {template.title}: {doc.title}", ""]
    for heading, fn in template.sections:
        body_parts.append(f"## {heading}\n{fn(doc)}\n")
    content = "\n".join(body_parts)

    slug = slugify(doc.title)
    return GeneratedDocument(
        type=document_type, title=f"{template.title} — {doc.title}",
        filename=f"{slug}-{document_type}.md", content=content,
    )


def _render_openapi(doc: SolutionDocument) -> GeneratedDocument:
    """Parses the already-generated API Design markdown table into a real,
    valid OpenAPI 3.0 skeleton. WS/streaming rows aren't valid HTTP
    operations and are omitted from `paths`, not fabricated as REST."""
    paths: dict = {}
    for method, endpoint, purpose in _API_ROW.findall(doc.api_design or ""):
        endpoint = endpoint.strip()
        # Convert {id}-style path params for OpenAPI's own {param} syntax (already compatible),
        # strip any inline query-string illustration (?from&to) which isn't part of the path.
        clean_path = endpoint.split("?")[0]
        paths.setdefault(clean_path, {})[method.lower()] = {
            "summary": purpose.strip(),
            "responses": {"200": {"description": "Successful response"}},
        }

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": doc.title,
            "description": doc.executive_summary or "Generated from the Axiom Solution Blueprint.",
            "version": "1.0.0",
        },
        "paths": paths,
    }
    slug = slugify(doc.title)
    return GeneratedDocument(
        type=_OPENAPI_KEY, title=f"OpenAPI Specification — {doc.title}",
        filename=f"{slug}-openapi.json", content=json.dumps(spec, indent=2),
    )
