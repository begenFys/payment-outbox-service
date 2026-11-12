from fastapi import FastAPI

from src.routes import api_router

app = FastAPI(title="Payment Outbox Service", version="0.1.0")
app.include_router(router=api_router)
