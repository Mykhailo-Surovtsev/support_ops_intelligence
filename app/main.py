from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.schemas import HealthResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Support Ops Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")