"""
OCIF Frames — Octagonal Cognitive Framework data contracts.

Defines every frame exchanged between the 8 cognitive engines, the shared
CognitiveContext they read/write, the user-facing SolutionDocument, and the
developer-mode-only CognitiveTrace.

The Octagonal Framework is INTERNAL: nothing in this module except
SolutionDocument is ever rendered to a normal end user.

Traces to:
  - Axiom Master Prompt Part B.1 (engine frames), Part B.3 (CognitiveContext)
  - AXIOM Mission directive: internal pipeline / visible Solution Document split
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from core.models.base import OCIFBaseModel, new_uuid, utc_now


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

class EngineName(str, Enum):
    PERCEPTION = "perception"
    CONTEXT = "context"
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    REASONING = "reasoning"
    VALIDATION = "validation"
    EXPERIENCE = "experience"


class Intent(str, Enum):
    SOLUTION_DESIGN = "solution_design"
    CODE_GENERATION = "code_generation"
    DOCUMENTATION = "documentation"
    AIOT_ENGINEERING = "aiot_engineering"
    REVIEW = "review"
    GENERAL_ENGINEERING = "general_engineering"
    TRIVIAL_CLARIFICATION = "trivial_clarification"


class SpecialistAgent(str, Enum):
    """Part E agent taxonomy — assigned by the Planning Engine."""
    ARCHITECTURE = "Architecture Agent"
    BACKEND = "Backend Agent"
    FRONTEND = "Frontend Agent"
    DATABASE = "Database Agent"
    SECURITY = "Security Agent"
    DEVOPS = "DevOps Agent"
    IOT = "IoT Agent"
    DOCUMENTATION = "Documentation Agent"
    TESTING = "Testing Agent"
    OPTIMIZATION = "Optimization Agent"
    RESEARCH = "Research Agent"
    VALIDATION = "Validation Agent"


class EngineStatus(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Engine frames (internal)
# ---------------------------------------------------------------------------

class PerceptionFrame(OCIFBaseModel):
    """Environment analysis + normalized inbound signal (Engine 1)."""
    raw_text: str = ""
    normalized_text: str = ""
    input_kinds: List[str] = Field(default_factory=list)   # text | code | document | config | log
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    environment: Dict[str, Any] = Field(default_factory=dict)
    is_safe: bool = True
    rejection_reason: Optional[str] = None


class UseCase(OCIFBaseModel):
    """A single expanded use case — internal analysis feeding Requirements."""
    id: str = ""
    actor: str = ""
    scenario: str = ""
    expected_behavior: str = ""


class ContextFrame(OCIFBaseModel):
    """Intent understanding — what is being asked, in what context (Engine 2)."""
    intent: Intent = Intent.GENERAL_ENGINEERING
    entities: List[str] = Field(default_factory=list)
    # Concrete domain nouns harvested from the request (patient, bed, loomweaver…),
    # separate from tech entities — drives per-project ER/class diagrams (Phase 5).
    domain_entities: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    use_cases: List[UseCase] = Field(default_factory=list)
    project: str = "default"
    conversation_state: Dict[str, Any] = Field(default_factory=dict)
    is_trivial: bool = False
    subject: str = ""  # short restatement of the problem


class Requirement(OCIFBaseModel):
    id: str = ""
    category: str = "functional"
    requirement: str = ""


class Plan(OCIFBaseModel):
    """Ordered solution plan produced by the Planning Engine (Engine 3)."""
    plan_id: str = Field(default_factory=new_uuid)
    objectives: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    required_agents: List[SpecialistAgent] = Field(default_factory=list)
    required_knowledge: bool = False
    functional_requirements: List[Requirement] = Field(default_factory=list)
    non_functional_requirements: List[Requirement] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    revision: int = 0


class KnowledgeSource(OCIFBaseModel):
    doc_id: str = ""
    title: str = ""
    excerpt: str = ""


class KnowledgeFrame(OCIFBaseModel):
    """Knowledge analysis output (Engine 4) — optional, never fabricated."""
    knowledge_used: bool = False
    facts: List[str] = Field(default_factory=list)
    sources: List[KnowledgeSource] = Field(default_factory=list)
    confidence: float = 0.0
    notes: str = "No external knowledge required; solved from engineering reasoning alone."


class MemoryFrame(OCIFBaseModel):
    """Memory slices per Master Prompt Part D (Engine 5)."""
    working: Dict[str, Any] = Field(default_factory=dict)
    conversation: List[Dict[str, str]] = Field(default_factory=list)
    project: List[str] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    learning: List[str] = Field(default_factory=list)
    feedback: List[str] = Field(default_factory=list)
    # Structured recall (Phase 6 — learning loop). `learning`/`feedback` above
    # are human-readable strings for prompts/traces; these carry the same recall
    # as structured records so the deterministic synthesizer can genuinely REUSE
    # a prior validated design (its title/entities/trade-offs) and let feedback
    # shift the next solution — not just decorate one sentence.
    recalled: List[Dict[str, Any]] = Field(default_factory=list)
    feedback_signals: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectUnderstandingFrame(OCIFBaseModel):
    """
    Deep project classification produced BEFORE Planning — the answer to
    "what kind of project is this, really?" (industry/domain/system shape),
    as opposed to ContextFrame's shallow intent + IT/IoT keyword extraction.
    Planning and Reasoning consume this instead of reading raw request text
    directly. Populated by a classifier that always has a rule-based
    fallback (see ocif/engines/project_understanding.py), so this frame is
    never None once Context has run and the request wasn't trivial.
    """
    industry: str = "general_software"
    business_domain: str = ""
    business_problem: str = ""
    engineering_problem: str = ""
    project_category: str = ""
    application_category: str = ""
    system_type: str = ""
    architecture_style: str = ""
    deployment_model: str = ""
    technical_constraints: List[str] = Field(default_factory=list)
    business_constraints: List[str] = Field(default_factory=list)
    actors: List[str] = Field(default_factory=list)
    technical_actors: List[str] = Field(default_factory=list)
    physical_assets: List[str] = Field(default_factory=list)
    logical_assets: List[str] = Field(default_factory=list)
    domain_entities: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    data_flow: str = ""
    control_flow: str = ""
    external_systems: List[str] = Field(default_factory=list)
    apis: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    communication_protocols: List[str] = Field(default_factory=list)
    sensors: List[str] = Field(default_factory=list)
    devices: List[str] = Field(default_factory=list)
    ai_components: List[str] = Field(default_factory=list)
    cloud_components: List[str] = Field(default_factory=list)
    edge_components: List[str] = Field(default_factory=list)
    # Descriptive only — the document/diagram catalog is structurally fixed
    # (see ocif/renderers/document_types.py); these do not filter it.
    recommended_documents: List[str] = Field(default_factory=list)
    recommended_diagrams: List[str] = Field(default_factory=list)
    required_images: List[str] = Field(default_factory=list)
    required_reports: List[str] = Field(default_factory=list)
    domain_expert_persona: str = "Solution Architect"
    confidence: float = 0.0
    classification_method: str = "rule_based_fallback"  # or "llm"


# ---------------------------------------------------------------------------
# User-facing Solution Document (the ONLY externally visible artifact)
# ---------------------------------------------------------------------------

class TechChoice(OCIFBaseModel):
    layer: str = ""
    choice: str = ""
    rationale: str = ""


class RoadmapPhase(OCIFBaseModel):
    phase: str = ""
    items: List[str] = Field(default_factory=list)


class Risk(OCIFBaseModel):
    risk: str = ""
    likelihood: str = "medium"
    impact: str = "medium"
    mitigation: str = ""


class SolutionDocument(OCIFBaseModel):
    """
    The complete engineering solution delivered to the user.
    Section order is fixed; every section must be non-empty
    (the Validation Engine fills 'Not applicable' rather than dropping one).
    """
    solution_id: str = Field(default_factory=new_uuid)
    title: str = "Engineering Solution"
    executive_summary: str = ""
    problem_statement: str = ""
    actors: List[str] = Field(default_factory=list)  # stakeholders/actors surfaced for System Context visualization
    domain_entities: List[str] = Field(default_factory=list)  # request's concrete nouns → per-project ER/class diagrams
    requirements_analysis: str = ""
    recommended_solution: str = ""
    architecture_overview: str = ""          # includes Mermaid architecture diagram
    technology_stack: List[TechChoice] = Field(default_factory=list)
    component_design: str = ""
    database_design: str = ""                # includes Mermaid ER diagram
    api_design: str = ""
    workflow: str = ""                       # includes Mermaid sequence diagram
    security_architecture: str = ""
    deployment_architecture: str = ""        # includes Mermaid deployment diagram
    monitoring_strategy: str = ""
    testing_strategy: str = ""
    implementation_roadmap: List[RoadmapPhase] = Field(default_factory=list)
    risk_assessment: List[Risk] = Field(default_factory=list)
    future_enhancements: List[str] = Field(default_factory=list)
    final_recommendations: str = ""


# Fixed user-facing section order — the Experience Engine renders exactly these.
SOLUTION_SECTIONS: List[str] = [
    "Executive Summary",
    "Problem Statement",
    "Requirements Analysis",
    "Recommended Solution",
    "Architecture Overview",
    "Technology Stack",
    "Component Design",
    "Database Design",
    "API Design",
    "Workflow",
    "Security Architecture",
    "Deployment Architecture",
    "Monitoring Strategy",
    "Testing Strategy",
    "Implementation Roadmap",
    "Risk Assessment",
    "Future Enhancements",
    "Final Recommendations",
]


# ---------------------------------------------------------------------------
# Reasoning / Validation results (internal)
# ---------------------------------------------------------------------------

class ReasoningResult(OCIFBaseModel):
    """Output of the Reasoning Engine (Engine 6). Never emitted directly."""
    solution_draft: SolutionDocument = Field(default_factory=SolutionDocument)
    confidence: float = 0.0
    rationale: str = ""
    tradeoffs: List[str] = Field(default_factory=list)
    provider_used: str = "internal-synthesizer"
    model_used: str = "axiom-solution-synthesizer"


class ValidationResult(OCIFBaseModel):
    """Fail-closed verdict of the Validation Engine (Engine 7)."""
    passed: bool = False
    checks_performed: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    corrections_made: List[str] = Field(default_factory=list)
    corrected_solution: Optional[SolutionDocument] = None


# ---------------------------------------------------------------------------
# Engine Contract envelope + trace
# ---------------------------------------------------------------------------

class EngineResult(OCIFBaseModel):
    """Uniform envelope returned by every engine's execute()."""
    engine: EngineName
    status: EngineStatus = EngineStatus.COMPLETED
    summary: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0


