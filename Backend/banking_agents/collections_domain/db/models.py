from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    city = Column(String)
    job_profile = Column(String)
    cibil_score = Column(Integer)
    
    # Relationships
    accounts = relationship("LoanAccount", back_populates="customer")

class LoanAccount(Base):
    __tablename__ = "loan_accounts"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"))
    product_type = Column(String)
    outstanding = Column(Float)
    emi = Column(Float)
    dpd = Column(Integer)
    bucket = Column(String)
    status = Column(String)
    priority = Column(String)
    investigation_flag = Column(Boolean, default=False)
    
    # Relationships
    customer = relationship("Customer", back_populates="accounts")
    ai_profile = relationship("AIProfile", back_populates="account", uselist=False)
    interactions = relationship("Interaction", back_populates="account")
    notes = relationship("Note", back_populates="account")
    tasks = relationship("Task", back_populates="account")
    call_history = relationship("CallHistory", back_populates="account")

class AIProfile(Base):
    __tablename__ = "ai_profiles"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"), unique=True)
    
    # Persona Intelligence
    persona = Column(String)
    persona_confidence = Column(Float)
    pending_persona = Column(String, nullable=True)
    
    # Risk Scores (Stored as JSON for flexibility, or could be separate columns)
    scores = Column(JSON) # keep for backward compatibility or extra features
    trust_score = Column(Float, nullable=True)
    atp_score = Column(Float, nullable=True)
    itp_score = Column(Float, nullable=True)
    contactability_score = Column(Float, nullable=True)
    
    # Recommendations
    primary_channel = Column(String)
    fallback_channel = Column(String)
    next_action = Column(String)
    ptp_date = Column(DateTime, nullable=True)
    
    account = relationship("LoanAccount", back_populates="ai_profile")

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    type = Column(String) # e.g., 'whatsapp', 'sms', 'voice_call'
    channel = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String)
    message = Column(Text)
    
    # For voice calls
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment = Column(String, nullable=True)
    
    account = relationship("LoanAccount", back_populates="interactions")

class CallHistory(Base):
    """Permanent call intelligence storage for voice calls"""
    __tablename__ = "call_history"
    
    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Integer, nullable=True)
    
    # Call metadata
    provider = Column(String)  # groq/template
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    # Call intelligence
    transcript = Column(Text)  # Full conversation transcript
    summary = Column(Text)  # AI-generated summary
    sentiment = Column(String)  # Overall sentiment
    sentiment_breakdown = Column(JSON)  # Per-turn sentiment analysis
    
    # AI analysis
    intent = Column(String)  # Primary intent
    intent_confidence = Column(Float)
    intent_breakdown = Column(JSON)  # Per-turn intent
    
    # Trust at time of call
    trust_gate_status = Column(String, nullable=True)
    trust_score_at_call = Column(Float, nullable=True)
    trust_confidence_at_call = Column(Float, nullable=True)
    
    # Persona tracking
    persona_before = Column(String)
    persona_after = Column(String)
    persona_shift = Column(Boolean, default=False)
    persona_shift_reason = Column(Text, nullable=True)
    
    # PTP (Promise to Pay)
    ptp_detected = Column(Boolean, default=False)
    ptp_date = Column(String, nullable=True)  # e.g., "20th of month"
    ptp_amount = Column(Float, nullable=True)
    
    # Risk signals
    life_event_detected = Column(Boolean, default=False)
    life_event_type = Column(String, nullable=True)
    stress_score = Column(Integer, default=50)
    
    # Negotiation
    negotiation_signal = Column(Boolean, default=False)
    objection_detected = Column(Boolean, default=False)
    compliance_flags = Column(JSON, nullable=True)
    
    # AI reasoning
    llm_reasoning = Column(Text, nullable=True)
    agent_guidance = Column(Text, nullable=True)
    
    # Recommendations
    next_action = Column(String)
    next_action_confidence = Column(Float)
    follow_up_actions = Column(JSON, nullable=True)  # List of action items
    
    # LLM full output
    raw_llm_output = Column(JSON, nullable=True)
    
    account = relationship("LoanAccount", back_populates="call_history")

