"""Consume transactions from Kafka and predict fraud."""

import os
import json
import signal
import requests
from typing import Any
from confluent_kafka import Consumer, KafkaError, KafkaException

from app.models.model import TransactionData
from app.services.prediction_store import PredictionResult

_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
_GROUP_ID: str = os.getenv("KAFKA_GROUP_ID", "fraud-detection-group")
_TOPIC: str = os.getenv("KAFKA_TOPIC", "transactions")
_AUTO_OFFSET_RESET: str = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")
_FRAUD_URL: str = os.getenv("FRAUD_API_URL", "")

conf: dict = {
    "bootstrap.servers": _BOOTSTRAP_SERVERS,
    "group.id": _GROUP_ID,
    "auto.offset.reset": _AUTO_OFFSET_RESET,
    "enable.auto.commit": True,
}

# Global flag for graceful shutdown
running = True


def signal_handler(sig: int, frame: Any) -> None:  # noqa: ARG001
    """Handle shutdown signals gracefully."""
    global running  # noqa: PLW0603
    print("\nShutting down consumer...")
    running = False


def parse_transaction_data(message_value: bytes | None) -> dict | None:
    """Parse the Kafka message into transaction data."""
    if message_value is None:
        return None
    try:
        return json.loads(message_value.decode("utf-8"))
    except json.JSONDecodeError as e:
        print(f"Failed to parse message: {e}")
        return None


def detect_fraud(data: TransactionData):
    if not _FRAUD_URL:
        raise(Exception("Fraud API url not set"))
    
    response = requests.post(f"{_FRAUD_URL}/detect", json=data)
    
    return response.json()


def consume_transactions() -> None:
    """Consume transactions from Kafka and predict fraud."""
    global running

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create Kafka consumer
    consumer = Consumer(conf)
    consumer.subscribe([_TOPIC])
    print(f"Subscribed to topic '{_TOPIC}', waiting for messages...")

    processed_count = 0
    fraud_count = 0

    try:
        while running:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if error := msg.error():
                raise KafkaException(error)

            # Parse and process the transaction
            transaction_data = parse_transaction_data(msg.value())
            if transaction_data is None:
                continue

            transaction_data = TransactionData(transaction=transaction_data.get("transaction", {}),
                                               metadata=transaction_data.get("metadata", {}))

            prediction_result = detect_fraud(transaction_data)
            if prediction_result is None:
                continue

            # Persist the prediction result to SQLite
            try:
                processed_count += 1
                if prediction_result.is_fraud:
                    fraud_count += 1

                # Log progress
                fraud_status = "FRAUD" if prediction_result.is_fraud else "LEGITIMATE"
                print(
                    f"[{processed_count}] Transaction {prediction_result.transaction_id[:8]}... "
                    f"-> {fraud_status} (prob: {prediction_result.fraud_probability:.2%})"
                )

            except Exception as e:
                print(f"Failed to persist prediction result: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        # Clean up
        consumer.close()
        print(f"\nConsumer stopped. Processed {processed_count} transactions, {fraud_count} flagged as fraud.")


if __name__ == "__main__":
    consume_transactions()