# Fraud Rule Engine

A real-time fraud detection system that processes transaction events, applies ML-based fraud prediction, and stores results in a SQLite database. The system supports two interaction modes.

## Overview

The application can be interacted with in **two ways**:

### Async Flow (Kafka Streaming)
- **Producer** → **Kafka** → **Consumer** → **Predictor** → **SQLite**
- Transactions stream through Kafka for real-time processing
- Consumer directly calls the ML predictor and persists results to SQLite

### Sync Flow (HTTP REST API)
- **HTTP Client** → **FastAPI** → **Predictor** → **SQLite**
- On-demand fraud detection via REST endpoints
- FastAPI directly calls the ML predictor and persists/queries SQLite

Both flows share the same:
- **XGBoost ML Model** for fraud prediction
- **SQLite Database** for persistence and retrieval

## Project Structure

```
Fraud-Rule-Engine/
├── app/                          # Main application package
│   ├── main.py                   # FastAPI application with endpoints
│   ├── models/
│   │   └── model.py              # Pydantic models (Transaction, TransactionData)
│   ├── services/
│   │   ├── predictor.py          # ML model loading and prediction logic
│   │   └── prediction_store.py   # SQLite database operations
│   └── fraud_detection/
│       └── best_fraud_model.pkl  # Pre-trained XGBoost fraud model
├── fraud_detection_model/        # Model training notebooks/scripts
│   ├── fraud_detection.ipynb
│   └── fraud_detection.py
├── tests/                        # Test suite
│   └── test_database_interactions.py
├── consumer.py                   # Kafka consumer - processes transactions
├── producer.py                   # Kafka producer - generates test transactions
├── docker-compose.yml            # Multi-container Docker setup
├── Dockerfile                    # Application container definition
├── requirements.txt              # Python dependencies
└── pyproject.toml                # Project configuration
```

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- uv or pip (for dependency management)

## Running the Service

### With Docker (Recommended)

Start all services (Kafka, API, Producer, Consumer):

```bash
docker compose up --build
```

This starts:
- **broker**: Apache Kafka on port `29092`
- **api**: FastAPI server on port `8000`
- **producer**: Generates and publishes test transactions
- **consumer**: Processes transactions and stores predictions

### Scale Transaction Volume

Generate more transactions without rebuilding:

```bash
docker compose run --rm -e NUM_TRANSACTIONS=500 producer
```

### Monitor Kafka Messages

```bash
docker exec broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:29092 \
  --topic transactions --from-beginning
```

## API Endpoints

Once running, access the API at `http://localhost:8000`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/detect` | Submit a transaction for fraud detection |
| `GET` | `/detect` | Retrieve all prediction results |
| `GET` | `/detect/{transaction_id}` | Get prediction by transaction ID |

### Interactive API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Example Request

```bash
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "transaction": {
      "transaction_id": "txn-001",
      "account_id": "CAPITEC123456",
      "amount": 5000.00,
      "transaction_type": "DEBIT",
      "merchant_id": "MERCHANT_001",
      "timestamp": "2026-03-04T14:30:00",
      "description": "Online purchase"
    },
    "metadata": {
      "merchant_name": "Crypto Exchange",
      "merchant_category": "Cryptocurrency",
      "location_mismatch": true,
      "foreign_transaction": true,
      "velocity_last_24h": 15,
      "cardholder_age": 25,
      "device_trust_score": 30
    }
  }'
```

## Local Development

### Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate.ps1

# Install dependencies
uv pip install -r requirements.txt
```

### Run API Locally

```bash
uvicorn app.main:app --reload --port 8000
```

### Run Tests

```bash
pytest tests/ -v
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:29092` | Kafka broker address |
| `KAFKA_TOPIC` | `transactions` | Topic for transaction events |
| `KAFKA_GROUP_ID` | `fraud-detection-group` | Consumer group ID |
| `NUM_TRANSACTIONS` | `100` | Number of transactions to generate |

## Architecture

See [architecture.drawio](architecture.drawio) for the high-level system architecture diagram.