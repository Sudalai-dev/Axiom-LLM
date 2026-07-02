"""
OCIF Prompt Builder — Layer 5.

Implements the standard and task-specific prompt construction templates
as defined in Document 12 Sections 3–4. Ensures provider-agnostic layouts.

Traces to:
  - Document 12 (Prompt Engineering Guide) Section 3: Standard Prompt Template
  - Document 12 (Prompt Engineering Guide) Section 4: Task-Specific Templates
  - Document 7 (LLD) Section 6: Orchestration prompt builder
"""

import json
from typing import Dict, Any, List

from axiom.core.models.context import ContextFrame
from axiom.core.models.knowledge import EnrichedContext

class PromptBuilder:
    """
    Renders structured system and user prompts matching the OCIF specifications.
    """

    SYSTEM_TEMPLATE = (
        "SYSTEM:\n"
        "You are an enterprise assistant operating within the OCIF platform for tenant: {tenant_name}.\n"
        "Industry context: {industry}.\n"
        "You must:\n"
        "- Answer only using the provided KNOWLEDGE CONTEXT when grounding is available.\n"
        "- If no relevant knowledge is found, state this explicitly rather than guessing.\n"
        "- Provide a confidence score (0.0-1.0) for your answer.\n"
        "- Cite sources using the provided citation IDs.\n"
        "- If the task requires an action with real-world effect, propose the action but do not assume it is authorized — output it as a structured proposal only.\n\n"
        "KNOWLEDGE CONTEXT:\n"
        "{retrieved_chunks_with_citations}\n\n"
        "CONVERSATION MEMORY:\n"
        "{summary_and_recent_turns}\n\n"
        "USER PROFILE:\n"
        "User: {username}, Role: {role}, Department: {department}\n\n"
        "TASK:\n"
        "{user_query}\n\n"
        "OUTPUT FORMAT:\n"
        "{output_format_instructions}"
    )

    TASK_FORMATS = {
        "CodeGen": (
            "Based on the task and available tools, propose the single next action.\n"
            "Respond in this JSON structure:\n"
            "{\n"
            "  \"action_type\": \"tool_call | clarify | final_answer\",\n"
            "  \"tool_id\": \"string | null\",\n"
            "  \"tool_input\": {},\n"
            "  \"rationale\": \"string\",\n"
            "  \"confidence\": number,\n"
            "  \"risk_self_assessment\": \"low | medium | high\"\n"
            "}"
        ),
        "ArchitectureReview": (
            "Review the requested architectural blueprint context. Answer the query and cite relevant chunks.\n"
            "Respond in this JSON structure:\n"
            "{\n"
            "  \"answer\": \"string\",\n"
            "  \"confidence\": number,\n"
            "  \"citations\": [\"chunk_id\", ...],\n"
            "  \"grounded\": boolean\n"
            "}"
        ),
        "GeneralQ&A": (
            "Answer the user's question using only the KNOWLEDGE CONTEXT above.\n"
            "Respond in this JSON structure:\n"
            "{\n"
            "  \"answer\": \"string\",\n"
            "  \"confidence\": number,\n"
            "  \"citations\": [\"chunk_id\", ...],\n"
            "  \"grounded\": boolean\n"
            "}"
        )
    }

    def build_system_prompt(self, enriched_context: EnrichedContext, query: str) -> str:
        """
        Compiles the full system prompt by populating the template with enriched context parameters.
        """
        context_frame = enriched_context.context_frame
        request_context = enriched_context.request_context

        # 1. Format chunks with citations
        chunks_str = ""
        if enriched_context.no_grounding_found or not enriched_context.retrieved_chunks:
            chunks_str = "[NOTICE: No grounding knowledge found. Flag uncertainty and reply accordingly.]"
        else:
            for chunk in enriched_context.retrieved_chunks:
                chunks_str += (
                    f"--- Chunk Citation ID: {chunk.chunk_id} (Source: {chunk.title}, Ref: {chunk.section_ref}) ---\n"
                    f"{chunk.text}\n\n"
                )

        # Append knowledge graph entity relationship lines if present
        if enriched_context.kg_relations:
            chunks_str += "--- Knowledge Graph Entity Relationships ---\n"
            chunks_str += "\n".join(enriched_context.kg_relations) + "\n\n"

        # 2. Format memory turns
        memory = context_frame.memory
        memory_str = ""
        if memory.summary:
            memory_str += f"Compacted History Summary: {memory.summary}\n"
        
        for turn in memory.turns:
            memory_str += f"- {turn.role}: {turn.content}\n"

        if not memory_str:
            memory_str = "No recent session turns."

        # 3. Determine formatting instructions based on intent
        intent = context_frame.intent
        output_format = self.TASK_FORMATS.get(intent, self.TASK_FORMATS["GeneralQ&A"])

        # 4. Populate Template
        system_prompt = self.SYSTEM_TEMPLATE.format(
            tenant_name=request_context.tenant.tenant_name,
            industry=request_context.tenant.industry,
            retrieved_chunks_with_citations=chunks_str,
            summary_and_recent_turns=memory_str,
            username=request_context.user.username,
            role=request_context.user.role.value if hasattr(request_context.user.role, "value") else request_context.user.role,

            department=request_context.user.department or "None",
            user_query=query,
            output_format_instructions=output_format
        )

        return system_prompt
