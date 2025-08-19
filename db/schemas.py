from enum import Enum
from typing import List, Optional, Literal
from sqlmodel import Field, SQLModel
from datetime import datetime
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, TIMESTAMP, JSONB
from pgvector.sqlalchemy import Vector

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship, mapped_column
from sqlalchemy import ForeignKey, String, Text, Float, Boolean
from sqlalchemy import func
from datetime import datetime
import os
from dataclasses import dataclass, asdict


class Base(DeclarativeBase):
    created_at: Mapped[DateTime] = mapped_column(TIMESTAMP, default=datetime.now())
    updated_at: Mapped[DateTime] = mapped_column(
        TIMESTAMP, onupdate=datetime.now(), default=datetime.now()
    )


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


@dataclass
class Token:
    name: str
    last_page_token: str


class Org(Base):
    __tablename__ = "org"
    # Primary email address from which we will read inbox
    email: Mapped[str] = mapped_column(String(256), primary_key=True)
    # This is the last date till we will fetch threads
    cutoff_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    # Multiple page tokens, i.e for draft, messages
    page_tokens: Mapped[List[Token]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"Org(email={self.email})"

    def get_page_token(self, name: str) -> Optional[str]:
        """Get the last page token for a specific name."""
        if not self.page_tokens:
            return None
        for token in self.page_tokens:
            print("Checking token: ")
            if token["name"] == name:
                return token["last_page_token"]
        return None

    def set_page_token(self, name: str, page_token: str):
        """Set the last page token for a specific name."""
        if not self.page_tokens:
            self.page_tokens = []
        for token in self.page_tokens:
            if token["name"] == name:
                token["last_page_token"] = page_token
                return
        self.page_tokens.append(asdict(Token(name=name, last_page_token=page_token)))


class Thread(Base):
    __tablename__ = "thread"
    # We use the same id provided by GMAIL API, 16-char hexadecimal value
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    # We don't use this but keeping for future use
    history_id: Mapped[str] = mapped_column(String(10))
    org_id: Mapped[str] = mapped_column(ForeignKey("org.email"))
    org: Mapped["Org"] = relationship(cascade="all, delete")
    # Doesn't belong to threads, but pre-computed peice
    message_count: Mapped[int]
    last_sync: Mapped[DateTime] = mapped_column(TIMESTAMP)

    messages: Mapped[List["Message"]] = relationship(
        back_populates="thread", cascade="all, delete"
    )

    def __repr__(self) -> str:
        return (
            f"Thread(id={self.id}, org_id={self.org_id}, history_id={self.history_id})"
        )


class StylometrySignalsForMessage:
    intents: Mapped[Optional[List[str]]] = None
    # Character Profiling Fields
    tone: Mapped[Optional[ToneEnum]] = None

    # Linguistic patterns
    greeting_phrases: Mapped[Optional[List[str]]] = None
    politeness_markers: Mapped[Optional[List[str]]] = None
    modal_verbs: Mapped[Optional[List[str]]] = None
    hedge_words: Mapped[Optional[List[str]]] = None
    boosters: Mapped[Optional[List[str]]] = None
    mitigating_phrases: Mapped[Optional[List[str]]] = None
    urgency_phrases: Mapped[Optional[List[str]]] = None
    filler_words: Mapped[Optional[List[str]]] = None
    emoji_usage: Mapped[Optional[List[str]]] = None
    question_phrases: Mapped[Optional[List[str]]] = None
    sentence_starters: Mapped[Optional[List[str]]] = None
    passive_voice_patterns: Mapped[Optional[List[str]]] = None
    abbreviation_usage: Mapped[Optional[List[str]]] = None
    discourse_markers: Mapped[Optional[List[str]]] = None

    # Punctuation Style
    ellipsis_frequency: Mapped[Optional[float]] = None
    exclamation_density: Mapped[Optional[float]] = None
    uses_caps_for_emphasis: Mapped[Optional[bool]] = None
    uses_inline_parentheses: Mapped[Optional[bool]] = None


class Message(Base):
    __tablename__ = "message"
    # We use the same id provided by GMAIL API, 16-char hexadecimal value
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("org.email"))
    org: Mapped["Org"] = relationship(cascade="all, delete")
    thread_id: Mapped[str] = mapped_column(ForeignKey("thread.id"))
    thread: Mapped["Thread"] = relationship(
        back_populates="messages", cascade="all, delete"
    )

    history_id: Mapped[str] = mapped_column(String(10))
    label_ids: Mapped[List[str]] = mapped_column(ARRAY(String(50)))
    internal_date: Mapped[DateTime] = mapped_column(TIMESTAMP)
    raw_content: Mapped[str] = mapped_column(Text())
    size_estimate = Mapped[int]

    # Based on RFC 2822 Protocols
    sender: Mapped[str] = mapped_column(String(254))
    receiver: Mapped[List[str]] = mapped_column(
        ARRAY(String(254)), nullable=True
    )  # In case of draft
    subject: Mapped[str] = mapped_column(
        String(255)
    )  # In most cases it shouldn't exceed this
    # We are ignoring all other fields such as cc, bcc, reply_to, etc.

    signals: Mapped[Optional[StylometrySignalsForMessage]] = mapped_column(
        JSONB, nullable=True
    )
    # Vector Embedding for the body of the message, so we can perform semantic search
    embeeding: Mapped[List[float]] = mapped_column(Vector(1024))
    parent_message_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("message.id"), nullable=True
    )
    parent_message: Mapped[Optional["Message"]] = relationship(
        "Message",
        remote_side=[id],
        backref="replies",
        cascade="all, delete",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"Message(id={self.id}, org_id={self.org_id}, thread_id={self.history_id}, from_email={self.from_email})"

    def get_signal(self, signal_name: str) -> Optional[any]:
        """
        Get a specific signal from the message's signals.
        """
        if not self.signals:
            return None
        return getattr(self.signals, signal_name, None)

    def set_signal(self, signal_name: str, value: any):
        """
        Set a specific signal in the message's signals.
        """
        if not self.signals:
            self.signals = dict()

        print(f"Setting signal {signal_name} to {value} for message {self.id}")
        self.signals[signal_name] = value
        # setattr(self.signals, signal_name, value)

    def has_signal(self, signal_name: str) -> bool:
        """
        Check if a specific signal exists in the message's signals.
        """
        if not self.signals:
            return False
        return (
            hasattr(self.signals, signal_name)
            and getattr(self.signals, signal_name) is not None
        )


# --- Non-table models for data processing ---


class CharacterProfile(SQLModel):
    sender: str
    num_messages: int
    # avg_size_estimate: float
    avg_cleaned_length: Optional[float] = None
    avg_ellipsis_frequency: Optional[float] = None
    avg_exclamation_density: Optional[float] = None
    uses_caps_for_emphasis: bool
    uses_inline_parentheses: bool
    avg_num_hedge_words: float
    avg_num_modal_verbs: float
    avg_num_boosters: float
    avg_num_politeness_markers: float
    avg_num_passive_patterns: float
    avg_num_emoji: float
    avg_num_question_phrases: float
    top_greeting_phrases: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_politeness_markers: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_modal_verbs: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_hedge_words: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_boosters: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_mitigating_phrases: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_urgency_phrases: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_filler_words: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_emoji_usage: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_question_phrases: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_sentence_starters: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_passive_voice_patterns: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_abbreviation_usage: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
    top_discourse_markers: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(TEXT))
    )
