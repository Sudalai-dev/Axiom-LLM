"""
Registry Module — Axiom Dataset Generation Platform.

The central knowledge registry defining seed vocabularies, combinatorial
templates, engineering rules, and generation logic for all 30 dataset types.

Architecture:
    Each dataset type is defined by a DatasetSpec that includes:
    - Schema (field names and types)
    - Seed vocabularies (real engineering terms, not toy examples)
    - Template strings with substitution slots
    - Combinatorial expansion rules
    - Domain-specific constraints

The generators use controlled random sampling with engineering rules to produce
unique, meaningful records at any requested scale (100 to 1,000,000).
"""

import hashlib
import itertools
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Shared Metadata Defaults
# ---------------------------------------------------------------------------

REVIEW_STATUSES = ["draft", "pending_review", "reviewed", "approved", "rejected"]
COMPLEXITY_LEVELS = ["trivial", "low", "medium", "high", "critical"]
SOURCES = ["engineering_seed", "template_expansion", "domain_expert", "standards_corpus", "organizational_knowledge"]
VERSIONS = ["1.0", "1.1", "1.2", "2.0"]


def _base_metadata(domain: str = "", industry: str = "", intent: str = "") -> Dict[str, Any]:
    """Returns the standard metadata envelope every record must carry."""
    now = datetime.utcnow()
    return {
        "id": str(uuid.uuid4()),
        "version": random.choice(VERSIONS),
        "source": random.choice(SOURCES),
        "tags": [],
        "confidence": round(random.uniform(0.70, 0.99), 2),
        "review_status": random.choice(REVIEW_STATUSES),
        "created_date": (now - timedelta(days=random.randint(0, 730))).isoformat(),
        "updated_date": now.isoformat(),
        "approval": random.choice(["approved", "pending", "conditional"]),
        "domain": domain,
        "industry": industry,
        "intent": intent,
        "complexity": random.choice(COMPLEXITY_LEVELS),
    }


# =========================================================================
#  SEED VOCABULARIES — Real engineering terms across all 30 categories
# =========================================================================

# --- 01. Intent Detection Seeds -------------------------------------------

INTENT_TYPES = [
    "generate_hld", "generate_lld", "generate_prd", "generate_prs",
    "generate_srs", "generate_brd", "generate_architecture",
    "expand_use_case", "analyze_failure", "troubleshoot",
    "database_design", "api_design", "deployment_planning",
    "migration_planning", "optimization", "security_review",
    "code_review", "performance_analysis", "capacity_planning",
    "cost_estimation", "risk_assessment", "compliance_audit",
    "monitoring_setup", "disaster_recovery", "data_pipeline_design",
    "integration_design", "testing_strategy", "devops_pipeline",
    "edge_computing_design", "iot_architecture",
]

INTENT_TEMPLATES = [
    "Design a {adjective} {system_type} for {use_case} in a {industry} environment",
    "Create a {document_type} for {system_type} that handles {requirement}",
    "Analyze the failure modes of {component} in {environment}",
    "Troubleshoot {symptom} occurring in {system_type} deployed on {platform}",
    "Design the database schema for {system_type} supporting {scale} {entities}",
    "Design RESTful APIs for {system_type} with {auth_type} authentication",
    "Plan the deployment of {system_type} on {platform} with {availability} availability",
    "Migrate {legacy_system} to {target_platform} while maintaining {constraint}",
    "Optimize {metric} for {system_type} currently experiencing {problem}",
    "Conduct a security review of {system_type} handling {data_type} data",
    "Review the {language} codebase of {system_type} for {quality_attribute}",
    "Analyze the performance bottlenecks in {system_type} under {load_pattern} load",
    "Estimate the capacity requirements for {system_type} serving {user_count} users",
    "Design a disaster recovery plan for {system_type} with RPO of {rpo} and RTO of {rto}",
    "Build a data pipeline from {source_system} to {target_system} processing {volume} events per second",
    "Design integration between {system_a} and {system_b} using {integration_pattern}",
    "Create a comprehensive testing strategy for {system_type} covering {test_types}",
    "Design a CI/CD pipeline for {system_type} deploying to {platform}",
    "Architect an edge computing solution for {use_case} with {constraint}",
    "Design an IoT telemetry pipeline for {sensor_count} sensors reporting every {interval}",
    "Generate a high-level design document for {system_type} supporting {feature_list}",
    "Create a low-level design for the {component} module of {system_type}",
    "Write a product requirements document for {product_name} targeting {market}",
    "Expand the use case '{use_case}' into detailed functional specifications",
    "Plan the horizontal scaling strategy for {system_type} handling {throughput} requests per second",
    "Design the monitoring and alerting infrastructure for {system_type} on {platform}",
    "Architect a multi-tenant {system_type} with {isolation_model} isolation",
    "Design a real-time event processing system for {use_case} using {messaging_tech}",
    "Create a compliance audit report for {system_type} against {standard}",
    "Design the caching strategy for {system_type} to reduce {metric} by {target_percent}%",
]

INTENT_ADJECTIVES = [
    "scalable", "fault-tolerant", "high-availability", "real-time", "distributed",
    "event-driven", "microservice-based", "serverless", "edge-native", "cloud-native",
    "containerized", "multi-region", "HIPAA-compliant", "PCI-DSS-compliant",
    "zero-trust", "air-gapped", "hybrid-cloud", "multi-tenant", "low-latency",
    "cost-optimized", "self-healing", "auto-scaling", "observable", "resilient",
]

SYSTEM_TYPES = [
    "patient monitoring platform", "predictive maintenance system", "inventory management system",
    "SCADA control system", "fleet management platform", "energy management system",
    "clinical trial management system", "warehouse automation system", "payment processing platform",
    "order management system", "supply chain visibility platform", "building automation system",
    "water treatment control system", "smart grid management platform", "agricultural monitoring system",
    "manufacturing execution system (MES)", "laboratory information management system (LIMS)",
    "asset tracking platform", "quality management system", "environmental monitoring system",
    "video surveillance analytics platform", "digital twin platform", "condition monitoring system",
    "remote diagnostics platform", "automated testing framework", "data lake analytics platform",
    "customer data platform", "fraud detection system", "anomaly detection engine",
    "recommendation engine", "natural language processing pipeline", "computer vision system",
    "robotic process automation platform", "workflow orchestration engine", "API gateway",
    "identity and access management system", "log aggregation platform", "configuration management database",
    "service mesh control plane", "container orchestration platform", "message broker cluster",
    "time-series database cluster", "graph database platform", "search engine cluster",
    "content delivery network", "load balancer cluster", "DNS management platform",
    "certificate management system", "secrets management vault", "backup and recovery system",
    "compliance reporting platform", "audit trail system",
]

USE_CASES = [
    "real-time patient vitals monitoring", "predictive bearing failure detection",
    "automated order fulfillment", "cold chain temperature monitoring",
    "smart building HVAC optimization", "industrial robot coordination",
    "autonomous vehicle fleet dispatch", "precision agriculture irrigation",
    "oil pipeline leak detection", "power grid frequency regulation",
    "pharmaceutical batch tracking", "retail shelf inventory tracking",
    "credit card fraud detection", "anti-money laundering screening",
    "clinical decision support", "surgical instrument tracking",
    "mine ventilation control", "steel mill quality inspection",
    "wastewater treatment optimization", "airport baggage handling",
    "railway signaling control", "traffic congestion prediction",
    "smart meter data analytics", "elevator predictive maintenance",
    "HVAC energy optimization in data centers", "drone-based infrastructure inspection",
    "offshore wind turbine monitoring", "solar panel performance tracking",
    "battery state-of-health estimation", "electric vehicle charging optimization",
    "food safety traceability", "worker safety wearable monitoring",
    "noise pollution monitoring", "air quality index prediction",
    "flood early warning", "seismic activity detection",
    "bridge structural health monitoring", "dam safety monitoring",
    "fire suppression system automation", "clean room environmental control",
]

INDUSTRIES = [
    "manufacturing", "healthcare", "energy", "oil_and_gas", "retail",
    "transportation", "construction", "agriculture", "utilities", "education",
    "finance", "government", "smart_cities", "industrial_automation",
    "aerospace", "defense", "mining", "telecommunications", "pharmaceuticals",
    "food_and_beverage", "automotive", "maritime", "logistics", "hospitality",
    "insurance", "real_estate", "media", "water_management", "chemicals",
]

PLATFORMS = [
    "AWS", "Azure", "GCP", "on-premises bare-metal", "on-premises VMware",
    "Kubernetes (EKS)", "Kubernetes (AKS)", "Kubernetes (GKE)", "OpenShift",
    "edge gateway (ARM)", "Raspberry Pi cluster", "NVIDIA Jetson",
    "hybrid cloud (AWS + on-prem)", "multi-cloud (AWS + Azure)",
    "Siemens MindSphere", "PTC ThingWorx", "AWS IoT Greengrass",
    "Azure IoT Edge", "Google Cloud IoT Core",
]

DOCUMENT_TYPES = [
    "High-Level Design (HLD)", "Low-Level Design (LLD)", "Product Requirement Document (PRD)",
    "Software Requirement Specification (SRS)", "Business Requirement Document (BRD)",
    "Architecture Decision Record (ADR)", "API Specification (OpenAPI 3.0)",
    "Database Design Document", "Deployment Runbook", "Disaster Recovery Plan",
    "Security Assessment Report", "Performance Test Plan", "Capacity Planning Report",
    "Migration Plan", "Integration Design Document", "Test Strategy Document",
]

OUTPUT_TYPES = [
    "solution_blueprint", "architecture_diagram", "api_specification",
    "database_schema", "deployment_manifest", "test_plan",
    "monitoring_dashboard", "runbook", "migration_script",
    "security_policy", "cost_analysis", "risk_matrix",
    "compliance_report", "performance_report", "capacity_plan",
]

# --- 02. Domain Classification Seeds -------------------------------------

DOMAINS = {
    "software_engineering": {
        "label": "Software Engineering",
        "keywords": ["microservices", "API", "REST", "GraphQL", "CI/CD", "testing", "refactoring", "design patterns"],
        "expert_personas": ["Senior Software Architect", "Principal Engineer", "Staff Developer"],
    },
    "backend": {
        "label": "Backend Engineering",
        "keywords": ["server", "API gateway", "message queue", "caching", "worker", "middleware", "ORM", "rate limiting"],
        "expert_personas": ["Backend Architect", "Platform Engineer", "API Design Lead"],
    },
    "frontend": {
        "label": "Frontend Engineering",
        "keywords": ["React", "Angular", "Vue", "responsive", "accessibility", "performance", "SSR", "PWA"],
        "expert_personas": ["Frontend Architect", "UX Engineer", "Design Systems Lead"],
    },
    "database": {
        "label": "Database Engineering",
        "keywords": ["schema", "normalization", "indexing", "replication", "sharding", "ACID", "CAP", "query optimization"],
        "expert_personas": ["Database Architect", "Data Modeling Specialist", "DBA Lead"],
    },
    "cloud": {
        "label": "Cloud Engineering",
        "keywords": ["AWS", "Azure", "GCP", "IaC", "Terraform", "serverless", "autoscaling", "multi-region"],
        "expert_personas": ["Cloud Solutions Architect", "DevOps Engineer", "SRE Lead"],
    },
    "ai_ml": {
        "label": "AI / Machine Learning",
        "keywords": ["training", "inference", "model", "pipeline", "feature store", "MLOps", "GPU", "batch prediction"],
        "expert_personas": ["ML Engineer", "AI Research Scientist", "MLOps Architect"],
    },
    "industrial_iot": {
        "label": "Industrial IoT",
        "keywords": ["MQTT", "OPC-UA", "Modbus", "SCADA", "PLC", "edge", "gateway", "sensor", "telemetry"],
        "expert_personas": ["IIoT Solutions Architect", "Automation Engineer", "Controls Engineer"],
    },
    "mechanical": {
        "label": "Mechanical Engineering",
        "keywords": ["pump", "compressor", "HVAC", "bearing", "motor", "valve", "conveyor", "hydraulics", "pneumatics"],
        "expert_personas": ["Mechanical Design Engineer", "Reliability Engineer", "Maintenance Lead"],
    },
    "electrical": {
        "label": "Electrical Engineering",
        "keywords": ["power distribution", "control panel", "VFD", "motor starter", "transformer", "switchgear", "protection relay"],
        "expert_personas": ["Electrical Design Engineer", "Power Systems Engineer", "Controls Specialist"],
    },
    "automation": {
        "label": "Industrial Automation",
        "keywords": ["PLC programming", "HMI", "SCADA", "DCS", "ladder logic", "function block", "servo", "robot"],
        "expert_personas": ["Automation Architect", "PLC Programmer", "Systems Integrator"],
    },
    "networking": {
        "label": "Networking",
        "keywords": ["TCP/IP", "VLAN", "firewall", "load balancer", "DNS", "CDN", "VPN", "SD-WAN", "BGP"],
        "expert_personas": ["Network Architect", "Network Security Engineer", "Infrastructure Lead"],
    },
    "security": {
        "label": "Cybersecurity",
        "keywords": ["zero-trust", "encryption", "IAM", "SIEM", "vulnerability", "penetration testing", "OWASP", "SOC"],
        "expert_personas": ["Security Architect", "CISO", "Penetration Tester", "Security Operations Lead"],
    },
    "embedded": {
        "label": "Embedded Systems",
        "keywords": ["RTOS", "firmware", "microcontroller", "interrupt", "DMA", "SPI", "I2C", "CAN bus", "watchdog"],
        "expert_personas": ["Embedded Systems Architect", "Firmware Engineer", "Hardware Design Lead"],
    },
    "business_analysis": {
        "label": "Business Analysis",
        "keywords": ["stakeholder", "requirements", "process mapping", "gap analysis", "user story", "acceptance criteria"],
        "expert_personas": ["Business Analyst", "Product Manager", "Requirements Engineer"],
    },
    "enterprise_architecture": {
        "label": "Enterprise Architecture",
        "keywords": ["TOGAF", "ArchiMate", "capability map", "integration", "governance", "technology radar"],
        "expert_personas": ["Enterprise Architect", "Solutions Architect", "Chief Technology Officer"],
    },
    "devops": {
        "label": "DevOps / SRE",
        "keywords": ["CI/CD", "GitOps", "Kubernetes", "Terraform", "Ansible", "monitoring", "SLO", "incident response"],
        "expert_personas": ["DevOps Architect", "Site Reliability Engineer", "Platform Engineering Lead"],
    },
    "data_engineering": {
        "label": "Data Engineering",
        "keywords": ["ETL", "data lake", "data warehouse", "streaming", "batch", "Spark", "Airflow", "dbt"],
        "expert_personas": ["Data Architect", "Data Engineering Lead", "Analytics Engineer"],
    },
}

