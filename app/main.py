from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.analytics import router as analytics_router

app = FastAPI(
    title="FinPilot API",
    description=(
        "Personal finance decision-support API. "
        "Provides financial clarity and spending intelligence "
        "without investment advice."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "finpilot",
    }