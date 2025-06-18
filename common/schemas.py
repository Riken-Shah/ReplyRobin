from enum import Enum
from typing import List, Optional, Literal
from sqlmodel import Field, SQLModel
from datetime import datetime
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, TIMESTAMP


class IntentEnum(str, Enum):
    """Enum for message intents"""

    REPORT_BUG = "report_bug"  # Issues with software functionality
    REQUEST_FEATURE = "request_feature"  # Asking for new capabilities
    ASK_HOW_TO = "ask_how_to"  # Seeking guidance on usage
    REPORT_BILLING = "report_billing_issue"  # Problems with payments
    REQUEST_INVOICE = "request_invoice"  # Asking for billing documentation
    ACCOUNT_HELP = "account_help"  # Questions about account management
    FOLLOW_UP = "follow_up"  # Continuing a previous conversation
    CONFIRM_RESOLUTION = "confirm_resolution"  # Verifying an issue was fixed
    GENERAL_QUESTION = "general_question"  # Miscellaneous inquiries
    FEEDBACK_POSITIVE = "feedback_positive"  # Expressing satisfaction
    FEEDBACK_NEGATIVE = "feedback_negative"  # Expressing dissatisfaction


class ToneEnum(str, Enum):
    FRIENDLY = "friendly"
    FORMAL = "formal"
    CONCISE = "concise"
    DETAILED = "detailed"
    ASSERTIVE = "assertive"
    HESITANT = "hesitant"
    ENTHUSIASTIC = "enthusiastic"
    APOLOGETIC = "apologetic"
    NEUTRAL = "neutral"
    URGENT = "urgent"
    ENCOURAGING = "encouraging"
    DIPLOMATIC = "diplomatic"


class Org(SQLModel, table=True):
    name: str
    max_thread_count: int = 10
    end_date: Optional[datetime] = None
    preferred_emails: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    email: str = Field(primary_key=True, index=True)
    creds_file: str
    last_synced_at: Optional[datetime] = None
    thread_page_token: Optional[str] = (
        None  # Record the page token for the last thread fetch, help us to sync the threads
    )

    def get_id(self):
        return self.email


class Thread(SQLModel, table=True):
    id: str = Field(primary_key=True)
    message_count: int
    last_synced_at: datetime
    history_id: int
    org_id: str = Field(foreign_key="org.email")


class Message(SQLModel, table=True):
    id: str = Field(primary_key=True)
    org_id: str = Field(foreign_key="org.email")
    thread_id: str = Field(foreign_key="thread.id")
    label_ids: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    history_id: str
    internal_date: datetime = Field(sa_column=Column(TIMESTAMP(timezone=False)))
    size_estimate: int
    body: str

    # Email header fields
    subject: Optional[str] = None
    sender: Optional[str] = None
    reply_to: Optional[str] = None
    recipients: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))  # To field
    cc_recipients: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    bcc_recipients: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))

    # Additional useful email metadata
    message_id: Optional[str] = None  # Original Message-ID from email header
    references: List[str] = Field(
        default=[], sa_column=Column(ARRAY(TEXT))
    )  # For threading
    in_reply_to: Optional[str] = None  # Message this is replying to
    importance: Optional[str] = None  # Priority/Importance of the email
    parent_message_id: Optional[str] = None  # Points to parent message id

    # After Enrichment step
    cleaned_content: Optional[str] = (
        None  # Stipped from welcome, closing and quoted text (Helps in getting the core content of the email)
    )
    intents: List[IntentEnum] = Field(
        default=[], sa_column=Column(ARRAY(TEXT))
    )  # Multiple intents that describe the email purpose

    # Use specifically for character profiling
    tone: Optional[ToneEnum] = None
    greeting_phrases: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    politeness_markers: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    modal_verbs: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    hedge_words: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    boosters: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    mitigating_phrases: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    urgency_phrases: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    filler_words: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    emoji_usage: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    question_phrases: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    sentence_starters: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    passive_voice_patterns: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    abbreviation_usage: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    discourse_markers: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))

    # Punctuation Style
    ellipsis_frequency: Optional[float] = None
    exclamation_density: Optional[float] = None
    uses_caps_for_emphasis: Optional[bool] = False
    uses_inline_parentheses: Optional[bool] = False


# --- Non-table models for data processing ---


class ActionItem(SQLModel):
    description: str
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    completed: Optional[bool] = False


class NamedEntities(SQLModel):
    people: List[str] = []
    organizations: List[str] = []
    locations: List[str] = []
    dates: List[str] = []
    amounts: List[str] = []
    misc: List[str] = []


class Participant(SQLModel):
    name: str
    email: str
    role: Optional[Literal["sender", "recipient", "cc", "bcc", "system"]] = None


class EmailThread(SQLModel):
    thread_id: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_from_user: bool
    last_message_timestamp: datetime
    summary: str
    intent: List[IntentEnum] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    status: Literal["awaiting_response", "resolved", "ongoing"]
    tone: Literal["formal", "casual", "urgent", "neutral"]
    tags: List[str] = []
    action_items: List[ActionItem] = []
    named_entities: NamedEntities
    participants: List[Participant] = []
    needs_dynamic_data: bool
    follow_up_required: bool
    urgency_score: float = Field(..., ge=0.0, le=1.0)
    preferred_reply_style: Optional[str] = None
    vector_id: str
    embedding_source: Literal["latest_message", "thread_summary"]
    is_starred: Optional[bool] = False
    has_attachment: Optional[bool] = False
    tags_llm_version: Optional[str] = None
