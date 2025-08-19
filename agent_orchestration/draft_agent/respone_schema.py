from pydantic import Field, BaseModel
from enum import Enum
from typing import List


class SectionType(Enum):
    INTRO = "intro"
    CORE_SECTION = "core-section"
    REACH_OUT_FOR_MORE_HELP = "reach-out-for-more-help"
    SIGN_OFF = "sign-off"


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
        # Ensure sections are in the correct order
        section_order = [
            SectionType.INTRO,
            SectionType.CORE_SECTION,
            SectionType.REACH_OUT_FOR_MORE_HELP,
            SectionType.SIGN_OFF,
        ]

        # Create a mapping of section types to blobs
        section_map = {blob.type: blob for blob in self.blobs}

        # Build the draft in the correct order
        ordered_sections = []
        for section_type in section_order:
            if section_type in section_map:
                ordered_sections.append(section_map[section_type].section)

        return "\n\n".join(ordered_sections)

    def validate_sections(self) -> bool:
        """Validate that all required sections are present"""
        required_sections = {
            SectionType.INTRO,
            SectionType.CORE_SECTION,
            SectionType.REACH_OUT_FOR_MORE_HELP,
            SectionType.SIGN_OFF,
        }

        present_sections = {blob.type for blob in self.blobs}
        return required_sections.issubset(present_sections)