DOMAIN_PROBLEM_TEMPLATES = [
    "Design a {adjective} {system_type} that handles {requirement} for {use_case}",
    "The {component} subsystem of our {system_type} is experiencing {symptom}; diagnose and propose a fix",
    "Evaluate whether to use {option_a} or {option_b} for {use_case} given {constraint}",
    "Create the architecture for a {system_type} that must comply with {standard}",
    "Our {system_type} needs to scale from {scale_a} to {scale_b}; design the scaling strategy",
    "Integrate {system_a} with {system_b} while maintaining {quality_attribute}",
    "Design a fault-tolerant {component} layer for {system_type} deployed across {topology}",
    "Migrate the {component} from {legacy_tech} to {modern_tech} with zero downtime",
]

# --- 03. Industry Classification Seeds -----------------------------------

INDUSTRY_DETAILS = {
    "manufacturing": {
        "label": "Manufacturing",
        "standards": ["ISA-95", "ISA-88", "IEC 62264", "ISO 9001", "ISO 22000", "OSHA 29 CFR 1910"],
        "regulations": ["FDA 21 CFR Part 11", "EPA regulations", "OSHA workplace safety"],
        "architecture_patterns": ["MES integration", "SCADA-ERP bridge", "OPC-UA unified namespace", "digital twin"],
        "common_problems": ["unplanned downtime", "quality defects", "production bottlenecks", "changeover time", "energy waste"],
        "terminology": ["OEE", "MTBF", "MTTR", "takt time", "cycle time", "yield", "WIP", "BOM", "routing"],
        "compliance": ["GMP", "HACCP", "ISO 14001", "CE marking"],
    },
    "healthcare": {
        "label": "Healthcare",
        "standards": ["HL7 FHIR R4", "DICOM", "IHE profiles", "ISO 13485", "IEC 62304"],
        "regulations": ["HIPAA", "HITECH Act", "FDA 510(k)", "GDPR (patient data)", "21 CFR Part 820"],
        "architecture_patterns": ["EHR integration", "clinical data repository", "patient portal", "telehealth platform"],
        "common_problems": ["data interoperability", "PHI exposure", "alert fatigue", "clinician burnout", "duplicate records"],
        "terminology": ["PHI", "EMR", "EHR", "ePHI", "ADT", "CDS", "CPOE", "PACS", "RIS"],
        "compliance": ["HIPAA Security Rule", "HIPAA Privacy Rule", "Meaningful Use", "MIPS"],
    },
    "energy": {
        "label": "Energy & Utilities",
        "standards": ["IEC 61850", "IEC 61968/61970 (CIM)", "IEEE 1547", "NERC CIP", "ISO 50001"],
        "regulations": ["FERC regulations", "NERC reliability standards", "EPA Clean Air Act", "state PUC rules"],
        "architecture_patterns": ["smart grid", "DERMS", "ADMS", "AMI head-end", "energy trading platform"],
        "common_problems": ["grid instability", "renewable integration", "demand forecasting", "outage management", "meter data gaps"],
        "terminology": ["SCADA", "DER", "AMI", "DERMS", "ADMS", "ISO/RTO", "LMP", "capacity factor", "curtailment"],
        "compliance": ["NERC CIP v6", "FERC Order 2222", "IEEE 2030"],
    },
    "oil_and_gas": {
        "label": "Oil & Gas",
        "standards": ["API standards", "ASME B31.3", "ISA-84 (SIS)", "IEC 61511", "NORSOK"],
        "regulations": ["BSEE regulations", "EPA SPCC", "OSHA PSM 1910.119", "PHMSA pipeline safety"],
        "architecture_patterns": ["field SCADA", "reservoir simulation", "production optimization", "pipeline SCADA"],
        "common_problems": ["corrosion detection", "well integrity", "flare management", "sand production", "H2S detection"],
        "terminology": ["upstream", "midstream", "downstream", "wellhead", "BOP", "MWD", "LWD", "ESP", "SIS"],
        "compliance": ["API RP 754", "OSHA PSM", "EPA RMP"],
    },
    "retail": {
        "label": "Retail & E-Commerce",
        "standards": ["PCI-DSS", "EMV", "GS1 standards", "EDI X12"],
        "regulations": ["PCI-DSS v4.0", "GDPR", "CCPA", "state consumer protection"],
        "architecture_patterns": ["omnichannel platform", "inventory sync", "recommendation engine", "loyalty platform"],
        "common_problems": ["cart abandonment", "inventory discrepancies", "payment failures", "seasonal spikes", "returns processing"],
        "terminology": ["SKU", "POS", "OMS", "WMS", "AOV", "CLV", "churn rate", "basket analysis"],
        "compliance": ["PCI-DSS SAQ", "GDPR consent management", "accessibility (WCAG 2.1)"],
    },
    "transportation": {
        "label": "Transportation & Logistics",
        "standards": ["SAE J1939", "ISO 15765 (UDS)", "NMEA 2000", "AIS", "ADSB"],
        "regulations": ["DOT FMCSA", "ELD mandate", "IATA DGR", "IMO SOLAS", "FAA Part 107"],
        "architecture_patterns": ["fleet telematics", "route optimization", "shipment tracking", "yard management"],
        "common_problems": ["route inefficiency", "driver compliance", "fuel waste", "load optimization", "ETA accuracy"],
        "terminology": ["TMS", "WMS", "ELD", "BOL", "POD", "dwell time", "deadhead miles", "LTL", "FTL"],
        "compliance": ["ELD mandate", "HOS regulations", "CSA scores"],
    },
    "construction": {
        "label": "Construction & Infrastructure",
        "standards": ["ISO 19650 (BIM)", "IFC/COBie", "ASCE standards", "ACI codes"],
        "regulations": ["OSHA 29 CFR 1926", "EPA stormwater", "local building codes", "ADA compliance"],
        "architecture_patterns": ["BIM platform", "project management", "site monitoring", "asset handover"],
        "common_problems": ["schedule delays", "cost overruns", "safety incidents", "rework", "coordination failures"],
        "terminology": ["BIM", "LOD", "RFI", "submittals", "punch list", "change order", "earned value"],
        "compliance": ["OSHA construction standards", "LEED certification", "local permitting"],
    },
    "agriculture": {
        "label": "Agriculture & Agritech",
        "standards": ["ISO 11783 (ISOBUS)", "EPSG geodetic", "OGC SensorThings"],
        "regulations": ["FDA FSMA", "EPA pesticide", "USDA organic certification", "water rights"],
        "architecture_patterns": ["precision agriculture", "crop monitoring", "irrigation automation", "livestock tracking"],
        "common_problems": ["irrigation efficiency", "pest detection", "soil degradation", "yield prediction", "cold chain"],
        "terminology": ["NDVI", "VRA", "GDD", "EC mapping", "soil moisture tension", "evapotranspiration"],
        "compliance": ["FSMA", "GAP certification", "GLOBALG.A.P."],
    },
    "finance": {
        "label": "Finance & Banking",
        "standards": ["PCI-DSS 4.0", "ISO 20022", "FIX protocol", "SWIFT standards", "Open Banking API"],
        "regulations": ["SOX", "Dodd-Frank", "Basel III", "AML/KYC", "GDPR", "MiFID II"],
        "architecture_patterns": ["core banking", "payment gateway", "fraud detection", "risk engine", "ledger system"],
        "common_problems": ["transaction latency", "fraud false positives", "reconciliation failures", "regulatory reporting", "data residency"],
        "terminology": ["ledger", "double-entry", "settlement", "clearing", "AML", "KYC", "PEP", "SAR", "ACH"],
        "compliance": ["PCI-DSS", "SOX Section 404", "AML 5th Directive", "Basel III capital requirements"],
    },
    "government": {
        "label": "Government & Public Sector",
        "standards": ["FedRAMP", "NIST SP 800-53", "FIPS 140-2", "WCAG 2.1", "Section 508"],
        "regulations": ["FISMA", "CJIS Security Policy", "ITAR", "EAR", "Privacy Act"],
        "architecture_patterns": ["citizen portal", "case management", "records management", "interagency integration"],
        "common_problems": ["legacy modernization", "data silos", "accessibility gaps", "procurement delays", "security clearance"],
        "terminology": ["ATO", "POAM", "FedRAMP", "IL4/IL5", "STIG", "RMF", "continuous ATO"],
        "compliance": ["FedRAMP High", "FISMA", "CJIS", "NIST RMF"],
    },
    "smart_cities": {
        "label": "Smart Cities",
        "standards": ["FIWARE", "OneM2M", "ISO 37120", "CityGML", "GTFS"],
        "regulations": ["GDPR", "local privacy ordinances", "open data mandates", "accessibility laws"],
        "architecture_patterns": ["urban data platform", "traffic management", "smart lighting", "waste management IoT"],
        "common_problems": ["data integration", "privacy vs analytics", "legacy infrastructure", "vendor lock-in", "citizen adoption"],
        "terminology": ["smart parking", "connected streetlight", "urban computing", "digital twin city", "mobility-as-a-service"],
        "compliance": ["ISO 37120 indicators", "GDPR urban data", "open data compliance"],
    },
    "industrial_automation": {
        "label": "Industrial Automation",
        "standards": ["ISA-95", "ISA-88", "IEC 62443", "OPC-UA", "PackML"],
        "regulations": ["machinery directive 2006/42/EC", "ATEX", "NEC 500/505", "SIL requirements"],
        "architecture_patterns": ["unified namespace", "SCADA-MES-ERP stack", "edge analytics", "digital thread"],
        "common_problems": ["IT/OT convergence", "legacy protocol bridging", "cybersecurity gaps", "alarm management", "batch tracking"],
        "terminology": ["PLC", "DCS", "HMI", "SCADA", "OPC-UA", "SIL", "SIS", "I/O rack", "fieldbus"],
        "compliance": ["IEC 62443 security", "SIL verification", "CE marking", "UL 508A"],
    },
    "aerospace": {
        "label": "Aerospace & Defense",
        "standards": ["DO-178C", "DO-254", "AS9100", "MIL-STD-882", "ARP 4754A"],
        "regulations": ["FAA certification", "EASA", "ITAR", "DFARS 252.204-7012"],
        "architecture_patterns": ["mission-critical avionics", "ground control station", "satellite command", "MRO platform"],
        "common_problems": ["DO-178C compliance cost", "obsolescence management", "supply chain traceability", "ITAR data handling"],
        "terminology": ["DAL", "MCDC coverage", "certification credit", "airworthiness", "CDR", "PDR", "TRR"],
        "compliance": ["DO-178C DAL A-E", "AS9100D", "ITAR/EAR"],
    },
    "telecommunications": {
        "label": "Telecommunications",
        "standards": ["3GPP 5G NR", "MEF LSO", "TM Forum APIs", "ETSI NFV", "ONF SDN"],
        "regulations": ["FCC Part 15/24", "GDPR", "CPNI rules", "E911 requirements"],
        "architecture_patterns": ["5G core (SBA)", "network slicing", "OSS/BSS modernization", "edge MEC"],
        "common_problems": ["spectrum interference", "core congestion", "handover failures", "billing errors", "SLA breaches"],
        "terminology": ["RAN", "core network", "NFV", "SDN", "MEC", "network slice", "SON", "NFVO", "VNF"],
        "compliance": ["3GPP security (33.501)", "FCC RF exposure", "CPNI protection"],
    },
}

# --- 04. Problem Classification Seeds ------------------------------------

PROBLEM_CATEGORIES = [
    "design", "implementation", "integration", "migration", "optimization",
    "troubleshooting", "failure_analysis", "capacity_planning", "security",
    "compliance", "monitoring", "data_management", "performance", "scalability",
    "reliability", "cost_optimization", "modernization", "automation",
]

# --- 05. Use Case Expansion Seeds ----------------------------------------

ACTORS = [
    "Plant Manager", "Control Room Operator", "Maintenance Technician",
    "Field Engineer", "Data Scientist", "DevOps Engineer", "Security Analyst",
    "Clinical Nurse", "Attending Physician", "Pharmacist", "Lab Technician",
    "Warehouse Supervisor", "Fleet Dispatcher", "Quality Inspector",
    "Building Manager", "Energy Analyst", "Network Administrator",
    "Database Administrator", "Software Developer", "Product Manager",
    "Compliance Officer", "Site Supervisor", "Safety Officer",
    "Instrument Technician", "Electrical Technician", "HVAC Technician",
]

DELIVERABLES = [
    "High-Level Design Document", "Low-Level Design Document",
    "API Specification (OpenAPI 3.0)", "Database Schema Diagram",
    "Deployment Architecture Diagram", "Network Topology Diagram",
    "Security Architecture Document", "Test Plan and Strategy",
    "Monitoring Dashboard Configuration", "Runbook / SOP",
    "Disaster Recovery Plan", "Cost Analysis Report",
    "Risk Assessment Matrix", "Compliance Audit Report",
    "User Training Manual", "Change Management Plan",
    "Integration Specification", "Data Flow Diagram",
    "Sequence Diagram", "State Machine Diagram",
]

# --- 06. Requirement Extraction Seeds ------------------------------------

NFR_CATEGORIES = {
    "performance": [
        "API response time < {latency}ms at p99",
        "Dashboard refresh interval < {interval} seconds",
        "Batch processing throughput > {throughput} records/second",
        "Search query latency < {latency}ms for {record_count} records",
        "Report generation completed within {duration} minutes",
    ],
    "availability": [
        "System uptime SLA of {uptime}%",
        "Planned maintenance window < {window} hours per month",
        "Automatic failover within {failover_time} seconds",
        "Zero-downtime deployments using {strategy}",
        "RTO of {rto} minutes and RPO of {rpo} minutes",
    ],
    "security": [
        "All data encrypted at rest using AES-256",
        "TLS 1.3 for all data in transit",
        "Role-based access control (RBAC) with {role_count} roles",
        "MFA required for all administrative access",
        "Audit logging for all data access with {retention} day retention",
        "Secrets managed via {vault_tool} with automatic rotation",
    ],
    "scalability": [
        "Horizontal scaling to {node_count} nodes",
        "Support {user_count} concurrent users",
        "Handle {event_rate} events per second sustained",
        "Database sharding strategy for > {data_size} TB",
        "Auto-scaling triggered at {cpu_threshold}% CPU utilization",
    ],
    "reliability": [
        "Circuit breaker pattern with {threshold} failure threshold",
        "Retry with exponential backoff (max {max_retries} retries)",
        "Bulkhead isolation for {service_count} critical services",
        "Chaos engineering tests run {frequency}",
        "Data replication factor of {replication_factor}",
    ],
    "maintainability": [
        "Code coverage > {coverage}%",
        "Cyclomatic complexity < {complexity} per function",
        "API versioning using {versioning_strategy}",
        "Feature flags for {flag_count} features",
        "Documentation coverage > {doc_coverage}%",
    ],
    "compliance": [
        "Compliant with {standard} section {section}",
        "Data residency in {region} region(s) only",
        "PII anonymization within {retention_days} days",
        "Audit trail immutability for {audit_years} years",
        "Penetration testing conducted {frequency}",
    ],
}

