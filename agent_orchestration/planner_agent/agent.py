from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from typing import Literal, List
from langgraph.pregel.call import P
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from agent_orchestration.planner_agent.system_prompt import make_prompt
from agent_orchestration.planner_agent.respone_schema import PlannerAgentResponse
from agent_orchestration.master_agent.state import MultiAgentState, Email
from pprint import pprint


def create_agent(llm, current_email: Email, past_emails: List[Email]):
    """Planner agent which will layout a plan for drafting the email"""
    return create_react_agent(
        llm,
        tools=[],
        prompt=make_prompt(current_email, past_emails),
        response_format=PlannerAgentResponse,
    )


def planner_node(state: MultiAgentState) -> Command[Literal["drafter"]]:
    """This is a planner node responsible to layout a plan for us to draft the node, it can also decide if we can move ahead or not"""
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", thinking_config={"include_thoughts": True}
    )
    planner_agent = create_agent(
        llm,
        state.get("current_email"),
        state.get("past_emails", []),
    )

    state["messages"] = [
        HumanMessage(content="Figure out a best stragey moving forward")
    ]

    result = planner_agent.invoke(state)

    planner_response: PlannerAgentResponse = result["structured_response"]
    # TODO add logging of all the plans LLM have come to based on previous emails
    print(f"We found {len(planner_response.possible_strategies)} possible plans.")

    if planner_response.strategy_selected is not None:
        print(
            "Selected plan: ",
            planner_response.possible_strategies[
                planner_response.strategy_selected
            ].stragy,
        )

    # If we cannot figure the suitable plan it is better to drop-out from here.
    selected_plan_cited_emails = (
        planner_response.possible_strategies[
            planner_response.strategy_selected
        ].citation_of_previous_email
        if planner_response.strategy_selected is not None
        else []
    )
    if not len(selected_plan_cited_emails):
        print("We cannot find any citation for slected plan, hence skipping this")
        planner_response.strategy_selected = None

    past_emails = state.get("past_emails")
    print([i for i, _ in enumerate(selected_plan_cited_emails)])
    return {
        # Sometimes AI fucks up and adds non-existent indexes to this, so right now we are avoiding "Out of Index" error
        "reference_emails": [
            past_emails[i] if i < len(past_emails) else ""
            for i in selected_plan_cited_emails
        ],
        "draft_plan_selected": planner_response.strategy_selected,
        "draft_plan_confidence": planner_response.confidence,
    }
