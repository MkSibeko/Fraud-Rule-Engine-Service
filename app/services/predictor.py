"""Inference helper utilities for fraud prediction."""
from __future__ import annotations

import pickle
import random
from typing import Any

import numpy as np
from app.models.model import TransactionData
from app.services.prediction_store import PredictionResult

MODEL_ARTIFACT_PATH = "app/fraud_detection/best_fraud_model.pkl"


def load_model_artifact(model_file_name: str = MODEL_ARTIFACT_PATH) -> dict[str, Any]:
    """Load the pickled model artifact produced by the training script."""
    with open(model_file_name, "rb") as model_file:
        return pickle.load(model_file)


def _encode_merchant_category(raw_value: str, encoder) -> int:
    if raw_value in encoder.classes_:
        return int(encoder.transform([raw_value])[0])
    return -1


def transaction_data_to_model_input(data: dict[str, Any], artifact: dict[str, Any]) -> np.ndarray:
    """Convert API transaction payload into a scaled model-ready row."""

    data["merchant_category"] = _encode_merchant_category(
            str(data["merchant_category"]), artifact["merchant_category_encoder"]
        )
    data["night_transaction"] = int(data["transaction_hour"] in [0, 1, 2, 3])
    data["high_amount"] = int(data["amount"] > 900)

    ordered_features = [data[column] for column in artifact["feature_columns"]]
    model_input = np.array([ordered_features], dtype=float)

    scaler = artifact["scaler"]
    return scaler.transform(model_input)


def predict_transaction(data: dict[str, Any], artifact: dict[str, Any] | None = None) -> tuple[bool, float]:
    """Make a fraud prediction for one API transaction payload."""
    loaded_artifact = artifact or load_model_artifact()
    model_input = transaction_data_to_model_input(data, loaded_artifact)

    model = loaded_artifact["model"]
    predicted_class = int(model.predict(model_input)[0])

    fraud_probability = 0.0
    if hasattr(model, "predict_proba"):
        fraud_probability = float(model.predict_proba(model_input)[0][1])

    return (
        bool(predicted_class),
        fraud_probability,
    )


def predictor_utility(transaction_data: TransactionData, model_artifact ) -> PredictionResult:

    device_trust_score = random.randint(0, 100) \
                        if not transaction_data.metadata.device_trust_score \
                        else transaction_data.metadata.device_trust_score
    
    data: dict[str, str | float | int | bool] = {
        "transaction_id": 0,
        "amount": transaction_data.transaction.amount,
        "transaction_hour": transaction_data.transaction.timestamp.hour,
        "merchant_category": transaction_data.metadata.merchant_category,
        "foreign_transaction": transaction_data.metadata.foreign_transaction,
        "location_mismatch": transaction_data.metadata.location_mismatch,
        "device_trust_score": device_trust_score,
        "velocity_last_24h": transaction_data.metadata.velocity_last_24h,
        "cardholder_age": transaction_data.metadata.cardholder_age,
    }

    is_fraud, fraud_probability = predict_transaction(data, model_artifact)

    return PredictionResult(
        transaction_id=transaction_data.transaction.transaction_id,
        merchant_id=transaction_data.transaction.merchant_id,
        account_id=transaction_data.transaction.account_id,
        is_fraud=is_fraud,
        fraud_probability=fraud_probability,
    )