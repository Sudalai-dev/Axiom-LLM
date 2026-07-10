"""
Industry pattern catalog for deterministic solution synthesis.

Each IndustryPattern supplies everything the SolutionSynthesizer
(ocif/engines/reasoning.py) needs to compose a domain-appropriate
SolutionDocument section: architecture components, tech stack, ER model,
API surface, workflow sequence, and extra security/risk/roadmap notes.
Selection is driven by ProjectUnderstandingFrame.industry/system_type
(see select_pattern below) rather than the narrow IT/IoT keyword match this
replaces — a hospital or school request now resolves to its own pattern
instead of silently collapsing onto the generic web pattern.

Adding a new industry means adding one IndustryPattern here — no other file
needs to change.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class IndustryPattern:
    key: str
    name: str
    components: List[Tuple[str, str]]                 # (name, description)
    stack: List[Tuple[str, str, str]]                  # (layer, choice, rationale)
    er_diagram: str                                    # mermaid erDiagram body
    er_notes: str
    api_rows: List[str]                                # markdown table rows
    workflow_diagram: str                              # mermaid sequenceDiagram body
    workflow_narrative: str
    security_extra: str = ""
    deployment_extra: str = ""
    monitoring_extra: str = ""
    testing_extra: str = ""
    roadmap_phase2_focus: str = "Implement the primary flows and core feature set."
    risks_extra: List[Tuple[str, str, str, str]] = field(default_factory=list)  # (risk, likelihood, impact, mitigation)
    future_extra: List[str] = field(default_factory=list)


GENERIC_SOFTWARE = IndustryPattern(
    key="generic_software",
    name="Layered Service Architecture (API-first)",
    components=[
        ("API Gateway / Reverse Proxy", "TLS termination, routing, rate limiting."),
        ("Application Service", "Business logic behind typed REST endpoints."),
        ("Data Layer", "Repository pattern over the relational store with migrations."),
        ("Background Workers", "Async jobs: notifications, exports, scheduled tasks."),
        ("Web Client", "Responsive SPA consuming the API."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Database", "PostgreSQL", "ACID guarantees, JSONB flexibility, mature operations."),
        ("Cache", "Redis", "Session store and hot-path caching."),
        ("Frontend", "React + TypeScript", "Type-safe component-driven UI."),
        ("Packaging", "Docker + docker-compose", "Reproducible environments from dev to prod."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    TENANT ||--o{ USER : has\n"
        "    USER ||--o{ SESSION : opens\n"
        "    TENANT ||--o{ RESOURCE : owns\n"
        "    RESOURCE ||--o{ EVENT : generates\n"
        "    USER ||--o{ AUDIT_LOG : recorded_in\n"
        "    RESOURCE {\n        uuid resource_id PK\n        uuid tenant_id FK\n        string name\n        string status\n        timestamptz created_at\n    }\n"
        "    EVENT {\n        uuid event_id PK\n        uuid resource_id FK\n        string type\n        jsonb payload\n        timestamptz ts\n    }"
    ),
    er_notes=(
        "PostgreSQL is the system of record. All tenant-scoped tables carry a tenant_id with "
        "row-level security; JSONB columns absorb schema-flexible payloads; schema changes are "
        "managed through versioned migrations (Alembic)."
    ),
    api_rows=[
        "| GET | /api/v1/resources | List resources (paginated, filtered) |",
        "| POST | /api/v1/resources | Create a resource |",
        "| GET | /api/v1/resources/{id} | Fetch a resource |",
        "| PATCH | /api/v1/resources/{id} | Update a resource |",
        "| DELETE | /api/v1/resources/{id} | Remove a resource |",
        "| GET | /api/v1/events?since= | Event history for auditing/sync |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant U as User\n"
        "    participant G as Gateway\n"
        "    participant S as Application Service\n"
        "    participant D as Database\n"
        "    participant W as Worker\n"
        "    U->>G: authenticated request\n"
        "    G->>S: route + authorize\n"
        "    S->>D: transactional read/write\n"
        "    S-->>W: enqueue async side-effects\n"
        "    S->>U: typed response\n"
        "    W->>U: eventual notification"
    ),
    workflow_narrative=(
        "Requests flow through the gateway for authentication and rate limiting, execute "
        "transactionally in the application service, and defer slow side-effects to workers."
    ),
)

INDUSTRIAL_IOT = IndustryPattern(
    key="industrial_iot",
    name="Edge-to-Cloud Event-Driven AIoT Architecture",
    components=[
        ("Edge Gateway", "Buffers and normalizes device telemetry; store-and-forward under intermittent connectivity."),
        ("MQTT Broker", "Central pub/sub backbone for device telemetry and command topics (QoS 1, retained state)."),
        ("Stream Processor", "Consumes telemetry, applies rules/ML models, detects anomalies, and emits domain events."),
        ("Time-Series Store", "Persists raw and aggregated telemetry for querying and dashboards."),
        ("Application API", "REST/WebSocket service exposing state, history, alerts, and configuration."),
        ("Alerting Service", "Deduplicates, escalates, and routes notifications to on-call channels."),
        ("Web Dashboard", "Role-scoped real-time visualization and administration UI."),
    ],
    stack=[
        ("Device Connectivity", "MQTT (Eclipse Mosquitto / EMQX)", "Industry-standard lightweight pub/sub for constrained devices; QoS levels fit unreliable links."),
        ("Edge Runtime", "Python edge agent in Docker", "Uniform packaging on gateways; easy protocol adapters (Modbus/OPC-UA)."),
        ("Stream Processing", "Python asyncio workers (Kafka consumers where scale demands)", "Simple to operate; upgrade path to Kafka Streams/Flink."),
        ("Time-Series Storage", "TimescaleDB (PostgreSQL extension)", "SQL ergonomics + hypertable compression; one operational database engine."),
        ("Application API", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Frontend", "React + TypeScript", "Component ecosystem for real-time dashboards; type safety."),
        ("Orchestration", "Docker Compose -> Kubernetes", "Compose for development, K8s for production scale and rollout control."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    DEVICE ||--o{ TELEMETRY : emits\n"
        "    DEVICE ||--o{ ALERT : triggers\n"
        "    DEVICE }o--|| SITE : located_at\n"
        "    ALERT ||--o{ NOTIFICATION : dispatches\n"
        "    DEVICE ||--o{ MAINTENANCE_TICKET : requires\n"
        "    DEVICE {\n        uuid device_id PK\n        string name\n        string protocol\n        string status\n    }\n"
        "    TELEMETRY {\n        uuid device_id FK\n        timestamptz ts\n        string metric\n        double value\n    }\n"
        "    ALERT {\n        uuid alert_id PK\n        uuid device_id FK\n        string severity\n        string state\n        timestamptz raised_at\n    }\n"
        "    MAINTENANCE_TICKET {\n        uuid ticket_id PK\n        uuid device_id FK\n        string status\n        double predicted_rul_hours\n    }"
    ),
    er_notes=(
        "Telemetry is stored in a TimescaleDB hypertable partitioned by time, with continuous "
        "aggregates for dashboard rollups and a retention policy for raw data. Maintenance tickets "
        "and remaining-useful-life estimates live in standard PostgreSQL tables linked to devices, "
        "with row-level tenant/site isolation."
    ),
    api_rows=[
        "| GET | /api/v1/devices | List registered devices with status |",
        "| POST | /api/v1/devices | Register/onboard a device |",
        "| GET | /api/v1/devices/{id}/telemetry?from&to | Query historical telemetry |",
        "| GET | /api/v1/alerts?state=open | List active alerts |",
        "| POST | /api/v1/alerts/{id}/ack | Acknowledge an alert |",
        "| GET | /api/v1/devices/{id}/rul | Remaining-useful-life estimate for a device |",
        "| WS | /api/v1/stream | Real-time telemetry/alert push |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant D as Device\n"
        "    participant G as Edge Gateway\n"
        "    participant B as MQTT Broker\n"
        "    participant P as Stream Processor\n"
        "    participant S as Time-Series Store\n"
        "    participant A as Alerting Service\n"
        "    participant U as Dashboard\n"
        "    D->>G: telemetry sample\n"
        "    G->>B: publish topic site/{id}/telemetry (QoS 1)\n"
        "    B->>P: consume telemetry\n"
        "    P->>S: persist + aggregate\n"
        "    alt threshold breached / RUL degrading\n"
        "        P->>A: raise alert + maintenance ticket\n"
        "        A->>U: push notification (WS)\n"
        "    end\n"
        "    U->>S: query history via API"
    ),
    workflow_narrative=(
        "The primary flow is telemetry ingestion -> evaluation -> persistence -> notification, "
        "with anomaly/degradation detection feeding predictive-maintenance ticketing. Edge buffering "
        "covers connectivity gaps; alert deduplication prevents notification storms."
    ),
    security_extra=(
        "\n- **Device identity:** per-device X.509 certificates or credential rotation; "
        "mutual TLS on MQTT; topic-level ACLs so devices publish/subscribe only to their own topics."
        "\n- **OT/IT segregation:** industrial protocols (Modbus/OPC-UA) terminate at the edge "
        "gateway; nothing on the OT network is directly internet-reachable."
    ),
    roadmap_phase2_focus="Implement telemetry ingestion, edge buffering, and the alerting/predictive-maintenance pipeline.",
    risks_extra=[
        ("Unreliable device connectivity causes data loss", "high", "medium",
         "Edge store-and-forward buffering, QoS 1 delivery, idempotent ingestion with deduplication."),
    ],
    future_extra=["Predictive maintenance models trained on accumulated telemetry (remaining-useful-life estimation)."],
)

HEALTHCARE = IndustryPattern(
    key="healthcare",
    name="Clinical Workflow & Patient Records Architecture",
    components=[
        ("API Gateway", "TLS termination, authentication, audit logging for every clinical access."),
        ("Patient Records Service", "Owns EMR/EHR data — demographics, encounters, orders, results."),
        ("Scheduling & Appointment Service", "Manages appointment slots, provider calendars, and reminders."),
        ("Clinical Workflow Engine", "Drives encounter/order/results state machines with role-based handoffs."),
        ("Integration Engine", "HL7/FHIR interface layer to labs, imaging, and pharmacy systems."),
        ("Web Portal", "Role-scoped views for clinicians, front-desk staff, and patients."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts; strong fit for HL7/FHIR integration libraries."),
        ("Database", "PostgreSQL (encrypted at rest)", "ACID guarantees required for clinical data; mature row-level security."),
        ("Interoperability", "FHIR R4 API layer", "Industry-standard healthcare data exchange with external systems."),
        ("Cache", "Redis", "Session store and appointment-slot locking."),
        ("Frontend", "React + TypeScript", "Type-safe, role-scoped clinical/patient UI."),
        ("Packaging", "Docker + Kubernetes", "Isolated, auditable deployment units for compliance."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    PATIENT ||--o{ APPOINTMENT : books\n"
        "    PATIENT ||--o{ ENCOUNTER : has\n"
        "    DOCTOR ||--o{ APPOINTMENT : attends\n"
        "    DOCTOR ||--o{ ENCOUNTER : conducts\n"
        "    ENCOUNTER ||--o{ ORDER : generates\n"
        "    ORDER ||--o{ RESULT : produces\n"
        "    PATIENT {\n        uuid patient_id PK\n        string mrn\n        string name\n        date dob\n    }\n"
        "    ENCOUNTER {\n        uuid encounter_id PK\n        uuid patient_id FK\n        uuid doctor_id FK\n        timestamptz started_at\n        string status\n    }\n"
        "    ORDER {\n        uuid order_id PK\n        uuid encounter_id FK\n        string type\n        string status\n    }"
    ),
    er_notes=(
        "PostgreSQL with column-level encryption for PHI (patient-identifiable data); every table "
        "carries a tenant/facility scope. All reads/writes to PATIENT and ENCOUNTER are audit-logged "
        "with the accessing clinician's identity for HIPAA-style compliance."
    ),
    api_rows=[
        "| GET | /api/v1/patients/{id} | Fetch patient demographics and summary |",
        "| POST | /api/v1/appointments | Book an appointment slot |",
        "| GET | /api/v1/doctors/{id}/schedule | Doctor's appointment calendar |",
        "| POST | /api/v1/encounters | Open a clinical encounter |",
        "| POST | /api/v1/encounters/{id}/orders | Place a lab/imaging/pharmacy order |",
        "| GET | /api/v1/orders/{id}/results | Retrieve order results |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant P as Patient\n"
        "    participant F as Front Desk\n"
        "    participant S as Scheduling Service\n"
        "    participant D as Doctor\n"
        "    participant E as Encounter Service\n"
        "    participant L as Lab/Imaging\n"
        "    P->>F: request appointment\n"
        "    F->>S: check availability + book\n"
        "    S->>P: confirmation + reminder\n"
        "    D->>E: open encounter at visit time\n"
        "    E->>L: place order\n"
        "    L->>E: result available\n"
        "    E->>D: result review + care plan update"
    ),
    workflow_narrative=(
        "The primary flow is appointment booking -> encounter -> order -> result -> care-plan update, "
        "with front-desk, doctor, and patient each interacting through role-scoped views."
    ),
    security_extra=(
        "\n- **PHI protection:** field-level encryption for patient-identifiable data, strict "
        "need-to-know access control per clinical role, and immutable audit trails on every access "
        "to patient records (compliance requirement, not optional)."
        "\n- **Consent management:** patient consent status gates data sharing with external systems."
    ),
    roadmap_phase2_focus="Implement patient records, scheduling, and the encounter/order/result clinical workflow.",
    risks_extra=[
        ("PHI exposure through misconfigured access control", "low", "high",
         "Role-based access control reviewed against a clinical-role matrix; automated compliance scanning in CI."),
    ],
    future_extra=["Clinical decision support suggestions surfaced during encounters."],
)

EDUCATION = IndustryPattern(
    key="education",
    name="Academic Workflow & Learning Records Architecture",
    components=[
        ("API Gateway", "Authentication (SSO), routing, rate limiting."),
        ("Identity & Roster Service", "Manages students, faculty, and class/section rosters."),
        ("Attendance Service", "Records and reconciles attendance events per session."),
        ("Course & Assessment Service", "Owns course structure, assignments, and grading."),
        ("Notification Service", "Alerts students/guardians/faculty on attendance and grade events."),
        ("Web Portal", "Role-scoped views for students, faculty, and administrators."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Database", "PostgreSQL", "ACID guarantees for grading/attendance records; mature operations."),
        ("Identity", "OAuth2/SSO (institutional identity provider)", "Single sign-on across academic systems."),
        ("Cache", "Redis", "Session store and roster caching."),
        ("Frontend", "React + TypeScript", "Type-safe, role-scoped academic UI."),
        ("Packaging", "Docker + docker-compose", "Reproducible environments from dev to prod."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    STUDENT ||--o{ ATTENDANCE_RECORD : has\n"
        "    STUDENT ||--o{ ENROLLMENT : has\n"
        "    FACULTY ||--o{ CLASS_SESSION : teaches\n"
        "    CLASS_SESSION ||--o{ ATTENDANCE_RECORD : generates\n"
        "    ENROLLMENT }o--|| COURSE : in\n"
        "    STUDENT {\n        uuid student_id PK\n        string name\n        string roll_number\n    }\n"
        "    CLASS_SESSION {\n        uuid session_id PK\n        uuid faculty_id FK\n        uuid course_id FK\n        timestamptz starts_at\n    }\n"
        "    ATTENDANCE_RECORD {\n        uuid record_id PK\n        uuid student_id FK\n        uuid session_id FK\n        string status\n        timestamptz marked_at\n    }"
    ),
    er_notes=(
        "PostgreSQL is the system of record for rosters, enrollments, and attendance. Attendance "
        "records are append-only (corrections create a new audited record rather than mutating "
        "history) so disputes can be reconciled against an immutable trail."
    ),
    api_rows=[
        "| GET | /api/v1/students/{id} | Fetch student profile and enrollment |",
        "| GET | /api/v1/faculty/{id}/sessions | Faculty's class-session schedule |",
        "| POST | /api/v1/sessions/{id}/attendance | Mark attendance for a session |",
        "| GET | /api/v1/students/{id}/attendance?course= | Attendance history for a student |",
        "| POST | /api/v1/courses/{id}/assignments | Create an assignment |",
        "| GET | /api/v1/students/{id}/grades | Retrieve grade summary |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant St as Student\n"
        "    participant Fa as Faculty\n"
        "    participant A as Attendance Service\n"
        "    participant N as Notification Service\n"
        "    participant G as Guardian\n"
        "    Fa->>A: open class session\n"
        "    St->>A: check in (or Fa marks manually)\n"
        "    A->>A: reconcile session roster vs check-ins\n"
        "    alt absence threshold breached\n"
        "        A->>N: raise low-attendance alert\n"
        "        N->>G: notify guardian\n"
        "    end\n"
        "    Fa->>A: review session attendance report"
    ),
    workflow_narrative=(
        "The primary flow is session creation -> attendance capture -> roster reconciliation -> "
        "reporting, with automated alerts when a student's attendance drops below a configured threshold."
    ),
    security_extra=(
        "\n- **Student data protection:** access to student records scoped strictly to the student's "
        "own faculty/guardians (FERPA-style data-minimization); guardians see only their own ward's records."
    ),
    roadmap_phase2_focus="Implement roster management, attendance capture, and the reconciliation/reporting flow.",
    future_extra=["Early-warning analytics correlating attendance trends with academic performance."],
)

BANKING_FINTECH = IndustryPattern(
    key="banking_fintech",
    name="Ledger-Centric Financial Services Architecture",
    components=[
        ("API Gateway", "Strong authentication, mTLS, rate limiting, fraud-signal pre-checks."),
        ("Account Service", "Owns account opening, KYC status, and balances."),
        ("Ledger Service", "Append-only double-entry ledger — the system of record for all money movement."),
        ("Payments/Transfer Service", "Orchestrates transfers, holds, and settlement with idempotent processing."),
        ("Fraud & Compliance Engine", "Real-time rule/ML scoring, AML transaction monitoring, case management."),
        ("Web/Mobile Client", "Customer-facing banking UI with strong session security."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts; strict input validation at every boundary."),
        ("Ledger Storage", "PostgreSQL (append-only, double-entry)", "ACID guarantees mandatory for financial correctness; no update/delete on ledger rows."),
        ("Messaging", "Kafka", "Durable, replayable log for payment events and audit trail."),
        ("Cache", "Redis", "Idempotency-key store and rate limiting."),
        ("Frontend", "React + TypeScript", "Type-safe, security-hardened banking UI."),
        ("Orchestration", "Kubernetes", "Isolated, auditable deployment with strict network policies."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    ACCOUNT ||--o{ LEDGER_ENTRY : posts\n"
        "    ACCOUNT ||--o{ TRANSFER : initiates\n"
        "    TRANSFER ||--o{ LEDGER_ENTRY : produces\n"
        "    ACCOUNT ||--o{ KYC_CHECK : requires\n"
        "    ACCOUNT {\n        uuid account_id PK\n        string account_number\n        string status\n        numeric balance\n    }\n"
        "    LEDGER_ENTRY {\n        uuid entry_id PK\n        uuid account_id FK\n        numeric amount\n        string direction\n        timestamptz posted_at\n    }\n"
        "    TRANSFER {\n        uuid transfer_id PK\n        uuid from_account FK\n        uuid to_account FK\n        string status\n        string idempotency_key\n    }"
    ),
    er_notes=(
        "The ledger is append-only double-entry: every transfer produces exactly two balanced "
        "LEDGER_ENTRY rows. Balances are derived, never mutated directly, so the ledger itself is "
        "the audit trail. All monetary columns use fixed-precision numeric types, never floats."
    ),
    api_rows=[
        "| POST | /api/v1/accounts | Open an account (subject to KYC) |",
        "| GET | /api/v1/accounts/{id}/balance | Current balance and hold amount |",
        "| POST | /api/v1/transfers | Initiate a transfer (idempotency-key required) |",
        "| GET | /api/v1/transfers/{id} | Transfer status |",
        "| GET | /api/v1/accounts/{id}/ledger?from&to | Ledger entries for statements/reconciliation |",
        "| POST | /api/v1/compliance/flags | Raise a fraud/AML case |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant C as Customer\n"
        "    participant G as Gateway\n"
        "    participant T as Transfer Service\n"
        "    participant F as Fraud Engine\n"
        "    participant L as Ledger Service\n"
        "    C->>G: initiate transfer (idempotency key)\n"
        "    G->>T: authorize + validate\n"
        "    T->>F: real-time risk score\n"
        "    alt flagged\n"
        "        F->>T: hold for review\n"
        "    else clear\n"
        "        T->>L: post balanced double-entry\n"
        "        L->>C: confirmation + updated balance\n"
        "    end"
    ),
    workflow_narrative=(
        "The primary flow is transfer initiation -> risk scoring -> ledger posting, with idempotency "
        "keys preventing duplicate execution on retry and flagged transactions routed to manual review."
    ),
    security_extra=(
        "\n- **Financial integrity:** idempotency keys on every money-movement endpoint; double-entry "
        "invariants enforced at the database layer, not just application code."
        "\n- **Regulatory:** AML transaction monitoring, KYC gating on account actions, immutable audit "
        "trail retained per regulatory retention requirements."
    ),
    roadmap_phase2_focus="Implement account/ledger core and the transfer flow with idempotency and fraud scoring.",
    risks_extra=[
        ("Duplicate transaction processing under retry/network failure", "medium", "high",
         "Mandatory idempotency keys on all money-movement endpoints; ledger uniqueness constraints."),
        ("Regulatory non-compliance (AML/KYC)", "low", "high",
         "Compliance rules encoded as enforced gates, not advisory checks; periodic third-party audit."),
    ],
)

AUTOMOTIVE = IndustryPattern(
    key="automotive",
    name="Connected Vehicle & Fleet Telematics Architecture",
    components=[
        ("Vehicle Gateway", "Onboard unit normalizing CAN-bus/OBD-II signals for uplink."),
        ("Telematics Ingestion Service", "Receives vehicle location, diagnostics, and driving-event streams."),
        ("Fleet Management Service", "Vehicle/driver assignment, trip history, maintenance scheduling."),
        ("Geofencing & Alerting Engine", "Evaluates location/diagnostic events against configured rules."),
        ("Application API", "REST/WebSocket service for fleet dashboards and driver apps."),
        ("Web Dashboard", "Fleet operator visualization and administration UI."),
    ],
    stack=[
        ("Vehicle Connectivity", "MQTT over cellular/LTE-M", "Lightweight pub/sub suited to intermittent vehicle connectivity."),
        ("Ingestion", "Python asyncio workers + Kafka", "High-throughput ingestion of location/diagnostic streams."),
        ("Storage", "TimescaleDB (PostgreSQL extension)", "Efficient time-series storage for trip/telemetry history."),
        ("Application API", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Frontend", "React + TypeScript", "Real-time fleet map and dashboard UI."),
        ("Orchestration", "Docker Compose -> Kubernetes", "Scales ingestion workers independently of the API tier."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    VEHICLE ||--o{ TRIP : completes\n"
        "    VEHICLE ||--o{ TELEMETRY_EVENT : emits\n"
        "    DRIVER ||--o{ TRIP : drives\n"
        "    VEHICLE ||--o{ MAINTENANCE_RECORD : requires\n"
        "    VEHICLE {\n        uuid vehicle_id PK\n        string vin\n        string status\n    }\n"
        "    TRIP {\n        uuid trip_id PK\n        uuid vehicle_id FK\n        uuid driver_id FK\n        timestamptz started_at\n        timestamptz ended_at\n    }\n"
        "    TELEMETRY_EVENT {\n        uuid vehicle_id FK\n        timestamptz ts\n        double lat\n        double lon\n        jsonb diagnostics\n    }"
    ),
    er_notes=(
        "Telemetry events are stored in a TimescaleDB hypertable partitioned by time; trip and "
        "maintenance records live in standard PostgreSQL tables linked to vehicles and drivers."
    ),
    api_rows=[
        "| GET | /api/v1/vehicles | List fleet vehicles with current status |",
        "| GET | /api/v1/vehicles/{id}/location | Latest known vehicle location |",
        "| GET | /api/v1/vehicles/{id}/trips | Trip history |",
        "| POST | /api/v1/geofences | Configure a geofence rule |",
        "| GET | /api/v1/alerts?state=open | Active fleet alerts |",
        "| WS | /api/v1/stream | Real-time vehicle location/alert push |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant V as Vehicle\n"
        "    participant G as Vehicle Gateway\n"
        "    participant I as Ingestion Service\n"
        "    participant E as Geofencing Engine\n"
        "    participant D as Dashboard\n"
        "    V->>G: CAN-bus/OBD-II signal\n"
        "    G->>I: telemetry uplink\n"
        "    I->>E: evaluate location/diagnostic rules\n"
        "    alt geofence or fault triggered\n"
        "        E->>D: push alert (WS)\n"
        "    end\n"
        "    D->>I: query trip/telemetry history via API"
    ),
    workflow_narrative=(
        "The primary flow is vehicle telemetry uplink -> rule evaluation -> alerting, with fleet "
        "operators consuming both real-time position and historical trip data through the dashboard."
    ),
    roadmap_phase2_focus="Implement telemetry ingestion and the geofencing/alerting pipeline.",
)

CONSTRUCTION = IndustryPattern(
    key="construction",
    name="Project & Site Management Architecture",
    components=[
        ("API Gateway", "Authentication, routing, rate limiting."),
        ("Project Service", "Owns project structure, phases, budgets, and milestones."),
        ("Site & Safety Service", "Tracks site inspections, incidents, and safety compliance records."),
        ("Resource & Equipment Service", "Manages crew assignments and equipment allocation across sites."),
        ("Document/BIM Service", "Stores and versions drawings, BIM models, and permits."),
        ("Web Dashboard", "Role-scoped views for project managers, site supervisors, and clients."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Database", "PostgreSQL", "ACID guarantees for budget/schedule data; mature operations."),
        ("Document/File Storage", "Object storage (S3-compatible)", "Cost-effective storage for drawings/BIM files with versioning."),
        ("Cache", "Redis", "Session store and schedule caching."),
        ("Frontend", "React + TypeScript", "Type-safe project/site dashboard UI."),
        ("Packaging", "Docker + docker-compose", "Reproducible environments from dev to prod."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    PROJECT ||--o{ PHASE : has\n"
        "    PROJECT ||--o{ SITE_INSPECTION : undergoes\n"
        "    PHASE ||--o{ TASK : contains\n"
        "    PROJECT ||--o{ EQUIPMENT_ASSIGNMENT : uses\n"
        "    PROJECT {\n        uuid project_id PK\n        string name\n        numeric budget\n        string status\n    }\n"
        "    SITE_INSPECTION {\n        uuid inspection_id PK\n        uuid project_id FK\n        string result\n        timestamptz inspected_at\n    }\n"
        "    TASK {\n        uuid task_id PK\n        uuid phase_id FK\n        string status\n        date due_date\n    }"
    ),
    er_notes=(
        "PostgreSQL is the system of record for project structure, schedule, and budget tracking; "
        "drawings and BIM models are stored in object storage with metadata rows referencing them."
    ),
    api_rows=[
        "| GET | /api/v1/projects/{id} | Project overview, budget, and schedule status |",
        "| POST | /api/v1/projects/{id}/inspections | Log a site inspection or safety incident |",
        "| GET | /api/v1/projects/{id}/tasks | Task/phase progress |",
        "| POST | /api/v1/equipment/assignments | Assign equipment/crew to a site |",
        "| GET | /api/v1/projects/{id}/documents | List drawings/BIM/permit documents |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant PM as Project Manager\n"
        "    participant S as Site Supervisor\n"
        "    participant P as Project Service\n"
        "    participant I as Site & Safety Service\n"
        "    PM->>P: define phases/tasks/budget\n"
        "    S->>I: log daily inspection/incident\n"
        "    I->>P: update site compliance status\n"
        "    alt safety issue raised\n"
        "        I->>PM: escalate incident\n"
        "    end\n"
        "    PM->>P: review schedule/budget variance"
    ),
    workflow_narrative=(
        "The primary flow is project/task setup -> site inspection and safety logging -> variance "
        "review, with safety incidents escalated to project managers immediately."
    ),
    security_extra="\n- **Site safety compliance:** inspection/incident records are immutable once logged, supporting regulatory audit.",
    roadmap_phase2_focus="Implement project/phase/task structure and the site inspection/safety logging flow.",
)

AGRICULTURE = IndustryPattern(
    key="agriculture",
    name="Farm & Crop Monitoring AIoT Architecture",
    components=[
        ("Field Gateway", "Aggregates soil/weather sensor readings from a field or zone."),
        ("MQTT Broker", "Pub/sub backbone for sensor telemetry from distributed field devices."),
        ("Agronomic Analytics Service", "Evaluates soil moisture, weather, and crop-stage data against thresholds."),
        ("Irrigation Control Service", "Issues irrigation/actuation commands based on analytics recommendations."),
        ("Application API", "REST/WebSocket service exposing field state, history, and recommendations."),
        ("Web Dashboard", "Farm operator visualization and administration UI."),
    ],
    stack=[
        ("Device Connectivity", "MQTT (low-power/LoRaWAN gateway)", "Suited to sparse rural connectivity and battery-powered field sensors."),
        ("Edge Runtime", "Python edge agent", "Uniform packaging for field gateways with intermittent connectivity."),
        ("Time-Series Storage", "TimescaleDB (PostgreSQL extension)", "Efficient storage for soil/weather telemetry history."),
        ("Application API", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Frontend", "React + TypeScript", "Field-map dashboard with real-time sensor overlays."),
        ("Orchestration", "Docker Compose -> Kubernetes", "Compose for development, K8s for production scale."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    FIELD ||--o{ SENSOR : contains\n"
        "    SENSOR ||--o{ READING : emits\n"
        "    FIELD ||--o{ IRRIGATION_EVENT : receives\n"
        "    FIELD {\n        uuid field_id PK\n        string name\n        string crop_type\n    }\n"
        "    SENSOR {\n        uuid sensor_id PK\n        uuid field_id FK\n        string type\n    }\n"
        "    READING {\n        uuid sensor_id FK\n        timestamptz ts\n        string metric\n        double value\n    }"
    ),
    er_notes=(
        "Sensor readings are stored in a TimescaleDB hypertable partitioned by time; field and "
        "irrigation-event records live in standard PostgreSQL tables scoped per farm/tenant."
    ),
    api_rows=[
        "| GET | /api/v1/fields/{id}/readings?from&to | Historical soil/weather readings for a field |",
        "| GET | /api/v1/fields/{id}/recommendation | Current irrigation/agronomic recommendation |",
        "| POST | /api/v1/fields/{id}/irrigation | Trigger/schedule an irrigation event |",
        "| GET | /api/v1/alerts?state=open | Active field alerts (drought stress, frost risk) |",
        "| WS | /api/v1/stream | Real-time sensor/alert push |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant Se as Field Sensor\n"
        "    participant G as Field Gateway\n"
        "    participant B as MQTT Broker\n"
        "    participant An as Analytics Service\n"
        "    participant Ir as Irrigation Service\n"
        "    Se->>G: soil/weather reading\n"
        "    G->>B: publish telemetry\n"
        "    B->>An: consume + evaluate thresholds\n"
        "    alt irrigation needed\n"
        "        An->>Ir: recommend/trigger irrigation\n"
        "    end\n"
        "    An->>An: persist + aggregate for dashboard"
    ),
    workflow_narrative=(
        "The primary flow is sensor telemetry ingestion -> agronomic evaluation -> irrigation "
        "recommendation/actuation, with edge buffering covering rural connectivity gaps."
    ),
    roadmap_phase2_focus="Implement field/sensor telemetry ingestion and the agronomic analytics/irrigation pipeline.",
    future_extra=["Yield-prediction models trained on accumulated soil/weather/crop-stage data."],
)

RETAIL_ECOMMERCE = IndustryPattern(
    key="retail_ecommerce",
    name="Order & Inventory Commerce Architecture",
    components=[
        ("API Gateway", "TLS termination, routing, rate limiting."),
        ("Catalog Service", "Owns product listings, pricing, and search."),
        ("Inventory Service", "Tracks stock levels across warehouses/stores with reservation on checkout."),
        ("Order & Payment Service", "Orchestrates checkout, payment capture, and order fulfillment status."),
        ("Fulfillment Worker", "Async processing: pick/pack/ship, shipment tracking updates."),
        ("Web/Mobile Storefront", "Customer-facing shopping and order-tracking UI."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Database", "PostgreSQL", "ACID guarantees for orders/inventory; mature operations."),
        ("Search", "Elasticsearch", "Fast, faceted product search and catalog browsing."),
        ("Cache", "Redis", "Cart/session store and inventory-reservation locking."),
        ("Frontend", "React + TypeScript", "Type-safe storefront and checkout UI."),
        ("Orchestration", "Docker Compose -> Kubernetes", "Scales storefront/order services independently."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    PRODUCT ||--o{ INVENTORY_ITEM : stocked_as\n"
        "    ORDER ||--o{ ORDER_LINE : contains\n"
        "    ORDER_LINE }o--|| PRODUCT : references\n"
        "    ORDER ||--o{ SHIPMENT : fulfilled_by\n"
        "    PRODUCT {\n        uuid product_id PK\n        string sku\n        numeric price\n    }\n"
        "    ORDER {\n        uuid order_id PK\n        uuid customer_id FK\n        string status\n        numeric total\n    }\n"
        "    INVENTORY_ITEM {\n        uuid product_id FK\n        uuid warehouse_id FK\n        int quantity_on_hand\n        int quantity_reserved\n    }"
    ),
    er_notes=(
        "PostgreSQL is the system of record for orders and inventory; stock reservation uses "
        "row-level locking (or Redis-backed reservation tokens) to prevent overselling under "
        "concurrent checkout."
    ),
    api_rows=[
        "| GET | /api/v1/products | Search/browse product catalog |",
        "| GET | /api/v1/inventory/{product_id} | Stock availability across warehouses |",
        "| POST | /api/v1/orders | Place an order (reserves inventory, captures payment) |",
        "| GET | /api/v1/orders/{id} | Order status and fulfillment tracking |",
        "| POST | /api/v1/orders/{id}/cancel | Cancel an order and release reserved stock |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant C as Customer\n"
        "    participant S as Storefront\n"
        "    participant O as Order Service\n"
        "    participant Inv as Inventory Service\n"
        "    participant F as Fulfillment Worker\n"
        "    C->>S: checkout cart\n"
        "    S->>O: place order\n"
        "    O->>Inv: reserve stock\n"
        "    O->>O: capture payment\n"
        "    O-->>F: enqueue fulfillment\n"
        "    F->>C: shipment tracking update"
    ),
    workflow_narrative=(
        "The primary flow is checkout -> stock reservation -> payment capture -> async fulfillment, "
        "with inventory reservations preventing overselling under concurrent orders."
    ),
    roadmap_phase2_focus="Implement catalog/inventory and the order checkout/fulfillment flow.",
)

LOGISTICS_SUPPLY_CHAIN = IndustryPattern(
    key="logistics_supply_chain",
    name="Shipment Tracking & Fleet Routing Architecture",
    components=[
        ("API Gateway", "Authentication, routing, rate limiting."),
        ("Shipment Service", "Owns shipment lifecycle from booking to delivery confirmation."),
        ("Fleet & Routing Service", "Vehicle assignment and route optimization across active shipments."),
        ("Tracking Ingestion Service", "Consumes GPS/scan-event streams from vehicles and warehouse scanners."),
        ("Warehouse Service", "Tracks inbound/outbound inventory movement at facilities."),
        ("Web Dashboard", "Operations visualization for dispatchers and customers."),
    ],
    stack=[
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Ingestion", "Kafka + Python asyncio workers", "High-throughput ingestion of GPS/scan-event streams."),
        ("Database", "PostgreSQL", "ACID guarantees for shipment/warehouse records."),
        ("Time-Series Storage", "TimescaleDB extension", "Efficient storage for GPS tracking history."),
        ("Frontend", "React + TypeScript", "Real-time shipment map and dispatcher dashboard."),
        ("Orchestration", "Docker Compose -> Kubernetes", "Scales ingestion workers independently of the API tier."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    SHIPMENT ||--o{ TRACKING_EVENT : generates\n"
        "    SHIPMENT }o--|| VEHICLE : assigned_to\n"
        "    VEHICLE ||--o{ ROUTE : follows\n"
        "    SHIPMENT {\n        uuid shipment_id PK\n        string status\n        string origin\n        string destination\n    }\n"
        "    TRACKING_EVENT {\n        uuid shipment_id FK\n        timestamptz ts\n        double lat\n        double lon\n        string event_type\n    }\n"
        "    VEHICLE {\n        uuid vehicle_id PK\n        string status\n    }"
    ),
    er_notes=(
        "Tracking events are stored in a TimescaleDB hypertable partitioned by time; shipment and "
        "vehicle records live in standard PostgreSQL tables."
    ),
    api_rows=[
        "| POST | /api/v1/shipments | Book a shipment |",
        "| GET | /api/v1/shipments/{id}/tracking | Real-time and historical tracking events |",
        "| POST | /api/v1/fleet/assignments | Assign a vehicle/route to a shipment |",
        "| GET | /api/v1/warehouses/{id}/inventory | Warehouse inbound/outbound inventory status |",
        "| WS | /api/v1/stream | Real-time shipment location push |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant Cu as Customer\n"
        "    participant Sh as Shipment Service\n"
        "    participant Fl as Fleet Service\n"
        "    participant Ve as Vehicle\n"
        "    participant Da as Dashboard\n"
        "    Cu->>Sh: book shipment\n"
        "    Sh->>Fl: request vehicle/route assignment\n"
        "    Fl->>Ve: dispatch\n"
        "    Ve->>Sh: tracking events en route\n"
        "    Sh->>Da: real-time status push\n"
        "    Sh->>Cu: delivery confirmation"
    ),
    workflow_narrative=(
        "The primary flow is shipment booking -> fleet assignment -> in-transit tracking -> delivery "
        "confirmation, with real-time location pushed to dispatcher and customer views."
    ),
    roadmap_phase2_focus="Implement shipment lifecycle and the fleet assignment/tracking ingestion pipeline.",
)

AI_ML_PLATFORM = IndustryPattern(
    key="ai_ml_platform",
    name="AI Inference & Retrieval Pipeline Architecture",
    components=[
        ("Ingestion Pipeline", "Parses, chunks, and embeds source documents into the vector store."),
        ("Vector Store", "Similarity search over embedded knowledge."),
        ("Inference Orchestrator", "Builds grounded prompts, routes to the model provider, validates outputs."),
        ("Model Gateway", "Provider-agnostic LLM access with fallback and cost tracking."),
        ("Application API", "Exposes query, feedback, and administration endpoints."),
        ("Evaluation Harness", "Regression suites scoring answer quality and grounding."),
    ],
    stack=[
        ("Orchestration", "Python (FastAPI + asyncio)", "First-class AI ecosystem; async pipelines."),
        ("Vector Store", "pgvector / Qdrant", "Start embedded in PostgreSQL; dedicated engine at scale."),
        ("Model Access", "Provider-agnostic gateway (Claude/GPT/Gemini/Llama)", "No hard provider lock-in; per-task routing."),
        ("Cache / Queue", "Redis", "Embedding cache and job queue."),
        ("Frontend", "React + TypeScript", "Interactive chat/analysis UI."),
        ("Orchestration Runtime", "Docker -> Kubernetes", "Standard container lifecycle."),
    ],
    er_diagram=(
        "erDiagram\n"
        "    DOCUMENT ||--o{ CHUNK : split_into\n"
        "    CHUNK ||--o{ EMBEDDING : produces\n"
        "    QUERY ||--o{ RETRIEVAL_RESULT : returns\n"
        "    DOCUMENT {\n        uuid doc_id PK\n        string title\n        string source\n    }\n"
        "    CHUNK {\n        uuid chunk_id PK\n        uuid doc_id FK\n        text content\n    }\n"
        "    QUERY {\n        uuid query_id PK\n        string text\n        timestamptz ts\n    }"
    ),
    er_notes=(
        "Documents are chunked and embedded once at ingestion; embeddings live alongside chunk text "
        "in a vector-capable store (pgvector for simplicity, dedicated vector DB at scale)."
    ),
    api_rows=[
        "| POST | /api/v1/documents | Ingest a source document |",
        "| POST | /api/v1/query | Ask a grounded question |",
        "| GET | /api/v1/query/{id}/sources | Retrieval sources behind an answer |",
        "| POST | /api/v1/feedback | Submit answer-quality feedback |",
    ],
    workflow_diagram=(
        "sequenceDiagram\n"
        "    participant U as User\n"
        "    participant O as Inference Orchestrator\n"
        "    participant V as Vector Store\n"
        "    participant M as Model Gateway\n"
        "    U->>O: question\n"
        "    O->>V: similarity search\n"
        "    V->>O: relevant chunks\n"
        "    O->>M: grounded prompt\n"
        "    M->>O: answer\n"
        "    O->>U: answer + cited sources"
    ),
    workflow_narrative=(
        "The primary flow is retrieval-augmented generation: relevant chunks are retrieved before "
        "the model is asked to answer, and sources are always returned alongside the answer."
    ),
    roadmap_phase2_focus="Implement the ingestion pipeline and the retrieval-augmented query flow.",
)

EVENT_DRIVEN_PLATFORM = IndustryPattern(
    key="event_driven_platform",
    name="Event-Driven Microservices Architecture",
    components=[
        ("API Gateway", "Single entry point: authentication, rate limiting, routing."),
        ("Domain Services", "Independently deployable services owning their data and publishing domain events."),
        ("Event Backbone", "Durable pub/sub log decoupling producers from consumers."),
        ("Read-Model / Query Service", "Materialized views optimized for the UI and reporting."),
        ("Worker Pool", "Asynchronous background processing of long-running jobs."),
    ],
    stack=[
        ("Event Backbone", "Apache Kafka", "Durable, replayable log; consumer groups for horizontal scale."),
        ("Services", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Cache / Coordination", "Redis", "Low-latency caching, distributed locks, rate limiting."),
        ("Primary Storage", "PostgreSQL", "ACID guarantees, JSONB flexibility, mature operations."),
        ("Frontend", "React + TypeScript", "Type-safe component-driven UI."),
        ("Orchestration", "Kubernetes", "Declarative deployment, autoscaling, self-healing."),
    ],
    er_diagram=GENERIC_SOFTWARE.er_diagram,
    er_notes=GENERIC_SOFTWARE.er_notes,
    api_rows=GENERIC_SOFTWARE.api_rows,
    workflow_diagram=GENERIC_SOFTWARE.workflow_diagram,
    workflow_narrative=(
        "Domain services publish events onto the backbone rather than calling each other directly; "
        "consumers materialize their own read models, and workers handle long-running side effects."
    ),
)


PATTERNS_BY_KEY = {
    p.key: p
    for p in (
        GENERIC_SOFTWARE, INDUSTRIAL_IOT, HEALTHCARE, EDUCATION, BANKING_FINTECH,
        AUTOMOTIVE, CONSTRUCTION, AGRICULTURE, RETAIL_ECOMMERCE,
        LOGISTICS_SUPPLY_CHAIN, AI_ML_PLATFORM, EVENT_DRIVEN_PLATFORM,
    )
}


def select_pattern(understanding) -> IndustryPattern:
    """
    Selects the IndustryPattern for a (possibly None) ProjectUnderstandingFrame.
    Falls back to the generic pattern for unclassified/novel industries rather
    than raising — synthesis must never fail because classification was
    uncertain.
    """
    if understanding is None:
        return GENERIC_SOFTWARE
    key = (understanding.industry or "").strip().lower().replace(" ", "_").replace("-", "_")
    return PATTERNS_BY_KEY.get(key, GENERIC_SOFTWARE)
