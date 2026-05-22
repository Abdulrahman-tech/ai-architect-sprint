# schemas.py — Day 10: Pydantic schemas for ClinAssist structured output
from pydantic import BaseModel, Field, field_validator
from typing import Literal, List, Optional
from datetime import datetime
from enum import Enum


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class TriageRecommendation(str, Enum):
    MONITOR = "Monitor at home"
    ROUTINE = "Schedule routine appointment (3-7 days)"
    URGENT = "See doctor today or tomorrow"
    EMERGENCY = "Go to emergency room immediately"


class EvidenceSource(BaseModel):
    source: str = Field(description="Source name e.g. WHO, NHS")
    title: str = Field(description="Document title")
    excerpt: str = Field(description="Relevant excerpt")
    relevance_score: float = Field(ge=0.0, le=1.0)


class ClinicalSummary(BaseModel):
    """Schema-validated clinical summary for ClinAssist."""

    patient_reported_symptoms: str
    urgency_level: UrgencyLevel
    triage_recommendation: TriageRecommendation
    symptom_summary: str = Field(min_length=10, max_length=500)
    evidence_sources: List[EvidenceSource] = Field(min_length=1)
    professional_consultation_required: bool = Field(default=True)
    disclaimer: str = Field(
        default=(
            "This assessment is for general guidance only and does not "
            "constitute medical advice. Always consult a qualified "
            "healthcare professional."
        )
    )
    assessed_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    @field_validator("professional_consultation_required")
    @classmethod
    def must_require_consultation(cls, v):
        if not v:
            raise ValueError("professional_consultation_required must always be True")
        return v

    @field_validator("disclaimer")
    @classmethod
    def disclaimer_must_mention_professional(cls, v):
        if "professional" not in v.lower() and "doctor" not in v.lower():
            raise ValueError("Disclaimer must mention consulting a professional")
        return v


def validate_clinical_summary(data: dict):
    """Validate a dict against ClinicalSummary schema.
    Returns (is_valid, summary_object, error_message)
    """
    try:
        summary = ClinicalSummary(**data)
        return True, summary, ""
    except Exception as e:
        return False, None, str(e)


def format_summary_report(summary: ClinicalSummary) -> str:
    """Format a validated ClinicalSummary into a readable report."""
    urgency_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "EMERGENCY": "🚨"}
    lines = [
        "=" * 55,
        "CLINASSIST CLINICAL SUMMARY REPORT",
        f"Generated: {summary.assessed_at}",
        "=" * 55,
        "",
        "SYMPTOMS REPORTED:",
        f"  {summary.patient_reported_symptoms}",
        "",
        f"URGENCY: {urgency_emoji.get(summary.urgency_level.value, '⚪')} {summary.urgency_level.value}",
        f"RECOMMENDATION: {summary.triage_recommendation.value}",
        "",
        "CLINICAL SUMMARY:",
        f"  {summary.symptom_summary}",
        "",
        "EVIDENCE SOURCES:",
    ]
    for i, src in enumerate(summary.evidence_sources, 1):
        lines.append(f"  [{i}] {src.source} — {src.title}")
        lines.append(f"      Relevance: {src.relevance_score}")
    lines += [
        "",
        f"CONSULTATION REQUIRED: {'Yes ✅' if summary.professional_consultation_required else 'No'}",
        "",
        "⚠️  DISCLAIMER:",
        f"  {summary.disclaimer}",
        "=" * 55,
    ]
    return "\n".join(lines)