# --- 07. Solution Blueprint Seeds ----------------------------------------

TECH_STACK_OPTIONS = {
    "backend_framework": ["FastAPI (Python)", "Spring Boot (Java)", "Express.js (Node)", "ASP.NET Core (C#)", "Go (Gin/Echo)", "Rust (Actix)"],
    "database_primary": ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "CockroachDB", "YugabyteDB"],
    "database_nosql": ["MongoDB", "Cassandra", "DynamoDB", "Cosmos DB", "Couchbase", "ScyllaDB"],
    "database_timeseries": ["TimescaleDB", "InfluxDB", "QuestDB", "Apache IoTDB", "TDengine"],
    "database_graph": ["Neo4j", "Amazon Neptune", "ArangoDB", "JanusGraph"],
    "cache": ["Redis", "Memcached", "Hazelcast", "Apache Ignite"],
    "messaging": ["Apache Kafka", "RabbitMQ", "NATS", "Apache Pulsar", "Amazon SQS/SNS", "Azure Service Bus"],
    "search": ["Elasticsearch", "OpenSearch", "Apache Solr", "Meilisearch", "Typesense"],
    "container_orchestration": ["Kubernetes", "Docker Swarm", "Amazon ECS", "Nomad"],
    "iac": ["Terraform", "Pulumi", "AWS CDK", "Azure Bicep", "Ansible", "Chef"],
    "cicd": ["GitHub Actions", "GitLab CI", "Jenkins", "ArgoCD", "Tekton", "CircleCI"],
    "monitoring": ["Prometheus + Grafana", "Datadog", "New Relic", "Dynatrace", "Elastic APM", "Splunk"],
    "logging": ["ELK Stack", "Loki + Grafana", "Splunk", "Datadog Logs", "Fluentd + S3"],
    "api_gateway": ["Kong", "AWS API Gateway", "Azure API Management", "Apigee", "Traefik", "Envoy"],
    "auth": ["Keycloak", "Auth0", "AWS Cognito", "Azure AD B2C", "Okta", "FusionAuth"],
    "frontend": ["React + TypeScript", "Angular", "Vue.js 3", "Next.js", "Svelte", "HTMX + Alpine.js"],
}

DEPLOYMENT_TOPOLOGIES = [
    "single-region active-passive", "multi-region active-active",
    "edge + cloud hybrid", "on-premises with cloud DR",
    "multi-cloud with traffic manager", "air-gapped secure enclave",
    "serverless event-driven", "Kubernetes multi-cluster federation",
]

# --- 08. Architecture Pattern Seeds --------------------------------------

ARCHITECTURE_PATTERNS = {
    "microservices": {
        "description": "Decompose application into independently deployable services",
        "when_to_use": ["team scaling", "independent deployability", "polyglot persistence", "fault isolation"],
        "tradeoffs": ["operational complexity", "distributed transactions", "network latency", "testing complexity"],
        "related_patterns": ["API Gateway", "Service Mesh", "CQRS", "Event Sourcing", "Saga"],
    },
    "event_driven": {
        "description": "Systems communicate through asynchronous events via message brokers",
        "when_to_use": ["decoupled services", "audit trails", "real-time processing", "eventual consistency acceptable"],
        "tradeoffs": ["eventual consistency", "debugging difficulty", "message ordering", "idempotency requirement"],
        "related_patterns": ["Event Sourcing", "CQRS", "Saga", "Outbox Pattern", "Dead Letter Queue"],
    },
    "cqrs": {
        "description": "Separate read and write models for different optimization strategies",
        "when_to_use": ["read-heavy workloads", "complex domain models", "different scaling needs", "event sourcing"],
        "tradeoffs": ["code duplication", "eventual consistency", "sync complexity", "operational overhead"],
        "related_patterns": ["Event Sourcing", "Materialized View", "Database per Service"],
    },
    "hexagonal": {
        "description": "Isolate core business logic from infrastructure through ports and adapters",
        "when_to_use": ["testability", "infrastructure flexibility", "domain-driven design", "long-lived systems"],
        "tradeoffs": ["abstraction overhead", "learning curve", "potential over-engineering for simple systems"],
        "related_patterns": ["Clean Architecture", "Onion Architecture", "Domain-Driven Design"],
    },
    "saga": {
        "description": "Manage distributed transactions through a sequence of local transactions with compensating actions",
        "when_to_use": ["distributed transactions", "microservices", "long-running processes", "eventual consistency"],
        "tradeoffs": ["complexity", "partial failure handling", "compensating transaction design", "debugging difficulty"],
        "related_patterns": ["Choreography", "Orchestration", "Outbox Pattern", "Idempotent Consumer"],
    },
    "strangler_fig": {
        "description": "Incrementally migrate legacy system by routing traffic to new implementation",
        "when_to_use": ["legacy migration", "risk reduction", "incremental delivery", "coexistence period"],
        "tradeoffs": ["routing complexity", "data synchronization", "extended migration period", "dual maintenance"],
        "related_patterns": ["Anti-Corruption Layer", "Branch by Abstraction", "Feature Toggle"],
    },
    "edge_fog": {
        "description": "Process data at network edge before selective cloud forwarding",
        "when_to_use": ["latency-sensitive IoT", "bandwidth constraints", "offline capability", "data sovereignty"],
        "tradeoffs": ["edge device management", "firmware updates", "limited compute", "sync complexity"],
        "related_patterns": ["Gateway Aggregation", "Store and Forward", "Edge ML Inference"],
    },
    "unified_namespace": {
        "description": "Central MQTT broker as single source of truth for all OT and IT data",
        "when_to_use": ["IT/OT convergence", "ISA-95 modernization", "real-time data fabric", "industrial IoT"],
        "tradeoffs": ["broker scalability", "topic design complexity", "security boundaries", "legacy protocol bridging"],
        "related_patterns": ["ISA-95 Levels", "OPC-UA Pub/Sub", "Sparkplug B"],
    },
}

# --- 09. Diagram Generation Seeds ----------------------------------------

DIAGRAM_TYPES = {
    "sequence_diagram": {
        "purpose": "Show interaction order between system components over time",
        "when_to_use": ["API flows", "authentication sequences", "order processing", "async messaging"],
        "mermaid_prefix": "sequenceDiagram",
    },
    "class_diagram": {
        "purpose": "Show static structure of domain entities and relationships",
        "when_to_use": ["domain modeling", "database design", "ORM mapping", "API contracts"],
        "mermaid_prefix": "classDiagram",
    },
    "flowchart": {
        "purpose": "Show process flow and decision points",
        "when_to_use": ["workflow automation", "troubleshooting", "business process", "state transitions"],
        "mermaid_prefix": "flowchart TD",
    },
    "er_diagram": {
        "purpose": "Show database entity relationships and cardinality",
        "when_to_use": ["database design", "data modeling", "schema migration", "normalization"],
        "mermaid_prefix": "erDiagram",
    },
    "deployment_diagram": {
        "purpose": "Show physical/cloud infrastructure and component placement",
        "when_to_use": ["deployment planning", "infrastructure review", "DR planning", "network topology"],
        "mermaid_prefix": "flowchart LR",
    },
    "state_diagram": {
        "purpose": "Show state transitions of an entity through its lifecycle",
        "when_to_use": ["order lifecycle", "ticket workflow", "device states", "protocol states"],
        "mermaid_prefix": "stateDiagram-v2",
    },
    "gantt_chart": {
        "purpose": "Show project timeline and task dependencies",
        "when_to_use": ["implementation roadmap", "migration planning", "sprint planning", "release planning"],
        "mermaid_prefix": "gantt",
    },
    "c4_context": {
        "purpose": "Show system context with external actors and dependencies",
        "when_to_use": ["system overview", "stakeholder communication", "architecture review"],
        "mermaid_prefix": "C4Context",
    },
    "pie_chart": {
        "purpose": "Show proportional distribution of categories",
        "when_to_use": ["cost breakdown", "traffic distribution", "error categorization", "resource allocation"],
        "mermaid_prefix": "pie",
    },
}

# --- 10. Document Generation Seeds ----------------------------------------

DOCUMENT_SPECS = {
    "hld": {
        "full_name": "High-Level Design Document",
        "sections": ["Executive Summary", "System Overview", "Architecture", "Technology Stack",
                      "Data Flow", "Integration Points", "Security", "Deployment", "Risks", "Roadmap"],
        "audience": "architects, tech leads, stakeholders",
    },
    "lld": {
        "full_name": "Low-Level Design Document",
        "sections": ["Component Design", "Class Diagrams", "Sequence Diagrams", "Database Schema",
                      "API Contracts", "Error Handling", "Logging Strategy", "Unit Test Plan"],
        "audience": "developers, QA engineers",
    },
    "prd": {
        "full_name": "Product Requirements Document",
        "sections": ["Problem Statement", "User Personas", "User Stories", "Acceptance Criteria",
                      "Non-Functional Requirements", "Wireframes", "Success Metrics", "Out of Scope"],
        "audience": "product managers, designers, developers",
    },
    "srs": {
        "full_name": "Software Requirements Specification",
        "sections": ["Purpose", "Scope", "Functional Requirements", "Non-Functional Requirements",
                      "Interface Requirements", "Data Requirements", "Constraints", "Assumptions"],
        "audience": "developers, QA, project managers",
    },
    "brd": {
        "full_name": "Business Requirements Document",
        "sections": ["Business Objectives", "Stakeholders", "Current State", "Future State",
                      "Gap Analysis", "Business Rules", "ROI Analysis", "Success Criteria"],
        "audience": "business stakeholders, sponsors, executives",
    },
    "deployment_guide": {
        "full_name": "Deployment Guide",
        "sections": ["Prerequisites", "Environment Setup", "Configuration", "Deployment Steps",
                      "Verification", "Rollback Procedure", "Troubleshooting", "Contacts"],
        "audience": "DevOps engineers, SREs",
    },
    "runbook": {
        "full_name": "Operations Runbook",
        "sections": ["Service Overview", "Architecture", "Health Checks", "Common Alerts",
                      "Troubleshooting Procedures", "Escalation Matrix", "Maintenance Windows", "Disaster Recovery"],
        "audience": "SREs, on-call engineers, operations",
    },
    "test_plan": {
        "full_name": "Test Plan and Strategy",
        "sections": ["Test Scope", "Test Types", "Environment", "Test Data", "Entry/Exit Criteria",
                      "Defect Management", "Risk-Based Testing", "Schedule"],
        "audience": "QA engineers, test leads",
    },
    "security_assessment": {
        "full_name": "Security Assessment Report",
        "sections": ["Executive Summary", "Scope", "Methodology", "Findings",
                      "Risk Ratings", "Remediation Plan", "Compliance Mapping", "Retesting Schedule"],
        "audience": "CISO, security team, auditors",
    },
    "api_specification": {
        "full_name": "API Specification (OpenAPI 3.0)",
        "sections": ["Info", "Servers", "Paths", "Schemas", "Security Schemes",
                      "Error Responses", "Rate Limiting", "Versioning Strategy"],
        "audience": "frontend developers, integration partners, API consumers",
    },
}

# --- 11. Engineering Reasoning Seeds --------------------------------------

ENGINEERING_DECISIONS = [
    {
        "problem": "Choose a message broker for high-throughput industrial telemetry",
        "options": ["Apache Kafka", "RabbitMQ", "MQTT (EMQX)", "NATS", "Apache Pulsar"],
        "evaluation_criteria": ["throughput", "latency", "durability", "ordering", "protocol support", "operational complexity"],
        "decision": "Apache Kafka",
        "reason": "Kafka provides durable, ordered, replayable event logs essential for industrial telemetry audit trails and supports partitioned parallel consumption for high throughput.",
    },
    {
        "problem": "Select a database for append-only financial ledger",
        "options": ["PostgreSQL", "CockroachDB", "Apache Cassandra", "TiDB", "Amazon QLDB"],
        "evaluation_criteria": ["ACID compliance", "auditability", "scalability", "query flexibility", "regulatory acceptance"],
        "decision": "PostgreSQL with append-only schema",
        "reason": "PostgreSQL provides strong ACID guarantees, row-level security, and is widely accepted by financial regulators. Append-only design enforced by triggers prevents mutation of ledger entries.",
    },
    {
        "problem": "Choose a container orchestration platform for a regulated healthcare environment",
        "options": ["Kubernetes (EKS)", "OpenShift", "Amazon ECS", "Docker Swarm", "Nomad"],
        "evaluation_criteria": ["HIPAA compliance tooling", "RBAC granularity", "audit logging", "ecosystem maturity", "managed service availability"],
        "decision": "OpenShift or EKS with hardened configuration",
        "reason": "Both provide HIPAA-eligible configurations with built-in RBAC, network policies, pod security standards, and audit logging. OpenShift adds operator-based compliance automation.",
    },
    {
        "problem": "Select an IoT communication protocol for a factory floor with 10,000 sensors",
        "options": ["MQTT", "OPC-UA", "Modbus TCP", "HTTP REST", "CoAP", "AMQP"],
        "evaluation_criteria": ["bandwidth efficiency", "publish-subscribe support", "QoS levels", "security", "edge device support", "standards compliance"],
        "decision": "MQTT for telemetry + OPC-UA for supervisory",
        "reason": "MQTT's lightweight pub/sub model is ideal for high-frequency sensor data with minimal overhead. OPC-UA provides rich information modeling and security for supervisory-level integration with MES/ERP.",
    },
    {
        "problem": "Choose a caching strategy for a high-traffic e-commerce platform",
        "options": ["Redis (standalone)", "Redis Cluster", "Memcached", "Application-level cache (Guava)", "CDN edge cache"],
        "evaluation_criteria": ["data structure support", "persistence", "cluster scalability", "latency", "operational simplicity"],
        "decision": "Redis Cluster + CDN edge cache",
        "reason": "Redis Cluster provides distributed caching with data structure support for sessions, inventory locks, and rate limiting. CDN caches static assets and API responses at the edge for global latency reduction.",
    },
    {
        "problem": "Select a monitoring stack for a Kubernetes-based microservices platform",
        "options": ["Prometheus + Grafana", "Datadog", "New Relic", "Elastic APM", "Dynatrace"],
        "evaluation_criteria": ["Kubernetes native integration", "cost model", "custom metrics", "alerting", "trace correlation", "log aggregation"],
        "decision": "Prometheus + Grafana + Loki + Tempo",
        "reason": "Open-source stack with native Kubernetes service discovery, PromQL for flexible alerting, Grafana for unified dashboards, Loki for cost-effective log aggregation, and Tempo for distributed tracing.",
    },
    {
        "problem": "Choose between microservices and modular monolith for a startup MVP",
        "options": ["Microservices", "Modular Monolith", "Serverless Functions", "Traditional Monolith"],
        "evaluation_criteria": ["team size", "deployment complexity", "time to market", "operational cost", "future scalability"],
        "decision": "Modular Monolith",
        "reason": "For a small team building an MVP, a modular monolith provides clear domain boundaries without distributed systems complexity. Well-defined module interfaces enable future extraction to microservices when scale demands it.",
    },
    {
        "problem": "Select a database replication strategy for a multi-region deployment",
        "options": ["Synchronous replication", "Asynchronous replication", "Semi-synchronous", "CockroachDB multi-region", "DynamoDB Global Tables"],
        "evaluation_criteria": ["consistency", "latency impact", "data loss risk", "operational complexity", "conflict resolution"],
        "decision": "Asynchronous replication with conflict detection",
        "reason": "Synchronous replication across regions introduces unacceptable latency for most workloads. Async replication with last-writer-wins or application-level conflict resolution provides acceptable consistency for most use cases.",
    },
]

