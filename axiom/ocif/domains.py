"""
Solution Domain taxonomy — the Octagonal Framework as a PRESENTATION model.

This is deliberately separate from `axiom.ocif.frames.EngineName` /
`CognitiveTrace`. Those describe the *internal cognitive engines* (hidden
reasoning, never shown to a normal user). `SolutionDomain` and the models
below describe the *finished engineering solution*, reorganized into the
same eight conceptual slots so a user can browse "how the solution is
organized" without ever seeing "how Axiom thought about it".

Everything here is built exclusively from `SolutionDocument` — the already
validated, already leak-scrubbed user-facing blueprint. Nothing in this
module ever reads `CognitiveContext`, `EngineResult`, or any internal frame.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from core.models.base import OCIFBaseModel, new_uuid


class SolutionDomain(str, Enum):
    """The eight conceptual domains a finished solution is organized into.
    Same eight words as the internal engines, entirely different meaning:
    these describe solution CONTENT, not cognitive execution."""
    PERCEPTION = "perception"
    CONTEXT = "context"
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    REASONING = "reasoning"
    VALIDATION = "validation"
    EXPERIENCE = "experience"


DOMAIN_LABELS: Dict[str, str] = {
    SolutionDomain.PERCEPTION.value: "Perception",
    SolutionDomain.CONTEXT.value: "Context",
    SolutionDomain.PLANNING.value: "Planning",
    SolutionDomain.KNOWLEDGE.value: "Knowledge",
    SolutionDomain.MEMORY.value: "Memory",
    SolutionDomain.REASONING.value: "Reasoning",
    SolutionDomain.VALIDATION.value: "Validation",
    SolutionDomain.EXPERIENCE.value: "Experience",
}

DOMAIN_DESCRIPTIONS: Dict[str, str] = {
    SolutionDomain.PERCEPTION.value: "Problem framing, environment, and inputs recognized for this solution.",
    SolutionDomain.CONTEXT.value: "Requirements, scope, and constraints driving the design.",
    SolutionDomain.PLANNING.value: "Implementation phases, task breakdown, timeline, and dependencies.",
    SolutionDomain.KNOWLEDGE.value: "Standards, references, and best-practice technology choices applied.",
    SolutionDomain.MEMORY.value: "The architecture, components, and data model that make up the solution.",
    SolutionDomain.REASONING.value: "The rationale behind the recommended approach and key trade-offs.",
    SolutionDomain.VALIDATION.value: "Risks, test strategy, security checks, and quality assurance.",
    SolutionDomain.EXPERIENCE.value: "Deployment, monitoring, and how the solution operates and evolves.",
}

# Fixed ring order — identical ordering to the internal engine ring, so the
# octagon shape is visually consistent, but every node here is solution
# content, never engine status/timing.
DOMAIN_ORDER: List[str] = [d.value for d in SolutionDomain]

# Fixed relationship graph between domains (the solution's own narrative
# flow: problem -> scope -> plan/standards -> design -> rationale ->
# quality -> operations, with two feedback/cross-reference edges).
DOMAIN_RELATIONSHIPS: List[Dict[str, str]] = [
    {"source": "perception", "target": "context", "relationship": "frames"},
    {"source": "context", "target": "planning", "relationship": "drives"},
    {"source": "context", "target": "knowledge", "relationship": "informs"},
    {"source": "knowledge", "target": "memory", "relationship": "shapes"},
    {"source": "planning", "target": "memory", "relationship": "builds"},
    {"source": "memory", "target": "reasoning", "relationship": "justifies"},
    {"source": "reasoning", "target": "validation", "relationship": "must satisfy"},
    {"source": "validation", "target": "experience", "relationship": "gates"},
    {"source": "experience", "target": "planning", "relationship": "feeds back into"},
    {"source": "knowledge", "target": "validation", "relationship": "grounds"},
]


class DomainArtifact(OCIFBaseModel):
    """One piece of solution content classified into a domain."""
    title: str = ""
    type: str = "text"  # text | list | table
    content: Any = None


class DomainDiagram(OCIFBaseModel):
    """A rendered engineering diagram attached to one domain node — e.g. the
    node's own architecture/ER/sequence/timeline/dependency/risk diagram.
    Distinct from `artifacts` (which carry text/table/list content): this
    carries ready-to-render diagram source."""
    title: str = ""
    type: str = "mermaid"  # mermaid | plantuml
    content: str = ""


class SolutionDomainNode(OCIFBaseModel):
    """A single octagon vertex: one solution domain and its artifacts."""
    domain: str = ""
    label: str = ""
    description: str = ""
    summary: str = ""
    artifacts: List[DomainArtifact] = Field(default_factory=list)
    diagrams: List[DomainDiagram] = Field(default_factory=list)
    related_domains: List[str] = Field(default_factory=list)


class DomainEdge(OCIFBaseModel):
    source: str = ""
    target: str = ""
    relationship: str = ""


class OctagonalModel(OCIFBaseModel):
    """
    Normalized graph of the finished solution, mapped onto the eight
    Octagonal domains. This — not any cognitive trace — is what a normal
    user receives to understand how their solution is organized.
    """
    graph_id: str = Field(default_factory=new_uuid)
    solution_id: str = ""
    title: str = ""
    nodes: List[SolutionDomainNode] = Field(default_factory=list)
    edges: List[DomainEdge] = Field(default_factory=list)
