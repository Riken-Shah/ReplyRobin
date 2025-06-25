from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage
from typing import Literal, List, Dict, Optional
from langgraph.pregel.call import P
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from common.schemas import CharacterProfile
from pydantic import Field
import logging
import logging

# Enhanced State Management
class EmailDraftState(MessagesState):
    character_profile: Optional[Dict] = None
    past_emails: Optional[List[str]] = None
    current_draft: Optional[str] = None
    revision_history: List[Dict] = Field(default_factory=list)
    iteration_count: int = 0
    current_scores: Optional[Dict] = None
    focus_areas: List[str] = Field(default_factory=list)
    email_context: Optional[str] = None
    target_recipient: Optional[str] = None
    required_intents: Optional[List[str]] = None

# Configuration
MAX_ITERATIONS = 5
APPROVAL_THRESHOLD = 8.0

# Base LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Enhanced Prompt Templates
def make_drafter_prompt(character_profile: Dict, past_emails: List[str], required_intents: List[str], email_context: str = "") -> str:
    """Create detailed drafter prompt with character profile specifics"""
    
    # Extract key metrics safely
    avg_length = character_profile.avg_cleaned_length
    ellipsis_freq = character_profile.avg_ellipsis_frequency
    exclamation_density = character_profile.avg_exclamation_density
    uses_caps = character_profile.uses_caps_for_emphasis
    uses_parentheses = character_profile.uses_inline_parentheses
    
    # Build examples section
    examples_section = ""
    if past_emails:
        examples_section = f"""
REFERENCE EXAMPLES - Actual emails from the target user:
{chr(10).join([f"EXAMPLE {i+1}:{chr(10)}{email}{chr(10)}" for i, email in enumerate(past_emails[:2])])}

Study these examples for natural flow, vocabulary, transitions, and tone.
"""

    return f"""You are an Email Style Mimicry Expert. Write/revise emails to perfectly match a specific user's writing style.

{examples_section}

STYLE PROFILE TO MATCH:
- Target email length: {avg_length} words (±20% acceptable)
- Punctuation patterns: {ellipsis_freq} ellipsis per message, {exclamation_density} exclamation density
- Emphasis style: {"Uses CAPS for emphasis" if uses_caps else "Avoids caps emphasis"}
- Parentheses usage: {"Frequently uses (inline parentheses)" if uses_parentheses else "Rarely uses parentheses"}

LINGUISTIC PATTERNS:
- Hedge words per message: {character_profile.avg_num_hedge_words}  
  Favorites: {character_profile.top_hedge_words}
- Modal verbs per message: {character_profile.avg_num_modal_verbs}
  Favorites: {character_profile.top_modal_verbs}
- Politeness markers: {character_profile.avg_num_politeness_markers}
  Favorites: {character_profile.top_politeness_markers}
- Passive voice frequency: {character_profile.avg_num_passive_patterns}

STYLISTIC ELEMENTS:
- Typical greetings: {character_profile.top_greeting_phrases}
- Common sentence starters: {character_profile.top_sentence_starters}
- Emoji usage: {character_profile.avg_num_emoji} per message
  Favorites: {character_profile.top_emoji_usage}
- Question patterns: {character_profile.top_question_phrases}
- Discourse markers: {character_profile.top_discourse_markers}

EMAIL CONTEXT: {email_context}

REQUIRED INTENTS: {required_intents}

REVISION INSTRUCTIONS:
1. Match the target word count (±20%)
2. Incorporate the user's favorite phrases naturally
3. Mirror their punctuation and emphasis patterns
4. Use their preferred greeting and closing styles
5. Maintain their level of formality/casualness
6. Address any specific feedback from previous iterations

Write a complete email that sounds authentically like this user."""

