from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import MessagesState
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Literal, List, Dict, Optional, Tuple, Any
from langgraph.types import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from enum import Enum
from pydantic import BaseModel, Field
from langgraph.store.memory import InMemoryStore
import logging

# Import structured output schemas
from reasoning_agent.schemas import (
    IntentAnalysisOutput,
    InfoRequirementOutput,
    InfoRequirementsOutput,
)

# Import the tools we created
from reasoning_agent.tools import (
    get_billing_information,
    get_account_information,
    search_faqs,
    get_custom_instruction,
)


# Intent Enumeration
class IntentEnum(str, Enum):
    """Enum for message intents"""

    REPORT_BUG = "report_bug"
    REQUEST_FEATURE = "request_feature"
    ASK_HOW_TO = "ask_how_to"
    REPORT_BILLING = "report_billing_issue"
    REQUEST_INVOICE = "request_invoice"
    ACCOUNT_HELP = "account_help"
    FOLLOW_UP = "follow_up"
    CONFIRM_RESOLUTION = "confirm_resolution"
    GENERAL_QUESTION = "general_question"
    FEEDBACK_POSITIVE = "feedback_positive"
    FEEDBACK_NEGATIVE = "feedback_negative"


# Information Requirements
class InfoRequirement(BaseModel):
    """Represents an information requirement for handling an intent"""

    requirement_type: str
    description: str
    is_sensitive: bool = False
    source: str = "not_available"  # "tool_call", "human_intervention", "available", "not_available"
    confidence: float = 0.0
    has_access: bool = False  # Whether we have access to this information
    access_method: Optional[str] = None  # How to access this information if accessible


# Enhanced State for Intent Analysis
class IntentAnalysisState(MessagesState):
    """Extended state for intent analysis and information gathering"""

    # Email content
    current_email: Optional[str] = None
    past_emails: Optional[List[str]] = None
    email_context: Optional[str] = None

    # Intent analysis
    detected_intents: List[str] = Field(default_factory=list)
    primary_intent: Optional[str] = None
    intent_confidence: float = 0.0

    # Information assessment
    required_information: List[InfoRequirement] = Field(default_factory=list)
    available_tools: List[str] = Field(default_factory=list)

    # Custom information gathered from tools
    custom_information: List[Dict] = Field(default_factory=list)

    # Final result
    can_proceed: bool = False
    termination_reason: Optional[str] = None

    # Character profile for response drafting
    character_profile: Optional[Dict] = None


# Base LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite")

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Information Access Store
def simple_embed(texts: List[str]) -> List[List[float]]:
    """Simple embedding function for text similarity"""
    # This is a placeholder - in production use a real embedding model
    return [[1.0, 0.5] * len(text) for text in texts]  # Simple dummy vectors


# Create in-memory store for information access rules
information_access_store = InMemoryStore(index={"embed": simple_embed, "dims": 2})


