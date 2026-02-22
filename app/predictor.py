"""Inference helper utilities for fraud prediction."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

MODEL_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[1] / "fraud_detection_model" / "best_fraud_model.pkl"
)


def load_model_artifact(path: Path = MODEL_ARTIFACT_PATH) -> dict[str, Any]:
    """Load the pickled model artifact produced by the training script."""
    with path.open("rb") as model_file:
        return pickle.load(model_file)


def _encode_merchant_category(raw_value: str, encoder) -> int:
    if raw_value in encoder.classes_:
        return int(encoder.transform([raw_value])[0])
    return -1


def transaction_data_to_model_input(data: dict[str, Any], artifact: dict[str, Any]) -> np.ndarray:
    """Convert API transaction payload into a scaled model-ready row."""
    feature_values = {
        "amount": float(data["amount"]),
        "transaction_hour": int(data["transaction_hour"]),
        "merchant_category": _encode_merchant_category(
            str(data["merchant_category"]), artifact["merchant_category_encoder"]
        ),
        "foreign_transaction": int(bool(data["foreign_transaction"])),
        "location_mismatch": int(bool(data["location_mismatch"])),
        "device_trust_score": float(data["device_trust_score"]),
        "velocity_last_24h": int(data["velocity_last_24h"]),
        "cardholder_age": int(data["cardholder_age"]),
    }

    feature_values["night_transaction"] = int(feature_values["transaction_hour"] in [0, 1, 2, 3])
    feature_values["high_amount"] = int(feature_values["amount"] > 900)

    ordered_features = [feature_values[column] for column in artifact["feature_columns"]]
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
