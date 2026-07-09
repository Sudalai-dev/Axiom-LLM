"""
OCIF Rate Limiter — Layer 2.

Implements a token-bucket rate limiting policy per tenant. Enforces 
60 requests/min for standard tiers and 600 requests/min for enterprise.
Uses Redis key storage, falling back to a thread-safe in-memory cache for dev.

Traces to:
  - Document 10 (API Specification) Section 9: Rate Limiting
  - Document 9 (Database Design) Section 6: Redis Design (ratelimit key patterns)
"""

import logging
import time
from threading import Lock
from typing import Dict, Tuple

from core.config import settings
from core.exceptions import RateLimitExceededError

logger = logging.getLogger("AxiomRateLimiter")


class RateLimiter:
    """
    Token Bucket Rate Limiter.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(RateLimiter, cls).__new__(cls, *args, **kwargs)
                cls._instance._init_limiter()
            return cls._instance

    def _init_limiter(self) -> None:
        self.redis_client = None
        self.redis_enabled = False
        
        # Local in-memory fallback (tenant_id -> (tokens, last_refill_timestamp))
        self.local_buckets: Dict[str, Tuple[float, float]] = {}
        self.local_lock = Lock()

        # Load redis if configured
        if settings.redis.host:
            try:
                import redis
                # Synchronous client pool is thread-safe
                self.redis_client = redis.Redis(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    password=settings.redis.password,
                    decode_responses=True
                )
                self.redis_client.ping()
                self.redis_enabled = True
                logger.info(f"Redis rate limiter client active on: {settings.redis.host}:{settings.redis.port}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory rate limiting.")

    def check_rate_limit(self, tenant_id: str, tier: str) -> int:
        """
        Validates rate limit for the given tenant and tier.
        Returns the number of remaining requests in the current window.
        Raises RateLimitExceededError if limit is reached.
        """
        # Determine capacity based on tier per Doc 10 Section 9
        if tier.lower() == "enterprise":
            capacity = settings.rate_limit.enterprise_requests_per_minute
        else:
            capacity = settings.rate_limit.standard_requests_per_minute

        refill_rate = capacity / 60.0  # tokens per second

        if self.redis_enabled and self.redis_client:
            return self._check_redis(tenant_id, capacity, refill_rate)
        else:
            return self._check_local(tenant_id, capacity, refill_rate)

    def _check_redis(self, tenant_id: str, capacity: int, refill_rate: float) -> int:
        """
        Evaluates token bucket policy inside Redis using a transaction or Lua script.
        To avoid complex script compilation, we use standard keys:
        - ratelimit:{tenant_id}:tokens (float)
        - ratelimit:{tenant_id}:last_update (float)
        """
        tokens_key = f"ratelimit:{tenant_id}:tokens"
        time_key = f"ratelimit:{tenant_id}:last_update"
        
        pipe = self.redis_client.pipeline()
        try:
            now = time.time()
            pipe.get(tokens_key)
            pipe.get(time_key)
            tokens_val, last_update_val = pipe.execute()
            
            last_update = float(last_update_val) if last_update_val else now
            tokens = float(tokens_val) if tokens_val is not None else float(capacity)
            
            # Refill tokens based on elapsed time
            elapsed = now - last_update
            tokens = min(float(capacity), tokens + (elapsed * refill_rate))
            
            if tokens < 1.0:
                # Calculate time until next token is available
                wait_time = int((1.0 - tokens) / refill_rate)
                raise RateLimitExceededError(
                    detail=f"Rate limit exceeded for tenant '{tenant_id}'. Capacity: {capacity}/min.",
                    retry_after_seconds=max(1, wait_time)
                )
            
            # Consume 1 token
            tokens -= 1.0
            
            # Save state with TTL to prevent leaks
            pipe.setex(tokens_key, 60, tokens)
            pipe.setex(time_key, 60, now)
            pipe.execute()
            
            return int(tokens)
        except RateLimitExceededError:
            raise
        except Exception as e:
            logger.error(f"Redis rate limiter transaction failure: {e}. Defaulting to allow.")
            return capacity

    def _check_local(self, tenant_id: str, capacity: int, refill_rate: float) -> int:
        """
        Evaluates token bucket in local thread-safe memory dictionary.
        """
        now = time.time()
        with self.local_lock:
            bucket = self.local_buckets.get(tenant_id)
            if not bucket:
                tokens = float(capacity)
                last_update = now
            else:
                tokens, last_update = bucket
                # Refill
                elapsed = now - last_update
                tokens = min(float(capacity), tokens + (elapsed * refill_rate))

            if tokens < 1.0:
                wait_time = int((1.0 - tokens) / refill_rate)
                raise RateLimitExceededError(
                    detail=f"Rate limit exceeded for tenant '{tenant_id}'. Capacity: {capacity}/min.",
                    retry_after_seconds=max(1, wait_time)
                )

            # Consume 1 token
            tokens -= 1.0
            self.local_buckets[tenant_id] = (tokens, now)
            
            return int(tokens)


# Global singleton instance
rate_limiter = RateLimiter()
