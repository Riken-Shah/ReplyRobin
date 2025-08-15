import os
from ingestion_pipeline.gmail_fetcher import GmailClient
from db.schemas import Org, Message
from db.handlers import (
    insert_org,
    get_org,
    upsert_messages,
    upsert_threads,
    update_org,
    fetch_messages_for_processing,
)
from ingestion_pipeline.semantic_effort.vector_embeeding import VectorEmbeddingProcess
from data_enrichment.processor import Processor
from sqlmodel import select
from jobs.pre_checks import self_checks
from agent_orchestration.character_profile import fetch_character_profile
from db.handlers import fetch_messages_for_response, get_org, fetch_semantic_similar_messages
from datetime import datetime
from agent_orchestration.master_agent.worker import Worker
from agent_orchestration.master_agent.state import Email

from sqlmodel import Session
from datetime import datetime


def fetcher_job(org: Org, embeeding_model: VectorEmbeddingProcess):
    # Our Fetcher class is responsible to do continuous fetching of threads + messages from the org's gmail account.
    # We can run this as cron job every hour, there might be a case where it fetches & computes few threads
    # again because we are using `nextPageToken` of `threads.list` API to fetch threads.

    gmail_client = GmailClient(org, embedding_process=embeeding_model)
    try:
        threads, messages, last_page_token = gmail_client.resume_threads_fetch()
        print(
            f"Found Threads: {len(threads)}, Messages: {len(messages)}, Page Token: {last_page_token}"
        )
    except Exception as e:
        print(f"Error fetching threads: {e}")
        raise e

    upsert_threads(threads)
    upsert_messages(messages)

    # Now also update the thread page token
    if last_page_token:
        org.set_page_token("threads", last_page_token)
        update_org(org)


def processor_job(org: Org):
    # Step 3: Process messages
    # Our `Processor` class adds the intent and lingustical anaylsis to all our messages,
    # allowing our AI agent to get the highthend intelligence of the inbox.
    processor = Processor(org)
    # Continue processing of new messages, this will run as cron job every hour until all messages are processed.
    new_messages = fetch_messages_for_processing(org.email, limit=1000)
    new_messages = processor.process(new_messages)
    upsert_messages(new_messages)


def generate_reply(org: Org, embeeding_model: VectorEmbeddingProcess):
    """
    Attempt to generate draft.

    Currently this is limited to new messages only in the thread where the thread size is 1.

    We pass current email, author profile (stylometry signals) and similar past messages to the agent.
    """
    # Find the messages in the recent thread where thread size == 1 and it's not the owner.
    # And only reply if you think it's worth replying to.
    profile = fetch_character_profile(org.email)

    messages = fetch_messages_for_response(org.email)

    gc = GmailClient(org)

    worker = Worker()
    for root in messages:
        thread_detail = gc._fetch_thread_detail(root.thread_id)
        messages = thread_detail.get("messages", [])

        if len(messages) > 1:
            print(f"Skipping thread {root.thread_id} with {len(messages)} messages")
            continue

        current_email = Email(
            subject=root.subject, body=root.raw_content, sender=root.sender
        )
        email_embeddings = embeeding_model.embed(current_email.format())
        past_messages = fetch_semantic_similar_messages(org.email, email_embeddings, 8)
        past_messages = [
            Email(subject=msg.subject, body=msg.raw_content, sender=msg.sender)
            for msg in past_messages
        ]

        result = worker.run_agent(
            character_profile=profile,
            current_email=current_email,
            past_emails=past_messages,
        )

        if not result.final_draft:
            print("No draft generated, skipping thread:", root.thread_id)
            continue

        gc.create_thread_draft(
            to_email=root.sender,
            subject=root.subject,
            body=result.final_draft,
            thread_id=root.thread_id,
        )
        print("Draft created for thread:", root.thread_id)

def pipe_jobs(embeeding_model: VectorEmbeddingProcess):
    # Failover if setup is incomplete
    self_checks()

    email = os.getenv("EMAIL_INBOX", None)
    cutoff_date_string = os.getenv("CUTOFF_DATE", "2022-12-01")
    cutoff_date = datetime.strptime(cutoff_date_string, "%Y-%m-%d")

    # Step 1: Upsert Org
    # Once we get the access to there gmail, we create an org object in our database.
    # It will overlook all other entites in the DB and give them org-scoped to there email.
    org = get_org(email)

    if not org:
        insert_org(email, cutoff_date)
        org = get_org(email)

    fetcher_job(org, embeeding_model)

    processor_job(org)

    


# TODO: Add scheduling logic
# # schedule.every().day.at("10:00").do(job)

# while True:
#     schedule.run_pending()
#     time.sleep(1)
