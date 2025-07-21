from langgraph.graph import END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from typing import Literal, List, Dict
from langgraph.pregel.call import P
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from agent_orchestration.judge_agent.system_prompt import make_prompt
from agent_orchestration.master_agent.state import MultiAgentState, MAX_ITERATIONS
from agent_orchestration.judge_agent.respone_schema import JudgeAgentResponse, Scores
from agent_orchestration.master_agent.state import Email


def create_agent(
    llm: ChatGoogleGenerativeAI,
    character_profile: Dict,
    reference_emails: List[str],
    current_email: Email,
):
    """Create judge agent with comprehensive evaluation prompt"""
    return create_react_agent(
        llm,
        tools=[],
        prompt=make_prompt(character_profile, reference_emails, current_email),
        response_format=JudgeAgentResponse,
    )


def calculate_weighted_score(scores: Scores) -> float:
    """Calculate weighted average from individual scores"""
    weights = {
        "structure_score": 0.15,
        "linguistic_score": 0.30,
        "stylistic_score": 0.20,
        "authenticity_score": 0.15,
        "intent_fulfillment_score": 0.20,
    }

    weighted_sum = 0
    total_weight = 0

    scores_dict = dict(scores)

    for category, weight in weights.items():
        print(f"{category}: {scores_dict[category]}")
        if scores_dict[category] is not None:
            weighted_sum += scores_dict[category] * weight
            total_weight += weight
            print(f"total_weight: {total_weight}")

    return weighted_sum / total_weight if total_weight > 0 else 0


def judge_node(state: MultiAgentState) -> Command[Literal["drafter", END]]:
    """Enhanced judge node with detailed evaluation and loop protection"""
    # Check iteration limit
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return Command(
            update={
                "messages": state["messages"]
                + [
                    HumanMessage(
                        content=f"FINAL ANSWER: Maximum iterations reached. Current draft accepted.",
                        name="judge",
                    )
                ]
            },
            goto=END,
        )

    # Create judge agent
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    judge_agent = create_agent(
        llm,
        state.get("character_profile"),
        state.get("reference_emails", []),
        state.get("current_email"),
    )

    # Add evaluation context
    eval_context = f"DRAFT TO EVALUATE:\n{state.get('current_draft', '')}\n\nIteration: {state.get('iteration_count', 0)}"
    context_message = HumanMessage(content=eval_context)
    enhanced_state = {**state, "messages": state["messages"] + [context_message]}
    result = judge_agent.invoke(enhanced_state)

    evaluation: JudgeAgentResponse = result["structured_response"]

    # Parse evaluation for individual scores and calculate weighted average
    weighted_score = calculate_weighted_score(evaluation.scores)

    current_scores = {**dict(evaluation.scores), "weighted_total": weighted_score}

    focus_areas = evaluation.focus_area_for_next_iteraion

    print(
        "Judge Model: ",
        "Current Score: ",
        current_scores,
        "Weighted Score: ",
        weighted_score,
        "Focus Area: ",
        focus_areas,
    )

    # Create final response with calculated weighted score
    final_evaluation = (
        f"{evaluation}\n\nCALCULATED WEIGHTED TOTAL: {weighted_score:.2f}/10"
    )

    # Update revision history
    revision_entry = {
        "iteration": state.get("iteration_count", 0) - 1,
        "draft": state.get("current_draft", ""),
        "evaluation": evaluation,
        "scores": current_scores,
        "focus_areas": focus_areas,
    }
    updated_revision_history = state.get("revision_history", []) + [revision_entry]

    result["messages"][-1] = HumanMessage(content=final_evaluation, name="judge")

    print("Score: ", weighted_score)

    return {
        "messages": result["messages"],
        "current_scores": current_scores,
        "focus_areas": focus_areas,
        "revision_history": updated_revision_history,
        "weighted_score": weighted_score,
    }
