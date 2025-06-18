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
            max_thread_count=10,
            end_date=datetime(2024, 1, 1),  # Set a more recent date
            email=email,
            creds_file=creds_file,
            inital_fetch=True,
        )
    else:
        print(f"Found existing Org for {email}")
        # Update fields that might change, like the creds file
        org.creds_file = creds_file

    session.add(org)
    session.commit()
    session.refresh(org)
    return org


if __name__ == "__main__":
    load_dotenv()

    # 1. Initialize DB (triggers auto-migration in dev mode)
    db = DB()

    email_to_test = "rikenshah.02@gmail.com"
    print("Starting Gmail API Auth...")
    creds_file = get_user_credentials_file(email_to_test)
    print("Creds file: ", creds_file)

    # 2. Get a session and create/update the Org object in the database
    # with next(db.get_session()) as session:
    #     org = create_or_update_org(session, email=email_to_test, creds_file=creds_file)
    org = Org(
        name="Test Org",
        end_date=datetime(2024, 1, 1),
        email=email_to_test,
        creds_file=creds_file,
        max_thread_count=10,
    )

    # 3. Initialize Fetcher with the DB instance and the Org object
    fetcher = Fetcher(db, org)

    # 4. Run the fetch process
    print("\nStarting fetch process...")
    fetcher.initial_fetch()
    print("\nFetch process complete.")

    # 5. Initialize Processor with the DB instance and the Org object
    processor = Processor(db, org)

    new_messages = []
    # Get messages from the database
    with db.session_scope() as session:
        result = session.exec(select(Message))
        msgs = result.all()

        for msg in msgs:
            print(msg.model_dump())
            new_messages.append(Message(**msg.model_dump()))

    # 6. Run the process process
    print("\nStarting process process...")
    processor.process(new_messages)
    print("\nProcess process co mplete.")