TECHNOLOGY_COMPARISONS = [
    ("MQTT", "OPC-UA", "industrial telemetry"),
    ("Kafka", "RabbitMQ", "event streaming"),
    ("PostgreSQL", "MongoDB", "application database"),
    ("Redis", "Memcached", "caching layer"),
    ("Kubernetes", "Docker Swarm", "container orchestration"),
    ("REST", "GraphQL", "API design"),
    ("gRPC", "REST", "inter-service communication"),
    ("Terraform", "Pulumi", "infrastructure as code"),
    ("Prometheus", "Datadog", "monitoring"),
    ("Elasticsearch", "Solr", "full-text search"),
    ("Kafka Streams", "Apache Flink", "stream processing"),
    ("PostgreSQL", "TimescaleDB", "time-series data"),
    ("Keycloak", "Auth0", "identity management"),
    ("Nginx", "Envoy", "reverse proxy / service mesh"),
    ("Jenkins", "GitHub Actions", "CI/CD pipeline"),
    ("Ansible", "Chef", "configuration management"),
    ("Consul", "etcd", "service discovery"),
    ("Vault", "AWS Secrets Manager", "secrets management"),
    ("Spark", "Flink", "batch + stream processing"),
    ("Airflow", "Dagster", "workflow orchestration"),
]

# --- 12–21. Domain-Specific Engineering Seeds ----------------------------

AIOT_PROTOCOLS = {
    "mqtt": {
        "name": "MQTT", "full_name": "Message Queuing Telemetry Transport",
        "standard": "ISO/IEC 20922", "port": 1883, "tls_port": 8883,
        "qos_levels": ["QoS 0 (at most once)", "QoS 1 (at least once)", "QoS 2 (exactly once)"],
        "use_cases": ["sensor telemetry", "device control", "last-will testament", "retained messages"],
        "security": ["TLS 1.3", "X.509 client certificates", "username/password", "ACL per topic"],
        "failure_modes": ["broker overload", "topic storm", "client reconnect loop", "QoS mismatch", "retained message corruption"],
    },
    "opcua": {
        "name": "OPC-UA", "full_name": "Open Platform Communications Unified Architecture",
        "standard": "IEC 62541", "port": 4840,
        "features": ["information modeling", "discovery", "pub/sub", "historical access", "alarms & conditions"],
        "use_cases": ["MES integration", "supervisory data", "process historian", "device onboarding"],
        "security": ["message signing", "encryption", "user token policies", "certificate management"],
        "failure_modes": ["certificate expiry", "subscription timeout", "server overload", "namespace mismatch"],
    },
    "modbus": {
        "name": "Modbus", "full_name": "Modbus TCP/RTU",
        "standard": "Modbus.org specification", "port": 502,
        "register_types": ["coils", "discrete inputs", "holding registers", "input registers"],
        "use_cases": ["legacy PLC communication", "simple sensor polling", "actuator control"],
        "security": ["none (inherently insecure)", "network segmentation required", "IDS monitoring"],
        "failure_modes": ["register address collision", "polling timeout", "serial bus contention", "byte order mismatch"],
    },
    "bacnet": {
        "name": "BACnet", "full_name": "Building Automation and Control Networks",
        "standard": "ASHRAE 135 / ISO 16484-5", "port": 47808,
        "services": ["ReadProperty", "WriteProperty", "SubscribeCOV", "WhoIs/IAm"],
        "use_cases": ["HVAC control", "lighting automation", "fire/life safety", "access control"],
        "security": ["BACnet/SC (Secure Connect)", "TLS tunneling", "network segmentation"],
        "failure_modes": ["device broadcast storm", "COV subscription overflow", "priority array conflict"],
    },
    "can_bus": {
        "name": "CAN Bus", "full_name": "Controller Area Network",
        "standard": "ISO 11898", "bitrates": ["250 kbps", "500 kbps", "1 Mbps"],
        "features": ["multi-master", "priority arbitration", "error detection", "fault confinement"],
        "use_cases": ["automotive ECU communication", "industrial machinery", "medical devices", "aerospace"],
        "security": ["message authentication", "encrypted payloads", "intrusion detection"],
        "failure_modes": ["bus-off state", "bit stuffing error", "dominant bit fault", "EMI interference"],
    },
}

MECHANICAL_ASSETS = {
    "centrifugal_pump": {
        "name": "Centrifugal Pump",
        "failure_modes": ["cavitation", "impeller erosion", "seal failure", "bearing failure", "shaft misalignment",
                          "suction recirculation", "discharge recirculation", "dead head operation"],
        "sensors": ["vibration (accelerometer)", "pressure (suction/discharge)", "flow meter", "temperature (bearing/motor)",
                    "current (motor amperage)", "ultrasonic thickness"],
        "maintenance": ["vibration analysis", "oil analysis", "thermography", "alignment check", "seal replacement",
                        "impeller inspection", "performance curve test"],
        "parameters": {"flow_rate": "m³/h", "head": "meters", "efficiency": "%", "NPSH": "meters", "speed": "RPM"},
        "standards": ["API 610", "ISO 5199", "ANSI/HI"],
    },
    "compressor": {
        "name": "Air/Gas Compressor",
        "failure_modes": ["valve failure", "piston ring wear", "intercooler fouling", "oil carryover",
                          "surge (centrifugal)", "bearing failure", "coupling misalignment"],
        "sensors": ["vibration", "discharge pressure", "inlet temperature", "discharge temperature",
                    "oil pressure", "oil temperature", "current"],
        "maintenance": ["valve inspection", "ring replacement", "cooler cleaning", "oil change",
                        "alignment check", "capacity test"],
        "parameters": {"pressure_ratio": "ratio", "flow": "CFM", "power": "kW", "efficiency": "%"},
        "standards": ["API 618 (reciprocating)", "API 617 (centrifugal)", "ASME PTC 10"],
    },
    "hvac_system": {
        "name": "HVAC System",
        "failure_modes": ["refrigerant leak", "compressor failure", "condenser fouling", "evaporator icing",
                          "damper actuator failure", "fan belt slip", "control valve stuck"],
        "sensors": ["temperature (supply/return)", "humidity", "CO2", "differential pressure (filter)",
                    "refrigerant pressure (high/low)", "airflow velocity"],
        "maintenance": ["filter replacement", "coil cleaning", "refrigerant charge check", "belt inspection",
                        "damper calibration", "BACnet point verification"],
        "parameters": {"capacity": "tons/kW", "COP": "ratio", "EER": "BTU/Wh", "airflow": "CFM"},
        "standards": ["ASHRAE 90.1", "ASHRAE 62.1", "ASHRAE 55"],
    },
    "electric_motor": {
        "name": "Electric Motor (AC Induction)",
        "failure_modes": ["bearing failure", "stator winding insulation breakdown", "rotor bar fracture",
                          "shaft misalignment", "voltage imbalance", "overheating", "VFD-induced bearing currents"],
        "sensors": ["vibration (triaxial)", "stator temperature (RTD/thermocouple)", "current (per phase)",
                    "voltage (per phase)", "speed (encoder/tachometer)", "insulation resistance (offline)"],
        "maintenance": ["vibration analysis", "motor circuit analysis (MCA)", "thermography", "insulation resistance test",
                        "alignment check", "bearing lubrication", "surge test"],
        "parameters": {"power": "kW/HP", "speed": "RPM", "voltage": "V", "current": "A", "power_factor": "ratio"},
        "standards": ["NEMA MG 1", "IEC 60034", "IEEE 112"],
    },
    "bearing": {
        "name": "Rolling Element Bearing",
        "failure_modes": ["fatigue spalling", "brinelling", "fretting corrosion", "cage failure",
                          "contamination", "lubrication starvation", "misalignment-induced wear"],
        "sensors": ["vibration (enveloping/demodulation)", "temperature", "acoustic emission",
                    "oil debris monitor", "shock pulse"],
        "maintenance": ["vibration trending", "oil analysis", "grease replenishment",
                        "visual inspection", "ultrasonic monitoring"],
        "parameters": {"BPFO": "Hz", "BPFI": "Hz", "BSF": "Hz", "FTF": "Hz", "L10_life": "hours"},
        "standards": ["ISO 281", "ISO 15243", "API 610 Appendix I"],
    },
    "control_valve": {
        "name": "Control Valve",
        "failure_modes": ["seat erosion", "packing leak", "stem binding", "cavitation damage",
                          "positioner failure", "flashing damage", "actuator diaphragm tear"],
        "sensors": ["stem position", "supply air pressure", "differential pressure",
                    "acoustic emission (cavitation)", "temperature"],
        "maintenance": ["valve signature test", "packing replacement", "seat lapping",
                        "positioner calibration", "actuator bench test", "fugitive emission test"],
        "parameters": {"Cv": "flow coefficient", "travel": "%", "rangeability": "ratio", "shut-off_class": "ANSI/FCI"},
        "standards": ["ISA-75.01", "IEC 60534", "API 6D"],
    },
    "conveyor_belt": {
        "name": "Conveyor Belt System",
        "failure_modes": ["belt tracking issues", "splice failure", "roller seizure",
                          "motor overload", "belt slip", "material spillage", "idler failure"],
        "sensors": ["belt speed", "motor current", "vibration (drive/tail pulley)", "belt scale (weigh)",
                    "alignment sensor", "rip detection"],
        "maintenance": ["belt tension adjustment", "roller replacement", "splice inspection",
                        "lagging replacement", "scraper adjustment", "alignment check"],
        "parameters": {"belt_speed": "m/s", "capacity": "t/h", "belt_width": "mm", "incline": "degrees"},
        "standards": ["CEMA standards", "DIN 22101", "ISO 5048"],
    },
}

ELECTRICAL_COMPONENTS = {
    "vfd": {
        "name": "Variable Frequency Drive",
        "failure_modes": ["DC bus capacitor degradation", "IGBT failure", "input rectifier failure",
                          "cooling fan failure", "ground fault trip", "overvoltage trip"],
        "parameters": {"voltage": "V", "current": "A", "frequency": "Hz", "power": "kW"},
        "standards": ["IEC 61800", "NEMA MG 1 Part 31", "UL 508C"],
    },
    "transformer": {
        "name": "Power Transformer",
        "failure_modes": ["winding insulation breakdown", "bushing failure", "tap changer malfunction",
                          "oil contamination", "core saturation", "thermal overload"],
        "parameters": {"kVA": "kVA", "voltage_ratio": "V/V", "impedance": "%Z", "losses": "W"},
        "standards": ["IEEE C57.12", "IEC 60076", "ANSI C57.91"],
    },
    "protection_relay": {
        "name": "Protection Relay",
        "failure_modes": ["CT saturation", "incorrect settings", "communication failure",
                          "auxiliary power loss", "contact wear", "firmware bug"],
        "parameters": {"pickup_current": "A", "time_dial": "ratio", "curve_type": "IEC/IEEE"},
        "standards": ["IEEE C37", "IEC 60255", "NERC PRC"],
    },
    "switchgear": {
        "name": "Medium Voltage Switchgear",
        "failure_modes": ["arc flash", "insulation failure", "mechanism jam", "busbar overheating",
                          "SF6 gas leak", "cable termination failure"],
        "parameters": {"voltage": "kV", "current_rating": "A", "fault_level": "kA", "arc_rating": "cal/cm²"},
        "standards": ["IEC 62271", "IEEE C37.20", "ANSI C37.06", "NFPA 70E"],
    },
}

