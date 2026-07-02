"""
OCIF Inter-Layer Contract Models.

Defines Pydantic DTOs for data exchange between the 8 layers of the 
Octagonal Cognitive Intelligence Framework.

Every layer consumes a specific model and produces the next model in the pipeline.
"""

from axiom.core.models.base import (
    UserRole, RiskLevel, DecisionOutcome, AgentType, ActionType,
    IngestionStatus, ExecutionStatus, SourceType, LLMProvider,
    ApprovalStatus, CoordinationPattern, PolicyCheckResult,
    OCIFBaseModel, TenantContext, UserContext, RequestContext,
)
from axiom.core.models.perception import PerceptionEvent, InputAttachment
from axiom.core.models.capture import CaptureEvent, SessionInfo
from axiom.core.models.context import ContextFrame, EntityInfo, MemoryTurn, ConversationMemory
from axiom.core.models.knowledge import EnrichedContext, GroundedChunk
from axiom.core.models.orchestration import OrchestrationPlan, AgentTaskStep
from axiom.core.models.cognition import CognitionResult, ProposedAction, TokenUsage
from axiom.core.models.decision import DecisionRecord, PolicyCheck, ExecutionLog
from axiom.core.models.experience import FeedbackEvent

__all__ = [
    # Base
    "UserRole", "RiskLevel", "DecisionOutcome", "AgentType", "ActionType",
    "IngestionStatus", "ExecutionStatus", "SourceType", "LLMProvider",
    "ApprovalStatus", "CoordinationPattern", "PolicyCheckResult",
    "OCIFBaseModel", "TenantContext", "UserContext", "RequestContext",
    
    # Layer 1
    "PerceptionEvent", "InputAttachment",
    
    # Layer 2
    "CaptureEvent", "SessionInfo",
    
    # Layer 3
    "ContextFrame", "EntityInfo", "MemoryTurn", "ConversationMemory",
    
    # Layer 4
    "EnrichedContext", "GroundedChunk",
    
    # Layer 5
    "OrchestrationPlan", "AgentTaskStep",
    
    # Layer 6
    "CognitionResult", "ProposedAction", "TokenUsage",
    
    # Layer 7
    "DecisionRecord", "PolicyCheck", "ExecutionLog",
    
    # Layer 8
    "FeedbackEvent",
]