# Initialize with default access rules
def initialize_access_store():
    """Initialize the information access store with default rules"""
    # Default access rules for common tools
    tool_access_rules = {
        "database_query": {
            "description": "Access to database query capabilities",
            "requirements": ["database_connection"],
            "sensitive_data": False,
            "access_method": "tool_call",
        },
        "billing_api": {
            "description": "Access to billing information",
            "requirements": ["billing_api_key"],
            "sensitive_data": True,
            "access_method": "tool_call",
        },
        "user_account_api": {
            "description": "Access to user account information",
            "requirements": ["account_api_key"],
            "sensitive_data": True,
            "access_method": "tool_call",
        },
    }

    # Default access rules for information types
    info_access_rules = {
        "email_history": {
            "description": "Access to email history",
            "requirements": [],  # No special requirements
            "sensitive_data": False,
            "access_method": "available",
        },
        "named_entities": {
            "description": "Access to named entities extraction",
            "requirements": [],  # Can extract from current email
            "sensitive_data": False,
            "access_method": "available",
        },
        "customer_verification": {
            "description": "Customer identity verification",
            "requirements": ["verification_api"],
            "sensitive_data": True,
            "access_method": "human_intervention",
        },
        "payment_details": {
            "description": "Payment details information",
            "requirements": ["billing_api"],
            "sensitive_data": True,
            "access_method": "tool_call",
        },
        "support_tier": {
            "description": "Customer support tier information",
            "requirements": ["user_account_api"],
            "sensitive_data": False,
            "access_method": "tool_call",
        },
        "account_status": {
            "description": "User account status",
            "requirements": ["user_account_api"],
            "sensitive_data": False,
            "access_method": "tool_call",
        },
        "feature_availability": {
            "description": "Product feature availability",
            "requirements": ["user_account_api"],
            "sensitive_data": False,
            "access_method": "tool_call",
        },
    }

    # Store the rules
    for tool_name, rule in tool_access_rules.items():
        information_access_store.put(("tools", "access"), tool_name, rule)

    for info_type, rule in info_access_rules.items():
        information_access_store.put(("info", "access"), info_type, rule)


# Initialize the store
initialize_access_store()


# Helper functions to manage access rules
def add_info_access_rule(
    info_type: str,
    description: str,
    requirements: List[str],
    sensitive_data: bool = False,
    access_method: str = "tool_call",
) -> None:
    """Add or update an information type access rule"""
    rule = {
        "description": description,
        "requirements": requirements,
        "sensitive_data": sensitive_data,
        "access_method": access_method,
    }
    information_access_store.put(("info", "access"), info_type.lower(), rule)
    logging.info(f"Added/updated access rule for information type: {info_type}")


def add_tool_access_rule(
    tool_name: str,
    description: str,
    requirements: List[str],
    sensitive_data: bool = False,
    access_method: str = "tool_call",
) -> None:
    """Add or update a tool access rule"""
    rule = {
        "description": description,
        "requirements": requirements,
        "sensitive_data": sensitive_data,
        "access_method": access_method,
    }
    information_access_store.put(("tools", "access"), tool_name.lower(), rule)
    logging.info(f"Added/updated access rule for tool: {tool_name}")


def get_access_info(info_type: str) -> Dict:
    """Get access information for a specific information type"""
    try:
        rule = information_access_store.get(("info", "access"), info_type.lower())
        return rule if rule else {}
    except Exception:
        return {}


# ===== INTENT ANALYSIS AGENT =====


def create_intent_analyzer_prompt() -> str:
    """Create prompt for intent analysis"""
    intent_descriptions = {
        IntentEnum.REPORT_BUG: "User is reporting a software bug or technical issue",
        IntentEnum.REQUEST_FEATURE: "User is requesting a new feature or enhancement",
        IntentEnum.ASK_HOW_TO: "User is asking for help or guidance on how to do something",
        IntentEnum.REPORT_BILLING: "User is reporting a billing or payment issue",
        IntentEnum.REQUEST_INVOICE: "User is requesting an invoice or billing document",
        IntentEnum.ACCOUNT_HELP: "User needs help with their account settings or management",
        IntentEnum.FOLLOW_UP: "User is following up on a previous conversation or request",
        IntentEnum.CONFIRM_RESOLUTION: "User is confirming that an issue has been resolved",
        IntentEnum.GENERAL_QUESTION: "User has a general question or inquiry",
        IntentEnum.FEEDBACK_POSITIVE: "User is providing positive feedback",
        IntentEnum.FEEDBACK_NEGATIVE: "User is providing negative feedback or complaints",
    }

    intent_list = "\n".join(
        [f"- {intent.value}: {desc}" for intent, desc in intent_descriptions.items()]
    )

    return f"""You are an expert email intent analyzer. Analyze the email and respond with ONLY valid JSON.

AVAILABLE INTENTS:
{intent_list}

CRITICAL: Your response must be ONLY valid JSON, no explanations, no markdown, no extra text.

Required JSON format:
{{
    "primary_intent": "intent_value",
    "all_intents": ["intent1", "intent2"],
    "confidence_score": 0.85,
    "reasoning": "Brief explanation",
    "urgency_level": "low",
    "emotional_tone": "neutral"
}}

Respond with ONLY the JSON object above, nothing else."""


