
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    contract_id: str
    status: str  # "completed" | "completed_with_errors" | "failed"
    contract_metadata: Optional[dict[str, Any]] = None
    compliance_results: Optional[dict[str, Any]] = None
    risk_results: Optional[dict[str, Any]] = None
    recommendations: Optional[list[dict[str, Any]]] = None
    legal_explanations: Optional[list[dict[str, Any]]] = None
    errors: list[dict[str, Any]] = []
    completed_steps: list[str] = []


class ErrorResponse(BaseModel):
    detail: str
