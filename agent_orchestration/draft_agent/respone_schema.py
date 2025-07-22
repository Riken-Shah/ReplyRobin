from pydantic import Field, BaseModel
from enum import Enum
from typing import List


class SectionType(Enum):
    GREETING = "greeting"
    CORE = "core"
    SIGNOFF = "signoff"


class DraftBlob(BaseModel):
    section: str = Field(
        description="Text blob which is self-contained and optionally can have citations"
    )
    type: SectionType = Field(description="Type of section")
    citations: List[int] = Field(
        default_factory=list,
        description="Indexes of emails from which this is used OR -1 if current_email ",
    )
    actions: List[str] = Field(
        default_factory=list,
        description="Define the actions that will make the current section valid",
    )


# Draft Agent Response
class DraftAgentResponse(BaseModel):
    "Draft response from the agent"

    blobs: List[DraftBlob] = Field(
        default_factory=list,
        description="Continous draft blob which will merge to form the draft",
    )

    def get_draft(self) -> str:
        return "".join([blob.section for blob in self.blobs])
