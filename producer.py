"""Produce transactions to kafka topic"""

import os
import socket
import random
import uuid
import json
from datetime import datetime
from confluent_kafka import Producer

_BOOTSTRAP_SERVERS: str = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
_NUM_TRANSACTIONS: int = int(os.getenv('NUM_TRANSACTIONS', '100'))
_TOPIC: str = os.getenv('KAFKA_TOPIC', 'transactions')

conf: dict = {
    'bootstrap.servers': _BOOTSTRAP_SERVERS,
    'client.id': socket.gethostname(),
}

# Transaction types matching the TransactionType enum
TRANSACTION_TYPES: list[str] = ["DEBIT", "CREDIT", "TRANSFER", "WITHDRAWAL", "DEPOSIT"]

# ── Merchant catalogues ────────────────────────────────────────────────────────
NORMAL_MERCHANTS: list[tuple[str, str]] = [
    ("Shoprite", "Grocery"),
    ("Checkers", "Grocery"),
    ("Pick n Pay", "Grocery"),
    ("Woolworths Food", "Grocery"),
    ("SPAR", "Grocery"),
    ("Engen Garage", "Fuel"),
    ("Shell Ultra City", "Fuel"),
    ("BP Express", "Fuel"),
    ("Clicks", "Pharmacy"),
    ("Dischem", "Pharmacy"),
    ("KFC South Africa", "Fast Food"),
    ("Steers", "Fast Food"),
    ("Nando's", "Restaurant"),
    ("McDonald's SA", "Fast Food"),
    ("Debonairs Pizza", "Fast Food"),
    ("Capitec ATM", "ATM Withdrawal"),
    ("Vodacom", "Airtime/Data"),
    ("MTN", "Airtime/Data"),
    ("Netflix", "Streaming"),
    ("DSTV", "Streaming"),
    ("Uber SA", "Transport"),
    ("Mr Price", "Clothing"),
    ("Edgars", "Clothing"),
    ("Game", "Electronics"),
    ("Incredible Connection", "Electronics"),
]

FRAUDULENT_MERCHANTS: list[tuple[str, str]] = [
    ("Crypto Exchange XYZ", "Cryptocurrency"),
    ("Online Casino SA", "Gambling"),
    ("Bitcoin ATM", "Cryptocurrency"),
    ("Offshore Gaming Ltd", "Gambling"),
    ("Unknown Vendor 0x9F", "Unknown"),
    ("International Wire Co.", "Wire Transfer"),
    ("Luxury Goods Dubai", "Luxury"),
    ("Foreign Exchange Fast", "Forex"),
    ("Dark Web Market", "Unknown"),
    ("Rapid Transfer Ltd", "Wire Transfer"),
]

# ── Locations ──────────────────────────────────────────────────────────────────
SA_LOCATIONS: list[str] = [
    "Cape Town, ZA",
    "Johannesburg, ZA",
    "Durban, ZA",
    "Pretoria, ZA",
    "Port Elizabeth, ZA",
    "Bloemfontein, ZA",
    "East London, ZA",
    "Polokwane, ZA",
]

FOREIGN_LOCATIONS: list[str] = [
    "Lagos, NG",
    "Nairobi, KE",
    "Dubai, AE",
    "London, GB",
    "New York, US",
    "Moscow, RU",
    "Beijing, CN",
    "Amsterdam, NL",
]

# ── Fraud strategies ───────────────────────────────────────────────────────────
FRAUD_STRATEGIES: list[str] = [
    "high_amount_foreign_merchant",
    "card_not_present_high_value",
    "odd_hours_large_amount",
    "unusual_merchant_category",
    "rapid_small_transactions",
]


def ack(err, msg):
    """Acknowledment callback function"""
    if err is not None:
        print(f"Failed to deliver message: {str(msg)}: {str(err)}")
    else:
        print(f"Message produced: {str(msg)}")


