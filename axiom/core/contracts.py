"""
Engine Contracts — Axiom Platform.

Defines the abstract base classes (interfaces) that all platform subsystems 
must implement, ensuring architectural compliance and contract consistency.

Traces to:
  - Document 8 (System Architecture) Section 3: Engine interfaces
  - Document 6 (LLD) Section 1: Class Interface Specifications
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# OCIF Cognitive Engine Contract (Master Prompt Part B)
#
# The uniform interface every octagonal cognitive engine satisfies:
#   initialize() / execute(context) -> EngineResult / validate(result) / shutdown()
#
# The canonical implementation lives in axiom.ocif.engine.CognitiveEngine;
# it is re-exported here so architectural compliance checks can reference a
# single contract module. Imported lazily to avoid a core -> ocif import cycle.
# ---------------------------------------------------------------------------

def get_cognitive_engine_contract():
    """Returns the OCIF CognitiveEngine ABC (the Engine Contract)."""
    from ocif.engine import CognitiveEngine
    return CognitiveEngine


class IParserEngine(ABC):
    """Contract for multi-format document parsers."""

    @abstractmethod
    def parse(self, filepath: str) -> str:
        """Parses a document file and returns its clean text representation."""
        pass


class IChunkEngine(ABC):
    """Contract for text chunking and boundary detection engines."""

    @abstractmethod
    def split(self, text: str) -> List[Any]:
        """Slices raw document text into structured semantic blocks."""
        pass


class IEmbeddingEngine(ABC):
    """Contract for semantic vector embedding generators."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Encodes text strings into dense floating-point vector representations."""
        pass


class IVectorEngine(ABC):
    """Contract for vector databases and retrieval clients."""

    @abstractmethod
    def insert(self, record_id: str, vector: List[float], payload: Dict[str, Any], project_id: int) -> None:
        """Inserts a single vector and metadata payload, isolated by project ID."""
        pass

    @abstractmethod
    def delete(self, record_id: str) -> None:
        """Removes a vector record by ID."""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        project_id: int,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Queries top-K similar vector records isolated by project ID."""
        pass


class IKnowledgeGraph(ABC):
    """Contract for Knowledge Graph database connectors."""

    @abstractmethod
    def retrieve_relationships(self, entities: List[Any]) -> List[str]:
        """Queries semantic relationships linking the given list of technology entities."""
        pass


class IMemoryEngine(ABC):
    """Contract for conversation session and long-term memory managers."""

    @abstractmethod
    async def get_conversation_memory(self, db: AsyncSession, session_id: str) -> Any:
        """Loads and returns compacted conversation memory turns for the session."""
        pass

    @abstractmethod
    async def persist_turn(self, db: AsyncSession, session_id: str, tenant_id: str, role: str, content: str) -> None:
        """Saves a single conversation turn into memory cache and database."""
        pass


class IPolicyEngine(ABC):
    """Contract for rules-as-code safety policy engine guardrails."""

    @abstractmethod
    async def evaluate_policies(
        self,
        db: AsyncSession,
        tenant_id: str,
        action_type: str,
        payload: Dict[str, Any]
    ) -> List[Any]:
        """Evaluates proposed actions against tenant policy rules."""
        pass
