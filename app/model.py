"""Models for the API (DTOs)"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class TransactionType(str, Enum):
    """Transaction type enumeration"""
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    TRANSFER = "TRANSFER"
    WITHDRAWAL = "WITHDRAWAL"
    DEPOSIT = "DEPOSIT"

class Transaction(BaseModel):
    """Transaction data model"""
    transaction_id: str = Field(description="Unique transaction identifier")
    account_id: str = Field(description="Account identifier")
    amount: float = Field(gt=0, description="Transaction amount")
    transaction_type: TransactionType = Field(description="Type of transaction")
    merchant_id: Optional[str] = Field(None, description="Merchant identifier")
    timestamp: datetime = Field(description="Transaction timestamp")
    description: Optional[str] = Field(None, description="Transaction description")

class TransactionMetadata(BaseModel):
    """Meta data about the transaction"""
    merchant_name: Optional[str] = Field(None, description="Merchant name")
    merchant_category: str = Field(description="Merchant category")
    location_mismatch: bool = Field(description="Billing vs transaction location mismatch")
    foreign_transaction: bool = Field(description="Is the transaction from a foreign country")
    velocity_last_24h: int = Field(description="Number of transactions in the last 24 hours")
    cardholder_age: int = Field(description="The age of the card holder")

class TransactionData(BaseModel):
    """API request body for fraud detection"""
    transaction: Transaction
    metadata: TransactionMetadata
