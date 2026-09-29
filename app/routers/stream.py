"""
Kafka stream simulation endpoint (Phase 9 of the original notebook).

Lets you trigger a producer -> consumer -> ML scoring cycle over HTTP
without needing a real Kafka broker, useful for demos and smoke-testing
the scoring path. See app/services/kafka_stream.py for the swap-in
points to point this at a real broker later.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from app.services.data_cache import get_master_df
from app.services.kafka_stream import run_simulation
from app.services.model_registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream", tags=["Stream Simulation"])


@router.post("/simulate")
def simulate_stream(n: int = Query(30, ge=1, le=500, description="Number of messages to simulate")):
    registry = get_registry()
    if not registry.is_ready():
        raise HTTPException(503, "Models not loaded — run train_pipeline.py first.")

    df = get_master_df()
    predictions = run_simulation(
        df, registry.rf_model, registry.iso_model, registry.scaler_iso, n=n
    )

    return {
        "messages_processed": len(predictions),
        "alerts_generated": sum(p["alert"] for p in predictions),
        "sample": predictions[:5],
    }
