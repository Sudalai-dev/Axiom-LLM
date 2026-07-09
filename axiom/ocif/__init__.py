"""
Axiom Octagonal Cognitive Framework (OCIF).

The internal 8-engine reasoning core of AXIOM. Engines satisfy the uniform
Engine Contract (initialize / execute / validate / shutdown), share a single
CognitiveContext, and communicate through the platform event bus. The user
only ever receives the final validated Solution Document.

A second, entirely separate pipeline (blueprint_pipeline / solution_mapping /
visualization / presentation) takes that finished SolutionDocument and
re-presents it as an Octagonal Engineering Visualization — the same eight
conceptual slots, but describing solution CONTENT, not cognitive execution.
It never touches CognitiveContext or any internal reasoning frame.
"""

from ocif.blueprint_pipeline import build_solution_response
from ocif.domains import OctagonalModel, SolutionDomain, SolutionDomainNode
from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    CognitiveTrace,
    ContextFrame,
    EngineName,
    EngineResult,
    EngineStatus,
    Intent,
    KnowledgeFrame,
    MemoryFrame,
    PerceptionFrame,
    Plan,
    ReasoningResult,
    SolutionDocument,
    UseCase,
    ValidationResult,
)
from ocif.kernel import KernelOutput, OctagonalKernel
from ocif.solution_mapping import SolutionMappingEngine
from ocif.visualization import OctagonalVisualizationEngine

__all__ = [
    "CognitiveEngine",
    "CognitiveContext",
    "CognitiveTrace",
    "ContextFrame",
    "EngineName",
    "EngineResult",
    "EngineStatus",
    "Intent",
    "KernelOutput",
    "KnowledgeFrame",
    "MemoryFrame",
    "OctagonalKernel",
    "OctagonalModel",
    "OctagonalVisualizationEngine",
    "PerceptionFrame",
    "Plan",
    "ReasoningResult",
    "SolutionDocument",
    "SolutionDomain",
    "SolutionDomainNode",
    "SolutionMappingEngine",
    "UseCase",
    "ValidationResult",
    "build_solution_response",
]
