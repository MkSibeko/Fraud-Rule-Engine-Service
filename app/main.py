"""Fraud Rule Engine"""
import random
import logging as log
from contextlib import asynccontextmanager

from fastapi import FastAPI
from .models.model import TransactionData
from .services.predictor import load_model_artifact, predictor_utility
from.services.prediction_store import PredictionResult, persist_prediction_result, init_datastore, get_all_prediction_results, get_a_prediction_result


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    init_datastore()
    yield


app = FastAPI(lifespan=lifespan)
app.state.model_artifact = None

@app.post("/detect", response_model=PredictionResult)
async def detect_if_fraud(transaction_data: TransactionData) -> PredictionResult:
    """Check if the trasaction is fraud or not"""
    if app.state.model_artifact is None:
        app.state.model_artifact = load_model_artifact()

    return persist_prediction_result(predictor_utility(transaction_data, app.state.model_artifact))

@app.get("/detect", response_model=list[PredictionResult])
async def read_prediction_results() -> list[PredictionResult]:
    """Get all fraud detection results"""
    return get_all_prediction_results()

@app.get("/detect/{transaction_id}", response_model=list[PredictionResult])
async def read_prediction_result(transaction_id: int) -> list[PredictionResult]:
    """Get a fraud detection result by transaction id"""
    return get_a_prediction_result(transaction_id)