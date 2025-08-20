from evals.base_eval import BaseEval
from db.schemas import CharacterProfile
from agent_orchestration.master_agent.state import Email
from typing import List, Dict, Any


class CustomerSupportEval(BaseEval):
    """Customer support specific evaluation that extends BaseEval"""

    def __init__(self, verbose: bool = False):
        super().__init__("Customer Support Email Evaluation", verbose=verbose)

    def get_grader_instructions(self) -> str:
        """Return LLM-as-judge instructions for customer support evaluation"""
        return """You are evaluating customer support email responses.

Evaluate the response based on these criteria:
1. APPROPRIATENESS: Is the response appropriate for the input email type?
   - Spam/promotional emails should receive NO response (empty output)
   - Vague requests without context should receive NO response (empty output)
   - Legitimate customer issues should receive a helpful response

2. PROFESSIONAL TONE: Does the response maintain a professional, helpful customer support tone?
   - Uses appropriate greetings and closings
   - Shows empathy and understanding
   - Maintains politeness throughout

3. CONTEXT AWARENESS: Does the response reference relevant past conversation history?
   - Acknowledges previous interactions when relevant
   - Builds upon established context appropriately

4. PROBLEM SOLVING: Does the response address the customer's specific issue?
   - Provides relevant solutions or next steps
   - Offers clear actionable advice
   - Shows understanding of the customer's situation

Rate the response as:
- CORRECT: if it appropriately handles the email type and provides quality customer support
- INCORRECT: if it fails to handle the email type appropriately or provides poor customer support

Explain your reasoning step-by-step."""

    def get_examples(self) -> List[Dict[str, Any]]:
        """Return the customer support evaluation examples"""
        return examples


# Customer support character profile and test data
dummy_character_profile = CharacterProfile(
    sender="sarah.smith@techsupport.com",
    num_messages=320,
    avg_cleaned_length=95.2,
    avg_ellipsis_frequency=0.3,
    avg_exclamation_density=0.8,
    uses_caps_for_emphasis=False,
    uses_inline_parentheses=True,
    avg_num_hedge_words=1.8,
    avg_num_modal_verbs=2.9,
    avg_num_boosters=1.2,
    avg_num_politeness_markers=5.1,
    avg_num_passive_patterns=2.1,
    avg_num_emoji=0.1,
    avg_num_question_phrases=1.9,
    top_greeting_phrases=["Hi", "Hello", "Thank you for contacting us"],
    top_politeness_markers=["please", "thank you", "appreciate", "sorry"],
    top_modal_verbs=["can", "will", "would"],
    top_hedge_words=["might", "possibly", "appears"],
    top_boosters=["certainly", "definitely", "happy to"],
    top_mitigating_phrases=[
        "I apologize for the inconvenience",
        "I understand your concern",
    ],
    top_urgency_phrases=["priority", "escalate", "immediate attention"],
    top_filler_words=["just", "actually", "basically"],
    top_emoji_usage=["😊", "👍"],
    top_question_phrases=["Can you please", "Would you be able to", "Could you try"],
    top_sentence_starters=["I understand", "Let me help", "I'd be happy to"],
    top_passive_voice_patterns=[
        "has been resolved",
        "will be addressed",
        "was processed",
    ],
    top_abbreviation_usage=["FAQ", "KB", "ID"],
    top_discourse_markers=["Additionally", "Meanwhile", "To clarify"],
)

# Past emails for different test cases
garbage_email_past_emails = [
    Email(
        subject="Weekly Newsletter - Product Updates",
        body="Here's what's new this week in our product updates...",
        sender="newsletter@company.com",
    ),
    Email(
        subject="Meeting reminder",
        body="Don't forget about tomorrow's team meeting at 2 PM.",
        sender="calendar@company.com",
    ),
]

insufficient_context_past_emails = [
    Email(
        subject="Re: Order issue",
        body="Hi Misa, We're sorry to hear you're having trouble with your order. We'd love to help you fix this as soon as possible. Could you please provide us with your order number and a brief description of the issue? This will help us assist you more effectively. Thank you!",
        sender="usrr@email.co",
    ),
    Email(
        subject="Re: Account problem",
        body="Hi Alex, Thanks for reaching out. We understand you're experiencing an issue with your account. Could you please provide more details about the problem? This will help us resolve it quickly. Looking forward to your response!",
        sender="user_b@email.com",
    ),
]


valid_email_past_emails = [
    Email(
        subject="Re: Trouble logging in",
        body="Hi Emma, Thanks for reaching out. If you’re seeing an ‘invalid password’ error, please try resetting your password using the Forgot Password link. Once reset, you should be able to log in successfully. Let us know if it still doesn’t work.",
        sender="support@service.com",
    ),
    Email(
        subject="Re: Login assistance needed",
        body="Hi Home, Thanks for reaching out. If you’re seeing an “invalid password” error, please try resetting your password using the Forgot Password link on the login page. After resetting, you should be able to sign in successfully. If the issue continues, let us know and we’ll be happy to help further.",
        sender="support@service.com",
    ),
]

# Create a dataset
examples = [
    # Case 1: Garbage email from promotions/spam - should not reply
    {
        "test_name": "spam_email_no_reply",
        "inputs": {
            "character_profile": dummy_character_profile,
            "current_email": Email(
                subject="💰 Earn $5000/week from home! No experience needed!",
                body="URGENT: Limited spots available! Make money from home with our proven system. No skills required! Click here to start earning TODAY! This offer expires in 24 hours. Don't miss this life-changing opportunity!",
                sender="money-maker@get-rich-quick.biz"
            ),
            "past_emails": garbage_email_past_emails,
        },
        "outputs": {
            "final_draft": "",
            "trajectory": ["planner"]
        }
    },
    # Case 2: Email with insufficient context - should skip
    {
        "test_name": "insufficient_context_response",
        "inputs": {
            "character_profile": dummy_character_profile,
            "current_email": Email(
                subject="Help needed",
                body="Hi, it's not working. Can you fix it?",
                sender="user123@email.com",
            ),
            "past_emails": insufficient_context_past_emails,
        },
        "outputs": {
            "final_draft": "Hi there, I understand you're experiencing an issue and that something appears to not be working as expected. I'm sorry to hear that! To help me fix this for you, could you please provide a few more details? It might be really helpful if you could tell me what specifically isn't working (e.g., is it a specific feature or the whole system?) and any steps you've already tried. This would allow the problem to be possibly pinpointed more quickly. Once I have a bit more information, I will be happy to look into this for you right away. Would you be able to provide those details when you get a moment? Thanks so much for your patience! 😊",
            "trajectory": ["planner", "drafter", "judge"],
        },
    },
    # Case 3: Valid customer support email requiring character profile-based response
    {
        "test_name": "account_lockout_support",
        "inputs": {
            "character_profile": dummy_character_profile,
            "current_email": Email(
                subject="Re: Account locked out",
                body="Hi support, I'm unable to access my account — it says my password is wrong. Can you help me get back in?",
                sender="sophia@customer.com",
            ),
            "past_emails": valid_email_past_emails,
        },
        "outputs": {
            "final_draft": "Hi there, Thank you for reaching out about your account. We appreciate you letting us know. I understand you're currently unable to access it, and it appears to be locked. If you're seeing an account locked message, it might be due to incorrect password attempts (this often happens for security reasons). You will need to reset your password. Could you please try using the 'Forgot Password' link on our login page? Once reset, you should be able to log in successfully. If you still find yourself unable to log in, or if you run into any other difficulties, please don't hesitate to let us know. We would be happy to assist you further! 😊",
            "trajectory": ["planner", "drafter", "judge"],
        },
    },
]
