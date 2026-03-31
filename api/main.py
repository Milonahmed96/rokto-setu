from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.database import engine
from api.routes import auth, location, requests

app = FastAPI(
    title="Rokto Setu API",
    description="রক্ত সেতু — AI-powered blood donor matching · Portfolio Demo",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes import auth, location, requests, chat, forecast, anomaly

app.include_router(auth.router)
app.include_router(location.router)
app.include_router(requests.router)
app.include_router(chat.router)
app.include_router(forecast.router)
app.include_router(anomaly.router)


@app.get("/")
async def root():
    return {
        "project": "Rokto Setu — রক্ত সেতু",
        "version": "0.1.0",
        "status":  "running",
        "message": "Blood Bridge · Bangladesh · AI Engineer Portfolio",
    }


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status":   "healthy",
        "database": db_status,
    }