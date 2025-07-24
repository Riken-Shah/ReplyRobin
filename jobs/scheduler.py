import schedule
import os
import time
from ingestion_pipeline.fetcher import Fetcher
from common.db import DB
from common.schemas import Org, Message
from ingestion_pipeline.semantic_effort.vector_embeeding import VectorEmbeddingProcess
from data_enrichment.processor import Processor
from sqlmodel import select
from jobs.pre_checks import self_checks

from sqlmodel import Session
from datetime import datetime


def fetcher_job(db: DB, org: Org, embeeding_model: VectorEmbeddingProcess):
    # Our Fetcher class is responsible to do continuous fetching of threads + messages from the org's gmail account.
    # We can run this as cron job every hour, there might be a case where it fetches & computes few threads
    # again because we are using `nextPageToken` of `threads.list` API to fetch threads.

    fetcher = Fetcher(db, org, embedding_process=embeeding_model)
    fetcher.continous_fetch()


def processor_job(db: DB, org: Org):
    # Step 3: Process messages
    # Our `Processor` class is adds the intent and lingustical anaylsis to all our messages,
    # allowing our AI agent to get the highthend intelligence of the inbox.
    processor = Processor(db, org)
    # Continue processing of new messages, this will run as cron job every hour until all messages are processed.
    new_messages = []
    with db.session_scope() as session:
        result = session.exec(select(Message).where(Message.intents.is_(None)))
        msgs = result.all()

        for msg in msgs:
            new_messages.append(Message(**msg.model_dump()))
    print("Found {} new messages to process".format(len(new_messages)))
    processor.process(new_messages)


def create_or_update_org(session: Session, email: str, creds_file: str) -> Org:
    """Gets an existing Org or creates a new one."""
    org = session.get(Org, email)
    if not org:
        print(f"Creating new Org for {email}")
        org = Org(
            name=os.getenv("ORG_NAME", "Test Org"),
            max_thread_count=100,
            end_date=datetime(2022, 1, 1),  # Set a more recent date
            email=email,
            creds_file=creds_file,
            inital_fetch=False,
        )
    else:
        print(f"Found existing Org for {email}")
        # Update fields that might change, like the creds file
        org.creds_file = creds_file

    session.add(org)
    session.commit()
    session.refresh(org)

    return Org(**org.model_dump())


def pipe_jobs(db: DB, embeeding_model: VectorEmbeddingProcess):
    # Failover if setup is incomplete
    creds_file = self_checks()

    email = os.getenv("EMAIL_INBOX", None)

    # Step 1: Upsert Org
    # Once we get the access to there gmail, we create an org object in our database.
    # It will overlook all other entites in the DB and give them org-scoped to there email.
    org = None
    with next(db.get_session()) as session:
        org = create_or_update_org(session, email=email, creds_file=creds_file)

    if not org:
        raise Exception("Org not found")

    fetcher_job(db, org, embeeding_model)
    processor_job(db, org)


# TODO: Add scheduling logic
# # schedule.every().day.at("10:00").do(job)

# while True:
#     schedule.run_pending()
#     time.sleep(1)
