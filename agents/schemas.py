"""
agents/schemas.py
 
Pydantic v2 output models for each agent.
 
Design decision: agents return typed Pydantic objects internally, then
call `.model_dump()` before handing the dict back to LangGraph. This gives
us validation + IDE autocomplete without changing the TypedDict-based graph
state that orchestration.py already defines.
 
If you later decide to make the LangGraph state itself a BaseModel, the
migration is: swap ContractReviewState from TypedDict → BaseModel here,
delete the `.model_dump()` calls in agents, and update orchestration.py.
"""
from __future__ import annotations
 
from typing import Any, Optional
from pydantic import BaseModel, Field
 
 
# ---------------------------------------------------------------------------
# contract_review_agent
# ---------------------------------------------------------------------------
 
class ContractMetadata(BaseModel):
    parties: list[str] = Field(default_factory=list, description="Named parties to the contract")
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    term: Optional[str] = None
    contract_type: Optional[str] = None        # e.g. "NDA", "SaaS MSA", "Employment"
    governing_law: Optional[str] = None
    jurisdiction: Optional[str] = None
 
 
class ContractReviewOutput(BaseModel):
    contract_metadata: ContractMetadata = Field(default_factory=ContractMetadata)
    is_valid_contract: bool = True
    intake_notes: str = ""
 
 
# ---------------------------------------------------------------------------
# clause_classification_agent
# ---------------------------------------------------------------------------
 
class ClassifiedClause(BaseModel):
    clause_id: str
    text: str
    category: str           # e.g. "indemnification", "termination", "payment"
    confidence: float = Field(ge=0.0, le=1.0)
    risk_flag: bool = False
    section_id: Optional[str] = None   # structural id from the chunker, e.g. "8.2"
    heading: Optional[str] = None       # section heading, e.g. "Indemnification"
 
 
class ClauseClassificationOutput(BaseModel):
    classified_clauses: list[ClassifiedClause] = Field(default_factory=list)
 
 
# ---------------------------------------------------------------------------
# document_understanding_agent
# ---------------------------------------------------------------------------
 
class DocumentUnderstandingOutput(BaseModel):
    document_summary: str = ""
    key_terms: dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# compliance_agent
# ---------------------------------------------------------------------------

class ComplianceViolation(BaseModel):
    clause_id: Optional[str] = None     # None = applies to the contract generally (e.g. missing clause)
    regulation: str = ""                # e.g. "GDPR Article 17"
    description: str = ""
    likelihood: str = "medium"          # "low" | "medium" | "high"
    impact: str = "medium"              # "low" | "medium" | "high"
    severity: str = "medium"            # derived from likelihood x impact, kept for compatibility


class ComplianceOutput(BaseModel):
    compliant: bool = True
    summary: str = ""
    # violations: list[ComplianceViolation] = Field(default_factory=list)
    violations: list[ComplianceViolation]
    missing_requirements: list[str] = []



# risk_agent


class RiskItem(BaseModel):
    clause_id: Optional[str] = None
    risk_type: str = ""                 # one of the 5 risk categories
    likelihood: str = "medium"
    impact: str = "medium"
    description: str = ""
    source: str = ""                    # "compliance_agent" | "risk_agent" | "fallback"


class CategoryRisk(BaseModel):
    likelihood: str = "low"
    impact: str = "low"
    score: int = 1                      # likelihood x impact, 1-9
    level: str = "low"                  # "low" | "medium" | "high"
    reasons: list[str] = Field(default_factory=list)


class RiskOutput(BaseModel):
    overall_risk_score: float = 0.0
    summary: str = ""
    category_risks: dict[str, CategoryRisk] = Field(default_factory=dict)
    risk_items: list[RiskItem] = Field(default_factory=list)

 
 