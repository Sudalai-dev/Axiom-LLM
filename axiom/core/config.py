"""
OCIF Platform Configuration — Core Settings Management.

Centralizes all environment-driven configuration for the Enterprise AI Platform.
Loads from environment variables with secure defaults. In production, secrets
are sourced from AWS Secrets Manager / KMS (per Doc 14 Section 4).

Traces to:
  - Document 8 (System Architecture) Section 2: Deployment topology & service config
  - Document 14 (Security Design) Section 4: Secrets management
  - Document 9 (Database Design) Section 2: Connection parameters
"""

import os
import secrets
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Environment(str, Enum):
    """Deployment environments per Doc 18 Section 4."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class RateLimitTier(str, Enum):
    """Rate limit tiers per Doc 10 Section 9."""
    STANDARD = "standard"      # 60 requests/min per user
    ENTERPRISE = "enterprise"  # 600 requests/min per user (configurable)


@dataclass(frozen=True)
class DatabaseConfig:
    """Database configuration.

    Production uses PostgreSQL; local/dev and the test suite use SQLite. Set a
    single ``AXIOM_DATABASE_URL`` (e.g. ``postgresql://user:pass@host:5432/db``)
    to point at Postgres — it is honoured verbatim and the async/sync driver
    prefix is normalised automatically (asyncpg for the app, psycopg2/plain for
    Alembic). When unset, AXIOM falls back to a local SQLite file, so nothing
    external is required to run or test. The discrete OCIF_DB_* fields below are
    retained for backward compatibility but ``AXIOM_DATABASE_URL`` takes
    precedence when present."""
    host: str = "localhost"
    port: int = 5432
    name: str = "ocif_platform"
    user: str = "ocif_app"
    password: str = ""
    pool_size: int = 20
    max_overflow: int = 10
    ssl_mode: str = "prefer"
    url_override: str = ""   # AXIOM_DATABASE_URL — full URL, wins over the fields above

    @property
    def _sqlite_path(self) -> str:
        data_dir = os.getenv("AXIOM_DATA_DIR", "data")
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, "ocif_platform.db")
        # SQLAlchemy sqlite URLs need forward slashes and, for a relative
        # path, an explicit leading "./" to anchor it at the CWD.
        path = path.replace("\\", "/")
        if not os.path.isabs(path):
            path = f"./{path}"
        return path

    @staticmethod
    def _as_async(url: str) -> str:
        """Normalise any DB URL to its async driver form (asyncpg / aiosqlite)."""
        if url.startswith(("postgresql+asyncpg", "sqlite+aiosqlite")):
            return url
        if url.startswith("postgresql"):
            return url.replace("postgresql", "postgresql+asyncpg", 1)
        if url.startswith("sqlite"):
            return url.replace("sqlite", "sqlite+aiosqlite", 1)
        return url

    @staticmethod
    def _as_sync(url: str) -> str:
        """Normalise any DB URL to its sync driver form (psycopg2 / sqlite) —
        used by Alembic migrations and background/admin tasks."""
        if url.startswith("postgresql+asyncpg"):
            return url.replace("postgresql+asyncpg", "postgresql", 1)
        if url.startswith("sqlite+aiosqlite"):
            return url.replace("sqlite+aiosqlite", "sqlite", 1)
        return url

    @property
    def url(self) -> str:
        """Async SQLAlchemy URL for the FastAPI app."""
        if self.url_override:
            return self._as_async(self.url_override)
        if self.password:
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"sqlite+aiosqlite:///{self._sqlite_path}"

    @property
    def sync_url(self) -> str:
        """Synchronous URL for Alembic migrations."""
        if self.url_override:
            return self._as_sync(self.url_override)
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"sqlite:///{self._sqlite_path}"


@dataclass(frozen=True)
class RedisConfig:
    """Redis configuration for session/memory cache per Doc 9 Section 6."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    session_ttl_seconds: int = 3600
    memory_ttl_seconds: int = 1800
    cache_ttl_seconds: int = 300

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class KafkaConfig:
    """Kafka/event bus configuration per Doc 8 Section 3."""
    bootstrap_servers: str = "localhost:9092"
    consumer_group: str = "ocif-platform"
    enabled: bool = False  # In-process bus used when False


@dataclass(frozen=True)
class VectorDBConfig:
    """Vector database configuration per Doc 9 Section 5 / Doc 11."""
    provider: str = "memory"  # "pinecone" | "memory"
    api_key: str = ""
    environment: str = ""
    index_name: str = "ocif-knowledge"
    dimension: int = 1024
    metric: str = "cosine"
    similarity_threshold: float = 0.72  # Per Doc 11 Section 4.2


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration per Doc 14 Section 3."""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_seconds: int = 3600
    jwt_refresh_expiration_seconds: int = 86400
    oauth2_issuer: str = ""
    oauth2_audience: str = "ocif-platform"


@dataclass(frozen=True)
class BootstrapConfig:
    """Local bootstrap configuration (seeded admin account)."""
    admin_password: str = "admin123"          # seeded admin password (dev default)


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limiting configuration per Doc 10 Section 9."""
    standard_requests_per_minute: int = 60
    enterprise_requests_per_minute: int = 600
    window_seconds: int = 60


@dataclass(frozen=True)
class RAGConfig:
    """RAG pipeline configuration per Doc 11."""
    chunk_size_tokens: int = 500
    chunk_overlap_percent: float = 0.15
    pre_fusion_top_k: int = 20
    post_fusion_top_k: int = 8
    rrf_k: int = 60  # Reciprocal Rank Fusion constant per Doc 11 Section 4.1
    retrieval_cache_ttl_seconds: int = 300  # Per Doc 11 Section 8
    embedding_model: str = "text-embedding-3-large"


@dataclass(frozen=True)
class PolicyConfig:
    """Policy engine configuration per Doc 14 Section 6."""
    default_risk_threshold: float = 0.7
    auto_approval_max_risk: float = 0.3
    hitl_required_min_risk: float = 0.7
    max_agent_steps: int = 15  # Per Doc 13 Section 8
    fail_closed: bool = True  # INVARIANT: always True per Doc 7 Section 12


@dataclass(frozen=True)
class ObservabilityConfig:
    """Observability configuration per Doc 8 Section 6 / Doc 18 Section 8."""
    log_level: str = "INFO"
    log_format: str = "json"
    otel_endpoint: str = ""
    otel_service_name: str = "ocif-platform"
    # Alerting thresholds per Doc 18 Section 8
    latency_warning_ms: int = 2500
    latency_critical_ms: int = 3000
    error_rate_warning_pct: float = 1.0
    error_rate_critical_pct: float = 5.0


@dataclass(frozen=True)
class LLMConfig:
    """Local, self-hosted LLM configuration (Ollama / OpenAI-compatible).

    AXIOM stays deterministic by default: the LLM is an OPT-IN enhancement
    layer that adds dynamic prose + a visible reasoning ("thinking") stream on
    top of the deterministic SolutionSynthesizer, which always runs first and
    guarantees a complete, contract-valid document. If the LLM is disabled,
    unreachable, or returns junk, the platform silently keeps the deterministic
    output — it never degrades. No external/cloud provider is involved: this
    talks only to a model running on the operator's own machine.
    """
    enabled: bool = False                       # opt-in via OCIF_LLM_ENABLED=true
    base_url: str = "http://localhost:11434"    # Ollama default (native API)
    model: str = "qwen2.5:3b"                   # Apache-2.0, commercially sellable
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout_seconds: int = 60
    # AXIOM's grounding prompts are long; Ollama defaults to a 2048-token context
    # which would silently truncate them. Ask for a larger window so the whole
    # request context reaches the model.
    context_tokens: int = 8192


@dataclass(frozen=True)
class OutputConfig:
    """User-facing output shape. AXIOM is a diagram generator: the primary
    response is the 8-diagram Blueprint. The legacy prose solution document is
    retained but returned only when explicitly enabled — kept behind a flag
    (reversible) rather than deleted."""
    prose_enabled: bool = False   # OCIF_PROSE_ENABLED=true → also return prose body


class PlatformSettings:
    """
    Root configuration aggregator for the OCIF Enterprise AI Platform.

    Reads all configuration from environment variables, providing secure
    defaults for local development. In production, environment variables
    are injected from AWS Secrets Manager via Kubernetes secret mounts.
    """

    def __init__(self) -> None:
        self.environment = Environment(
            os.getenv("OCIF_ENVIRONMENT", Environment.DEVELOPMENT.value)
        )
        self.platform_name = os.getenv("OCIF_PLATFORM_NAME", "OCIF Enterprise AI Platform")
        self.api_version = "v1"
        self.cors_origins = os.getenv("OCIF_CORS_ORIGINS", "http://localhost:3000").split(",")

        self.database = DatabaseConfig(
            host=os.getenv("OCIF_DB_HOST", "localhost"),
            port=int(os.getenv("OCIF_DB_PORT", "5432")),
            name=os.getenv("OCIF_DB_NAME", "ocif_platform"),
            user=os.getenv("OCIF_DB_USER", "ocif_app"),
            password=os.getenv("OCIF_DB_PASSWORD", ""),
            pool_size=int(os.getenv("OCIF_DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("OCIF_DB_MAX_OVERFLOW", "10")),
            url_override=os.getenv("AXIOM_DATABASE_URL", "").strip(),
        )

        self.redis = RedisConfig(
            host=os.getenv("OCIF_REDIS_HOST", "localhost"),
            port=int(os.getenv("OCIF_REDIS_PORT", "6379")),
            password=os.getenv("OCIF_REDIS_PASSWORD", ""),
        )

        self.kafka = KafkaConfig(
            bootstrap_servers=os.getenv("OCIF_KAFKA_BROKERS", "localhost:9092"),
            enabled=os.getenv("OCIF_KAFKA_ENABLED", "false").lower() == "true",
        )

        self.vector_db = VectorDBConfig(
            provider=os.getenv("OCIF_VECTOR_PROVIDER", "memory"),
            api_key=os.getenv("OCIF_PINECONE_API_KEY", ""),
            environment=os.getenv("OCIF_PINECONE_ENV", ""),
            index_name=os.getenv("OCIF_PINECONE_INDEX", "ocif-knowledge"),
            dimension=int(os.getenv("OCIF_VECTOR_DIMENSION", "1024")),
        )

        self.auth = AuthConfig(
            jwt_secret_key=self._resolve_jwt_secret(),
            jwt_algorithm=os.getenv("OCIF_JWT_ALGORITHM", "HS256"),
            jwt_expiration_seconds=int(os.getenv("OCIF_JWT_EXPIRY", "3600")),
        )

        self.bootstrap = BootstrapConfig(
            admin_password=os.getenv("OCIF_ADMIN_PASSWORD", "admin123"),
        )

        self.rate_limit = RateLimitConfig(
            standard_requests_per_minute=int(os.getenv("OCIF_RATE_LIMIT_STANDARD", "60")),
            enterprise_requests_per_minute=int(os.getenv("OCIF_RATE_LIMIT_ENTERPRISE", "600")),
        )

        self.rag = RAGConfig(
            chunk_size_tokens=int(os.getenv("OCIF_RAG_CHUNK_SIZE", "500")),
            chunk_overlap_percent=float(os.getenv("OCIF_RAG_OVERLAP", "0.15")),
            rrf_k=int(os.getenv("OCIF_RAG_RRF_K", "60")),
        )

        self.policy = PolicyConfig(
            default_risk_threshold=float(os.getenv("OCIF_POLICY_RISK_THRESHOLD", "0.7")),
            auto_approval_max_risk=float(os.getenv("OCIF_POLICY_AUTO_APPROVE_MAX", "0.3")),
            max_agent_steps=int(os.getenv("OCIF_MAX_AGENT_STEPS", "15")),
        )

        self.observability = ObservabilityConfig(
            log_level=os.getenv("OCIF_LOG_LEVEL", "INFO"),
            otel_endpoint=os.getenv("OCIF_OTEL_ENDPOINT", ""),
            otel_service_name=os.getenv("OCIF_OTEL_SERVICE_NAME", "ocif-platform"),
        )

        self.output = OutputConfig(
            prose_enabled=os.getenv("OCIF_PROSE_ENABLED", "false").lower() == "true",
        )

        self.llm = LLMConfig(
            enabled=os.getenv("OCIF_LLM_ENABLED", "false").lower() == "true",
            base_url=os.getenv("OCIF_LLM_BASE_URL", "http://localhost:11434").rstrip("/"),
            model=os.getenv("OCIF_LLM_MODEL", "qwen2.5:3b"),
            temperature=float(os.getenv("OCIF_LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("OCIF_LLM_MAX_TOKENS", "1024")),
            timeout_seconds=int(os.getenv("OCIF_LLM_TIMEOUT", "60")),
            context_tokens=int(os.getenv("OCIF_LLM_CONTEXT_TOKENS", "8192")),
        )

    def _resolve_jwt_secret(self) -> str:
        """Resolves the JWT signing secret.

        A per-process random fallback (the previous behavior) silently
        invalidated every token on restart and differed across workers, so
        multi-worker deployments rejected each other's tokens. We now require
        an explicit secret in production (fail-fast) and use a STABLE, clearly
        insecure default in non-production so local dev/tests keep working
        across restarts.
        """
        secret = os.getenv("OCIF_JWT_SECRET", "")
        if secret:
            return secret
        if self.environment == Environment.PRODUCTION:
            raise RuntimeError(
                "OCIF_JWT_SECRET must be set in production. Refusing to start with "
                "an ephemeral signing key (would invalidate all tokens on restart "
                "and break multi-worker deployments)."
            )
        return "axiom-dev-insecure-jwt-secret-do-not-use-in-production"

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT


# Module-level singleton — imported as `from axiom.core.config import settings`
settings = PlatformSettings()