STANDARDS_REGISTRY = {
    "isa_95": {"name": "ISA-95", "full_name": "Enterprise-Control System Integration", "scope": "Manufacturing IT/OT integration", "key_models": ["Physical Model", "Activity Model", "Object Model", "Function Model"], "architecture_impact": "Defines Levels 0-4 for industrial system hierarchy"},
    "iec_62443": {"name": "IEC 62443", "full_name": "Industrial Automation and Control Systems Security", "scope": "Industrial cybersecurity", "key_parts": ["General", "Policies & Procedures", "System", "Component"], "architecture_impact": "Zones and conduits security model; security levels (SL) 1-4"},
    "iso_27001": {"name": "ISO 27001", "full_name": "Information Security Management Systems", "scope": "Information security management", "key_clauses": ["Context", "Leadership", "Planning", "Support", "Operation", "Evaluation", "Improvement"], "architecture_impact": "Risk-based security controls selection"},
    "nist_csf": {"name": "NIST CSF", "full_name": "NIST Cybersecurity Framework", "scope": "Cybersecurity risk management", "key_functions": ["Identify", "Protect", "Detect", "Respond", "Recover"], "architecture_impact": "Layered security controls across all system tiers"},
    "owasp_top10": {"name": "OWASP Top 10", "full_name": "Open Web Application Security Project Top 10", "scope": "Web application security", "vulnerabilities": ["Broken Access Control", "Cryptographic Failures", "Injection", "Insecure Design", "Security Misconfiguration", "Vulnerable Components", "Authentication Failures", "Data Integrity Failures", "Logging Failures", "SSRF"], "architecture_impact": "Security testing and code review checklist"},
    "hipaa": {"name": "HIPAA", "full_name": "Health Insurance Portability and Accountability Act", "scope": "Healthcare data privacy and security", "key_rules": ["Privacy Rule", "Security Rule", "Breach Notification Rule", "Enforcement Rule"], "architecture_impact": "PHI encryption, access controls, audit logging, BAA requirements"},
    "pci_dss": {"name": "PCI-DSS 4.0", "full_name": "Payment Card Industry Data Security Standard", "scope": "Payment card data protection", "requirements_count": 12, "architecture_impact": "Network segmentation, encryption, access control, monitoring, and testing"},
    "gdpr": {"name": "GDPR", "full_name": "General Data Protection Regulation", "scope": "EU personal data protection", "key_principles": ["Lawfulness", "Purpose Limitation", "Data Minimisation", "Accuracy", "Storage Limitation", "Integrity/Confidentiality", "Accountability"], "architecture_impact": "Data residency, consent management, right to erasure, DPIAs"},
    "iso_9001": {"name": "ISO 9001", "full_name": "Quality Management Systems", "scope": "Quality management", "architecture_impact": "Process documentation, continuous improvement, audit trails"},
    "mqtt_v5": {"name": "MQTT v5.0", "full_name": "MQTT Version 5.0", "scope": "IoT messaging protocol", "standard_ref": "ISO/IEC 20922", "architecture_impact": "Topic-based pub/sub, QoS levels, session management, shared subscriptions"},
    "openapi_3": {"name": "OpenAPI 3.0", "full_name": "OpenAPI Specification", "scope": "API description format", "architecture_impact": "Machine-readable API contracts, code generation, documentation"},
    "rest": {"name": "REST", "full_name": "Representational State Transfer", "scope": "API architectural style", "constraints": ["Client-Server", "Stateless", "Cacheable", "Layered", "Uniform Interface", "Code on Demand (optional)"], "architecture_impact": "Resource-oriented API design with HTTP methods and status codes"},
    "graphql": {"name": "GraphQL", "full_name": "GraphQL Query Language", "scope": "API query language", "features": ["queries", "mutations", "subscriptions", "fragments", "directives"], "architecture_impact": "Client-driven data fetching, schema-first design, N+1 query risk"},
}

# --- 22–23. Failure Analysis & RCA Seeds ----------------------------------

FAILURE_ANALYSIS_TEMPLATES = {
    "mechanical": [
        {"problem": "{asset} experiencing excessive vibration at {frequency} Hz",
         "symptoms": ["increased noise levels", "elevated bearing temperature", "visible shaft movement"],
         "possible_causes": ["imbalance", "misalignment", "bearing defect", "loose foundation", "resonance"],
         "tests": ["vibration spectrum analysis", "phase analysis", "orbit plot", "alignment check"],
         "preventive_action": "Implement vibration monitoring program with monthly trending and alarm thresholds"},
        {"problem": "{asset} seal leaking {fluid} at {rate}",
         "symptoms": ["visible fluid around seal area", "dropping reservoir level", "contamination downstream"],
         "possible_causes": ["seal face wear", "shaft runout", "incorrect installation", "thermal shock", "chemical attack"],
         "tests": ["visual inspection", "shaft runout measurement", "fluid analysis", "seal face inspection"],
         "preventive_action": "Install seal condition monitoring (leak detection, temperature) and establish spare seal inventory"},
    ],
    "electrical": [
        {"problem": "VFD tripping on {fault_type} fault during {operating_condition}",
         "symptoms": ["drive fault code {code}", "motor stops unexpectedly", "alarm on HMI"],
         "possible_causes": ["cable insulation degradation", "motor winding fault", "ground fault in cabling", "DC bus ripple"],
         "tests": ["megger test (motor and cable)", "drive fault log review", "harmonic analysis", "thermal imaging"],
         "preventive_action": "Schedule quarterly megger testing of motor circuits and annual drive capacitor testing"},
        {"problem": "Transformer oil DGA showing elevated {gas_type}",
         "symptoms": ["gas-in-oil analysis alarm", "temperature rise", "change in sound"],
         "possible_causes": ["partial discharge", "arcing", "thermal fault", "cellulose degradation", "oil contamination"],
         "tests": ["dissolved gas analysis (DGA)", "Duval triangle analysis", "power factor test", "turns ratio test"],
         "preventive_action": "Implement online DGA monitoring and establish trending baselines; schedule thermography annually"},
    ],
    "software": [
        {"problem": "API latency spikes to {latency}ms during {peak_period}",
         "symptoms": ["HTTP 504 gateway timeouts", "queue depth increasing", "CPU utilization at {cpu}%"],
         "possible_causes": ["database connection pool exhaustion", "N+1 query pattern", "missing index", "GC pauses", "thread starvation"],
         "tests": ["APM trace analysis", "slow query log review", "heap dump analysis", "connection pool metrics"],
         "preventive_action": "Implement query caching, connection pool monitoring with alerts, and load testing in CI/CD pipeline"},
        {"problem": "Memory leak in {service_name} causing OOM kills every {interval}",
         "symptoms": ["RSS grows linearly over time", "OOM killer events in dmesg", "pod restarts increasing"],
         "possible_causes": ["event listener not cleaned up", "cache without eviction", "connection pool leak", "circular references"],
         "tests": ["heap profiling", "memory trending over 24h", "GC log analysis", "code review of lifecycle hooks"],
         "preventive_action": "Add memory usage alerting, implement bounded caches, and add leak detection to CI/CD quality gates"},
    ],
    "networking": [
        {"problem": "Packet loss of {loss_rate}% between {source} and {destination}",
         "symptoms": ["TCP retransmissions", "application timeouts", "degraded throughput"],
         "possible_causes": ["interface errors (CRC/FCS)", "congestion", "MTU mismatch", "duplex mismatch", "faulty cable/optic"],
         "tests": ["interface error counters", "traceroute/mtr", "packet capture", "cable test", "optic power levels"],
         "preventive_action": "Implement SNMP-based interface monitoring with error-rate alerting and scheduled optic inspections"},
    ],
    "cloud": [
        {"problem": "{cloud_provider} {service} experiencing intermittent {error_code} errors",
         "symptoms": ["sporadic API failures", "increased error rate in CloudWatch/Azure Monitor", "SLA breach approaching"],
         "possible_causes": ["service throttling", "regional capacity issue", "misconfigured IAM policy", "certificate expiry", "DNS propagation delay"],
         "tests": ["CloudTrail/Activity Log review", "service health dashboard check", "IAM policy simulator", "DNS resolution test"],
         "preventive_action": "Implement multi-region failover, circuit breakers, and cloud service health monitoring with automated incident response"},
    ],
    "industrial": [
        {"problem": "PLC communication timeout with {device_count} field devices on {network_type}",
         "symptoms": ["I/O module fault indicators", "HMI showing stale data", "alarm flood on SCADA"],
         "possible_causes": ["network cable fault", "switch port failure", "PLC scan time overrun", "IP conflict", "EMI on fieldbus"],
         "tests": ["network traffic capture", "cable continuity test", "PLC diagnostic buffer review", "EMI survey"],
         "preventive_action": "Implement network redundancy (PRP/HSR), managed switches with monitoring, and PLC scan time optimization"},
    ],
}

# --- 29. Octagonal Mapping Seeds ------------------------------------------

OCTAGONAL_STAGES = [
    {"stage": "perception", "purpose": "Classify intent, extract entities, detect safety", "outputs": ["intent", "entities", "domain_hints", "safety_flag"]},
    {"stage": "context", "purpose": "Expand use cases, map requirements, understand project scope", "outputs": ["use_cases", "requirements", "context_frame"]},
    {"stage": "planning", "purpose": "Generate solution plan with phases, dependencies, and resources", "outputs": ["plan", "phases", "milestones"]},
    {"stage": "knowledge", "purpose": "Load domain knowledge packs, standards, best practices", "outputs": ["knowledge_sources", "standards", "patterns"]},
    {"stage": "memory", "purpose": "Recall past decisions, organizational experience, lessons learned", "outputs": ["past_decisions", "similar_solutions", "lessons"]},
    {"stage": "reasoning", "purpose": "Synthesize solution blueprint with engineering intelligence", "outputs": ["solution_document", "technology_stack", "diagrams", "roadmap"]},
    {"stage": "validation", "purpose": "Verify solution completeness, consistency, and standards compliance", "outputs": ["validation_report", "completeness_score", "issues"]},
    {"stage": "experience", "purpose": "Record solution for organizational learning and future retrieval", "outputs": ["experience_record", "confidence", "trace"]},
]


# =========================================================================
#  GENERATOR FUNCTIONS — One per dataset type
# =========================================================================

def _pick(collection, count=1):
    """Randomly sample from a collection without errors if count > len."""
    if isinstance(collection, dict):
        collection = list(collection.keys())
    return random.sample(collection, min(count, len(collection)))


def _fill_template(template: str, params: Dict[str, Any]) -> str:
    """Best-effort template filling; unfilled slots are left as-is."""
    result = template
    for k, v in params.items():
        result = result.replace("{" + k + "}", str(v))
    return result


def generate_intent_detection(count: int) -> List[Dict[str, Any]]:
    """Generate intent detection training records."""
    records = []
    used_inputs = set()
    for _ in range(count):
        intent = random.choice(INTENT_TYPES)
        template = random.choice(INTENT_TEMPLATES)
        params = {
            "adjective": random.choice(INTENT_ADJECTIVES),
            "system_type": random.choice(SYSTEM_TYPES),
            "use_case": random.choice(USE_CASES),
            "industry": random.choice(INDUSTRIES),
            "document_type": random.choice(DOCUMENT_TYPES),
            "requirement": random.choice(["99.9% uptime", "sub-100ms latency", "horizontal scalability", "multi-tenant isolation",
                                          "HIPAA compliance", "PCI-DSS compliance", "real-time processing", "offline capability"]),
            "component": random.choice(["authentication service", "data pipeline", "message broker", "API gateway",
                                        "database cluster", "monitoring stack", "edge gateway", "load balancer"]),
            "environment": random.choice(["factory floor", "hospital network", "cloud VPC", "edge cluster", "data center"]),
            "symptom": random.choice(["intermittent timeouts", "memory leaks", "connection drops", "high latency",
                                      "excessive CPU usage", "disk I/O saturation", "GC pauses"]),
            "platform": random.choice(PLATFORMS),
            "auth_type": random.choice(["OAuth 2.0", "API key", "mTLS", "JWT", "SAML"]),
            "availability": random.choice(["99.9%", "99.95%", "99.99%", "99.999%"]),
            "legacy_system": random.choice(["monolithic Java application", "COBOL mainframe", "on-premises Oracle DB", "legacy SOAP services"]),
            "target_platform": random.choice(PLATFORMS),
            "constraint": random.choice(["zero data loss", "backward compatibility", "regulatory compliance", "sub-second latency"]),
            "metric": random.choice(["p99 latency", "throughput", "error rate", "resource utilization", "cost per transaction"]),
            "problem": random.choice(["connection pool exhaustion", "N+1 query patterns", "cache stampede", "hot partition"]),
            "data_type": random.choice(["PHI", "PII", "PCI", "classified", "financial", "telemetry"]),
            "language": random.choice(["Python", "Java", "Go", "TypeScript", "C#", "Rust"]),
            "quality_attribute": random.choice(["maintainability", "testability", "security", "performance", "readability"]),
            "load_pattern": random.choice(["steady-state", "bursty", "seasonal", "exponential growth"]),
            "user_count": random.choice(["10,000", "100,000", "1,000,000", "10,000,000"]),
            "rpo": random.choice(["0 minutes", "5 minutes", "15 minutes", "1 hour"]),
            "rto": random.choice(["5 minutes", "15 minutes", "1 hour", "4 hours"]),
            "source_system": random.choice(["SAP ERP", "Salesforce", "legacy Oracle", "IoT gateway", "Kafka cluster"]),
            "target_system": random.choice(["data warehouse", "data lake", "ML feature store", "analytics dashboard"]),
            "volume": random.choice(["1,000", "10,000", "100,000", "1,000,000"]),
            "system_a": random.choice(["ERP", "CRM", "MES", "SCADA", "e-commerce platform"]),
            "system_b": random.choice(["data warehouse", "BI platform", "ML pipeline", "notification service"]),
            "integration_pattern": random.choice(["REST API", "event-driven (Kafka)", "file-based (SFTP)", "ETL batch", "webhook"]),
            "test_types": random.choice(["unit, integration, E2E, performance, security", "unit, contract, chaos"]),
            "sensor_count": random.choice(["100", "1,000", "10,000", "50,000"]),
            "interval": random.choice(["1 second", "5 seconds", "30 seconds", "1 minute"]),
            "feature_list": random.choice(["real-time dashboards, alerting, reporting, and API access",
                                           "user management, RBAC, audit logging, and SSO integration"]),
            "product_name": random.choice(["SmartFactory", "MediTrack", "FinGuard", "AgriSense", "FleetPulse"]),
            "market": random.choice(["mid-market manufacturing", "enterprise healthcare", "SMB retail", "government agencies"]),
            "throughput": random.choice(["1,000", "10,000", "50,000", "100,000"]),
            "messaging_tech": random.choice(["Apache Kafka", "RabbitMQ", "NATS", "Redis Streams"]),
            "standard": random.choice(["HIPAA", "PCI-DSS 4.0", "SOC 2 Type II", "ISO 27001", "NERC CIP"]),
            "target_percent": random.choice(["30", "50", "70", "90"]),
            "isolation_model": random.choice(["database-per-tenant", "schema-per-tenant", "row-level", "silo"]),
        }
        input_text = _fill_template(template, params)

        # Ensure uniqueness
        attempt = 0
        while input_text in used_inputs and attempt < 5:
            template = random.choice(INTENT_TEMPLATES)
            input_text = _fill_template(template, params)
            attempt += 1
        used_inputs.add(input_text)

        record = _base_metadata(
            domain=random.choice(list(DOMAINS.keys())),
            industry=random.choice(INDUSTRIES),
            intent=intent,
        )
        record.update({
            "input": input_text,
            "expected_output_type": random.choice(OUTPUT_TYPES),
            "tags": _pick(["hld", "lld", "architecture", "database", "api", "deployment", "security",
                           "performance", "migration", "iot", "industrial", "cloud", "monitoring"], 3),
        })
        records.append(record)
    return records


