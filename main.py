from datetime import datetime
from dotenv import load_dotenv
from sqlmodel import Session

from common.db import DB
from ingestion_pipeline.fetcher import Fetcher
from data_enrichment.processor import Processor
from common.schemas import Org, Message
from sqlmodel import select
from local_auth.auth import get_user_credentials_file


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

    # 1. Initialize DB (triggers auto-migration in dev mode)
    db = DB()

    test_email = "support@karo.chat"

    print("Starting Gmail API Auth...")
    creds_file = get_user_credentials_file(test_email)
    print("Creds file: ", creds_file)

    # 2. Get a session and create/update the Org object in the database
    org = None
    with next(db.get_session()) as session:
        org = create_or_update_org(session, email=test_email, creds_file=creds_file)

    if not org:
        raise Exception("Org not found")

    # 3. Initialize Fetcher with the DB instance and the Org object
    fetcher = Fetcher(db, org)

    # 4. Run the fetch process
    print("\nStarting fetch process...")
    fetcher.initial_fetch()
    print("\nFetch process complete.")

    # # 5. Initialize Processor with the DB instance and the Org object
    processor = Processor(db, org)

    new_messages = []
    # Get messages from the database
    with db.session_scope() as session:
        result = session.exec(select(Message).where(Message.intents.is_(None)))
        msgs = result.all()

        for msg in msgs:
            new_messages.append(Message(**msg.model_dump()))

    # # 6. Run the process process
    print("\nStarting process process...")
    processor.process(new_messages)
    print("Found {} new messages to process".format(len(new_messages)))
    print("\nProcess process complete.")
