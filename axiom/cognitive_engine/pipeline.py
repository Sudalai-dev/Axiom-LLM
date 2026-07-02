import logging
from typing import Dict, Any, List

from axiom.cognitive_engine.perception import PerceptionLayer
from axiom.cognitive_engine.capture import CaptureLayer
from axiom.cognitive_engine.normalization import NormalizationLayer
from axiom.cognitive_engine.enrichment import EnrichmentLayer
from axiom.cognitive_engine.synthesis import SynthesisLayer
from axiom.cognitive_engine.cognition import CognitionLayer
from axiom.cognitive_engine.prescription import PrescriptionLayer
from axiom.cognitive_engine.experience import ExperienceLayer

# Evolved AI OS Sub-Engine Imports
from axiom.context_engine.context import ContextEngine
from axiom.planning_engine.planner import PlanningEngine
from axiom.agent_engine.agents import AgentManager
from axiom.validation_engine.validator import ValidationEngine
from axiom.execution_engine.executor import ExecutionEngine
from axiom.experience_engine.experience import ExperienceEngine
from axiom.ai.adapter import ModelProviderAdapter

class AxiomCognitivePipeline:
    """
    Evolved Axiom Cognitive Pipeline: Orchestrates all 33 modules in the
    AI Operating System, running event-driven planning, collaborative agents,
    sandboxed execution, security validation, and auto-correcting feedback loops.
    """
    def __init__(self, workspace_path: str = "D:\\Tasks\\Axiom - LLM"):
        # Legacy Layers
        self.perception = PerceptionLayer()
        self.capture = CaptureLayer(workspace_path=workspace_path)
        self.normalization = NormalizationLayer()
        self.enrichment = EnrichmentLayer()
        self.synthesis = SynthesisLayer()
        self.cognition = CognitionLayer(use_simulated_llm=True)
        self.prescription = PrescriptionLayer()
        self.experience = ExperienceLayer()
        
        # New OS Modules
        self.context_engine = ContextEngine()
        self.planning_engine = PlanningEngine()
        self.agent_manager = AgentManager()
        self.validation_engine = ValidationEngine()
        self.execution_engine = ExecutionEngine()
        self.experience_engine = ExperienceEngine()
        self.inference_adapter = ModelProviderAdapter()
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("AxiomOSPipeline")

    def execute(self, query: str, session_id: str = "default-session", max_correction_attempts: int = 3) -> Dict[str, Any]:
        attempts = 0
        current_query = query
        
        # Mock Session and User parameters (in production, retrieved from storage engine)
        user_info = {"username": "admin", "role": "Admin"}
        project_info = {"name": "Axiom Core Workspace", "description": "Local-first IoT platform"}
        goals = ["Decompose the request", "Generate code", "Validate and execute sandboxed tests"]
        history = [{"role": "system", "content": "Session initialized"}]
        heuristics = ["Always check imports", "Strip print statements"]

        while attempts < max_correction_attempts:
            attempts += 1
            self.logger.info(f"Executing OS Pipeline - Attempt {attempts}/{max_correction_attempts}")
            
            payload = {
                "query": current_query,
                "session_id": session_id,
                "attempt": attempts
            }

            # 1. Perception
            payload = self.perception.run(payload)
            if payload.get("status") == "REJECTED":
                return payload

            # 2. Context Engineering
            eng_context = self.context_engine.compile_context(
                user_info=user_info,
                project_info=project_info,
                goals=goals,
                history=history,
                heuristics=heuristics
            )
            payload["engineering_context"] = eng_context

            # 3. Task Planning
            plan = self.planning_engine.generate_plan(current_query, eng_context)
            payload["execution_plan"] = plan

            # 4. Context Capture (Local Knowledge base query)
            payload = self.capture.run(payload)
            payload = self.normalization.run(payload)
            payload = self.enrichment.run(payload)
            payload = self.synthesis.run(payload)
            
            # 5. Model Inference (Decoupled Adapter Call)
            synthesized_context = str(payload.get("synthesis_model"))
            inference_completion = self.inference_adapter.execute_completion(synthesized_context)
            payload["cognition_reasoning"] = inference_completion

            # 6. Collaborative Agent Execution
            agent_results = self.agent_manager.execute_plan(plan, eng_context)
            payload["agent_results"] = agent_results

            # 7. Sandbox Execution & Output Validation
            execution_reports = []
            has_errors = False
            error_details = []

            for res in agent_results:
                art = res.get("artifacts", {})
                content = art.get("content", "")
                art_type = art.get("type", "")

                # Validation Engine Check
                val_res = self.validation_engine.validate_artifact(art_type, content)
                if val_res.get("status") == "FAILED":
                    has_errors = True
                    error_details.append(f"Validation failure in {art_type}: {', '.join(val_res.get('errors', []))}")
                    continue

                # Execution Sandbox Run (for Python scripts)
                if art_type == "python":
                    run_report = self.execution_engine.run_sandbox(content)
                    execution_reports.append(run_report)
                    if run_report.get("status") == "RUNTIME_ERROR":
                        has_errors = True
                        error_details.append(f"Sandbox execution error: {run_report.get('error')}")

            # 8. Experience Rendering or Closed-loop Rerun
            if not has_errors:
                # Default empty report if no python scripts ran
                final_exec_report = execution_reports[0] if execution_reports else {"status": "PASSED", "stdout": ""}
                
                # Render formatted presentation output
                output_markdown = self.experience_engine.render(
                    reasoning_trace=payload.get("cognition_reasoning", ""),
                    agent_results=agent_results,
                    execution_logs=final_exec_report
                )
                
                payload["experience_output"] = output_markdown
                payload["status"] = "SUCCESS"
                break
            else:
                self.logger.warning("Errors detected in validation/execution layer. Executing Closed-loop Healing...")
                error_context = "\n".join(error_details)
                current_query = (
                    f"Correct the following validation/execution errors:\n{error_context}\n"
                    f"Original Prompt: {query}"
                )
                history.append({"role": "system", "content": f"Errors encountered: {error_context}"})
                
        payload["attempt"] = attempts
        return payload