def make_judge_prompt(character_profile: Dict, required_intents: List[str] = None) -> str:
    """Create comprehensive judge evaluation prompt with intent checking"""
    
    intent_section = ""
    if required_intents:
        intent_list = "\n   ".join([f"- {intent}" for intent in required_intents])
        intent_section = f"""
5. INTENT FULFILLMENT (Weight: 20%)
   Check if the email fulfills ALL required intents:
   {intent_list}
   - Score 10/10 if ALL intents are clearly addressed
   - Score 8/10 if most intents addressed but some could be clearer
   - Score 6/10 if some intents missing or poorly addressed
   - Score 4/10 or lower if major intents are missing or unclear
"""
    
    return f"""You are a Style Matching Evaluator. Provide detailed scoring of how well the draft matches the target user's writing style AND fulfills the required intent.

EVALUATION CRITERIA - Score each section 0-10:

1. STRUCTURE & LENGTH (Weight: 15%)
   - Target length: {character_profile.avg_cleaned_length} words
   - Appropriate paragraph structure
   - Overall email organization

2. LINGUISTIC PATTERNS (Weight: 30%)
   - Hedge words: Target {character_profile.avg_num_hedge_words}
     Should use: {character_profile.top_hedge_words}
   - Modal verbs: Target {character_profile.avg_num_modal_verbs}
     Should use: {character_profile.top_modal_verbs}
   - Politeness: Target {character_profile.avg_num_politeness_markers}
     Should use: {character_profile.top_politeness_markers}
   - Passive voice: Target {character_profile.avg_num_passive_patterns}

3. STYLISTIC ELEMENTS (Weight: 20%)
   - Greeting matches: {character_profile.top_greeting_phrases}
   - Sentence starters: {character_profile.top_sentence_starters}
   - Punctuation: Ellipsis {character_profile.avg_ellipsis_frequency}, Exclamation {character_profile.avg_exclamation_density}
   - Caps usage: {"Should use CAPS for emphasis" if character_profile.uses_caps_for_emphasis else "Should avoid CAPS"}
   - Emoji usage: {character_profile.avg_num_emoji} per message

4. AUTHENTICITY (Weight: 15%)
   - Natural flow and rhythm
   - Maintains user's personality
   - Uses typical discourse markers: {character_profile.top_discourse_markers}
   - Sounds genuinely like the user

{intent_section}

SCORING INSTRUCTIONS:
- Score each category individually (0-10)
- DO NOT calculate weighted average yourself - just provide the individual scores
- Provide detailed reasoning for each score

FORMAT YOUR RESPONSE EXACTLY AS:
SCORE BREAKDOWN:
- Structure & Length: X/10 (reason)
- Linguistic Patterns: X/10 (reason)  
- Stylistic Elements: X/10 (reason)
- Authenticity: X/10 (reason)
{f"- Intent Fulfillment: X/10 (reason)" if required_intents else ""}

DETAILED FEEDBACK:
[Specific areas to improve with examples and suggestions]

FOCUS AREAS FOR NEXT ITERATION:
[List 2-3 most critical improvements needed]"""

def calculate_weighted_score(scores: Dict) -> float:
    """Calculate weighted average from individual scores"""
    weights = {
        'structure': 0.15,
        'linguistic': 0.30,
        'stylistic': 0.20,
        'authenticity': 0.15,
        'intent_fulfillment': 0.20
    }
    
    weighted_sum = 0
    total_weight = 0
    
    for category, weight in weights.items():
        if category in scores and scores[category] is not None:
            weighted_sum += scores[category] * weight
            total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0

def parse_judge_scores(evaluation: str) -> Dict:
    """Parse individual scores from judge evaluation"""
    scores = {}
    
    try:
        lines = evaluation.split('\n')
        for line in lines:
            if 'Structure & Length:' in line:
                score_str = line.split(':')[1].strip().split('/')[0]
                scores['structure'] = float(score_str)
            elif 'Linguistic Patterns:' in line:
                score_str = line.split(':')[1].strip().split('/')[0]
                scores['linguistic'] = float(score_str)
            elif 'Stylistic Elements:' in line:
                score_str = line.split(':')[1].strip().split('/')[0]
                scores['stylistic'] = float(score_str)
            elif 'Authenticity:' in line:
                score_str = line.split(':')[1].strip().split('/')[0]
                scores['authenticity'] = float(score_str)
            elif 'Intent Fulfillment:' in line:
                score_str = line.split(':')[1].strip().split('/')[0]
                scores['intent_fulfillment'] = float(score_str)
    except Exception as e:
        print(f"Error parsing scores: {e}")
    
    return scores

# ----- AGENT DEFINITIONS -----

