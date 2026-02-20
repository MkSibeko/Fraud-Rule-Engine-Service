"""Fraud Rule Engine"""
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def read_root():
    """Heath Check"""
    return {"Hello": "World"}


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    """Example request"""
    return {"item_id": item_id, "q": q}
