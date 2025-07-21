from typing import List, Optional
from pydantic import Field, BaseModel


# Planner Agent Response
class PlannerAgentResponse(BaseModel):
    "Precise and descriptive response of our planner agent"

    # We might extend this later to be more descriptive and more detailed
    possible_strategies: List[str] = Field(
        default_factory=list,
        description="List down all possible straegies based on previous email context",
    )
    # Our agent makes the descion of selecting the best plan, assesing current email and previous email context
    strategy_selected: Optional[int] = Field(
        None,
        description="Index of selected possible_strategies, it can be null if no one is found fit or you are unsure",
    )
    # Now describe how sure are you about the selected plan
    confidence: Optional[int] = Field(
        None,
        description="Confidence from 0 to 10 if selected plan can give the satisfid response based on email context",
    )
    reason: Optional[str] = Field(
        "",
        description="One liner reasoning why the selected plan is best, if yes, why yes? and no, why no?",
    )
    useful_context_previous_emails: List[int] = Field(
        default_factory=list,
        description="Indices of past email we used to come to descion of selected strategy_selected",
    )
