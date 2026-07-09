# Product Vision Document: Axiom AI Platform
*(Legacy Name: OctaMind)*

## 1. Executive Summary
Axiom is an enterprise-grade AI Operating System and Engineering Intelligence Platform designed to serve as the cognitive foundation for IoT orchestration and developer workflow automation. While standard LLMs are treated as simple chat interfaces, Axiom treats the LLM as merely one module within a larger, self-governing cognitive wrapper.

The product encompasses the entire ecosystem around the language model: data ingestion parsing, custom tokenizers/embeddings, local vector and graph databases, deterministic cognitive layers, multi-agent planners, sandboxed execution runtime, and performance monitoring dashboards.

---

## 2. Product Evolution Path
The platform evolves through four distinct stages:

```
[V1: Open-weight LLM + Custom Wrapper]
                   ↓
   [V2: Fine-Tuned Engineering Model]
                   ↓
 [V3: Custom Tokenizer, Embeddings & Data Pipeline]
                   ↓
    [V4: Custom Engineering Transformer Model]
```

*   **V1: Open-Weight Integration**: Orchestrates open-weight models (e.g. Llama 3, Qwen) using a deterministic 8-layer cognitive pipeline and custom context engines.
*   **V2: Domain Specialization**: Integrates fine-tuned adapters (LoRA/QLoRA) specialized in engineering schemas, database designs, and system code.
*   **V3: Proprietary Foundations**: Introduces custom tokenizers and embedding models optimized for log metrics and code semantics, alongside custom training pipelines.
*   **V4: Custom Transformer**: A fully custom-trained transformer model built from scratch on proprietary enterprise engineering data.

---

## 3. Core Architectural Modules
The platform is structured into independent subsystems:

1.  **Frontend User Portal**: React/Vite web application providing specialized interfaces for system architecture drawing, code generation, and deployment monitoring.
2.  **Backend Services & REST APIs**: FastAPI-based REST API managing authentication, RBAC, projects, sessions, logs, and database configurations.
3.  **AI Gateway & Router**: Central gateway coordinating queries between prompt builders, planners, and active agents.
4.  **8-Layer Cognitive Engine**: Coordinates the processing flow (Perception, Capture, Normalization, Enrichment, Synthesis, Cognition, Prescription, Experience).
5.  **Knowledge & Parsing Engine**: Customs parsers and chunking algorithms feeding concepts and relationships into a local Knowledge Graph and Vector Database.
6.  **Memory Engine**: Maintains short-term thread states and long-term project/user preferences across execution cycles.
7.  **Reasoning & Agent Framework**: Orchestrates specialized autonomous agents (Architecture, Backend, Frontend, IoT, Database, DevOps, Security) without external agentic dependencies.
8.  **Execution & Sandboxing Engine**: Validates, tests, and deploys scripts in a secure, isolated local sandbox runtime.