def generate_transaction() -> dict:
    """Randomly generates a Capitec bank transaction simulation.

    80 % of transactions are ordinary (normal merchants, reasonable amounts,
    business hours, card present in South Africa).  The remaining 20 % are
    flagged as fraudulent and follow one of several fraud strategies:

    - high_amount_foreign_merchant  : large ZAR amount at a known suspicious
                                      merchant in a foreign country.
    - card_not_present_high_value   : CNP transaction for a high value at an
                                      unusual merchant, typically in the early
                                      hours of the morning.
    - odd_hours_large_amount        : a large legitimate-looking debit that
                                      occurs between 01:00–04:00.
    - unusual_merchant_category     : crypto, gambling or wire-transfer
                                      merchants regardless of amount.
    - rapid_small_transactions      : suspiciously small, card-not-present
                                      debits that probe account validity.

    Returns:
        dict: A transaction record ready to be serialised and published.
    """
    is_fraudulent: bool = random.random() < 0.20  # 20 % fraud rate

    account_number: str = f"CAPITEC{random.randint(1_000_000_000, 9_999_999_999)}"
    strategy: str = "none"

    # ── Build fraud / normal parameters ───────────────────────────────────────
    if is_fraudulent:
        strategy: str = random.choice(FRAUD_STRATEGIES)

        if strategy == "high_amount_foreign_merchant":
            merchant_name, merchant_category = random.choice(FRAUDULENT_MERCHANTS)
            amount: float = round(random.uniform(5_000, 50_000), 2)
            location: str = random.choice(FOREIGN_LOCATIONS)
            hour: int = random.randint(0, 23)

        elif strategy == "card_not_present_high_value":
            merchant_name, merchant_category = random.choice(FRAUDULENT_MERCHANTS)
            amount = round(random.uniform(8_000, 30_000), 2)
            location = random.choice(FOREIGN_LOCATIONS)
            hour = random.randint(1, 4)          # Early hours

        elif strategy == "odd_hours_large_amount":
            merchant_name, merchant_category = random.choice(NORMAL_MERCHANTS)
            amount = round(random.uniform(3_000, 20_000), 2)
            location = random.choice(SA_LOCATIONS)
            hour = random.choice([1, 2, 3, 4])  # Suspicious window

        elif strategy == "unusual_merchant_category":
            merchant_name, merchant_category = random.choice(FRAUDULENT_MERCHANTS)
            amount = round(random.uniform(500, 15_000), 2)
            location = random.choice(SA_LOCATIONS + FOREIGN_LOCATIONS)
            hour = random.randint(0, 23)

        else:  # rapid_small_transactions
            merchant_name, merchant_category = random.choice(NORMAL_MERCHANTS)
            amount = round(random.uniform(1, 49), 2)
            location = random.choice(SA_LOCATIONS)
            hour = random.randint(0, 23)

    else:
        # ── Ordinary Capitec transaction ───────────────────────────────────
        merchant_name, merchant_category = random.choice(NORMAL_MERCHANTS)
        amount = round(random.uniform(5, 2_500), 2)
        location = random.choice(SA_LOCATIONS)
        hour = random.randint(7, 21)   # Normal business hours

    # Timestamp anchored to today with the chosen hour
    now = datetime.now()
    timestamp = now.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )

    # Determine if foreign transaction based on location
    is_foreign = location not in SA_LOCATIONS
    
    # Generate velocity (higher for fraudulent rapid transactions)
    velocity_last_24h = random.randint(10, 50) if strategy == "rapid_small_transactions" else random.randint(1, 10)
    
    # Generate cardholder age
    cardholder_age = random.randint(18, 75)
    
    # Device trust score (lower for suspicious transactions)
    device_trust_score = random.randint(10, 40) if is_fraudulent else random.randint(60, 100)

    # Build TransactionData schema matching the API model
    transaction_data: dict = {
        "transaction": {
            "transaction_id": str(uuid.uuid4()),
            "account_id": account_number,
            "amount": amount,
            "transaction_type": random.choices(TRANSACTION_TYPES, weights=[40, 20, 15, 15, 10])[0],
            "merchant_id": f"MERCHANT_{random.randint(1000, 9999)}",
            "timestamp": timestamp.isoformat(),
            "description": f"Transaction at {merchant_name}",
        },
        "metadata": {
            "merchant_name": merchant_name,
            "merchant_category": merchant_category,
            "location_mismatch": is_foreign or (is_fraudulent and random.random() < 0.7),
            "foreign_transaction": is_foreign,
            "velocity_last_24h": velocity_last_24h,
            "cardholder_age": cardholder_age,
            "device_trust_score": device_trust_score,
        },
    }

    return transaction_data


def publish_transactions(num_transactions: int = 100) -> None:
    """Bank transactions published to transaction topic"""
    producer = Producer(conf)
    for _ in range(num_transactions):
        transaction = generate_transaction()
        producer.produce(
            topic=_TOPIC,
            key=transaction["transaction"]["account_id"],
            value=json.dumps(transaction).encode('utf-8'),
            callback=ack,
        )
    producer.flush()
    print(f"Published {num_transactions} transactions to topic '{_TOPIC}'")


if __name__ == "__main__":
    publish_transactions(_NUM_TRANSACTIONS)
