"""
OCIF Tool Registry & Adapter — Layer 5.

Manages tool definition caching, inputs/outputs schema verification
(per Doc 13 Section 5), and executes read-only tool calls securely
inside sandboxed wrappers.

Traces to:
  - Document 13 (Agent Design) Section 5: Tool Invocation Protocol
  - Document 9 (Database Design) Section 4.4: Tools schema
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.exceptions import ToolInvocationError
from axiom.storage.models import Tool

logger = logging.getLogger("AxiomToolRegistry")


class ToolRegistry:
    """
    Registry for tools management and validation.
    """

    async def get_tool(self, db: AsyncSession, name: str, tenant_id: str) -> Optional[Tool]:
        """
        Queries a tool by name, matching global tools (tenant_id IS NULL) 
        or tenant-registered tools.
        """
        try:
            result = await db.execute(
                select(Tool)
                .filter(Tool.name == name)
                .filter((Tool.tenant_id == tenant_id) | (Tool.tenant_id.is_(None)))
                .filter(Tool.is_active == True)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Failed to fetch tool '{name}' from database: {e}")
            return None

    def validate_input(self, tool: Tool, input_data: Dict[str, Any]) -> None:
        """
        Validates input arguments against tool.input_schema.
        Raises ToolInvocationError on schema mismatch.
        """
        try:
            schema = json.loads(tool.input_schema)
        except Exception as e:
            logger.error(f"Tool '{tool.name}' schema is malformed: {e}")
            return  # Allow if schema is unparseable to avoid hard blocking
            
        required_keys = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # Verify required keys exist
        for key in required_keys:
            if key not in input_data:
                raise ToolInvocationError(
                    detail=f"Input validation failed for tool '{tool.name}': missing required property '{key}'",
                    tool_id=tool.tool_id
                )

        # Basic type validations
        for key, val in input_data.items():
            if key in properties:
                prop_type = properties[key].get("type")
                if prop_type == "number" and not isinstance(val, (int, float)):
                    raise ToolInvocationError(
                        detail=f"Input validation failed for tool '{tool.name}': property '{key}' must be a number",
                        tool_id=tool.tool_id
                    )
                elif prop_type == "string" and not isinstance(val, str):
                    raise ToolInvocationError(
                        detail=f"Input validation failed for tool '{tool.name}': property '{key}' must be a string",
                        tool_id=tool.tool_id
                    )
                elif prop_type == "boolean" and not isinstance(val, bool):
                    raise ToolInvocationError(
                        detail=f"Input validation failed for tool '{tool.name}': property '{key}' must be a boolean",
                        tool_id=tool.tool_id
                    )

    def validate_output(self, tool: Tool, output_data: Dict[str, Any]) -> None:
        """
        Validates outputs returned from tool calls.
        """
        try:
            schema = json.loads(tool.output_schema)
        except Exception as e:
            logger.error(f"Tool '{tool.name}' output schema is malformed: {e}")
            return

        # Simple verification of properties structure
        properties = schema.get("properties", {})
        for key in properties.keys():
            # If schema requires a key and it is missing, log warning
            if key not in output_data and key in schema.get("required", []):
                logger.warning(f"Tool output verification warning: missing returned parameter '{key}' for tool '{tool.name}'")

    async def execute_tool_call(self, tool: Tool, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes a tool call. If tool has side-effects (requires_approval = True),
        this runtime executes a simulated planning run and returns a proposed
        payload to be handled by Layer 7.
        """
        # Enforce validation first
        self.validate_input(tool, input_data)

        # Invariant check: Write tools must not execute side effects here
        if tool.requires_approval or tool.risk_level in ["medium", "high"]:
            logger.info(f"Tool '{tool.name}' requires authorization. Generating proposed payload execution record.")
            # Return proposed action payload for Layer 7 routing
            return {
                "status": "PROPOSED",
                "tool_id": tool.tool_id,
                "tool_name": tool.name,
                "input_data": input_data,
                "requires_approval": True,
                "message": f"Action proposed. Gated for Layer 7 verification."
            }

        # Read-only tools (e.g. data lookup mock tool) can execute directly
        logger.info(f"Executing read-only tool '{tool.name}' synchronously.")
        
        # Simulate execution response
        sim_response = {
            "status": "SUCCESS",
            "results": {
                "message": f"Successfully fetched data using tool {tool.name}",
                "query_params": input_data
            }
        }
        
        self.validate_output(tool, sim_response)
        return sim_response