def create_intent_analyzer_agent(memory=None):
    """Create the intent analysis agent"""
    system_prompt = create_intent_analyzer_prompt()

    # Create the intent analyzer agent with relevant tools and memory
    agent_executor = create_react_agent(
        llm, tools=[], prompt=system_prompt, response_format=IntentAnalysisOutput
    )
    return agent_executor


# ===== INFORMATION REQUIREMENTS AGENT =====


def create_info_requirements_prompt() -> str:
    """Create prompt for analyzing information requirements"""
    return """You are an expert at analyzing information requirements. Respond with ONLY valid JSON.

INFORMATION SOURCES:
- "available": Information we already have
- "tool_call": Information from API/database
- "human_intervention": Requires human expertise
- "not_available": Cannot be obtained

CRITICAL: Respond with ONLY valid JSON, no explanations, no markdown, no extra text.

Required JSON format:
{{
    "required_info": [
        {{
            "requirement_type": "user_account_details",
            "description": "Need user's billing information",
            "is_sensitive": true,
            "source": "tool_call",
            "confidence": 0.9
        }}
    ],
    "can_respond_with_available_info": true,
    "missing_critical_info": ["billing_history"],
    "overall_confidence": 0.75,
    "reasoning": "Brief explanation"
}}

Respond with ONLY the JSON object above, nothing else."""


def check_information_access(
    info_req: InfoRequirement, available_tools: List[str], character_profile: Dict
) -> InfoRequirement:
    """Check if we have access to the required information using the information access store"""
    # Normalize requirement type for lookup
    req_type = info_req.requirement_type.lower().strip()

    # First, check if character has permissions in their profile
    character_permissions = character_profile.get("permissions", {})
    if character_permissions:
        # If this is sensitive information and character can't access sensitive data
        if info_req.is_sensitive and not character_permissions.get(
            "can_access_sensitive_data", False
        ):
            info_req.has_access = False
            info_req.access_method = "human_intervention"
            return info_req

        # Check for specific permission overrides in character profile
        for perm_type, has_permission in character_permissions.items():
            if perm_type.startswith("can_access_") and has_permission:
                permission_name = perm_type[11:]  # Remove "can_access_" prefix
                if permission_name in req_type:
                    info_req.has_access = True
                    info_req.access_method = "character_permission"
                    return info_req

    # Try to get access rules from the information store
    try:
        # First check for exact match in info access rules
        info_rule = information_access_store.get(("info", "access"), req_type)
        if info_rule:
            logging.info(f"Found information access rule for: {req_type}")

            # Check if required tools are available for this information type
            tools_available = True
            for required_tool in info_rule.get("requirements", []):
                if required_tool not in available_tools:
                    tools_available = False
                    logging.warning(
                        f"Missing required tool {required_tool} for {req_type}"
                    )

            # Set access based on tool availability
            info_req.has_access = tools_available

            # Set access method based on rule
            info_req.access_method = info_rule.get("access_method", "not_available")

            # Override access method if tools not available
            if not tools_available:
                info_req.access_method = "not_available"

            # Override for sensitive information if we don't have permission
            if info_rule.get("sensitive_data", False) and info_req.is_sensitive:
                if not character_permissions.get("can_access_sensitive_data", False):
                    info_req.has_access = False
                    info_req.access_method = "human_intervention"

            return info_req

        # If no exact match, try semantic search
        search_results = information_access_store.search(
            ("info", "access"),
            query=req_type,
            k=1,  # Get the closest match
        )

        if search_results and len(search_results) > 0:
            best_match_rule = search_results[0][1]  # First result's data
            logging.info(f"Found similar information access rule for: {req_type}")

            # Check if required tools are available
            tools_available = True
            for required_tool in best_match_rule.get("requirements", []):
                if required_tool not in available_tools:
                    tools_available = False

            # Set access based on tool availability
            info_req.has_access = tools_available
            info_req.access_method = best_match_rule.get(
                "access_method", "not_available"
            )
            if not tools_available:
                info_req.access_method = "not_available"

            return info_req

        # Fallback to checking if we have direct tool access
        for tool in available_tools:
            # Get tool access rule if it exists
            tool_rule = information_access_store.get(("tools", "access"), tool)
            if tool_rule and tool.lower() in req_type:
                info_req.has_access = True
                info_req.access_method = "tool_call"
                return info_req

    except Exception as e:
        logging.error(f"Error checking information access: {e}")

    # Default fallbacks
    # Always assume access to basic non-sensitive information types
    if req_type in ["email_history", "named_entities"]:
        info_req.has_access = True
        info_req.access_method = "available"
    # Default for sensitive information
    elif info_req.is_sensitive:
        info_req.has_access = False
        info_req.access_method = "human_intervention"
    else:
        # For any other type without explicit rules, assume no access
        info_req.has_access = False
        info_req.access_method = "not_available"

    return info_req


