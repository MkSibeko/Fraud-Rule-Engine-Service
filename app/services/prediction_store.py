from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine, select

engine = create_engine("sqlite:///frauddetection.db")

class PredictionResult(SQLModel, table=True):
    """API response body for fraud detection endpoint"""
    transaction_id: str = Field(primary_key=True, description="Unique transaction identifier")
    merchant_id: Optional[str] = Field(None, description="Merchant identifier")
    account_id: str = Field(description="Account identifier")
    is_fraud: bool = Field(description="Whether the transaction is predicted as fraud")
    fraud_probability: float = Field(description="Predicted fraud probability")

def init_datastore():
    SQLModel.metadata.create_all(engine)

def persist_prediction_result(prediction_result: PredictionResult):
    with Session(engine) as session:
        session.add(prediction_result)
        session.commit()
        session.refresh(prediction_result)
        return prediction_result

def get_all_prediction_results():
    with Session(engine) as session:
        return session.exec(select(PredictionResult)).all()

def get_a_prediction_result(transaction_id):
    with Session(engine) as session:
        statement = select(PredictionResult)\
                        .where(PredictionResult.transaction_id == transaction_id)
        return session.exec(statement).first()
