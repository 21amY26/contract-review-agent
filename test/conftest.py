"""
tests/conftest.py

Shared pytest fixtures.

The key fixture is `mock_ollama`, which patches `agents.llm_router.chat`
so unit tests never need a running Ollama instance.

Usage in a test:
    async def test_something(mock_ollama):
        mock_ollama.return_value = '{"key": "value"}'
        result = await some_agent.run(state)
        assert result["key"] == "value"
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Reusable contract state fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_state() -> dict[str, Any]:
    """Bare-minimum valid state — just enough for every agent to not crash."""
    return {
        "contract_id": "test-001",
        "raw_text": (
            "SERVICE AGREEMENT\n\n"
            "This Service Agreement ('Agreement') is entered into as of January 1, 2025, "
            "between Acme Corp ('Client') and WidgetCo Ltd ('Provider').\n\n"
            "1. Services\nProvider shall deliver software consulting services.\n\n"
            "2. Payment\nClient shall pay $10,000 per month within 30 days of invoice.\n\n"
            "3. Term\nThis Agreement commences on January 1, 2025 and continues for 12 months.\n\n"
            "4. Termination\nEither party may terminate with 30 days written notice.\n\n"
            "5. Governing Law\nThis Agreement is governed by the laws of Delaware.\n\n"
            "IN WITNESS WHEREOF, the parties have executed this Agreement."
        ),
        "chunks": [
            "1. Services\nProvider shall deliver software consulting services.",
            "2. Payment\nClient shall pay $10,000 per month within 30 days of invoice.",
            "3. Term\nThis Agreement commences on January 1, 2025 and continues for 12 months.",
            "4. Termination\nEither party may terminate with 30 days written notice.",
            "5. Governing Law\nThis Agreement is governed by the laws of Delaware.",
        ],
        "file_metadata": {"filename": "service_agreement.pdf"},
        "errors": [],
        "completed_steps": [],
    }


@pytest.fixture
def rich_state(minimal_state) -> dict[str, Any]:
    """State populated as if earlier pipeline stages already ran."""
    return {
        **minimal_state,
        "contract_metadata": {
            "parties": ["Acme Corp", "WidgetCo Ltd"],
            "effective_date": "2025-01-01",
            "expiry_date": "2025-12-31",
            "term": "12 months",
            "contract_type": "Service Agreement",
            "governing_law": "Delaware",
            "jurisdiction": None,
        },
        "is_valid_contract": True,
        "intake_notes": "",
        "classified_clauses": [
            {
                "clause_id": "clause_000",
                "text": "Provider shall deliver software consulting services.",
                "category": "other",
                "confidence": 0.9,
                "risk_flag": False,
            },
            {
                "clause_id": "clause_001",
                "text": "Client shall pay $10,000 per month within 30 days of invoice.",
                "category": "payment",
                "confidence": 0.95,
                "risk_flag": False,
            },
            {
                "clause_id": "clause_003",
                "text": "Either party may terminate with 30 days written notice.",
                "category": "termination",
                "confidence": 0.88,
                "risk_flag": True,
            },
        ],
        "document_summary": "A 12-month service agreement between Acme Corp and WidgetCo Ltd for software consulting.",
        "key_terms": {
            "payment_amount": "$10,000/month",
            "notice_period": "30 days",
            "auto_renewal": False,
        },
        "retrieved_context": [
            {
                "source": "gdpr/art28.txt",
                "content": "Data processor agreements must include specific provisions...",
                "score": 0.82,
            }
        ],
        "compliance_results": {
            "compliant": False,
            "summary": "Missing data processing agreement clause.",
            "violations": [
                {
                    "clause_id": None,
                    "regulation": "GDPR Art. 28",
                    "description": "No data processing agreement clause found.",
                    "severity": "high",
                }
            ],
        },
        "risk_results": {
            "overall_risk_score": 4.5,
            "summary": "Moderate risk. Termination clause is one-sided.",
            "risk_items": [
                {
                    "clause_id": "clause_003",
                    "risk_type": "termination",
                    "description": "30-day notice is short for a $10k/month engagement.",
                    "severity": "medium",
                    "mitigation": "Negotiate to 60 days minimum.",
                }
            ],
        },
        "recommendations": [
            {
                "priority": 1,
                "clause_id": None,
                "action": "Add GDPR Art. 28 data processing agreement clause.",
                "rationale": "Required by law for any EU data processing.",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Ollama mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ollama():
    """
    Patch agents.llm_router.chat so no real HTTP calls are made.

    Tests set mock_ollama.return_value to the raw string the 'model' returns.
    For JSON-returning calls (chat_json), set it to a JSON string.

    Example:
        mock_ollama.return_value = json.dumps({"is_valid_contract": True, ...})
    """
    with patch("agents.llm_router.chat", new_callable=AsyncMock) as mock:
        # Default: return a valid but empty JSON object so tests that don't
        # customise the mock still get parseable output.
        mock.return_value = json.dumps({})
        yield mock