def create_info_requirements_agent(memory=None):
    """Create the information requirements analysis agent"""
    system_prompt = create_info_requirements_prompt()

    # Create the info requirements agent with relevant tools and memory
    agent_executor = create_react_agent(
        llm,
        tools=[
            get_custom_instruction,
            get_billing_information,
            get_account_information,
            search_faqs,
        ],
        prompt=system_prompt,
        checkpointer=memory,
        response_format=InfoRequirementsOutput,
    )
    return agent_executor


# ===== WORKFLOW NODES =====


def intent_analysis_node(
    state: IntentAnalysisState,
) -> Command[Literal["info_requirements"]]:
    """Analyze the intent of the incoming email"""
    logging.info("--- Intent Analysis Node ---")

    # Create memory store for this session
    memory = InMemoryStore()
    analyzer = create_intent_analyzer_agent()

    # Prepare context
    email_content = state.get("current_email", "")
    past_emails = state.get("past_emails", [])

    context = f"""
EMAIL TO ANALYZE:
{email_content}

PAST EMAIL CONTEXT:
{chr(10).join(past_emails[-3:]) if past_emails else "No past emails available"}
"""

    try:
        # Invoke analyzer with memory
        result = analyzer.invoke({"messages": [HumanMessage(content=context)]})

        # With structured output, the analysis is already parsed as a proper object
        analysis = result["structured_response"]

        logging.info(
            f"Intent analysis complete with confidence: {analysis.confidence_score:.2f}"
        )

        return Command(
            update={
                "primary_intent": analysis.primary_intent,
                "detected_intents": analysis.all_intents,
                "intent_confidence": analysis.confidence_score,
                "messages": result["messages"],
            },
            goto="info_requirements",
        )

    except Exception as e:
        logging.error(f"Intent analysis failed: {e}")
        return Command(
            update={
                "primary_intent": "general_question",
                "detected_intents": ["general_question"],
                "intent_confidence": 0.3,
                "messages": state.get("messages", []),
            },
            goto="info_requirements",
        )