def make_system_prompt(role_description: str) -> str:
    """Create system prompt with role description"""
    return f"""You are an AI assistant specialized in email drafting.

{role_description}

Respond with a well-crafted email that matches the requested style and context."""

def create_drafter_agent(character_profile: Dict, past_emails: List[str], required_intents: List[str], email_context: str = ""):
    """Create drafter agent with dynamic prompt"""
    drafter_prompt = make_drafter_prompt(character_profile, past_emails, required_intents, email_context)
    # print(drafter_prompt)
    system_prompt = make_system_prompt(drafter_prompt)
    return create_react_agent(
        llm,
        tools=[],
        prompt=system_prompt
    )

def create_judge_agent(character_profile: Dict, required_intents: List[str]):
    """Create judge agent with comprehensive evaluation prompt"""
    # print("Judge Prompt: ", make_judge_prompt(character_profile, required_intents))
    return create_react_agent(
        llm,
        tools=[],
        prompt=make_system_prompt(make_judge_prompt(character_profile, required_intents))
    )

def drafter_node(state: EmailDraftState) -> Command[Literal["judge"]]:
    logging.info(f"--- Iteration {state.get('iteration_count', 0)}: Drafter Node ---")
    """Enhanced drafter node with memory management"""
    
    # Create agent with current context
    drafter_agent = create_drafter_agent(
        state["character_profile"], 
        state["past_emails"], 
        state.get("required_intents", []),
        state.get("email_context", "")
    )
    
    # Add context from previous iterations
    context_messages = []
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
    last_message = result["messages"][-1]
    draft_content = last_message.content
    
    # Update state and return
    logging.info(f"Draft generated: {draft_content[:200]}...")
    updated_state = {
        "messages": result["messages"],
        "current_draft": draft_content,
        "iteration_count": state.get("iteration_count", 0) + 1
    }
    
    # Ensure proper message format
    result["messages"][-1] = HumanMessage(
        content=draft_content,
        name="drafter"
    )
    
    return Command(
        update=updated_state,
        goto="judge"
    )

def judge_node(state: EmailDraftState) -> Command[Literal["drafter", END]]:
    logging.info(f"--- Iteration {state.get('iteration_count', 0)}: Judge Node ---")
    """Enhanced judge node with detailed evaluation and loop protection"""
    
    # Check iteration limit
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return Command(
            update={"messages": state["messages"] + [HumanMessage(
                content=f"FINAL ANSWER: Maximum iterations reached. Current draft accepted.",
                name="judge"
            )]},
            goto=END
        )
    
    # Create judge agent
    judge_agent = create_judge_agent(state["character_profile"], state.get("required_intents", []))
    
    # Add evaluation context
    eval_context = f"DRAFT TO EVALUATE:\n{state.get('current_draft', '')}\n\nIteration: {state.get('iteration_count', 0)}"
    context_message = HumanMessage(content=eval_context)
    
    enhanced_state = {**state, "messages": state["messages"] + [context_message]}
    result = judge_agent.invoke(enhanced_state)
    # print("Judge Result: ", result)
    
    last_message = result["messages"][-1]
    evaluation = last_message.content
    
    # Parse evaluation for individual scores and calculate weighted average
    individual_scores = parse_judge_scores(evaluation)
    weighted_score = calculate_weighted_score(individual_scores) if individual_scores else 0
    
    current_scores = {
        **individual_scores,
        'weighted_total': weighted_score
    }
    
    # Check if we should approve (weighted score >= threshold)
    should_approve = weighted_score >= APPROVAL_THRESHOLD
    
    focus_areas = []
    
    try:
        if "FOCUS AREAS FOR NEXT ITERATION:" in evaluation:
            focus_section = evaluation.split("FOCUS AREAS FOR NEXT ITERATION:")[1]
            focus_areas = [area.strip() for area in focus_section.split('\n') if area.strip() and not area.startswith('[')]
    
    except Exception as e:
        print(f"Error parsing focus areas: {e}")
    
    # Create final response with calculated weighted score
    final_evaluation = f"{evaluation}\n\nCALCULATED WEIGHTED TOTAL: {weighted_score:.2f}/10"

    if should_approve:
        logging.info(f"Judge approved draft with score {weighted_score:.2f}.")
        final_evaluation += f"\n\nFINAL ANSWER: {weighted_score:.2f}/10 - Draft approved (threshold: {APPROVAL_THRESHOLD})"
    else:
        logging.info(f"Judge requested revision. Score: {weighted_score:.2f}. Focus areas: {focus_areas}")

    # Update revision history
    revision_entry = {
        "iteration": state.get("iteration_count", 0) -1,
        "draft": state.get("current_draft", ""),
        "evaluation": evaluation,
        "scores": current_scores,
        "focus_areas": focus_areas
    }
    updated_revision_history = state.get("revision_history", []) + [revision_entry]

    result["messages"][-1] = HumanMessage(
        content=final_evaluation,
        name="judge"
    )

    return {
        "messages": result["messages"],
        "current_scores": current_scores,
        "focus_areas": focus_areas,
        "revision_history": updated_revision_history
    }

