Project Axiom: Enterprise AI PlatformPowered by the Octagonal Cognitive Intelligence Framework (OCIF)Project Axiom is a production-grade, modular, cloud-native Enterprise AI Platform governed by the Octagonal Cognitive Intelligence Framework (OCIF)[cite: 1]. It serves as a unifying substrate that allows conversational UIs, copilots, autonomous agents, Retrieval-Augmented Generation (RAG), and complex workflow automations to safely coexist, share enterprise infrastructure, and operate under a single, non-bypassable decision governance layer[cite: 1].## The Core Problem SpaceTraditional enterprise AI adoption often leads to fragmented capabilities: siloed chatbots without knowledge access, RAG pipelines lacking execution authority, and autonomous agents operating with no safety or audit controls[cite: 1]. This fragmentation results in point-solution sprawl, duplicate infrastructure spend, and critical compliance vulnerabilities[cite: 1].Axiom solves this by treating perception, context, knowledge, orchestration, reasoning, decision governance, and experience as first-class, independently scalable architectural layers[cite: 1].## Architectural Framework (OCIF Layer Model)The framework models enterprise AI cognition into eight sequential, composable layers, prioritizing strict governance before any real-world action is taken[cite: 1, 7].Code snippetflowchart TD
    L1["Layer 1 — Perception<br/>Input Capture & Normalization"] 
    L2["Layer 2 — Capture<br/>Gateway, Auth & Streaming"]
    L3["Layer 3 — Context Intelligence<br/>Intent, Entities & Memory"]
    L4["Layer 4 — Knowledge Enrichment<br/>Hybrid RAG & Knowledge Graph"]
    L5["Layer 5 — Intelligence Orchestration<br/>Agent Runtime & Planning"]
    L6["Layer 6 — Cognition<br/>Model-Agnostic LLM Inference"]
    L7["Layer 7 — Decision & Action (META CORE)<br/>Guardrails, HITL & Audit"]
    L8["Layer 8 — Experience<br/>UIs, Dashboards & Public APIs"]

    L1 --> L2 --> L3 --> L4 --> L5 --> L6 --> L7 --> L8
    L7 -.->|Feedback & Correction| L5
    L8 -.->|User Feedback Loop| L3
### The Layer BreakdownLayerResponsibilityKey SpecificationL1: PerceptionNormalizes inbound signals (text, voice, docs, APIs)[cite: 7].Speech-to-text, OCR, document parsing, schema mapping[cite: 7].L2: CaptureSecures ingress, resolves identity, manages sessions[cite: 7].API Gateway routing, OAuth2/JWT authentication, Kafka publishing[cite: 7].L3: Context IntelligenceIdentifies user intent and retains long/short-term memory[cite: 7].Intent classification, NER pipelines, Redis/PostgreSQL memory management[cite: 6, 7].L4: Knowledge EnrichmentGrounds requests in authoritative enterprise knowledge bases[cite: 7].Vector search (Pinecone), hybrid ranking (RRF), Knowledge Graph queries[cite: 6, 7].L5: OrchestrationFormulates execution plans and coordinates multi-agent routines[cite: 7].Prompt templating, tool registry validation, stateful LangGraph runtimes[cite: 5, 6, 7].L6: CognitionExecutes core reasoning and generates structured outputs[cite: 7].Model-agnostic abstraction layer (OpenAI, Claude, Gemini, Llama)[cite: 1, 7].L7: Decision & ActionMETA CORE: Mandatory governance checkpoint before any action[cite: 1, 7].Policy engine, hallucination detection, Human-in-the-Loop (HITL), tamper-evident audit logs[cite: 6, 7].L8: ExperienceHandles front-end delivery and user continuous learning loops[cite: 7].Next.js chat interfaces, operational dashboards, analytics telemetry[cite: 1, 3, 7].The Patent-Worthy Innovation (Layer 7): Unlike standard agent frameworks where an LLM calls tools directly, Axiom interposes a mandatory, non-bypassable policy engine between reasoning and action[cite: 7]. If an output triggers a high risk threshold, it is automatically routed to a Human-in-the-Loop queue for confirmation, writing a cryptographically chained ledger entry for compliance auditing[cite: 6, 7].## Key Platform FeaturesConversational Copilot Widgets: Embeddable assistants with contextual memory and multi-turn citation tracking[cite: 3].Enterprise Hybrid RAG: Document ingestion pipeline deploying Reciprocal Rank Fusion (RRF) across semantic vector namespaces and relational keyword structures[cite: 6].Multi-Agent Workflow Builder: Visual execution graphs connecting discrete triggers, tool registries, and model endpoints[cite: 3].Tamper-Evident Auditing: Chronological SHA-256 chained ledger recording all reasoning states, retrieved sources, policy passes, and final outcomes[cite: 6].Multi-Tenant Compute Isolation: Comprehensive defense-in-depth architecture enforcing database Row-Level Security (RLS) alongside tenant-partitioned vector indexing[cite: 8, 9].## Reference Technology StackProject Axiom is designed around a modern, vendor-neutral, cloud-native stack[cite: 1]:Frontend: React, Next.js, Tailwind CSS, TypeScript[cite: 1]Backend & Frameworks: Python, FastAPI, LangGraph, LangChain, LlamaIndex[cite: 1]Databases & Caches: PostgreSQL (Multi-AZ RDS), Pinecone (Vector Store), Redis (ElastiCache)[cite: 1, 5]Event Broker: Apache Kafka (Amazon MSK)[cite: 1, 5]Infrastructure & CI/CD: Docker, Kubernetes (Amazon EKS), AWS WAF/CloudFront, GitHub Actions[cite: 1, 5, 8]## Repository StructurePlaintextaxiom-core/
├── apps/
│   ├── frontend/             # Next.js user interfaces & dashboards (L8)
│   └── gateway/              # FastAPI entrypoint & token auth middleware (L2)
├── services/
│   ├── context/              # Intent parsing & conversational memory (L3)
│   ├── enrichment/           # Document ingestion & Pinecone query routing (L4)
│   ├── orchestration/        # LangGraph state machine & tool registry (L5)
│   ├── cognition/            # Multi-provider LLM abstraction interface (L6)
│   └── decision/             # Policy evaluation, risk calculation & audit (L7)
├── deployment/
│   ├── helm/                 # Kubernetes namespace orchestration charts
│   └── terraform/            # Infrastructure-as-Code for AWS/Pinecone footprints
└── docs/                     # Full 20-part specifications (Vision, BRD, PRD, SRS)
## Getting Started### PrerequisitesDocker & Docker ComposeKubernetes Cluster (or local alternative like Minikube)Python 3.11+ & Node.js 18+### Quickstart (Local Development Environment)Clone the repository and initialize environmental values:Bashgit clone https://github.com/enterprise-ai/axiom-core.git
cd axiom-core
cp .env.example .env
Spin up core data-tier services (PostgreSQL, Redis, Mock Kafka):Bashdocker-compose -f deployment/docker-compose.local.yml up -d
Initialize database schemas and default tenant policies:Bashcd services/decision
pip install -r requirements.txt
python scripts/init_db.py
Launch the local orchestration cluster:Bashcd ../../
docker-compose -f deployment/docker-compose.apps.yml up --build
The platform API gateway will now be running locally at http://localhost:8080[cite: 10]. Access the visual developer admin workspace at http://localhost:3000 to register your enterprise tools, define compliance policy packs, and run sample pipelines[cite: 3, 6].
