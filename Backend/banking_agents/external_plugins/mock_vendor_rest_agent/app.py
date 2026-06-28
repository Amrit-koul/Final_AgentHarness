"""A tiny, separately hosted vendor agent used to exercise the REST adapter."""
from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Mock Vendor Agent", version="1.0.0")


class InvokeRequest(BaseModel):
    query: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)


class InvokeResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    vendor: str
    trace_id: str


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    """Return a deterministic vendor-style answer without accessing bank data."""
    return InvokeResponse(
        answer=f"Mock Vendor Agent summary: {request.query.strip()}",
        confidence=0.92,
        vendor="Mock Vendor Agent",
        trace_id=request.trace_id,
    )
