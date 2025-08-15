from db.singleton import get_session_manager
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from db.schemas import Message, Org, Thread
from typing import List, Union
from datetime import datetime


def fetch_messages_for_processing(org_id: str, limit: int = 100) -> List[Message]:
    stmt = (
        select(Message)
        .filter(Message.org_id == org_id, Message.signals.is_(None))
        .limit(limit)
    )
    with get_session_manager() as local_session:
        messages = local_session.scalars(stmt).all()
        return messages


def fetch_messages_for_response(org_id: str, limit: int = 100) -> List[Message]:
    stmt = (
        select(Message)
        .filter(
            Message.org_id == org_id,
            Message.sender != org_id,
            Message.thread_id.in_(select(Thread.id).where(Thread.message_count == 1)),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )

    with get_session_manager() as local_session:
        messages = local_session.scalars(stmt).all()
        return messages


def fetch_semantic_similar_messages(
    org_id: str, query_embedding: List[float], limit: int = 10
) -> List[Message]:
    stmt = (
        select(Message)
        .filter(Message.org_id == org_id)
        .order_by(Message.embeeding.cosine_distance(query_embedding))
        .limit(limit)
    )

    with get_session_manager() as local_session:
        messages = local_session.scalars(stmt).all()
        return messages


def insert_org(email: str, cutoff_date: Union[None, datetime]):
    stmt = insert(Org).values(email=email, cutoff_date=cutoff_date)
    with get_session_manager() as local_session:
        local_session.execute(stmt)
        local_session.commit()


def update_org(org: Org):
    stmt = update(Org).where(Org.email == org.email).values(orm_to_dict(org))
    with get_session_manager() as local_session:
        local_session.execute(stmt)
        local_session.commit()


def get_org(email: str) -> Org:
    stmt = select(Org).filter_by(email=email)
    with get_session_manager() as local_session:
        return local_session.scalars(stmt).one_or_none()


def upsert_messages(messages: List[Message]):
    if not messages:
        return

    messages_dict = [orm_to_dict(msg) for msg in messages]
    stmt = insert(Message).values(messages_dict)
    # Build update set dict: take all columns except primary key
    update_dict = {
        col.name: stmt.excluded[col.name]
        for col in Message.__table__.columns
        if col.name != "id"  # skip PK
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],  # or use `constraint="thread_pkey"`
        set_=update_dict,
    )
    with get_session_manager() as local_session:
        local_session.execute(stmt)
        local_session.commit()


def upsert_threads(threads: List[Thread]):
    if not threads:
        return

    thread_dicts = [orm_to_dict(thread) for thread in threads]
    stmt = insert(Thread).values(thread_dicts)

    # Build update set dict: take all columns except primary key
    update_dict = {
        col.name: stmt.excluded[col.name]
        for col in Thread.__table__.columns
        if col.name != "id"  # skip PK
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],  # or use `constraint="thread_pkey"`
        set_=update_dict,
    )

    with get_session_manager() as local_session:
        local_session.execute(stmt)
        local_session.commit()


# Helper functions
def orm_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
