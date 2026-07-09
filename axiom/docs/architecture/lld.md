# Low-Level Design (LLD): Axiom Platform

## 1. Class Interface Specifications

### 1.1 Cognitive Engine Layer Modules
Every layer in the 8-layer engine must implement a uniform interface:

```python
from typing import Dict, Any

class BaseLayer:
    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives payload dictionary, performs transformation, 
        and returns the updated dictionary.
        """
        raise NotImplementedError
```

*   **`PerceptionLayer`**: Parses `query`, checks against safety rules, classifies `intent` into `["CodeGen", "ArchitectureReview", "GeneralQ&A"]`.
*   **`CaptureLayer`**: Connects to the local vector and graph clients, fetching chunks.
*   **`NormalizationLayer`**: Regex replacement mapping legacy keywords to standard entities.
*   **`EnrichmentLayer`**: Injects target coding guidelines and API schemas.
*   **`SynthesisLayer`**: Combines intermediate inputs to format the LLM prompt payload.
*   **`CognitionLayer`**: Invokes local inference models (vLLM client wrapper).
*   **`PrescriptionLayer`**: Parses markdown code blocks and verifies python script compilation.
*   **`ExperienceLayer`**: Combines execution reports, visual diagrams, and code into final presentation formatting.

### 1.2 Chunk & Ingestion Engines
```python
class ParserEngine:
    def detect_file_type(self, filepath: str) -> str:
        pass
        
    def extract_text(self, filepath: str) -> str:
        pass

class ChunkEngine:
    def split_by_heading(self, text: str) -> list[str]:
        pass
        
    def split_by_paragraph(self, text: str) -> list[str]:
        pass
```

### 1.3 Memory Engine Schema
```python
class MemoryEngine:
    def get_session_memory(self, session_id: str) -> list[dict]:
        pass
        
    def save_message(self, session_id: str, role: str, content: str):
        pass
        
    def get_long_term_profile(self, user_id: str, project_id: str) -> dict:
        pass
```

---

## 2. Multi-Agent Planning Architecture
The Agent Framework operates as a state machine coordinate router:

```python
class AgentManager:
    def __init__(self):
        self.agents = {
            "architecture": ArchitectureAgent(),
            "code": CodeAgent(),
            "devops": DevOpsAgent(),
            "iot": IoTAgent()
        }

    def dispatch(self, task_plan: dict) -> dict:
        # Sequentially routes sub-tasks to the correct agents and aggregates responses
        pass
```
Each agent executes inside the cognitive sandbox framework, using standard prompt templates.
