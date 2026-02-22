"""Fraud Rule Engine"""
import random

from fastapi import FastAPI
from model import TransactionData

app = FastAPI()


@app.get("/")
async def read_root():
    """Heath Check"""
    return {"Hello": "World"}


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    """Example request"""
    return {"item_id": item_id, "q": q}


@app.post("/detect")
async def detect_if_fraud(transaction_data: TransactionData):
    """Check if the trasaction is fraud or not"""
    data: dict[str, str | float | int | bool ] = {
        "transaction_id": transaction_data.transaction.transaction_id,
        "amount": transaction_data.transaction.amount,
        "transaction_hour": transaction_data.transaction.timestamp.hour,
        "merchant_category": transaction_data.metadata.merchant_category,
        "foreign_transaction": transaction_data.metadata.foreign_transaction,
        "location_mismatch": transaction_data.metadata.location_mismatch,
        "device_trust_score": random.randint(0, 100),
        "velocity_last_24h": transaction_data.metadata.velocity_last_24h,
        "cardholder_age": transaction_data.metadata.cardholder_age,
    }

    # store transaction it in a sqlite db transactionId, accountId, merchantId, isFraud