def generate_domain_classification(count: int) -> List[Dict[str, Any]]:
    """Generate domain classification training records."""
    records = []
    domain_keys = list(DOMAINS.keys())
    for _ in range(count):
        primary_key = random.choice(domain_keys)
        primary = DOMAINS[primary_key]
        secondary_keys = [k for k in _pick(domain_keys, 3) if k != primary_key]

        template = random.choice(DOMAIN_PROBLEM_TEMPLATES)
        params = {
            "adjective": random.choice(INTENT_ADJECTIVES),
            "system_type": random.choice(SYSTEM_TYPES),
            "requirement": random.choice(primary["keywords"]),
            "use_case": random.choice(USE_CASES),
            "component": random.choice(["API layer", "data pipeline", "control loop", "authentication module",
                                        "message broker", "edge gateway", "monitoring agent"]),
            "symptom": random.choice(["high latency", "data corruption", "connection drops", "memory leak",
                                      "configuration drift", "resource exhaustion"]),
            "option_a": random.choice(primary["keywords"]),
            "option_b": random.choice(DOMAINS[random.choice(domain_keys)]["keywords"]),
            "constraint": random.choice(["limited budget", "tight timeline", "regulatory compliance", "legacy integration"]),
            "standard": random.choice(list(STANDARDS_REGISTRY.keys())),
            "scale_a": random.choice(["100 users", "1,000 devices", "10 GB/day"]),
            "scale_b": random.choice(["100,000 users", "100,000 devices", "10 TB/day"]),
            "system_a": random.choice(SYSTEM_TYPES[:10]),
            "system_b": random.choice(SYSTEM_TYPES[10:20]),
            "quality_attribute": random.choice(["availability", "performance", "security", "maintainability"]),
            "topology": random.choice(["3 availability zones", "2 regions", "edge + cloud"]),
            "legacy_tech": random.choice(["Oracle Forms", "COBOL", "SOAP Web Services", "Delphi"]),
            "modern_tech": random.choice(["React + FastAPI", "Angular + Spring Boot", "Vue + Go"]),
        }
        problem = _fill_template(template, params)

        record = _base_metadata(domain=primary_key, industry=random.choice(INDUSTRIES), intent="domain_classification")
        record.update({
            "problem": problem,
            "primary_domain": primary["label"],
            "secondary_domains": [DOMAINS[k]["label"] for k in secondary_keys],
            "expert_personas": primary["expert_personas"],
            "keywords_detected": _pick(primary["keywords"], 4),
            "tags": _pick(primary["keywords"], 3),
        })
        records.append(record)
    return records


def generate_industry_classification(count: int) -> List[Dict[str, Any]]:
    """Generate industry classification training records."""
    records = []
    ind_keys = list(INDUSTRY_DETAILS.keys())
    for _ in range(count):
        ind_key = random.choice(ind_keys)
        ind = INDUSTRY_DETAILS[ind_key]

        problem_template = "In a {industry} environment, {problem}. The system must comply with {standard} and handle {terminology}."
        params = {
            "industry": ind["label"],
            "problem": random.choice(ind["common_problems"]),
            "standard": random.choice(ind["standards"]),
            "terminology": random.choice(ind["terminology"]),
        }
        problem = _fill_template(problem_template, params)

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=ind_key, intent="industry_classification")
        record.update({
            "problem": problem,
            "industry_label": ind["label"],
            "standards": ind["standards"],
            "regulations": ind["regulations"],
            "architecture_patterns": ind["architecture_patterns"],
            "common_problems": ind["common_problems"],
            "terminology": _pick(ind["terminology"], 4),
            "compliance": ind["compliance"],
            "tags": [ind_key] + _pick(ind["terminology"], 2),
        })
        records.append(record)
    return records


def generate_problem_classification(count: int) -> List[Dict[str, Any]]:
    """Generate problem classification training records."""
    records = []
    for _ in range(count):
        category = random.choice(PROBLEM_CATEGORIES)
        system = random.choice(SYSTEM_TYPES)
        use_case = random.choice(USE_CASES)
        problem = f"{category.replace('_', ' ').title()} challenge in {system} supporting {use_case}"

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="problem_classification")
        record.update({
            "problem": problem,
            "category": category,
            "system_type": system,
            "use_case": use_case,
            "severity": random.choice(["low", "medium", "high", "critical"]),
            "impact_scope": random.choice(["single_component", "subsystem", "system_wide", "cross_system"]),
            "tags": [category, "problem_classification"],
        })
        records.append(record)
    return records


def generate_usecase_expansion(count: int) -> List[Dict[str, Any]]:
    """Generate use case expansion training records."""
    records = []
    for _ in range(count):
        use_case = random.choice(USE_CASES)
        industry = random.choice(INDUSTRIES)

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=industry, intent="expand_use_case")
        record.update({
            "title": use_case,
            "business_objective": f"Improve operational efficiency through {use_case} in {industry.replace('_', ' ')} operations",
            "technical_objective": f"Design and implement a {random.choice(INTENT_ADJECTIVES)} system for {use_case}",
            "actors": _pick(ACTORS, random.randint(2, 5)),
            "inputs": _pick(["sensor data", "user commands", "API requests", "database queries", "file uploads",
                             "MQTT messages", "OPC-UA tags", "ERP transactions", "manual entries", "scheduled triggers"], 4),
            "outputs": _pick(["dashboards", "alerts", "reports", "API responses", "control signals",
                              "audit logs", "notifications", "exported data", "compliance reports"], 4),
            "functional_requirements": [f"FR-{i+1}: System shall {random.choice(['process', 'validate', 'store', 'transmit', 'analyze', 'display', 'alert on'])} {random.choice(['incoming data', 'user requests', 'sensor readings', 'transactions', 'events'])}" for i in range(random.randint(4, 8))],
            "non_functional_requirements": [random.choice(nfrs) for cat, nfrs in NFR_CATEGORIES.items() for _ in range(1)][:5],
            "constraints": _pick(["budget under $50K", "timeline under 6 months", "must use existing infrastructure",
                                   "limited team of 3 developers", "must integrate with legacy SAP",
                                   "must run on-premises", "air-gapped network", "24/7 operation requirement"], 3),
            "assumptions": _pick(["stable network connectivity", "existing database infrastructure", "trained operators available",
                                   "vendor support contract in place", "security infrastructure exists",
                                   "CI/CD pipeline available", "cloud account provisioned"], 3),
            "risks": _pick(["vendor lock-in", "scope creep", "integration complexity", "data quality issues",
                            "regulatory changes", "key personnel turnover", "technology obsolescence",
                            "security vulnerabilities", "performance under load"], 3),
            "dependencies": _pick(["ERP system availability", "network infrastructure upgrade", "security team approval",
                                    "vendor API documentation", "hardware procurement", "training completion",
                                    "compliance certification", "data migration completion"], 3),
            "expected_deliverables": _pick(DELIVERABLES, random.randint(3, 6)),
            "tags": ["use_case", industry],
        })
        records.append(record)
    return records


def generate_requirement_extraction(count: int) -> List[Dict[str, Any]]:
    """Generate requirement extraction training records."""
    records = []
    for _ in range(count):
        system = random.choice(SYSTEM_TYPES)
        nfr_cat = random.choice(list(NFR_CATEGORIES.keys()))
        nfr_templates = NFR_CATEGORIES[nfr_cat]
        template = random.choice(nfr_templates)

        params = {
            "latency": random.choice(["50", "100", "200", "500"]),
            "interval": random.choice(["1", "3", "5", "10"]),
            "throughput": random.choice(["1000", "5000", "10000", "50000"]),
            "record_count": random.choice(["1M", "10M", "100M"]),
            "duration": random.choice(["1", "5", "15", "30"]),
            "uptime": random.choice(["99.9", "99.95", "99.99"]),
            "window": random.choice(["2", "4", "8"]),
            "failover_time": random.choice(["10", "30", "60"]),
            "strategy": random.choice(["blue-green", "canary", "rolling"]),
            "rto": random.choice(["5", "15", "60"]),
            "rpo": random.choice(["0", "5", "15"]),
            "role_count": random.choice(["5", "10", "20"]),
            "retention": random.choice(["90", "180", "365", "730"]),
            "vault_tool": random.choice(["HashiCorp Vault", "AWS Secrets Manager", "Azure Key Vault"]),
            "node_count": random.choice(["10", "50", "100"]),
            "user_count": random.choice(["10000", "100000", "1000000"]),
            "event_rate": random.choice(["1000", "10000", "100000"]),
            "data_size": random.choice(["1", "10", "100"]),
            "cpu_threshold": random.choice(["60", "70", "80"]),
            "threshold": random.choice(["3", "5", "10"]),
            "max_retries": random.choice(["3", "5", "10"]),
            "service_count": random.choice(["5", "10", "20"]),
            "frequency": random.choice(["weekly", "monthly", "quarterly"]),
            "replication_factor": random.choice(["2", "3", "5"]),
            "coverage": random.choice(["80", "85", "90"]),
            "complexity": random.choice(["10", "15", "20"]),
            "versioning_strategy": random.choice(["URI path", "header", "query parameter"]),
            "flag_count": random.choice(["10", "20", "50"]),
            "doc_coverage": random.choice(["80", "90", "95"]),
            "standard": random.choice(["HIPAA", "PCI-DSS", "SOC 2", "ISO 27001"]),
            "section": random.choice(["§164.312", "Req 3.4", "CC6.1", "A.12.4"]),
            "region": random.choice(["US East", "EU", "APAC"]),
            "retention_days": random.choice(["30", "90", "365"]),
            "audit_years": random.choice(["3", "5", "7"]),
        }
        requirement_text = _fill_template(template, params)

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="requirement_extraction")
        record.update({
            "system": system,
            "requirement_type": nfr_cat,
            "requirement_text": requirement_text,
            "category": random.choice(["functional", "non_functional"]),
            "priority": random.choice(["must_have", "should_have", "could_have", "wont_have"]),
            "verification_method": random.choice(["test", "inspection", "analysis", "demonstration"]),
            "tags": [nfr_cat, "requirement"],
        })
        records.append(record)
    return records


def generate_solution_blueprints(count: int) -> List[Dict[str, Any]]:
    """Generate canonical solution blueprint training records."""
    records = []
    for _ in range(count):
        system = random.choice(SYSTEM_TYPES)
        industry = random.choice(INDUSTRIES)
        ind_detail = INDUSTRY_DETAILS.get(industry, INDUSTRY_DETAILS["manufacturing"])

        tech_stack = {}
        for layer, options in TECH_STACK_OPTIONS.items():
            tech_stack[layer] = random.choice(options)

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=industry, intent="solution_blueprint")
        record.update({
            "problem": f"Design a complete {random.choice(INTENT_ADJECTIVES)} {system} for {random.choice(USE_CASES)} in {ind_detail['label']}",
            "solution_title": system,
            "architecture_pattern": random.choice(list(ARCHITECTURE_PATTERNS.keys())),
            "technology_stack": tech_stack,
            "components": _pick(["API Gateway", "Auth Service", "Core Service", "Data Pipeline", "Message Broker",
                                 "Cache Layer", "Search Service", "Notification Service", "Monitoring Agent",
                                 "Edge Gateway", "ML Inference Service", "Report Generator", "Scheduler"], 6),
            "database_design": {"primary": tech_stack.get("database_primary", "PostgreSQL"),
                                "cache": tech_stack.get("cache", "Redis"),
                                "search": tech_stack.get("search", "Elasticsearch")},
            "api_design": {"style": random.choice(["REST", "GraphQL", "gRPC"]),
                           "auth": random.choice(["OAuth 2.0", "API Key", "mTLS"]),
                           "versioning": random.choice(["URI path", "header"])},
            "deployment_topology": random.choice(DEPLOYMENT_TOPOLOGIES),
            "security_controls": _pick(["WAF", "mTLS", "RBAC", "encryption at rest", "audit logging",
                                        "vulnerability scanning", "SIEM integration", "DDoS protection"], 4),
            "testing_strategy": _pick(["unit tests", "integration tests", "E2E tests", "performance tests",
                                       "security tests", "chaos engineering", "contract tests"], 4),
            "monitoring": {"metrics": tech_stack.get("monitoring", "Prometheus + Grafana"),
                           "logging": tech_stack.get("logging", "ELK Stack"),
                           "alerting": random.choice(["PagerDuty", "OpsGenie", "Slack webhooks"])},
            "roadmap_phases": [
                {"phase": "Foundation", "duration": f"{random.randint(2, 4)} weeks", "deliverables": ["infrastructure setup", "CI/CD pipeline", "core services"]},
                {"phase": "Core Features", "duration": f"{random.randint(4, 8)} weeks", "deliverables": ["primary use cases", "API layer", "database"]},
                {"phase": "Integration", "duration": f"{random.randint(2, 4)} weeks", "deliverables": ["external integrations", "data pipeline", "monitoring"]},
                {"phase": "Hardening", "duration": f"{random.randint(2, 4)} weeks", "deliverables": ["security review", "performance testing", "documentation"]},
            ],
            "risks": _pick(ind_detail["common_problems"], 3) + _pick(["vendor lock-in", "scope creep", "key person dependency"], 2),
            "standards": _pick(ind_detail["standards"], 3),
            "recommended_diagrams": _pick(list(DIAGRAM_TYPES.keys()), 4),
            "recommended_documents": _pick(list(DOCUMENT_SPECS.keys()), 3),
            "tags": [industry, "blueprint"],
        })
        records.append(record)
    return records


def generate_architecture_patterns(count: int) -> List[Dict[str, Any]]:
    """Generate architecture pattern training records."""
    records = []
    pattern_keys = list(ARCHITECTURE_PATTERNS.keys())
    for _ in range(count):
        pk = random.choice(pattern_keys)
        pattern = ARCHITECTURE_PATTERNS[pk]

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="architecture_pattern")
        record.update({
            "pattern_name": pk,
            "description": pattern["description"],
            "when_to_use": pattern["when_to_use"],
            "tradeoffs": pattern["tradeoffs"],
            "related_patterns": pattern["related_patterns"],
            "example_system": random.choice(SYSTEM_TYPES),
            "example_use_case": random.choice(USE_CASES),
            "tags": [pk, "architecture"],
        })
        records.append(record)
    return records


