from __future__ import annotations

import logging
import tempfile
import uuid
import asyncio
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from agents.orchestration.orchestration import (
    create_initial_state,
    run_contract_review,
)
from ingestion.chunking.splitter import chunk_parse_result
from ingestion.parsers import UnsupportedFormatError, get_parser
from schemas.api_models import AnalyzeResponse
from api.database import get_db, SessionLocal
from api.models import User, AnalysisJob
from api.auth import get_current_user

logger = logging.getLogger("contract_review.api.analyze")

router = APIRouter(tags=["analyze", "history", "reports"])

# Matches ingestion/parsers/__init__.py EXTENSION_MAP
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".docm"}


async def process_contract_background(
    contract_id: str, tmp_path: Path, filename: str
):
    try:
        try:
            parser = get_parser(tmp_path)
            parsed = parser.parse(tmp_path)
        except UnsupportedFormatError as exc:
            _update_job_status(contract_id, "failed", {"errors": [{"error": str(exc)}]})
            return
        
        if not parsed.full_text.strip():
            _update_job_status(contract_id, "failed", {"errors": [{"error": "No extractable text found"}]})
            return
            
        chunks = chunk_parse_result(parsed, source_name=filename or contract_id)

        state = create_initial_state(
            contract_id=contract_id,
            raw_text=parsed.full_text,
            # Pass structural context (section_id/heading) alongside text so the
            # clause classifier can preserve it, not just the bare string.
            chunks=[
                {
                    "text": c.text,
                    "section_id": c.section_id,
                    "heading": c.heading,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
            file_metadata={"filename": filename, **parsed.metadata},
        )

        try:
            result = await run_contract_review(state, thread_id=contract_id)
            _update_job_status(contract_id, result.get("status", "failed"), result)
        except Exception as e:
            logger.exception("Pipeline run failed for contract_id=%s", contract_id)
            _update_job_status(contract_id, "failed", {"errors": [{"error": str(e)}]})
    finally:
        tmp_path.unlink(missing_ok=True)


def _update_job_status(contract_id: str, status: str, result_data: dict = None):
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.contract_id == contract_id).first()
        if job:
            job.status = status
            if result_data:
                job.result_data = result_data
            db.commit()
        else:
            logger.warning(
                "Job row not found for contract_id=%s — status update to '%s' dropped",
                contract_id,
                status,
            )
    finally:
        db.close()


@router.post("/analyze")
async def analyze_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    contract_id = f"contract-{uuid.uuid4().hex[:12]}"

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)
        
    # Create AnalysisJob in DB
    job = AnalysisJob(
        user_id=current_user.id,
        contract_id=contract_id,
        filename=file.filename,
        status="pending"
    )
    db.add(job)
    db.commit()

    # Queue background task
    background_tasks.add_task(process_contract_background, contract_id, tmp_path, file.filename)
    
    return {"contract_id": contract_id, "status": "pending"}

@router.get("/analyze/{contract_id}/status")
async def get_analyze_status(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    job = db.query(AnalysisJob).filter(AnalysisJob.contract_id == contract_id, AnalysisJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    response = {
        "contract_id": job.contract_id,
        "status": job.status,
    }
    
    if job.status in ["completed", "completed_with_errors", "rejected", "failed"] and job.result_data:
        response.update({
            "contract_metadata": job.result_data.get("contract_metadata"),
            "intake_notes": job.result_data.get("intake_notes"),
            "compliance_results": job.result_data.get("compliance_results"),
            "risk_results": job.result_data.get("risk_results"),
            "recommendations": job.result_data.get("recommendations"),
            "legal_explanations": job.result_data.get("legal_explanations"),
            "errors": job.result_data.get("errors", []),
            "completed_steps": job.result_data.get("completed_steps", []),
        })
    return response

@router.get("/history")
async def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    jobs = db.query(AnalysisJob).filter(AnalysisJob.user_id == current_user.id).order_by(AnalysisJob.created_at.desc()).all()
    
    # Format according to what frontend HistoryPage expects
    return [
        {
            "id": job.contract_id,
            "filename": job.filename,
            "date": job.created_at.isoformat(),
            "status": job.status,
            "risk_score": (
                job.result_data.get("risk_results", {}).get("overall_risk_score", 0)
                if job.result_data else 0
            ),
        }
        for job in jobs
    ]

@router.get("/reports")
async def get_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Provide list of completed reports for Reports tab
    jobs = db.query(AnalysisJob).filter(
        AnalysisJob.user_id == current_user.id,
        AnalysisJob.status.in_(["completed", "completed_with_errors"])
    ).order_by(AnalysisJob.created_at.desc()).all()
    return [
        {
            "id": job.contract_id,
            "filename": job.filename,
            "date": job.created_at.isoformat(),
            "status": job.status,
            "risk_score": (
                job.result_data.get("risk_results", {}).get("overall_risk_score", 0)
                if job.result_data else 0
            )
        }
        for job in jobs
    ]