def info_requirements_node(
    state: IntentAnalysisState,
) -> Command[Literal["gather_information"]]:
    """Analyze information requirements for response"""
    logging.info("--- Information Requirements Analysis Node ---")

    # Create memory store for this session
    memory = InMemoryStore()
    analyzer = create_info_requirements_agent(memory=memory)

    # Prepare context
    context = f"""
PRIMARY INTENT: {state.get("primary_intent")}
ALL INTENTS: {state.get("detected_intents", [])}
EMAIL CONTENT: {state.get("current_email", "")}
AVAILABLE TOOLS: {state.get("available_tools", [])}
"""

    try:
        # Invoke analyzer
        result = analyzer.invoke({"messages": [HumanMessage(content=context)]})

        # With structured output, the analysis is already parsed as a proper object
        analysis = result["structured_response"]
        logging.info(
            f"Info requirements analysis complete with {len(analysis.required_info)} requirements"
        )

        # Convert to InfoRequirement objects and check access
        required_info = []
        for req in analysis.required_info:
            try:
                # Convert from schema to our domain model
                info_req = InfoRequirement(
                    requirement_type=req.requirement_type,
                    description=req.description,
                    is_sensitive=req.is_sensitive,
                    source="tool_call",  # Default source
                    confidence=req.confidence,
                )

                # Check if we have access to this information requirement
                info_req = check_information_access(
                    info_req,
                    available_tools=state.get("available_tools", []),
                    character_profile=state.get("character_profile", {}),
                )

                required_info.append(info_req)
            except Exception as e:
                logging.warning(f"Failed to create InfoRequirement: {e}")

        return Command(
            update={
                "required_information": required_info,
                "messages": state["messages"] + result["messages"],
            },
            goto="gather_information",
        )

    except Exception as e:
        logging.error(f"Info requirements analysis failed: {e}")
        return Command(
            update={"required_information": [], "messages": state.get("messages", [])},
            goto="gather_information",
        )


def gather_information_node(state: IntentAnalysisState) -> Command[Literal[END]]:
    """Gather information using available tools or terminate with reason"""
    logging.info("--- Gather Information Node ---")

    required_info = state.get("required_information", [])
    custom_information = []
    termination_reason = None
    can_proceed = True

    # Check for critical missing information
    critical_missing = []
    accessible_info = []

    for info in required_info:
        if info.confidence > 0.7:  # High confidence requirement
            if not info.has_access or info.access_method in [
                "not_available",
                "human_intervention",
            ]:
                critical_missing.append(info.description)
                logging.warning(f"Critical information missing: {info.description}")
            else:
                accessible_info.append(info)

    # If we have critical missing information, terminate
    if critical_missing:
        termination_reason = f"Cannot proceed - missing critical information: {', '.join(critical_missing)}"
        can_proceed = False
        logging.warning(f"Terminating flow: {termination_reason}")

        return Command(
            update={
                "can_proceed": can_proceed,
                "termination_reason": termination_reason,
                "custom_information": custom_information,
            },
            goto=END,
        )

    # Try to gather accessible information using tools
    available_tools = {
        "get_billing_information": get_billing_information,
        "get_account_information": get_account_information,
        "search_faqs": search_faqs,
        "get_custom_instruction": get_custom_instruction,
    }

    for info in accessible_info:
        if info.access_method == "tool_call":
            try:
                # Determine which tool to use based on requirement type
                tool_to_use = None
                if "billing" in info.requirement_type.lower():
                    tool_to_use = available_tools.get("get_billing_information")
                elif "account" in info.requirement_type.lower():
                    tool_to_use = available_tools.get("get_account_information")
                elif (
                    "faq" in info.requirement_type.lower()
                    or "help" in info.requirement_type.lower()
                ):
                    tool_to_use = available_tools.get("search_faqs")
                elif "instruction" in info.requirement_type.lower():
                    tool_to_use = available_tools.get("get_custom_instruction")

                if tool_to_use:
                    # Call the tool with appropriate parameters
                    # This is a simplified approach - in practice you'd need to extract
                    # relevant parameters from the email content
                    tool_result = tool_to_use.invoke({"query": info.description})

                    custom_information.append(
                        {
                            "type": info.requirement_type,
                            "description": info.description,
                            "data": tool_result,
                            "source": "tool_call",
                        }
                    )

                    logging.info(
                        f"Successfully gathered information for: {info.requirement_type}"
                    )

            except Exception as e:
                logging.error(
                    f"Failed to gather information for {info.requirement_type}: {e}"
                )
                # Continue with other information gathering

        elif info.access_method == "available":
            # Information that's already available (like email history, extracted entities)
            custom_information.append(
                {
                    "type": info.requirement_type,
                    "description": info.description,
                    "data": "Available from current context",
                    "source": "available",
                }
            )

    # Final decision
    if can_proceed:
        logging.info(
            f"Successfully gathered {len(custom_information)} pieces of information"
        )
        return Command(
            update={
                "can_proceed": can_proceed,
                "custom_information": custom_information,
                "termination_reason": None,
            },
            goto=END,
        )
    else:
        return Command(
            update={
                "can_proceed": can_proceed,
                "termination_reason": termination_reason or "Unknown error occurred",
                "custom_information": custom_information,
            },
            goto=END,
        )


