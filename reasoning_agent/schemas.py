"""
Schemas for structured output in reasoning agent
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class IntentAnalysisOutput(BaseModel):
    """Schema for intent analysis output"""

    primary_intent: str = Field(description="The primary intent detected in the email")
    all_intents: List[str] = Field(
        description="List of all intents detected in the email", default_factory=list
    )
    confidence_score: float = Field(
        description="Confidence score for the primary intent (0.0-1.0)", ge=0.0, le=1.0
    )
    context_summary: Optional[str] = Field(
        description="Brief summary of the email context", default=None
    )


class InfoRequirementOutput(BaseModel):
    """Schema for information requirement output"""

    requirement_type: str = Field(
        description="Type of information required (e.g., 'billing_info', 'account_details')"
    )
    description: str = Field(description="Description of the required information")
    is_sensitive: bool = Field(
        description="Whether this information is sensitive/confidential", default=False
    )
    confidence: float = Field(
        description="Confidence that this information is required (0.0-1.0)",
        ge=0.0,
        le=1.0,
        default=0.0,
    )


class InfoRequirementsOutput(BaseModel):
    """Schema for overall information requirements output"""

    required_info: List[InfoRequirementOutput] = Field(
        description="List of all required information items", default_factory=list
    )


class ResponseCapabilityOutput(BaseModel):
    """Schema for response capability assessment output"""

    can_respond: bool = Field(
        description="Whether we have enough information to respond"
    )
    safe_to_proceed: bool = Field(
        description="Whether it's safe to proceed with automated response", default=True
    )
    confidence_score: float = Field(
        description="Confidence score for the capability assessment (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )
    response_template: Optional[str] = Field(
        description="Optional template or guidance for the response", default=None
    )