def generate_diagram_generation(count: int) -> List[Dict[str, Any]]:
    """Generate diagram planning training records."""
    records = []
    diagram_keys = list(DIAGRAM_TYPES.keys())
    for _ in range(count):
        dk = random.choice(diagram_keys)
        diagram = DIAGRAM_TYPES[dk]

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="diagram_generation")
        record.update({
            "diagram_type": dk,
            "purpose": diagram["purpose"],
            "when_to_use": diagram["when_to_use"],
            "mermaid_prefix": diagram["mermaid_prefix"],
            "target_system": random.choice(SYSTEM_TYPES),
            "target_use_case": random.choice(USE_CASES),
            "context": f"Generate a {dk.replace('_', ' ')} for {random.choice(SYSTEM_TYPES)} showing {random.choice(diagram['when_to_use'])}",
            "tags": [dk, "diagram"],
        })
        records.append(record)
    return records


def generate_document_generation(count: int) -> List[Dict[str, Any]]:
    """Generate document type training records."""
    records = []
    doc_keys = list(DOCUMENT_SPECS.keys())
    for _ in range(count):
        dk = random.choice(doc_keys)
        doc = DOCUMENT_SPECS[dk]

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="document_generation")
        record.update({
            "document_type": dk,
            "full_name": doc["full_name"],
            "sections": doc["sections"],
            "audience": doc["audience"],
            "target_system": random.choice(SYSTEM_TYPES),
            "context": f"Generate a {doc['full_name']} for {random.choice(SYSTEM_TYPES)} in {random.choice(INDUSTRIES).replace('_', ' ')}",
            "tags": [dk, "document"],
        })
        records.append(record)
    return records


def generate_engineering_reasoning(count: int) -> List[Dict[str, Any]]:
    """Generate engineering reasoning / decision-making training records."""
    records = []
    for _ in range(count):
        # Use a seed decision and add variation
        seed = random.choice(ENGINEERING_DECISIONS)
        comparison = random.choice(TECHNOLOGY_COMPARISONS)

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="engineering_reasoning")
        record.update({
            "problem": seed["problem"] if random.random() > 0.4 else f"Compare {comparison[0]} vs {comparison[1]} for {comparison[2]}",
            "options": seed["options"] if random.random() > 0.4 else [comparison[0], comparison[1]],
            "evaluation_criteria": seed.get("evaluation_criteria", ["performance", "cost", "operational complexity", "ecosystem"]),
            "decision": seed["decision"] if random.random() > 0.4 else random.choice([comparison[0], comparison[1]]),
            "reason": seed["reason"] if random.random() > 0.4 else f"{comparison[0]} is preferred for {comparison[2]} due to its superior {random.choice(['throughput', 'ecosystem', 'reliability', 'cost-effectiveness'])}.",
            "tags": ["reasoning", "decision"],
        })
        records.append(record)
    return records


def generate_aiot(count: int) -> List[Dict[str, Any]]:
    """Generate AIoT / Industrial IoT training records."""
    records = []
    protocol_keys = list(AIOT_PROTOCOLS.keys())
    for _ in range(count):
        pk = random.choice(protocol_keys)
        proto = AIOT_PROTOCOLS[pk]

        record = _base_metadata(domain="industrial_iot", industry=random.choice(["manufacturing", "energy", "oil_and_gas", "industrial_automation"]), intent="aiot_engineering")
        record.update({
            "protocol": proto["name"],
            "full_name": proto.get("full_name", proto["name"]),
            "standard": proto.get("standard", ""),
            "use_cases": proto["use_cases"],
            "security": proto["security"],
            "failure_modes": proto["failure_modes"],
            "architecture_overview": f"{proto['name']}-based telemetry architecture with edge gateway, broker cluster, and cloud analytics",
            "components": _pick(["edge gateway", "broker cluster", "historian", "analytics engine", "dashboard",
                                 "PLC interface", "protocol converter", "security gateway"], 4),
            "monitoring_approach": f"Monitor {proto['name']} broker health via {random.choice(['Prometheus metrics', 'SNMP', 'built-in dashboard', 'custom health checks'])}",
            "recommended_diagrams": _pick(list(DIAGRAM_TYPES.keys()), 3),
            "tags": [pk, "aiot", "iot"],
        })
        records.append(record)
    return records


def generate_mechanical(count: int) -> List[Dict[str, Any]]:
    """Generate mechanical engineering knowledge records."""
    records = []
    asset_keys = list(MECHANICAL_ASSETS.keys())
    for _ in range(count):
        ak = random.choice(asset_keys)
        asset = MECHANICAL_ASSETS[ak]

        failure_mode = random.choice(asset["failure_modes"])
        record = _base_metadata(domain="mechanical", industry=random.choice(["manufacturing", "energy", "oil_and_gas"]), intent="mechanical_engineering")
        record.update({
            "asset": asset["name"],
            "failure_mode": failure_mode,
            "all_failure_modes": asset["failure_modes"],
            "sensors": asset["sensors"],
            "maintenance_activities": asset["maintenance"],
            "parameters": asset["parameters"],
            "standards": asset["standards"],
            "diagnostics": f"For {failure_mode} in {asset['name']}: {random.choice(asset['maintenance'])}",
            "tags": [ak, "mechanical"],
        })
        records.append(record)
    return records


def generate_electrical(count: int) -> List[Dict[str, Any]]:
    """Generate electrical engineering knowledge records."""
    records = []
    comp_keys = list(ELECTRICAL_COMPONENTS.keys())
    for _ in range(count):
        ck = random.choice(comp_keys)
        comp = ELECTRICAL_COMPONENTS[ck]

        failure = random.choice(comp["failure_modes"])
        record = _base_metadata(domain="electrical", industry=random.choice(["manufacturing", "energy", "utilities"]), intent="electrical_engineering")
        record.update({
            "component": comp["name"],
            "failure_mode": failure,
            "all_failure_modes": comp["failure_modes"],
            "parameters": comp["parameters"],
            "standards": comp["standards"],
            "diagnostics": f"For {failure} in {comp['name']}: inspect per {random.choice(comp['standards'])}",
            "tags": [ck, "electrical"],
        })
        records.append(record)
    return records


def generate_cloud(count: int) -> List[Dict[str, Any]]:
    """Generate cloud engineering training records."""
    records = []
    for _ in range(count):
        provider = random.choice(["AWS", "Azure", "GCP"])
        service_category = random.choice(["compute", "storage", "database", "networking", "security", "analytics", "ML"])

        record = _base_metadata(domain="cloud", industry=random.choice(INDUSTRIES), intent="cloud_engineering")
        record.update({
            "cloud_provider": provider,
            "service_category": service_category,
            "architecture_pattern": random.choice(list(ARCHITECTURE_PATTERNS.keys())),
            "deployment_topology": random.choice(DEPLOYMENT_TOPOLOGIES),
            "iac_tool": random.choice(TECH_STACK_OPTIONS["iac"]),
            "monitoring": random.choice(TECH_STACK_OPTIONS["monitoring"]),
            "use_case": random.choice(USE_CASES),
            "cost_optimization": random.choice(["reserved instances", "spot/preemptible", "right-sizing", "auto-scaling", "storage tiering"]),
            "security_controls": _pick(["VPC isolation", "security groups", "IAM policies", "KMS encryption",
                                        "WAF rules", "CloudTrail/Activity Log", "GuardDuty/Defender"], 4),
            "tags": [provider.lower(), "cloud", service_category],
        })
        records.append(record)
    return records


def generate_networking(count: int) -> List[Dict[str, Any]]:
    """Generate networking training records."""
    records = []
    for _ in range(count):
        topic = random.choice(["routing", "switching", "firewall", "load_balancing", "dns", "vpn", "sd_wan",
                                "wireless", "network_security", "network_monitoring"])
        record = _base_metadata(domain="networking", industry=random.choice(INDUSTRIES), intent="networking_engineering")
        record.update({
            "topic": topic,
            "problem": f"Design {topic.replace('_', ' ')} for {random.choice(SYSTEM_TYPES)}",
            "protocols": _pick(["TCP", "UDP", "HTTP/2", "gRPC", "MQTT", "BGP", "OSPF", "VRRP", "802.1Q"], 3),
            "security_controls": _pick(["ACLs", "firewall rules", "IDS/IPS", "802.1X", "MACsec", "IPsec", "TLS"], 3),
            "tags": [topic, "networking"],
        })
        records.append(record)
    return records


def generate_database(count: int) -> List[Dict[str, Any]]:
    """Generate database engineering training records."""
    records = []
    for _ in range(count):
        db_type = random.choice(["relational", "document", "timeseries", "graph", "key_value", "search"])
        record = _base_metadata(domain="database", industry=random.choice(INDUSTRIES), intent="database_design")
        record.update({
            "database_type": db_type,
            "technology": random.choice(TECH_STACK_OPTIONS.get(f"database_{db_type}", TECH_STACK_OPTIONS["database_primary"])),
            "use_case": random.choice(USE_CASES),
            "design_considerations": _pick(["normalization", "denormalization", "partitioning", "sharding",
                                            "replication", "indexing", "caching", "connection pooling",
                                            "query optimization", "backup strategy", "encryption at rest"], 4),
            "scalability_pattern": random.choice(["vertical scaling", "read replicas", "horizontal sharding",
                                                   "partitioning", "federation", "CQRS"]),
            "tags": [db_type, "database"],
        })
        records.append(record)
    return records


def generate_security(count: int) -> List[Dict[str, Any]]:
    """Generate cybersecurity training records."""
    records = []
    for _ in range(count):
        topic = random.choice(["authentication", "authorization", "encryption", "network_security", "application_security",
                                "cloud_security", "iot_security", "incident_response", "compliance", "vulnerability_management"])
        record = _base_metadata(domain="security", industry=random.choice(INDUSTRIES), intent="security_review")
        record.update({
            "security_topic": topic,
            "threat_model": random.choice(["STRIDE", "DREAD", "PASTA", "attack tree"]),
            "controls": _pick(["WAF", "RBAC", "MFA", "encryption", "audit logging", "IDS/IPS",
                               "SIEM", "DLP", "CASB", "EDR", "zero-trust network"], 4),
            "standards": _pick(["OWASP Top 10", "NIST CSF", "ISO 27001", "CIS Benchmarks",
                               "IEC 62443", "HIPAA Security Rule", "PCI-DSS"], 3),
            "use_case": random.choice(USE_CASES),
            "tags": [topic, "security"],
        })
        records.append(record)
    return records


def generate_backend(count: int) -> List[Dict[str, Any]]:
    """Generate backend engineering training records."""
    records = []
    for _ in range(count):
        record = _base_metadata(domain="backend", industry=random.choice(INDUSTRIES), intent="backend_design")
        record.update({
            "framework": random.choice(TECH_STACK_OPTIONS["backend_framework"]),
            "architecture_pattern": random.choice(list(ARCHITECTURE_PATTERNS.keys())),
            "api_style": random.choice(["REST", "GraphQL", "gRPC"]),
            "database": random.choice(TECH_STACK_OPTIONS["database_primary"]),
            "cache": random.choice(TECH_STACK_OPTIONS["cache"]),
            "messaging": random.choice(TECH_STACK_OPTIONS["messaging"]),
            "use_case": random.choice(USE_CASES),
            "design_considerations": _pick(["connection pooling", "rate limiting", "circuit breaker", "retry logic",
                                            "idempotency", "pagination", "bulk operations", "async processing",
                                            "input validation", "error handling", "logging", "health checks"], 5),
            "tags": ["backend"],
        })
        records.append(record)
    return records


def generate_frontend(count: int) -> List[Dict[str, Any]]:
    """Generate frontend engineering training records."""
    records = []
    for _ in range(count):
        record = _base_metadata(domain="frontend", industry=random.choice(INDUSTRIES), intent="frontend_design")
        record.update({
            "framework": random.choice(TECH_STACK_OPTIONS["frontend"]),
            "use_case": random.choice(USE_CASES),
            "design_considerations": _pick(["responsive design", "accessibility (WCAG 2.1)", "performance optimization",
                                            "state management", "code splitting", "lazy loading", "SSR/SSG",
                                            "PWA capabilities", "internationalization", "error boundaries",
                                            "design system integration", "real-time updates (WebSocket)"], 5),
            "tags": ["frontend"],
        })
        records.append(record)
    return records


def generate_api_design(count: int) -> List[Dict[str, Any]]:
    """Generate API design training records."""
    records = []
    for _ in range(count):
        style = random.choice(["REST", "GraphQL", "gRPC", "WebSocket", "Server-Sent Events"])
        record = _base_metadata(domain=random.choice(["backend", "software_engineering"]), industry=random.choice(INDUSTRIES), intent="api_design")
        record.update({
            "api_style": style,
            "use_case": random.choice(USE_CASES),
            "auth_method": random.choice(["OAuth 2.0 + PKCE", "API Key + HMAC", "mTLS", "JWT Bearer", "SAML 2.0"]),
            "versioning": random.choice(["URI path (/v1/)", "Accept header", "query parameter", "custom header"]),
            "rate_limiting": random.choice(["token bucket", "sliding window", "fixed window", "leaky bucket"]),
            "pagination": random.choice(["offset-based", "cursor-based", "keyset", "page-number"]),
            "error_format": random.choice(["RFC 7807 Problem Details", "custom JSON envelope", "GraphQL errors array"]),
            "documentation": random.choice(["OpenAPI 3.0", "GraphQL SDL + Playground", "Protocol Buffers .proto"]),
            "gateway": random.choice(TECH_STACK_OPTIONS["api_gateway"]),
            "tags": [style.lower(), "api"],
        })
        records.append(record)
    return records


