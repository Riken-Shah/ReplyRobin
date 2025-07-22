from langgraph.graph.message import MessagesState
from typing import List, Dict, Optional
from pydantic import Field, BaseModel


class Email(BaseModel):
    subject: str
    body: str
    sender: str

    def format(self) -> str:
        return f"Subject: {self.subject}; Body: {self.body}"


# Enhanced State Management
class MultiAgentState(MessagesState):
    character_profile: Optional[Dict] = None
    current_email: Email = None
    past_emails: List[Email] = None

    # State mangaged between Drafter and Judge Model
    iteration_count: int = 0
    focus_areas: List[str] = Field(default_factory=list)
    revision_history: List[Dict] = Field(default_factory=list)
    current_scores: Optional[Dict] = None
    weighted_score: float

    # Our planner agent will decide what is our action plan for draft
    draft_plan_selected: str
    draft_plan_confidence: int
    # Filtered past emails which our relevant to our plan
    reference_emails: List[str] = Field(default_factory=list)

    # Current draft stored by our Drafter Agent
    current_draft: Optional[str] = None


# Maximum allowed iteration between drafter-judge agent
MAX_ITERATIONS = 3
APPROVAL_THRESHOLD = 7.0
