from dotenv import load_dotenv
from sqlalchemy import text


from common.db import DB


from common.schemas import Org, Message, Thread
from sqlmodel import select
from ingestion_pipeline.semantic_effort.qwen import QwenEmbeddingProcess
from agent_orchestration.character_profile import fetch_character_profile
from agent_orchestration.master_agent.worker import Worker
from agent_orchestration.master_agent.state import Email
from jobs.scheduler import pipe_jobs
import os


if __name__ == "__main__":
    load_dotenv()
    embeeding_model = QwenEmbeddingProcess()

    # 1. Initialize DB (triggers auto-migration in dev mode)
    db = DB()
    pipe_jobs(db, embeeding_model)

    # print("Processed {} new messages".format(len(new_messages)))

    email = os.getenv("EMAIL_INBOX")

    # Find the messages in the recent thread where thread size == 1 and it's not the owner.
    # And only reply if you think it's worth replying to.
    profile = fetch_character_profile(db, email)

    with db.session_scope() as session:
        result = session.exec(
            select(Message)
            .where(Message.sender != email)
            .where(
                Message.thread_id.in_(
                    select(Thread.id).where(Thread.message_count == 1)
                )
            )
        )
        msgs = result.all()

        worker = Worker()

        for root in msgs:
            subject = root.subject
            body = root.body
            current_email = Email(
                subject=root.subject, body=root.body, sender=root.sender
            )
            test_embedding = embeeding_model.embed(current_email.format())
            past_messages = db.vector_search(
                test_embedding, sender_email="support@karo.chat", match_count=8
            )
            past_messages = [
                Email(subject=msg.subject, body=msg.body, sender=msg.sender)
                for msg in past_messages
            ]
            print("Profile: ", profile)
            result = worker.run_agent(
                character_profile=profile,
                current_email=current_email,
                past_emails=past_messages,
            )
            print("Body: ", current_email.format())
            print("Final Draft: ", result.final_draft)
            # break


# Points to rembebmer:
# - we need to cite the context email and reasoing of selecting the stragey
# - give all the information to the user, subject email name and intent
# - use citation when reasoing the draft or possible plans this will lead to more concreate and closed approch
# - are we presuming to take any action? how to do avoid writting if we are not sure
# - create one multi-agent workflow
# - think how are we managing memory - org informaton, lingustic changes, specfic style changes
#
# - improve schemas and db calls
# - handle threads, save threads and avoid if thread is done 
