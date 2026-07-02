"""
OCIF Event Bus Abstraction — Messaging & Integration Backbone.

Provides an asynchronous pub/sub messaging interface for inter-service communication.
Acts as an in-process event hub for local development, with swappable configuration
to route events via MSK Kafka in production topologies.

Traces to:
  - Document 8 (System Architecture) Section 3: Event bus and routing architecture
  - Document 9 (Database Design) Section 2: Integration Strategy (Kafka event backbone)
"""

import asyncio
import logging
from typing import Dict, Any, List, Callable, Awaitable

from axiom.core.config import settings
from axiom.core.observability import logger as obs_logger

logger = logging.getLogger("AxiomEventBus")


class EventBus:
    """
    Core Event Bus Broker.
    Routes inter-layer system event frames asynchronously.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EventBus, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_bus()
        return cls._instance

    def _init_bus(self) -> None:
        self.subscribers: Dict[str, List[Callable[[str, Dict[str, Any]], Awaitable[None]]]] = {}
        self.kafka_producer = None
        self.kafka_enabled = settings.kafka.enabled

        if self.kafka_enabled:
            try:
                # Dynamically attempt to load aiokafka to keep local dependencies light
                from aiokafka import AIOKafkaProducer
                self.kafka_producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
                logger.info(f"Kafka event bus enabled. Connecting to brokers: {settings.kafka.bootstrap_servers}")
            except ImportError:
                obs_logger.warning(
                    "aiokafka package not installed. Falling back to internal in-process event routing engine.",
                    extra_fields={"bootstrap_servers": settings.kafka.bootstrap_servers}
                )
                self.kafka_enabled = False
        else:
            logger.info("Internal in-process async event bus loaded (Kafka integration disabled).")

    async def start(self) -> None:
        """Starts the Kafka producer connection if enabled."""
        if self.kafka_enabled and self.kafka_producer:
            try:
                await self.kafka_producer.start()
                logger.info("Kafka connection started successfully.")
            except Exception as e:
                logger.error(f"Failed to start Kafka producer connection: {e}. Falling back to in-process.")
                self.kafka_enabled = False

    async def stop(self) -> None:
        """Gracefully closes active broker connections."""
        if self.kafka_enabled and self.kafka_producer:
            await self.kafka_producer.stop()
            logger.info("Kafka connection stopped.")

    async def publish(self, topic: str, key: str, payload: Dict[str, Any]) -> None:
        """
        Publishes a message to a topic.
        
        Per Document 9, correlation IDs are injected into event payloads
        before transport.
        """
        payload_serialized = payload.copy()
        
        # Ensure event contains tracing parameters
        if "correlation_id" not in payload_serialized:
            payload_serialized["correlation_id"] = key

        logger.debug(f"Publishing event to topic '{topic}' with key '{key}'")

        if self.kafka_enabled and self.kafka_producer:
            import json
            try:
                val_bytes = json.dumps(payload_serialized).encode("utf-8")
                key_bytes = key.encode("utf-8")
                await self.kafka_producer.send_and_wait(topic, value=val_bytes, key=key_bytes)
            except Exception as e:
                logger.error(f"Kafka message send failed: {e}. Routing through in-process callbacks.")
                await self._publish_local(topic, key, payload_serialized)
        else:
            await self._publish_local(topic, key, payload_serialized)

    async def _publish_local(self, topic: str, key: str, payload: Dict[str, Any]) -> None:
        """Internal asynchronous in-process router."""
        callbacks = self.subscribers.get(topic, [])
        if not callbacks:
            logger.debug(f"No local subscribers registered for topic '{topic}'")
            return

        # Execute callbacks concurrently using async tasks
        async def run_callback(cb):
            try:
                await cb(key, payload)
            except Exception as ex:
                logger.error(f"Error handling event subscriber callback on topic '{topic}': {ex}", exc_info=True)

        tasks = [asyncio.create_task(run_callback(cb)) for cb in callbacks]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(self, topic: str, callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Registers an asynchronous listener callback to a topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        logger.debug(f"Registered subscriber callback to topic '{topic}'")


# Singleton instance of the Event Bus Broker
event_bus = EventBus()