class CognitiveTrace(OCIFBaseModel):
    """
    Developer-mode-only view of the octagonal execution.
    Never included in normal user responses.
    """
    correlation_id: str = ""
    engine_timeline: List[EngineResult] = Field(default_factory=list)
    intent: str = ""
    entities: List[str] = Field(default_factory=list)
    use_cases: List[UseCase] = Field(default_factory=list)
    plan: Optional[Plan] = None
    knowledge_sources: List[KnowledgeSource] = Field(default_factory=list)
    validation_report: Optional[ValidationResult] = None
    confidence: float = 0.0
    reasoning_rationale: str = ""
    tradeoffs: List[str] = Field(default_factory=list)
    provider_used: str = ""
    octagon_svg: str = ""
    project_understanding: Optional[ProjectUnderstandingFrame] = None
    # Engineering Intelligence pipeline provenance (intent/domains/experts plus
    # Knowledge Platform usage: assembled packs, standards, rules). Developer/
    # admin-only, like the rest of the trace — never in user responses.
    engineering_intelligence: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# CognitiveContext — shared object all engines read/write (Part B.3)
# ---------------------------------------------------------------------------

class CognitiveContext(OCIFBaseModel):
    """
    The single shared context threaded through the octagonal execution graph.
    Always carries user, tenant, project, conversation_id for traceability.
    """
    correlation_id: str = Field(default_factory=new_uuid)
    user_id: str = "anonymous"
    tenant_id: str = "default"
    project: str = "default"
    conversation_id: str = Field(default_factory=new_uuid)

    task: str = ""
    intent: str = ""
    entities: List[str] = Field(default_factory=list)
    confidence: float = 0.0

    perception: Optional[PerceptionFrame] = None
    context: Optional[ContextFrame] = None
    project_understanding: Optional[ProjectUnderstandingFrame] = None
    plan: Optional[Plan] = None
    knowledge: Optional[KnowledgeFrame] = None
    memory: Optional[MemoryFrame] = None
    reasoning: Optional[ReasoningResult] = None
    validation: Optional[ValidationResult] = None

    workflow_state: str = "initialized"
    execution_state: Dict[str, Any] = Field(default_factory=dict)
    engine_trace: List[EngineResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
