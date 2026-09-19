from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents import llm_router
from agents.compliance_agent import run as run_compliance
from agents.contract_review_agent import run as run_contract_review
from agents.clause_classification_agent import run as run_clause_classification
from agents.legal_explanation_agent import run as run_legal_explanation
from agents.recommendation_agent import run as run_recommendation
from agents.risk_agent import run as run_risk
from src.ingestion.ingest_contracts import ingest_contract_file
from src.retrieval.retriever import search_contracts, search_compliance, search_risks


def resolve_contract_path(candidate: str | Path | None) -> Path:
    """Resolve a contract path from an explicit input or a repository sample PDF."""
    search_paths: list[Path] = []
    if candidate is not None:
        search_paths.append(Path(candidate))

    search_paths.extend(
        [
            REPO_ROOT / "test" / "Sample_Master_Services_Agreement.pdf",
            REPO_ROOT / "ingestion" / "parsers" / "tests" / "data" / "sample_report.pdf",
            REPO_ROOT / "sample_report.pdf",
        ]
    )

    for path in search_paths:
        if path.exists():
            return path.resolve()

    if candidate is None:
        raise FileNotFoundError(
            "No contract PDF found. Checked default sample paths under the repository."
        )
    raise FileNotFoundError(f"PDF not found: {candidate}")


async def run_full_review(pdf_path: str | Path) -> dict[str, Any]:
    """Parse a PDF, ingest it into Chroma, and execute the contract review workflow."""
    contract_path = resolve_contract_path(pdf_path)

    ingest_contract_file(contract_path)

    raw_text = contract_path.read_text(errors="ignore") if contract_path.suffix.lower() == ".txt" else None
    if raw_text is None:
        from ingestion.parsers.pdf_parser import PDFParser

        parse_result = PDFParser().parse(contract_path)
        raw_text = "\n\n".join(page.text for page in parse_result.pages if page.text.strip())

    state = {
        "contract_id": contract_path.stem,
        "raw_text": raw_text or "",
        "chunks": [chunk for chunk in raw_text.split("\n\n") if chunk.strip()] if raw_text else [],
        "file_metadata": {"filename": contract_path.name},
        "errors": [],
        "completed_steps": [],
    }

    state.update(await run_contract_review(state))
    state.update(await run_clause_classification(state))
    state.update(await run_compliance(state))
    state.update(await run_risk(state))
    state.update(await run_recommendation(state))
    state.update(await run_legal_explanation(state))

    state["retrieved_context"] = {
        "contracts": search_contracts(state.get("raw_text", "")[:1000], n_results=3),
        "compliance": search_compliance(state.get("raw_text", "")[:1000], n_results=3),
        "risks": search_risks(state.get("raw_text", "")[:1000], n_results=3),
    }

    return state


async def ask_contract_chatbot(pdf_path: str | Path, question: str) -> str:
    """Answer a contract-review question using the review workflow plus retrieval context."""
    review = await run_full_review(pdf_path)
    retrieved = review.get("retrieved_context", {})
    context_blocks = []
    for key, items in retrieved.items():
        if not items:
            continue
        context_blocks.append(f"[{key}]\n" + "\n".join(item.get("text", "") for item in items[:2]))

    prompt = f"""
You are a contract-review assistant.
Use the review results and retrieved context below to answer the user's question.

Review summary:
{summary}

Retrieved context:
{context}

User question:
{question}
"""
    summary = json.dumps(
        {
            "contract_metadata": review.get("contract_metadata", {}),
            "compliance_results": review.get("compliance_results", {}),
            "risk_results": review.get("risk_results", {}),
            "recommendations": review.get("recommendations", []),
        },
        indent=2,
        default=str,
    )
    messages = [
        {"role": "system", "content": "You answer concisely and mention risks, clauses, and recommended actions."},
        {"role": "user", "content": prompt.format(summary=summary, context="\n\n".join(context_blocks), question=question)},
    ]
    return await llm_router.chat(messages)


if __name__ == "__main__":
    async def _interactive_loop() -> None:
        default_pdf = resolve_contract_path(None)
        pdf_path = str(default_pdf)
        if not Path(pdf_path).exists():
            while pdf_path is None or not Path(pdf_path).exists():
                pdf_path = input("Enter the path to a PDF contract: ").strip().strip('"')
                if not pdf_path:
                    print("Please provide a valid PDF path.")
                    continue
                if not Path(pdf_path).exists():
                    print("File not found. Try again.")
        else:
            print(f"Using default sample PDF: {pdf_path}")

        print("\nContract review chatbot ready. Type 'exit' to quit.\n")
        while True:
            question = input("You: ").strip()
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                print("Goodbye!")
                break
            answer = await ask_contract_chatbot(pdf_path, question)
            print(f"\nAssistant: {answer}\n")

    asyncio.run(_interactive_loop())
