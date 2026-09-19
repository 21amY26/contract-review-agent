from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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


async def run_monitoring_pipeline(
    state: dict[str, Any],
    stages: list[tuple[str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]]],
    *,
    print_output: bool = True,
) -> list[tuple[str, dict[str, Any]]]:
    """Run a list of async pipeline stages and print each stage's output.

    This is a lightweight helper for monitoring the contract review workflow
    stage-by-stage during development or debugging.
    """
    results: list[tuple[str, dict[str, Any]]] = []

    for name, stage in stages:
        result = await stage(state)
        if not isinstance(result, dict):
            raise TypeError(f"Stage '{name}' must return a dict")

        state.update(result)
        results.append((name, result))

        if print_output:
            print(f"\n=== {name} ===")
            print(json.dumps(result, indent=2, default=str))

    return results


async def monitor_contract_review_pipeline(
    initial_state: dict[str, Any],
    *,
    print_output: bool = True,
) -> list[tuple[str, dict[str, Any]]]:
    """Run the contract review agents in order and print their outputs."""
    from agents import (
        contract_review_agent,
        clause_classification_agent,
        document_understanding_agent,
        compliance_agent,
        risk_agent,
        recommendation_agent,
        legal_explanation_agent,
    )

    # Mirrors the LangGraph order in agents/orchestration/orchestration.py so a
    # manual run reproduces the real pipeline (document_understanding populates
    # document_summary/key_terms/retrieved_context used downstream).
    stages = [
        ("contract_review_agent", contract_review_agent.run),
        ("clause_classification_agent", clause_classification_agent.run),
        ("document_understanding_agent", document_understanding_agent.run),
        ("compliance_agent", compliance_agent.run),
        ("risk_agent", risk_agent.run),
        ("recommendation_agent", recommendation_agent.run),
        ("legal_explanation_agent", legal_explanation_agent.run),
    ]

    return await run_monitoring_pipeline(initial_state, stages, print_output=print_output)


if __name__ == "__main__":
    async def _demo() -> None:
        sample_pdf = resolve_contract_path(None)

        from ingestion.parsers.pdf_parser import PDFParser

        parse_result = PDFParser().parse(sample_pdf)
        raw_text = "\n\n".join(page.text for page in parse_result.pages if page.text.strip())

        sample_state = {
            "contract_id": sample_pdf.stem,
            "raw_text": raw_text,
            "chunks": [chunk for chunk in raw_text.split("\n\n") if chunk.strip()],
            "file_metadata": {"filename": sample_pdf.name},
            "errors": [],
            "completed_steps": [],
        }
        await monitor_contract_review_pipeline(sample_state)

    asyncio.run(_demo())
