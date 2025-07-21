from langgraph.graph import StateGraph, END
from typing import Literal
import logging
from character_agent.master_agent.state import (
    MAX_ITERATIONS,
    APPROVAL_THRESHOLD,
    MultiAgentState,
)
from character_agent.draft_agent.agent import drafter_node
from character_agent.judge_agent.agent import judge_node
from character_agent.planner_agent.agent import planner_node


def should_continue_with_drafter_judge_loop(
    state: MultiAgentState,
) -> Literal["judge", "drafter", "end"]:
    """Determine whether to continue drafting or end."""
    iteration = state.get("iteration_count", 0)
    weighted_score = state.get("weighted_score", {})

    if weighted_score >= APPROVAL_THRESHOLD:
        logging.info("--- Workflow Complete: Draft Approved ---")
        return "end"
    if iteration >= MAX_ITERATIONS:
        logging.warning("--- Workflow Complete: Max Iterations Reached ---")
        return "end"
    return "drafter"


def should_continue_with_drafter_or_exit(
    state: MultiAgentState,
) -> Literal["judge", "drafter", "end"]:
    """Determine whether to continue drafting or end."""
    draft_plan_selected = state.get("draft_plan_selected")
    reference_emails = state.get("reference_emails", [])
    if len(reference_emails) == 0 or draft_plan_selected == "":
        logging.info(
            "--- Workflow Complete: No plan selected or lack of reference emails ---"
        )
        return "end"
    return "drafter"


def email_drafter_agent_workflow():
    """Create the enhanced workflow graph"""
    workflow = StateGraph(MultiAgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("drafter", drafter_node)
    workflow.add_node("judge", judge_node)

    workflow.set_entry_point("planner")
    workflow.add_conditional_edges(
        "planner",
        should_continue_with_drafter_or_exit,
        {"drafter": "drafter", "end": END},
    )
    workflow.add_edge("drafter", "judge")
    workflow.add_conditional_edges(
        "judge",
        should_continue_with_drafter_judge_loop,
        {"drafter": "drafter", "end": END},
    )

    return workflow.compile()
