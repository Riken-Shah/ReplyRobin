from agent_orchestration.master_agent.orchestrator import email_drafter_agent_workflow
from typing import List, Optional
from db.schemas import CharacterProfile
from agent_orchestration.master_agent.state import MultiAgentState, Email
from pydantic import BaseModel


class WorkerResponseSchema(BaseModel):
    final_draft: Optional[str]
    iteration_count: int


class Worker:
    def __init__(self):
        # Complile the workflow once and then use it
        self.__graph_workflow = email_drafter_agent_workflow()

    def run_agent(
        self,
        character_profile: CharacterProfile,
        current_email: Email,
        past_emails: List[Email],
    ) -> WorkerResponseSchema:
        zero_state = MultiAgentState(
            current_email=current_email,
            character_profile=character_profile,
            past_emails=past_emails,
        )

        # Workflow
        final_state = self.__graph_workflow.invoke(
            zero_state,
        )

        current_draft = final_state.get("current_draft", None)

        print(
            "Final draft after all iterations: ",
            current_draft.get_draft() if current_draft else None,
        )
        return WorkerResponseSchema(
            final_draft=current_draft.get_draft() if current_draft else None,
            iteration_count=final_state.get("iteration_count", 0),
        )