# ----- WORKFLOW SETUP -----

def should_continue(state: EmailDraftState) -> Literal["judge", "drafter", "end"]:
    """Determine whether to continue drafting or end."""
    iteration = state.get("iteration_count", 0)
    scores = state.get("current_scores", {})
    weighted_score = calculate_weighted_score(scores)

    if weighted_score >= APPROVAL_THRESHOLD:
        logging.info("--- Workflow Complete: Draft Approved ---")
        return "end"
    if iteration >= MAX_ITERATIONS:
        logging.warning("--- Workflow Complete: Max Iterations Reached ---")
        return "end"
    return "drafter"

def create_email_style_workflow():
    """Create the enhanced workflow graph"""
    workflow = StateGraph(EmailDraftState)
    workflow.add_node("drafter", drafter_node)
    workflow.add_node("judge", judge_node)

    workflow.set_entry_point("drafter")

    workflow.add_edge("drafter", "judge")
    workflow.add_conditional_edges(
        "judge",
        should_continue,
        {
            "drafter": "drafter",
            "end": END
        }
    )

    return workflow.compile()

# ----- USAGE EXAMPLE -----
def run_email_generation(character_profile: CharacterProfile, past_emails: List[str], 
                        email_context: str, initial_request: str = "Write a crisp and concise email", required_intents: List[str] = None):
    logging.info("--- Starting Email Generation Workflow ---")
    """Run the email generation workflow"""
    
    # Create workflow
    graph = create_email_style_workflow()
    
    # Initial state
    initial_state = {
        "messages": [HumanMessage(content=initial_request)],
        "character_profile": character_profile,
        "past_emails": past_emails,
        "email_context": email_context,
        "iteration_count": 0,
        "revision_history": [],
        "focus_areas": [],
        "required_intents": required_intents
    }
    
    # Run workflow
    final_state = graph.invoke(initial_state)
    
    return {
        "final_draft": final_state.get("current_draft"),
        "final_evaluation": final_state["messages"][-1].content,
        "revision_history": final_state.get("revision_history", []),
        "total_iterations": final_state.get("iteration_count", 0)
    }

# Example usage:
if __name__ == "__main__":
    # Example character profile (simplified)
    sample_profile = {
        "avg_cleaned_length": 150,
        "avg_ellipsis_frequency": 0.5,
        "avg_exclamation_density": 0.2,
        "uses_caps_for_emphasis": True,
        "uses_inline_parentheses": False,
        "avg_num_hedge_words": 2.0,
        "top_hedge_words": ["maybe", "perhaps", "I think"],
        "avg_num_modal_verbs": 1.5,
        "top_modal_verbs": ["could", "should", "might"],
        "top_greeting_phrases": ["Hi there", "Hello"],
        "top_politeness_markers": ["please", "thank you"]
    }
    
    sample_past_emails = [
        "Hi there! I think we should maybe schedule a meeting for next week. Let me know what works for you. Thanks!",
        "Hello, I wanted to follow up on our discussion. Could we perhaps finalize the details? I'd appreciate your input."
    ]
    
    result = run_email_generation(
        character_profile=sample_profile,
        past_emails=sample_past_emails,
        email_context="Following up on a project deadline",
        initial_request="Write an email asking about project status and next steps",
        required_intents=["Request for information", "Follow up"]
    )
    
    logging.info(f"Final Draft: {result.get('final_draft')}")
    logging.info(f"Total Iterations: {result.get('total_iterations')}")