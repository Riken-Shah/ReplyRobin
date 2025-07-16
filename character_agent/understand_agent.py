from typing import List, Optional, Annotated, Any
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import json

# ---------------------------
# 1. Output Schema Definition
# ---------------------------
class StrategyResponse(BaseModel):
    strategy_selected: Optional[int] = Field(None, description="Index of possible_strategies selected (can be null)")
    confidence: Optional[int] = Field(None, description="Confidence from 0 to 10")
    reason: str = Field("", description="Reasoning behind confidence")
    possible_strategies: List[str] = Field(default_factory=list, description="All strategies based on context")
    useful_context_previous_emails: List[int] = Field(default_factory=list, description="Indices of useful previous emails")
    draft_intent: List[str] = Field(default_factory=list, description="Draft intents based on context")

# ---------------------------
# 2. LangGraph State
# ---------------------------
class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    current_email: str
    previous_emails: List[str]

# ---------------------------
# 3. Prompt Construction
# ---------------------------
def build_prompt(current_email: str, previous_emails: List[str]) -> str:
    previous_str = "\n".join(f"{i}. {email}" for i, email in enumerate(previous_emails))
    schema_str = json.dumps(StrategyResponse.model_json_schema(), indent=2)

    return f"""
You are a founder of an app called "Karo". Your name is Mustafa Yusuf. Your job is to figure out the best strategy to respond to the mail based on previous context only.
If no context is found, abstain from replying.

Use previous context as your memory bank and pick the best strategy according to our situation.

Current Email:
{current_email}

Previous Emails:
{previous_str}

Reply using the following JSON Schema format:
{schema_str}
""".strip()

# ---------------------------
# 4. LLM Setup
# ---------------------------
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
parser = JsonOutputParser(pydantic_object=StrategyResponse)

# ---------------------------
# 5. Node Logic
# ---------------------------
def ask_strategy(state: State):
    try:
        prompt_str = build_prompt(state["current_email"], state["previous_emails"])
        response = llm.invoke(prompt_str)
        parsed = parser.invoke(response)

        # Ensure JSON serializable output
        if isinstance(parsed, BaseModel):
            content = parsed.json(indent=2)
        else:
            content = json.dumps(parsed, indent=2)

        return {"messages": [{"role": "assistant", "content": content}]}

    except Exception as e:
        print("Error:", e)
        return {"messages": [{"role": "system", "content": f"Error: {e}"}]}

# ---------------------------
# 6. LangGraph Setup
# ---------------------------
def create_strategy_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("ask_strategy", ask_strategy)
    graph.add_edge(START, "ask_strategy")
    graph.add_edge("ask_strategy", END)
    app = graph.compile()
    return app

def get_strategy(current_email: str, previous_emails: List[str]) -> StrategyResponse:
    state = {
        "current_email": current_email,
        "previous_emails": previous_emails,
        "messages": [{"role": "user", "content": "Analyze the new email"}]
    }
    
    app = create_strategy_graph()
    result = app.invoke(state)
    message = json.loads(result["messages"][-1].content)
    strategy_response = StrategyResponse(
        strategy_selected=int(message["strategy_selected"]) if message["strategy_selected"] is not None else None,
        confidence=int(message["confidence"]),
        reason=message["reason"],
        possible_strategies=message["possible_strategies"],
        useful_context_previous_emails=[int(i) for i in message["useful_context_previous_emails"]],
        draft_intent=message["draft_intent"]
    )
    return strategy_response
    

# ---------------------------
# 7. Run the Graph (Demo)
# ---------------------------
if __name__ == "__main__":
    demo_input = {
        "current_email": "Can we integrate with Slack for notifications and reminders?",
        "previous_emails": [
            "We’ve been discussing internal tooling for notification workflows.",
            "Customer X asked for WhatsApp support last week.",
            "We already support email and in-app notifications."
        ],
        "messages": [{"role": "user", "content": "Analyze the new email"}]
    }

    print(get_strategy(demo_input["current_email"], demo_input["previous_emails"]))
