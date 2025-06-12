from typing import List, Optional, Literal
from sqlmodel import Field, SQLModel
from datetime import datetime
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, TIMESTAMP


class Org(SQLModel, table=True):
    name: str
    max_thread_count: int = 10
    end_date: Optional[datetime] = None
    preferred_emails: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    email: str = Field(primary_key=True, index=True)
    creds_file: str
    initial_fetch: bool = False


class Thread(SQLModel, table=True):
    id: str = Field(primary_key=True)
    message_count: int
    last_synced_at: datetime
    history_id: int


class Message(SQLModel, table=True):
    id: str = Field(primary_key=True)
    thread_id: str = Field(foreign_key="thread.id")
    label_ids: List[str] = Field(default=[], sa_column=Column(ARRAY(TEXT)))
    history_id: str
    internal_date: datetime = Field(sa_column=Column(TIMESTAMP(timezone=False)))
    size_estimate: int
    body: str


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
    intent: str
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
