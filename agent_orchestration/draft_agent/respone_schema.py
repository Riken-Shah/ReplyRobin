from pydantic import Field, BaseModel


# Draft Agent Response
class DraftAgentResponse(BaseModel):
    "Draft response from the agent"

    draft: str = Field(description="Intermediatary draft generated")
