from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional, Literal
from banking_agents.communication.intent import Intent

class UserQuery(BaseModel):
    query: str
    session_id: str

class CustomerLoanProfile(BaseModel):
    """
    Structured customer profile for loan eligibility assessment.
    Populated from the user query context or via the /api/v1/loan/assess endpoint.
    """
    loan_type: Literal["PERSONAL", "HOME", "AUTO", "BUSINESS"]
    applicant_age: int
    monthly_income: float                           # Gross monthly income in INR
    employment_type: Literal["SALARIED", "SELF_EMPLOYED", "BUSINESS_OWNER"]
    cibil_score: int                                # Range: 300–900
    existing_emi_amount: float = 0.0                # Total existing monthly EMI obligations
    loan_amount_requested: float                     # Requested loan amount in INR
    loan_tenure_months: int                          # Requested tenure in months
    property_value: Optional[float] = None           # Required for HOME/AUTO loans
    annual_interest_rate_percent: Optional[float] = None

    @field_validator("cibil_score")
    @classmethod
    def validate_cibil(cls, v):
        if not 300 <= v <= 900:
            raise ValueError("CIBIL score must be between 300 and 900.")
        return v

    @field_validator("applicant_age")
    @classmethod
    def validate_age(cls, v):
        if not 18 <= v <= 70:
            raise ValueError("Applicant age must be between 18 and 70.")
        return v

    @field_validator("monthly_income", "loan_amount_requested")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Monthly income and requested loan amount must be greater than zero.")
        return v

    @field_validator("existing_emi_amount")
    @classmethod
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError("Existing EMI amount must be non-negative.")
        return v

    @field_validator("loan_tenure_months")
    @classmethod
    def validate_tenure(cls, v):
        if not 1 <= v <= 480:
            raise ValueError("Loan tenure must be between 1 and 480 months.")
        return v

    @field_validator("annual_interest_rate_percent")
    @classmethod
    def validate_interest_rate(cls, v):
        if v is not None and not 0 < v <= 100:
            raise ValueError("Annual interest rate must be greater than 0 and at most 100 percent.")
        return v

    @model_validator(mode="after")
    def validate_secured_loan_value(self):
        if self.loan_type in {"HOME", "AUTO"} and (
            self.property_value is None or self.property_value <= 0
        ):
            raise ValueError("Property/asset value is required for HOME and AUTO loans.")
        return self

class AgentContext(BaseModel):
    session_id: str
    history: List[Dict[str, str]] = Field(default_factory=list)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    current_intent: Optional[Intent] = None

class AgentResponse(BaseModel):
    final: str
    context: AgentContext
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
