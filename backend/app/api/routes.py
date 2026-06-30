from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from backend.app.models.schemas import TelemetryEvent
from backend.app.services.telemetry_service import TelemetryService

router = APIRouter()


def get_telemetry_service(request: Request) -> TelemetryService:
    return request.app.state.telemetry_service


@router.get("/health")
def health(request: Request) -> dict:
    store_ok = request.app.state.store.ping()
    models_ready = request.app.state.model_service.ready
    return {"status": "ok", "mongodb": store_ok, "models_ready": models_ready}


@router.post("/telemetry")
async def ingest_telemetry(
    event: TelemetryEvent,
    request: Request,
    service: TelemetryService = Depends(get_telemetry_service),
) -> dict:
    prediction = service.ingest(event)
    payload = {"event": event.model_dump(mode="json"), "prediction": prediction.model_dump(mode="json")}
    await request.app.state.websocket_manager.broadcast(payload)
    return payload


@router.get("/dashboard")
def dashboard(service: TelemetryService = Depends(get_telemetry_service)) -> dict:
    return service.snapshot().model_dump(mode="json")


@router.get("/telemetry/recent")
def recent_telemetry(
    limit: int = Query(default=100, ge=1, le=500),
    service: TelemetryService = Depends(get_telemetry_service),
) -> list[dict]:
    return service.recent_telemetry(limit)


@router.get("/alerts")
def alerts(
    limit: int = Query(default=50, ge=1, le=200),
    service: TelemetryService = Depends(get_telemetry_service),
) -> list[dict]:
    return service.recent_alerts(limit)


@router.get("/reports/history")
def history_report(
    start: datetime | None = None,
    end: datetime | None = None,
    service: TelemetryService = Depends(get_telemetry_service),
) -> list[dict]:
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start must be before end")
    return service.history_report(start, end)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