def generate_failure_analysis(count: int) -> List[Dict[str, Any]]:
    """Generate failure analysis / diagnostics training records."""
    records = []
    fa_categories = list(FAILURE_ANALYSIS_TEMPLATES.keys())
    for _ in range(count):
        cat = random.choice(fa_categories)
        templates = FAILURE_ANALYSIS_TEMPLATES[cat]
        template = random.choice(templates)

        params = {
            "asset": random.choice(list(MECHANICAL_ASSETS.values()))["name"] if cat == "mechanical" else "system component",
            "frequency": random.choice(["120", "240", "600", "1200"]),
            "fluid": random.choice(["oil", "water", "coolant", "refrigerant"]),
            "rate": random.choice(["2 drops/minute", "steady drip", "visible stream"]),
            "fault_type": random.choice(["ground", "overcurrent", "overvoltage", "overtemperature"]),
            "operating_condition": random.choice(["startup", "full load", "variable speed", "regenerative braking"]),
            "code": random.choice(["F001", "F023", "F050", "A201"]),
            "gas_type": random.choice(["acetylene (C2H2)", "hydrogen (H2)", "ethylene (C2H4)", "methane (CH4)"]),
            "latency": random.choice(["2000", "5000", "10000"]),
            "peak_period": random.choice(["Black Friday", "end-of-month batch", "market open"]),
            "cpu": random.choice(["85", "92", "98"]),
            "service_name": random.choice(["order-service", "auth-service", "data-pipeline", "notification-service"]),
            "interval": random.choice(["24 hours", "48 hours", "7 days"]),
            "loss_rate": random.choice(["0.5", "2", "5", "10"]),
            "source": random.choice(["application server", "database cluster", "edge gateway"]),
            "destination": random.choice(["API gateway", "monitoring server", "cloud endpoint"]),
            "cloud_provider": random.choice(["AWS", "Azure", "GCP"]),
            "service": random.choice(["Lambda", "RDS", "S3", "EKS", "Functions", "Cosmos DB"]),
            "error_code": random.choice(["503", "429", "500", "timeout"]),
            "device_count": random.choice(["50", "200", "500"]),
            "network_type": random.choice(["Ethernet/IP", "PROFINET", "Modbus TCP", "EtherCAT"]),
        }

        problem = _fill_template(template["problem"], params)
        symptoms = [_fill_template(s, params) if "{" in s else s for s in template["symptoms"]]
        causes = template["possible_causes"]
        tests = template["tests"]
        preventive = template["preventive_action"]

        record = _base_metadata(domain=cat if cat in DOMAINS else random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="failure_analysis")
        record.update({
            "category": cat,
            "problem": problem,
            "symptoms": symptoms,
            "possible_causes": causes,
            "probability_ranking": {c: round(random.uniform(0.05, 0.50), 2) for c in causes},
            "diagnostic_tests": tests,
            "diagnosis": random.choice(causes),
            "recommended_fix": f"Address {random.choice(causes)} by performing {random.choice(tests)}",
            "preventive_action": preventive,
            "tags": [cat, "failure_analysis"],
        })
        records.append(record)
    return records


def generate_root_cause_analysis(count: int) -> List[Dict[str, Any]]:
    """Generate root cause analysis training records."""
    records = []
    for _ in range(count):
        system = random.choice(SYSTEM_TYPES)
        symptom = random.choice(["performance degradation", "intermittent failures", "data corruption",
                                  "security breach", "compliance violation", "resource exhaustion",
                                  "communication timeout", "sensor drift", "calibration loss"])
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="root_cause_analysis")
        record.update({
            "system": system,
            "incident_description": f"{symptom.title()} observed in {system}",
            "rca_method": random.choice(["5 Whys", "Fishbone (Ishikawa)", "Fault Tree Analysis", "Failure Mode Effects Analysis (FMEA)",
                                          "Kepner-Tregoe", "Change Analysis", "Barrier Analysis"]),
            "contributing_factors": _pick(["human error", "design flaw", "environmental condition", "component wear",
                                           "process deviation", "software bug", "configuration change",
                                           "vendor issue", "inadequate maintenance", "training gap"], 3),
            "root_cause": f"Primary root cause: {random.choice(['inadequate process', 'component degradation', 'design limitation', 'human error', 'configuration error'])}",
            "corrective_actions": _pick(["update procedure", "replace component", "add monitoring", "retrain staff",
                                         "design modification", "add redundancy", "update configuration management",
                                         "vendor engagement", "add automated checks"], 3),
            "preventive_actions": _pick(["periodic review cycle", "predictive monitoring", "design standard update",
                                          "training program enhancement", "automated validation"], 2),
            "tags": ["rca", "root_cause"],
        })
        records.append(record)
    return records


def generate_standards(count: int) -> List[Dict[str, Any]]:
    """Generate standards knowledge training records."""
    records = []
    std_keys = list(STANDARDS_REGISTRY.keys())
    for _ in range(count):
        sk = random.choice(std_keys)
        std = STANDARDS_REGISTRY[sk]

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="standards_knowledge")
        record.update({
            "standard_id": std["name"],
            "full_name": std.get("full_name", std["name"]),
            "scope": std.get("scope", ""),
            "architecture_impact": std.get("architecture_impact", ""),
            "when_to_apply": f"Apply {std['name']} when designing systems that require {std.get('scope', 'compliance')}",
            "key_details": {k: v for k, v in std.items() if k not in ("name", "full_name", "scope", "architecture_impact")},
            "tags": [sk, "standards"],
        })
        records.append(record)
    return records


def generate_best_practices(count: int) -> List[Dict[str, Any]]:
    """Generate best practices training records."""
    records = []
    practices = [
        ("API Design", ["Use nouns for resources", "Version your APIs", "Implement rate limiting", "Return proper HTTP status codes", "Use pagination for collections"]),
        ("Database Design", ["Normalize to 3NF minimum", "Index frequently queried columns", "Use connection pooling", "Implement read replicas for read-heavy workloads", "Regular backup testing"]),
        ("Security", ["Principle of least privilege", "Defense in depth", "Encrypt at rest and in transit", "Rotate secrets regularly", "Regular vulnerability scanning"]),
        ("Monitoring", ["Define SLIs and SLOs", "Alert on symptoms not causes", "Implement distributed tracing", "Log structured data (JSON)", "Dashboard per service"]),
        ("CI/CD", ["Trunk-based development", "Automate everything", "Fast feedback loops", "Immutable artifacts", "Blue-green or canary deployments"]),
        ("Microservices", ["Single responsibility per service", "API-first design", "Implement circuit breakers", "Use saga pattern for distributed transactions", "Containerize everything"]),
        ("IoT Architecture", ["Edge processing for latency-critical data", "Store-and-forward for connectivity gaps", "Secure device provisioning", "OTA firmware updates", "Topic hierarchy design"]),
        ("Mechanical Maintenance", ["Condition-based maintenance over time-based", "Vibration analysis trending", "Oil analysis program", "Alignment verification after installation", "Root cause analysis for recurring failures"]),
        ("Disaster Recovery", ["Document RTO and RPO", "Test recovery procedures quarterly", "Automate failover", "Geographic redundancy", "Data replication verification"]),
        ("Code Review", ["Focus on design over style", "Automate linting", "Review for security implications", "Check error handling paths", "Verify test coverage"]),
    ]
    for _ in range(count):
        category, tips = random.choice(practices)
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="best_practices")
        record.update({
            "category": category,
            "practices": tips,
            "context": f"Best practices for {category} in {random.choice(SYSTEM_TYPES)}",
            "tags": [category.lower().replace(" ", "_"), "best_practices"],
        })
        records.append(record)
    return records


def generate_company_knowledge(count: int) -> List[Dict[str, Any]]:
    """Generate company knowledge ingestion records (simulated document metadata)."""
    records = []
    doc_formats = ["markdown", "pdf", "docx", "pptx", "csv", "xlsx", "code", "image", "email"]
    doc_categories = ["architecture_diagram", "meeting_notes", "specification", "lessons_learned",
                       "engineering_decision", "design_review", "incident_report", "project_retrospective",
                       "vendor_evaluation", "training_material", "SOP", "compliance_audit"]
    for _ in range(count):
        doc_format = random.choice(doc_formats)
        doc_category = random.choice(doc_categories)
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="company_knowledge")
        record.update({
            "document_format": doc_format,
            "document_category": doc_category,
            "title": f"{doc_category.replace('_', ' ').title()} - {random.choice(SYSTEM_TYPES)}",
            "author": f"engineer_{random.randint(1, 50)}@company.com",
            "department": random.choice(["engineering", "operations", "quality", "IT", "maintenance", "R&D"]),
            "project": f"PRJ-{random.randint(1000, 9999)}",
            "summary": f"Document covering {doc_category.replace('_', ' ')} for {random.choice(USE_CASES)}",
            "extracted_entities": _pick(["technology", "standard", "vendor", "metric", "risk", "decision"], 3),
            "ingestion_status": random.choice(["pending", "processed", "indexed", "verified"]),
            "tags": [doc_format, doc_category, "knowledge"],
        })
        records.append(record)
    return records


def generate_learning_memory(count: int) -> List[Dict[str, Any]]:
    """Generate learning memory records (approved solution outcomes)."""
    records = []
    for _ in range(count):
        system = random.choice(SYSTEM_TYPES)
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="learning_memory")
        record.update({
            "problem": f"Implement {random.choice(INTENT_ADJECTIVES)} {system}",
            "blueprint_id": str(uuid.uuid4()),
            "documents_generated": _pick(list(DOCUMENT_SPECS.keys()), 3),
            "diagrams_generated": _pick(list(DIAGRAM_TYPES.keys()), 3),
            "engineer_feedback": random.choice(["Excellent solution, implemented as-is",
                                                 "Good foundation, minor adjustments needed for database schema",
                                                 "Architecture pattern well-suited, added custom monitoring",
                                                 "Security section needed expansion for compliance requirements",
                                                 "Tech stack recommendations aligned with team expertise"]),
            "production_outcome": random.choice(["deployed_successfully", "deployed_with_modifications",
                                                  "partially_implemented", "deferred", "rejected"]),
            "success_score": round(random.uniform(0.60, 0.99), 2),
            "lessons_learned": _pick(["Start with monitoring before features", "Invest in CI/CD early",
                                       "Database schema decisions are hard to reverse", "Security cannot be bolted on",
                                       "Stakeholder alignment is critical", "Prototype before committing to architecture",
                                       "Document assumptions explicitly", "Test with production-like data volumes"], 2),
            "tags": ["learning", "memory"],
        })
        records.append(record)
    return records


def generate_feedback_learning(count: int) -> List[Dict[str, Any]]:
    """Generate feedback learning records (continuous improvement signals)."""
    records = []
    for _ in range(count):
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="feedback_learning")
        record.update({
            "original_solution_id": str(uuid.uuid4()),
            "feedback_type": random.choice(["correction", "enhancement", "validation", "rejection"]),
            "feedback_source": random.choice(["senior_engineer", "architect", "devops_lead", "security_team",
                                               "production_incident", "code_review", "audit_finding"]),
            "original_recommendation": f"Use {random.choice(TECH_STACK_OPTIONS['backend_framework'])} with {random.choice(TECH_STACK_OPTIONS['database_primary'])}",
            "feedback_detail": random.choice([
                "PostgreSQL was the right choice but we needed partitioning from day one",
                "The microservices split was premature for our team size; modular monolith would have been faster",
                "Kafka was overkill for our volume; RabbitMQ would have sufficed",
                "The security section underestimated compliance requirements for our industry",
                "Monitoring should have been prioritized in Phase 1, not Phase 3",
                "The API versioning strategy saved us during the mobile app migration",
                "Container orchestration choice was validated by our scaling needs",
            ]),
            "adjustment_applied": random.choice([True, False]),
            "impact_score": round(random.uniform(0.1, 1.0), 2),
            "tags": ["feedback", "learning"],
        })
        records.append(record)
    return records


def generate_octagonal_mapping(count: int) -> List[Dict[str, Any]]:
    """Generate octagonal cognitive pipeline mapping records."""
    records = []
    for _ in range(count):
        use_case = random.choice(USE_CASES)
        system = random.choice(SYSTEM_TYPES)

        stages_mapping = {}
        for stage in OCTAGONAL_STAGES:
            stages_mapping[stage["stage"]] = {
                "purpose": stage["purpose"],
                "outputs": stage["outputs"],
                "input_context": f"Process '{use_case}' through {stage['stage']} stage for {system}",
            }

        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="octagonal_mapping")
        record.update({
            "input_request": f"Design {system} for {use_case}",
            "stages": stages_mapping,
            "expected_final_output": "Complete solution blueprint with architecture, diagrams, and documentation",
            "tags": ["octagonal", "pipeline"],
        })
        records.append(record)
    return records


def generate_evaluation(count: int) -> List[Dict[str, Any]]:
    """Generate evaluation / benchmark records for regression testing."""
    records = []
    for _ in range(count):
        system = random.choice(SYSTEM_TYPES)
        record = _base_metadata(domain=random.choice(list(DOMAINS.keys())), industry=random.choice(INDUSTRIES), intent="evaluation")
        record.update({
            "test_input": f"Design a {random.choice(INTENT_ADJECTIVES)} {system} for {random.choice(USE_CASES)}",
            "expected_intent": random.choice(INTENT_TYPES),
            "expected_domain": random.choice(list(DOMAINS.keys())),
            "expected_industry": random.choice(INDUSTRIES),
            "expected_sections": _pick(["Executive Summary", "Architecture", "Technology Stack",
                                        "Data Model", "API Design", "Security", "Deployment",
                                        "Testing", "Monitoring", "Roadmap", "Risks"], 5),
            "minimum_diagram_count": random.randint(2, 6),
            "minimum_confidence": round(random.uniform(0.75, 0.95), 2),
            "evaluation_criteria": _pick(["completeness", "consistency", "standards_compliance",
                                           "domain_relevance", "actionability", "no_placeholders",
                                           "no_internal_leakage", "proper_formatting"], 4),
            "tags": ["evaluation", "benchmark"],
        })
        records.append(record)
    return records


# =========================================================================
#  GENERATOR REGISTRY — Maps dataset IDs to their generator functions
# =========================================================================

DATASET_GENERATORS: Dict[str, Callable[[int], List[Dict[str, Any]]]] = {
    "01_intent_detection": generate_intent_detection,
    "02_domain_classification": generate_domain_classification,
    "03_industry_classification": generate_industry_classification,
    "04_problem_classification": generate_problem_classification,
    "05_usecase_expansion": generate_usecase_expansion,
    "06_requirement_extraction": generate_requirement_extraction,
    "07_solution_blueprints": generate_solution_blueprints,
    "08_architecture_patterns": generate_architecture_patterns,
    "09_diagram_generation": generate_diagram_generation,
    "10_document_generation": generate_document_generation,
    "11_engineering_reasoning": generate_engineering_reasoning,
    "12_aiot": generate_aiot,
    "13_mechanical": generate_mechanical,
    "14_electrical": generate_electrical,
    "15_cloud": generate_cloud,
    "16_networking": generate_networking,
    "17_database": generate_database,
    "18_security": generate_security,
    "19_backend": generate_backend,
    "20_frontend": generate_frontend,
    "21_api_design": generate_api_design,
    "22_failure_analysis": generate_failure_analysis,
    "23_root_cause_analysis": generate_root_cause_analysis,
    "24_standards": generate_standards,
    "25_best_practices": generate_best_practices,
    "26_company_knowledge": generate_company_knowledge,
    "27_learning_memory": generate_learning_memory,
    "28_feedback_learning": generate_feedback_learning,
    "29_octagonal_mapping": generate_octagonal_mapping,
    "30_evaluation": generate_evaluation,
}

ALL_DATASET_IDS = list(DATASET_GENERATORS.keys())
