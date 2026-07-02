"""
Layer 5 — Orchestration Plan Contract.

Defines the canonical output of the Intelligence Orchestration Layer (L5).
The OrchestrationPlan models a decomposed task execution flow, tracking
individual sub-agent assignments, tool queries, execution status, and dependencies.

Traces to:
  - Document 7 (LLD) Section 6: Orchestration Layer contract
  - Document 13 (Agent Design) Section 3: Agent runtime & plan queue
  - Document 13 (Agent Design) Section 4: Agent state machine (LangGraph states)
  - Document 7 (LLD) Section 11: Inter-layer events (OrchestrationPlan)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, RequestContext, AgentType, CoordinationPattern,
    ExecutionStatus, new_uuid, utc_now,
)
from axiom.core.models.knowledge import EnrichedContext


class AgentTaskStep(OCIFBaseModel):
    """
    A single sub-step in the multi-agent execution graph.
    Matches the LangGraph node trace representations.
    """
    step_id: str = Field(..., description="Unique step identifier")
    title: str = Field(..., description="Title of task step")
    description: str = Field(..., description="Functional details of task to run")
    agent_type: AgentType = Field(..., description="Agent assigned to the step")
    
    # Dependencies
    dependencies: List[str] = Field(default_factory=list, description="IDs of steps that must finish first")
    
    # Execution states
    status: ExecutionStatus = Field(default=ExecutionStatus.RUNNING)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Tool invocation tracking
    tool_id: Optional[str] = Field(default=None, description="Registered tool used in this step")
    tool_input: Optional[Dict[str, Any]] = Field(default=None, description="Arguments passed to the tool")
    tool_output: Optional[str] = Field(default=None, description="Result payload returned by the tool")
    error_message: Optional[str] = Field(default=None)


class OrchestrationPlan(OCIFBaseModel):
    """
    Canonical output of Layer 5 — Orchestration.

    Contains the agent graph execution state model, step logs, execution status,
    coordination routing guidelines, and upstream grounding variables.

    Per Doc 7 Section 6 and Doc 13:
    - Task decomposition and tracking
    - Agent task step dependency tracking
    - In-progress tool call logs and outputs
    - Maximum step limit guard verification
    """
    plan_id: str = Field(default_factory=new_uuid, description="Unique plan session ID")
    timestamp: datetime = Field(default_factory=utc_now)
    status: ExecutionStatus = Field(default=ExecutionStatus.RUNNING)

    # Coordination strategy
    coordination_pattern: CoordinationPattern = Field(default=CoordinationPattern.SEQUENTIAL)
    steps: List[AgentTaskStep] = Field(default_factory=list, description="Ordered timeline steps")
    current_step_id: Optional[str] = Field(default=None, description="Currently active execution step ID")

    # Safety checks
    step_count: int = Field(default=0, description="Total steps executed (used for max steps guard)")
    risk_estimate: float = Field(default=0.0, description="Pre-calculated composite action execution risk score")

    # Upstream layers & request contexts
    enriched_context: EnrichedContext = Field(..., description="Grounded knowledge enrichment context")
    request_context: RequestContext = Field(..., description="Request execution metadata envelope")
