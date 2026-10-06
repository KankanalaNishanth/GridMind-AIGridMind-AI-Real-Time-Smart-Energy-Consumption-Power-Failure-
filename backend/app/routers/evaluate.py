"""Serves the model evaluation summary produced by evaluate_pipeline.py."""
import json
import logging

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluate", tags=["Evaluation"])


@router.get("/summary")
def get_evaluation_summary():
    settings = get_settings()
    path = settings.reports_path / "evaluation_summary.json"
    if not path.exists():
        raise HTTPException(
            503,
            "No evaluation summary found — run 'python evaluate_pipeline.py' after training.",
        )
    with open(path) as f:
        return json.load(f)
