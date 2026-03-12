"""
Kafka Producer and Consumer helpers for RiskIntelligenceEngine.
Wraps confluent-kafka with JSON serialization and structured logging.
"""
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


# ─── Topic Definitions ────────────────────────────────────────────────────────

TOPICS = {
    "CLIENT_ONBOARDED": "client_onboarded",
    "TRANSACTION_EVENT": "transaction_event",
    "KYC_UPDATED": "kyc_updated",
    "RISK_SCORE_GENERATED": "risk_score_generated",
    "SUSPICIOUS_ACTIVITY": "suspicious_activity",
    "AUDIT_LOG": "audit_log",
}


def default_serializer(obj: Any) -> str:
    """JSON serializer that handles datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ─── Producer ────────────────────────────────────────────────────────────────

class AMLProducer:
    """Thread-safe Kafka producer for AML events."""

    def __init__(self, bootstrap_servers: str):
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "client.id": "aml-producer",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 300,
            "linger.ms": 5,
            "compression.type": "snappy",
        })

    def produce(
        self,
        topic: str,
        key: str,
        value: Dict[str, Any],
        on_delivery: Optional[Callable] = None,
    ) -> None:
        """Produce a JSON message to a Kafka topic."""
        try:
            payload = json.dumps(value, default=default_serializer).encode("utf-8")
            self._producer.produce(
                topic=topic,
                key=key.encode("utf-8"),
                value=payload,
                on_delivery=on_delivery or self._default_delivery_report,
            )
            self._producer.poll(0)
            logger.debug(f"Produced message to topic={topic} key={key}")
        except KafkaException as e:
            logger.error(f"Failed to produce message: {e}")
            raise

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout=timeout)

    @staticmethod
    def _default_delivery_report(err, msg):
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")


# ─── Consumer ────────────────────────────────────────────────────────────────

class AMLConsumer:
    """Kafka consumer for AML microservices."""

    def __init__(self, bootstrap_servers: str, group_id: str, topics: list[str]):
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
        })
        self._consumer.subscribe(topics)
        self._running = False

    def consume(self, handler: Callable[[Dict[str, Any]], None], poll_timeout: float = 1.0) -> None:
        """Consume messages and invoke handler for each."""
        self._running = True
        logger.info("Consumer started")
        try:
            while self._running:
                msg = self._consumer.poll(poll_timeout)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                    handler(event)
                    self._consumer.commit(msg)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except Exception as e:
                    logger.error(f"Handler error: {e}")
        finally:
            self._consumer.close()
            logger.info("Consumer stopped")

    def stop(self) -> None:
        self._running = False


# ─── Topic Admin ─────────────────────────────────────────────────────────────

def ensure_topics(bootstrap_servers: str, num_partitions: int = 3, replication_factor: int = 1) -> None:
    """Create Kafka topics if they don't exist."""
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    new_topics = [
        NewTopic(topic, num_partitions=num_partitions, replication_factor=replication_factor)
        for topic in TOPICS.values()
    ]
    futures = admin.create_topics(new_topics)
    for topic, future in futures.items():
        try:
            future.result()
            logger.info(f"Topic '{topic}' created")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug(f"Topic '{topic}' already exists")
            else:
                logger.warning(f"Topic '{topic}' creation failed: {e}")
