from fastapi import FastAPI

from schemas import HealthResponse

app = FastAPI(
    title="Brasaland API",
    version="0.1.0",
    description="Central API for Brasaland operations.",
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")