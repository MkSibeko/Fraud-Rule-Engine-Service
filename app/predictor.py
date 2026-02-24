"""Inference helper utilities for fraud prediction."""
from __future__ import annotations

import pickle
from typing import Any

import numpy as np

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
