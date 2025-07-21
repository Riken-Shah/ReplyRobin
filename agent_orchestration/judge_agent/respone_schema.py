from typing import List
from pydantic import Field, BaseModel


class Scores(BaseModel):
    structure_score: int = Field(
        description="Structure score based on draft and reference email"
    )
    linguistic_score: int = Field(
        description="Linguistic score based on draft and lingustic metrics"
    )
    stylistic_score: int = Field(
        description="Stylistic score based on draft and lingustic metrics"
    )
    authenticity_score: int = Field(
        description="Authenticity score based on draft and reference email"
    )
    intent_fulfillment_score: int = Field(
        description="Intent score based on draft and reference email"
    )


# Judge Agent Response
class JudgeAgentResponse(BaseModel):
    "Judge agent response from the agent"

    focus_area_for_next_iteraion: List[str] = Field(
        default_factory=list,
        description="What should we improve in next iteration for better score, this is optional",
    )
    scores: Scores = Field(description="Scores of current iteration")
