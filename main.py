from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session

from common.db import DB
from ingestion_pipeline.fetcher import Fetcher
from data_enrichment.processor import Processor
from common.schemas import Org, Message, Thread
from sqlmodel import select
from local_auth.auth import get_user_credentials_file
from ingestion_pipeline.semantic_effort.qwen import QwenEmbeddingProcess
from reasoning_agent.agent import analyze_email_intent_simplified
from character_agent.mimic import MimicAgent, run_email_generation
from character_agent.understand_agent import get_strategy

def create_or_update_org(session: Session, email: str, creds_file: str) -> Org:
    """Gets an existing Org or creates a new one."""
    org = session.get(Org, email)
    if not org:
        print(f"Creating new Org for {email}")
        org = Org(
            name="Test Org",
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


if __name__ == "__main__":
    load_dotenv()
    embeeding_model = QwenEmbeddingProcess()

    # 1. Initialize DB (triggers auto-migration in dev mode)
    db = DB()

    test_email = "support@karo.chat"

    # Step 0: Access to GMAIL
    # Get the user's credentials file (stored as [email].json in our storage), this file is generated once 
    # user authorizes as access to there gmail account.
    creds_file = get_user_credentials_file(test_email)

    
    # Step 1: Upsert Org 
    # Once we get the access to there gmail, we create an org object in our database.
    # It will overlook all other entites in the DB and give them org-scoped to there email.
    org = None
    with next(db.get_session()) as session:
        org = create_or_update_org(session, email=test_email, creds_file=creds_file)

    if not org:
        raise Exception("Org not found")

    # Step 2: Fetch threads + messages
    # Our Fetcher class is responsible to do continuous fetching of threads + messages from the org's gmail account.
    # We can run this as cron job every hour, there might be a case where it fetches & computes few threads 
    # again because we are using `nextPageToken` of `threads.list` API to fetch threads.
    fetcher = Fetcher(db, org, embedding_process=embeeding_model)
    fetcher.initial_fetch()

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
    print("Processed {} new messages".format(len(new_messages)))

    # Find the messages in the recent thread where thread size == 1 and it's not the owner. 
    # And only reply if you think it's worth replying to.

    agent = MimicAgent(db, org)
    profile = agent.fetch_character_profile("support@karo.chat")

    with db.session_scope() as session:
        result = session.exec(select(Message).where(Message.sender != org.email).where(Message.thread_id.in_(select(Thread.id).where(Thread.message_count == 1))))
        msgs = result.all()
        
        for root in msgs:
            subject = root.subject
            body = root.body
            one = f"Subject: {subject} Body: {body}"
            test_embedding = embeeding_model.embed(one)
            past_messages = db.vector_search(test_embedding, sender_email="support@karo.chat", match_count=8)
            past_messages = [f"Subject: {msg.subject} Body: {msg.body}" for msg in past_messages] 
            strategy = get_strategy(one, past_messages)
            result = run_email_generation(character_profile=profile, past_emails=past_messages, email_context=strategy.reason, required_intents=strategy.draft_intent)
            print("Body: ", one)
            print("Strategy: ", strategy.reason, strategy.draft_intent, strategy.confidence, strategy.useful_context_previous_emails)
            print("Final Draft: ", result.get("final_draft"))

        

