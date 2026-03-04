"""Tests for database interactions in both HTTP API and Kafka consumer."""
import os
import uuid
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlmodel import SQLModel, create_engine, Session, select
from fastapi.testclient import TestClient

from app.services.prediction_store import (
    PredictionResult,
    persist_prediction_result,
    get_a_prediction_result,
    get_all_prediction_results,
    init_datastore,
)
from app.models.model import TransactionData, Transaction, TransactionMetadata
from app.main import app
from consumer import parse_transaction_data, process_transaction

# Test with an in-memory SQLite database
TEST_DATABASE_URL = "sqlite:///tests/test_frauddetection.db"


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine and clean up after each test."""
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    yield engine
    # Cleanup: drop all tables and dispose engine before file removal
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def mock_model_artifact():
    """Mock the model artifact to avoid loading the actual model."""
    return MagicMock()


class TestPredictionStore:
    """Tests for the prediction_store module database operations."""

    def test_init_datastore_creates_tables(self, test_engine):
        """Test that init_datastore creates the required tables."""
        with patch("app.services.prediction_store.engine", test_engine):
            init_datastore()
            
            # Verify table exists by attempting to query
            with Session(test_engine) as session:
                results = session.exec(select(PredictionResult)).all()
                assert results == []

    def test_persist_prediction_result(self, test_engine):
        """Test persisting a single prediction result."""
        with patch("app.services.prediction_store.engine", test_engine):
            init_datastore()
            
            # Create a test prediction result
            prediction = PredictionResult(
                transaction_id=str(uuid.uuid4()),
                merchant_id="MERCHANT_1234",
                account_id="CAPITEC1234567890",
                is_fraud=True,
                fraud_probability=0.85,
            )
            
            result = persist_prediction_result(prediction)
            
            assert result.transaction_id == prediction.transaction_id
            assert result.is_fraud is True
            assert result.fraud_probability == 0.85

    def test_get_all_prediction_results(self, test_engine):
        """Test retrieving all prediction results."""
        with patch("app.services.prediction_store.engine", test_engine):
            
            init_datastore()
            
            # Persist multiple predictions
            for i in range(3):
                prediction = PredictionResult(
                    transaction_id=str(uuid.uuid4()),
                    merchant_id=f"MERCHANT_{i}",
                    account_id=f"CAPITEC{i}",
                    is_fraud=i % 2 == 0,
                    fraud_probability=0.1 * i,
                )
                persist_prediction_result(prediction)
            
            results = get_all_prediction_results()
            
            assert len(results) == 3

    def test_get_a_prediction_result(self, test_engine):
        """Test retrieving a specific prediction result by transaction_id."""
        with patch("app.services.prediction_store.engine", test_engine):

            
            init_datastore()
            
            # Create and persist a prediction
            transaction_id = str(uuid.uuid4())
            prediction = PredictionResult(
                transaction_id=transaction_id,
                merchant_id="MERCHANT_TEST",
                account_id="CAPITEC_TEST",
                is_fraud=False,
                fraud_probability=0.15,
            )
            persist_prediction_result(prediction)
            
            # Retrieve the prediction
            result = get_a_prediction_result(transaction_id)
            
            assert result is not None
            assert result.transaction_id == transaction_id
            assert result.is_fraud is False
            assert result.fraud_probability == 0.15

    def test_get_nonexistent_prediction_result(self, test_engine):
        """Test retrieving a non-existent prediction returns None."""
        with patch("app.services.prediction_store.engine", test_engine):
            init_datastore()
            
            result = get_a_prediction_result("nonexistent_id")
            
            assert result is None


class TestHTTPAPIDatabase:
    """Tests for the HTTP API database interactions."""

    @pytest.fixture
    def client(self, test_engine):
        """Create a test client with mocked database."""
        with patch("app.services.prediction_store.engine", test_engine):
            with patch("app.main.init_datastore") as mock_init:
                init_datastore()
                
                # Initialize the datastore for tests
                app.state.model_artifact = None
                
                yield TestClient(app)

    def test_detect_endpoint_persists_to_database(self, client, test_engine):
        """Test that POST /detect persists prediction to database."""
        with patch("app.services.prediction_store.engine", test_engine):
            with patch("app.main.load_model_artifact") as mock_load:
                with patch("app.main.predictor_utility") as mock_predictor:
                    # Setup mock
                    mock_load.return_value = {}
                    transaction_id = str(uuid.uuid4())
                    mock_predictor.return_value = PredictionResult(
                        transaction_id=transaction_id,
                        merchant_id="MERCHANT_API",
                        account_id="CAPITEC_API",
                        is_fraud=True,
                        fraud_probability=0.92,
                    )
                    
                    # Make request
                    response = client.post(
                        "/detect",
                        json={
                            "transaction": {
                                "transaction_id": transaction_id,
                                "account_id": "CAPITEC_API",
                                "amount": 1500.0,
                                "transaction_type": "DEBIT",
                                "merchant_id": "MERCHANT_API",
                                "timestamp": datetime.now().isoformat(),
                                "description": "Test transaction",
                            },
                            "metadata": {
                                "merchant_name": "Test Merchant",
                                "merchant_category": "Grocery",
                                "location_mismatch": False,
                                "foreign_transaction": False,
                                "velocity_last_24h": 5,
                                "cardholder_age": 35,
                                "device_trust_score": 80,
                            },
                        },
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["transaction_id"] == transaction_id
                    assert data["is_fraud"] is True
                    
                    # Verify it was persisted
                    results = get_all_prediction_results()
                    assert len(results) >= 1

    def test_get_all_predictions_endpoint(self, client, test_engine):
        """Test that GET /detect retrieves all predictions from database."""
        with patch("app.services.prediction_store.engine", test_engine):
            # Pre-populate database
            for i in range(2):
                prediction = PredictionResult(
                    transaction_id=str(uuid.uuid4()),
                    merchant_id=f"MERCHANT_{i}",
                    account_id=f"CAPITEC{i}",
                    is_fraud=False,
                    fraud_probability=0.1,
                )
                persist_prediction_result(prediction)
            
            response = client.get("/detect")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) >= 2


class TestKafkaConsumerDatabase:
    """Tests for the Kafka consumer database interactions."""

    def test_consumer_persists_prediction_to_database(self, test_engine):
        """Test that the consumer correctly persists predictions."""
        with patch("app.services.prediction_store.engine", test_engine):
            init_datastore()
            
            # Simulate what the consumer does
            prediction = PredictionResult(
                transaction_id=str(uuid.uuid4()),
                merchant_id="MERCHANT_KAFKA",
                account_id="CAPITEC_KAFKA",
                is_fraud=True,
                fraud_probability=0.75,
            )
            
            persist_prediction_result(prediction)
            
            results = get_all_prediction_results()
            assert len(results) == 1
            assert results[0].is_fraud is True
            assert results[0].fraud_probability == 0.75

    def test_consumer_process_transaction_integration(self, test_engine):
        """Test the full consumer transaction processing flow."""
        with patch("app.services.prediction_store.engine", test_engine):
            with patch("consumer.load_model_artifact") as mock_load:
                init_datastore()
                
                # Create mock model artifact
                mock_artifact = MagicMock()
                mock_load.return_value = mock_artifact
                
                # Create test transaction data
                transaction_data = TransactionData(
                    transaction=Transaction(
                        transaction_id=str(uuid.uuid4()),
                        account_id="CAPITEC_CONSUMER",
                        amount=500.0,
                        transaction_type="DEBIT",
                        merchant_id="MERCHANT_CONSUMER",
                        timestamp=datetime.now(),
                        description="Consumer test",
                    ),
                    metadata=TransactionMetadata(
                        merchant_name="Test",
                        merchant_category="Grocery",
                        location_mismatch=False,
                        foreign_transaction=False,
                        velocity_last_24h=3,
                        cardholder_age=30,
                        device_trust_score=90,
                    ),
                )
                
                with patch("consumer.predictor_utility") as mock_predictor:
                    mock_predictor.return_value = PredictionResult(
                        transaction_id=transaction_data.transaction.transaction_id,
                        merchant_id=transaction_data.transaction.merchant_id,
                        account_id=transaction_data.transaction.account_id,
                        is_fraud=False,
                        fraud_probability=0.05,
                    )
                    
                    result = process_transaction(transaction_data, mock_artifact)
                    
                    assert result is not None
                    assert result.is_fraud is False

    def test_parse_transaction_data_valid_json(self):
        """Test parsing valid JSON from Kafka message."""
        valid_json = b'{"transaction": {"transaction_id": "123"}, "metadata": {}}'
        result = parse_transaction_data(valid_json)
        
        assert result is not None
        assert "transaction" in result

    def test_parse_transaction_data_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        invalid_json = b'not valid json'
        result = parse_transaction_data(invalid_json)
        
        assert result is None

    def test_parse_transaction_data_none_input(self):
        """Test parsing None input returns None."""

        
        result = parse_transaction_data(None)
        
        assert result is None


class TestDatabaseEdgeCases:
    """Tests for edge cases in database operations."""

    def test_duplicate_transaction_id_handling(self, test_engine):
        """Test behavior when inserting duplicate transaction IDs."""
        with patch("app.services.prediction_store.engine", test_engine):
    
            init_datastore()
            
            transaction_id = str(uuid.uuid4())
            
            # First insert
            prediction1 = PredictionResult(
                transaction_id=transaction_id,
                merchant_id="MERCHANT_1",
                account_id="CAPITEC_1",
                is_fraud=False,
                fraud_probability=0.1,
            )
            persist_prediction_result(prediction1)
            
            # Second insert with same ID should raise an error
            prediction2 = PredictionResult(
                transaction_id=transaction_id,
                merchant_id="MERCHANT_2",
                account_id="CAPITEC_2",
                is_fraud=True,
                fraud_probability=0.9,
            )
            
            with pytest.raises(Exception):
                persist_prediction_result(prediction2)

    def test_high_fraud_probability_persistence(self, test_engine):
        """Test persisting predictions with edge probability values."""
        with patch("app.services.prediction_store.engine", test_engine):
            
            init_datastore()
            
            # Test with probability = 1.0
            transaction_id = str(uuid.uuid4())
            prediction = PredictionResult(
                transaction_id=transaction_id,
                merchant_id="MERCHANT_HIGH",
                account_id="CAPITEC_HIGH",
                is_fraud=True,
                fraud_probability=1.0,
            )
            persist_prediction_result(prediction)
            
            result = get_a_prediction_result(transaction_id)
            assert result is not None
            assert result.fraud_probability == 1.0

    def test_zero_fraud_probability_persistence(self, test_engine):
        """Test persisting predictions with zero probability."""
        with patch("app.services.prediction_store.engine", test_engine):
            
            init_datastore()
            
            transaction_id = str(uuid.uuid4())
            prediction = PredictionResult(
                transaction_id=transaction_id,
                merchant_id="MERCHANT_ZERO",
                account_id="CAPITEC_ZERO",
                is_fraud=False,
                fraud_probability=0.0,
            )
            persist_prediction_result(prediction)
            
            result = get_a_prediction_result(transaction_id)
            assert result is not None
            assert result.fraud_probability == 0.0
