from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from typing import Literal, List
from langgraph.pregel.call import P
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from common.schemas import CharacterProfile
from agent_orchestration.draft_agent.system_prompt import make_prompt
from agent_orchestration.draft_agent.respone_schema import DraftAgentResponse
from agent_orchestration.master_agent.state import MultiAgentState


def create_agent(
    llm: ChatGoogleGenerativeAI,
    character_profile: CharacterProfile,
    reference_emails: List[str],
    current_email: str,
):
    """Draft agent which will generate a draft for email"""
    return create_react_agent(
        llm,
        tools=[],
        prompt=make_prompt(character_profile, reference_emails, current_email),
        response_format=DraftAgentResponse,
    )


def drafter_node(state: MultiAgentState) -> Command[Literal["judge"]]:
    """Enhanced drafter node with memory management"""
    # Create agent with current context
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    drafter_agent = create_agent(
        llm,
        state.get("character_profile"),
        state.get("reference_emails"),
        state.get("current_email"),
    )

    # Add context from previous iterations
    context_messages = []

    context_messages.append(
        HumanMessage(
            content="Can you please draft correct intent and lingusitic correct draft."
        )
    )
    if state.get("focus_areas"):
        focus_context = f"PRIORITY FOCUS AREAS: {', '.join(state['focus_areas'])}"
        context_messages.append(HumanMessage(content=focus_context))

    # Include previous draft for revision
    if state.get("current_draft") and state["iteration_count"] > 0:
        revision_context = f"CURRENT DRAFT TO REVISE:\n{state['current_draft']}"
        context_messages.append(HumanMessage(content=revision_context))

    # Invoke agent with context
    enhanced_state = {**state, "messages": state["messages"] + context_messages}
    result = drafter_agent.invoke(enhanced_state)

    # Extract the draft from the response
    draft_content: DraftAgentResponse = result["structured_response"]

    # Update state and return
    updated_state = {
        "messages": result["messages"],
        "current_draft": draft_content,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }

    # Ensure proper message format
    result["messages"][-1] = HumanMessage(
        content=draft_content.get_draft(), name="drafter"
    )

    return Command(update=updated_state, goto="judge")