class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    author = Column(String) # system or agent name
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("LoanAccount", back_populates="notes")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    title = Column(String)
    description = Column(Text)
    status = Column(String) # pending, completed
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("LoanAccount", back_populates="tasks")

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    claim_type = Column(String)
    claim_details = Column(Text)
    verification_state = Column(String, default="UNDER_REVIEW") # CLAIMED, UNDER_REVIEW, EVIDENCE_SUBMITTED, VERIFIED, CONTRADICTED, REJECTED
    evidence_provided = Column(JSON, nullable=True)
    created_from_transcript_id = Column(String, ForeignKey("call_history.id"), nullable=True)
    contradicted_flag = Column(Boolean, default=False)
    contradiction_reason = Column(Text, nullable=True)
    claim_confidence = Column(Float, nullable=True)
    source_interaction_id = Column(String, ForeignKey("interactions.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    # Supervisor workflow fields
    reviewer = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    evidence_required = Column(Text, nullable=True)
    source_quote = Column(Text, nullable=True)

    account = relationship("LoanAccount")

class ScoreHistory(Base):
    __tablename__ = "score_history"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    atp_score = Column(Float)
    atp_confidence = Column(Float)
    atp_reasons = Column(JSON)
    
    itp_score = Column(Float)
    itp_confidence = Column(Float)
    itp_reasons = Column(JSON)
    
    contactability_score = Column(Float)
    contactability_confidence = Column(Float)
    contactability_reasons = Column(JSON)
    
    self_cure_score = Column(Float)
    self_cure_confidence = Column(Float)
    self_cure_reasons = Column(JSON)
    
    trust_score = Column(Float)
    trust_confidence = Column(Float)
    trust_reasons = Column(JSON)
    
    trust_gate_status = Column(String, nullable=True)
    model_version = Column(String, default="v2.0")
    score_delta = Column(Float, nullable=True)
    
    account = relationship("LoanAccount")
    
class TrustAuditLog(Base):
    __tablename__ = "trust_audit_logs"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    requested_persona = Column(String)
    final_persona = Column(String)
    requested_nba = Column(String)
    final_nba = Column(String)
    
    gate_status = Column(String)
    reasons = Column(JSON)
    
    trust_score = Column(Float)
    trust_confidence = Column(Float)
    
    gate_version = Column(String)
    model_version = Column(String)
    pipeline_stage = Column(String) # POST_CALL / MANUAL / AI_PROFILE
    
    account = relationship("LoanAccount")

class PTPHistory(Base):
    __tablename__ = "ptp_history"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    ptp_date = Column(DateTime)
    ptp_amount = Column(Float)
    status = Column(String) # HONORED, BROKEN, PENDING
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    account = relationship("LoanAccount")


class ReviewCase(Base):
    """
    Supervisor review workflow entity.
    Created when post-call pipeline detects a change that requires human approval.
    The ONLY path to committing a persona change is Approve on this entity.
    """
    __tablename__ = "review_cases"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("loan_accounts.id"))
    call_id = Column(String, ForeignKey("call_history.id"), nullable=True)

    # Workflow status
    # OPEN / IN_REVIEW / PENDING_DOCUMENTS / APPROVED / REJECTED / ESCALATED / CLOSED
    status = Column(String, default="OPEN")

    # Case classification (business terminology)
    # CLASSIFICATION_CHANGE / UNVERIFIED_CLAIM / SETTLEMENT / ESCALATION / FRAUD / FIELD_OUTCOME
    case_type = Column(String)

    # Persona change under review
    current_persona = Column(String)
    proposed_persona = Column(String, nullable=True)

    # NBA change under review
    current_nba = Column(String, nullable=True)
    proposed_nba = Column(String, nullable=True)

    # Business-language explanation (never internal signal strings)
    review_reason = Column(Text)
    customer_assessment = Column(Text, nullable=True)

    # Evidence extracted from call
    claims_extracted = Column(JSON, nullable=True)   # list of claim dicts
    ptp_extracted = Column(JSON, nullable=True)      # {detected, date, amount}
    sentiment = Column(String, nullable=True)
    objections_extracted = Column(JSON, nullable=True)  # list of strings
    call_summary = Column(Text, nullable=True)

    # Supervisor decision
    assigned_to = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    decision_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Audit trail (list of {timestamp, event, actor})
    audit_timeline = Column(JSON, nullable=True)

    account = relationship("LoanAccount")


