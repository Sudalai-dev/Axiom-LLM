"""
Engine Registry — Axiom Core.

Manages platform-wide system engine registrations, lifecycle resolution,
and dependency injection of concrete implementations for OCIF contracts —
both the infrastructure engines (parser, chunker, vectors, …) and the 8
octagonal cognitive engines.
"""

from typing import Any, Dict, Optional, Type

from core.contracts import (
    IParserEngine, IChunkEngine, IEmbeddingEngine,
    IVectorEngine, IKnowledgeGraph, IMemoryEngine, IPolicyEngine
)


class EngineRegistry:
    """
    Central registry for engine components.
    Provides dependency injection resolution.
    """

    def __init__(self) -> None:
        self._registry: Dict[Type, Any] = {}
        self._instances: Dict[Type, Any] = {}
        self._register_defaults()

    def register(self, contract: Type, implementation: Any) -> None:
        """Registers a class or instance as the implementation of a contract."""
        self._registry[contract] = implementation
        # Clear cached instance if overwritten
        if contract in self._instances:
            del self._instances[contract]

    def resolve(self, contract: Type) -> Any:
        """Resolves the contract and returns the registered implementation singleton."""
        if contract in self._instances:
            return self._instances[contract]

        impl = self._registry.get(contract)
        if not impl:
            raise KeyError(f"No engine implementation registered for contract: {contract.__name__}")

        # If the implementation is a class/callable, instantiate it
        if isinstance(impl, type) or callable(impl):
            try:
                instance = impl()
            except TypeError as te:
                raise TypeError(
                    f"Registered implementation for '{contract.__name__}' is not parameterless "
                    f"and cannot be auto-instantiated: {te}"
                )
            self._instances[contract] = instance
            return instance

        # Otherwise, treat it as a direct instance singleton
        self._instances[contract] = impl
        return impl

    def _register_defaults(self) -> None:
        """Hooks up default concrete engines to contracts."""
        # 1. Parser Engine
        from knowledge.parser import ParserEngine
        IParserEngine.register(ParserEngine)
        self.register(IParserEngine, ParserEngine)

        # 2. Chunk Engine
        from knowledge.chunker import ChunkEngine
        IChunkEngine.register(ChunkEngine)
        self.register(IChunkEngine, ChunkEngine)

        # 3. Embedding Engine
        from knowledge.embedder import EmbeddingEngine
        IEmbeddingEngine.register(EmbeddingEngine)
        self.register(IEmbeddingEngine, EmbeddingEngine)

        # 4. Vector Engine
        from knowledge.vector_store import VectorEngine
        IVectorEngine.register(VectorEngine)
        self.register(IVectorEngine, VectorEngine)

        # 5. Knowledge Graph
        from knowledge.graph_service import KnowledgeGraphService
        IKnowledgeGraph.register(KnowledgeGraphService)
        self.register(IKnowledgeGraph, KnowledgeGraphService)

        # 6. Memory Engine
        from memory.conversation import MemoryManager
        IMemoryEngine.register(MemoryManager)
        self.register(IMemoryEngine, MemoryManager)

        # 7. Policy Engine
        from governance.policy_engine import PolicyEngine
        IPolicyEngine.register(PolicyEngine)
        self.register(IPolicyEngine, PolicyEngine)


# ---------------------------------------------------------------------------
# Octagonal Cognitive Framework wiring
# ---------------------------------------------------------------------------

def register_cognitive_engines(registry: "EngineRegistry") -> None:
    """
    Registers the 8 OCIF cognitive engines by their EngineName contract,
    verifying each satisfies the Engine Contract before registration.
    """
    from ocif.engine import CognitiveEngine
    from ocif.engines import (
        ContextEngine, ExperienceEngine, KnowledgeEngine, MemoryEngine,
        PerceptionEngine, PlanningEngine, EngineeringIntelligenceEngine, ValidationEngine,
    )

    for engine_cls in (
        PerceptionEngine, ContextEngine, PlanningEngine, KnowledgeEngine,
        MemoryEngine, EngineeringIntelligenceEngine, ValidationEngine, ExperienceEngine,
    ):
        if not issubclass(engine_cls, CognitiveEngine):
            raise TypeError(
                f"{engine_cls.__name__} does not satisfy the OCIF Engine Contract"
            )
        registry.register(engine_cls, engine_cls)


def build_octagonal_kernel(
    knowledge_service: Optional[Any] = None,
    learning_store: Optional[Any] = None,
    knowledge_platform: Optional[Any] = None,
):
    """
    Factory assembling the OctagonalKernel with platform infrastructure:
    when a KnowledgeService is supplied, its embedder + vector store back the
    Knowledge Engine's retriever (fail-soft inside the engine). When a
    LearningStore is supplied, it backs the Memory Engine's persistent
    "learned from past conversations" recall — pass the same instance used
    elsewhere (e.g. the feedback endpoint) so both read/write one durable store.

    One shared InferenceAdapter is constructed here and passed to both the
    Reasoning Engine (final solution authoring) and the Project
    Understanding classifier (upstream industry/domain classification) so
    they share a single ModelRouter instance/circuit-breaker state instead
    of each building their own.
    """
    from ocif.engines import KnowledgeEngine, MemoryEngine, EngineeringIntelligenceEngine
    from ocif.engines.project_understanding import ProjectUnderstandingEngine
    from ocif.inference_adapter import InferenceAdapter
    from ocif.kernel import OctagonalKernel

    retriever = None
    if knowledge_service is not None:
        async def retriever(query: str, tenant_id: str):
            vector = knowledge_service.embedder.embed(query)
            matches = await knowledge_service.vector_retriever.search_vectors(
                query_vector=vector, tenant_id=tenant_id, limit=8
            )
            results = []
            for match in matches or []:
                payload = match.get("payload", match)
                results.append({
                    "doc_id": payload.get("doc_id", ""),
                    "title": payload.get("title", "Untitled source"),
                    "text": payload.get("text", ""),
                })
            return results

    inference = InferenceAdapter()
    kernel = OctagonalKernel(
        project_understanding=ProjectUnderstandingEngine(inference=inference),
        knowledge=KnowledgeEngine(retriever=retriever),
        memory=MemoryEngine(learning_store=learning_store),
        reasoning=EngineeringIntelligenceEngine(inference=inference, knowledge_platform=knowledge_platform),
    )
    kernel.initialize()
    return kernel


# Global Singleton of the Engine Registry
engine_registry = EngineRegistry()
register_cognitive_engines(engine_registry)
