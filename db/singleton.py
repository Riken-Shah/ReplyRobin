from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

engine = None
session_manager = None


def init_engine():
    global engine, session_manager
    connection_link = os.getenv("POSTGRES_CONNECTION", None)
    if not connection_link:
        raise Exception("`POSTGRES_CONNECTION` not found in .env")

    engine = create_engine(connection_link, echo=True, future=True)
    session_manager = sessionmaker(engine)
    print("SESSION_MANAGER: ", session_manager)


def get_session_manager():
    return session_manager()
