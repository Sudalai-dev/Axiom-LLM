# Coding Standards & Guidelines: Axiom Platform

## 1. Python Syntax & Style Rules

### 1.1 Formatting Standards
*   Code must conform strictly to **PEP 8** style guidelines.
*   Use 4 spaces for indentation. Never use tab characters.
*   Max line length must not exceed 120 characters.

### 1.2 Type Hinting & Annotations
*   All function and method signatures must declare parameter types and return type hints.
*   Import standard types from the `typing` module (e.g. `Dict`, `List`, `Any`, `Optional`).
*   Example:
    ```python
    from typing import Dict, Any, List
    
    def process_data(payload: Dict[str, Any], limit: int) -> List[str]:
        # Implementation
        return []
    ```

---

## 2. Platform Architecture Constraints

### 2.1 No External APIs or Services
*   All modules must execute locally inside the isolation boundary.
*   Do not import network clients designed for external APIs (e.g. `openai`, `anthropic`).
*   No cloud calls are allowed. If communicating with an LLM, use local endpoint wrappers (such as a local vLLM REST endpoint or local PyTorch loaders).

### 2.2 Volatile Memory Management
*   The `SynthesisLayer` state must be transient.
*   Do not cache intermediate synthesized context payloads to persistent disk databases; keep them in volatile memory structures and clean them up after execution is complete.

---

## 3. Cognitive Engine Implementations
*   Every engine layer must inherit from `BaseLayer` and return a dictionary containing `"status"` keys.
*   Exceptions must be logged using Python's standard `logging` library instead of being printed directly to standard output.