# ===== WORKFLOW SETUP =====


def create_simplified_intent_workflow():
    """Create the simplified intent analysis workflow"""
    workflow = StateGraph(IntentAnalysisState)

    # Add nodes
    workflow.add_node("intent_analysis", intent_analysis_node)
    workflow.add_node("info_requirements", info_requirements_node)
    workflow.add_node("gather_information", gather_information_node)

    # Set entry point
    workflow.set_entry_point("intent_analysis")

    # Add edges
    workflow.add_edge("intent_analysis", "info_requirements")
    workflow.add_edge("info_requirements", "gather_information")
    workflow.add_edge("gather_information", END)

    return workflow.compile()


# ===== MAIN FUNCTION =====


def analyze_email_intent_simplified(
    current_email: str,
    past_emails: List[str] = None,
    character_profile: Dict = None,
    available_tools: List[str] = None,
) -> Dict:
    """
    Simplified function to analyze email intent and gather information
    Returns either termination reason or main_intent with custom_information
    """
    logging.info("--- Starting Simplified Intent Analysis ---")

    # Create workflow
    workflow = create_simplified_intent_workflow()

    # Initial state
    initial_state = {
        "messages": [HumanMessage(content="Analyze this email")],
        "current_email": current_email,
        "past_emails": past_emails or [],
        "character_profile": character_profile or {},
        "available_tools": available_tools
        or [
            "get_billing_information",
            "get_account_information",
            "search_faqs",
            "get_custom_instruction",
        ],
    }

    # Run workflow
    final_state = workflow.invoke(initial_state)

    # Prepare results
    if final_state.get("can_proceed", False):
        return {
            "main_intent": final_state.get("primary_intent"),
            "custom_information": final_state.get("custom_information", []),
            "confidence": final_state.get("intent_confidence", 0.0),
        }
    else:
        return {
            "termination_reason": final_state.get(
                "termination_reason", "Unknown error"
            ),
            "main_intent": final_state.get("primary_intent"),
            "confidence": final_state.get("intent_confidence", 0.0),
        }


# ===== EXAMPLE USAGE =====

if __name__ == "__main__":
    # Example email
    sample_email = """    
    Hi,
    Otp not wokring for my number +91 9876543210
    
    
    
    Thanks,
    John
    """

    sample_past_emails = [
        "Previous billing inquiry resolved successfully",
    ]

    # Run simplified analysis
    result = analyze_email_intent_simplified(
        current_email=sample_email, past_emails=sample_past_emails
    )

    print("=== SIMPLIFIED ANALYSIS RESULTS ===")
    if "termination_reason" in result:
        print(f"TERMINATED: {result['termination_reason']}")
        print(f"Intent: {result.get('main_intent', 'Unknown')}")
    else:
        print(f"SUCCESS - Main Intent: {result['main_intent']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Custom Information Gathered: {len(result['custom_information'])} items")
        for info in result["custom_information"]:
            print(f"  - {info['type']}: {info['description']}")
