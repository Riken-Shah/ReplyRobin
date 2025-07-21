import os
from typing import List, Type
from sqlalchemy import text
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv
from contextlib import contextmanager
from sqlalchemy import select

# This line is crucial for SQLModel to discover the table models.
from common.schemas import *

load_dotenv()


class DB:
    def __init__(self, database_url: str = None):
        if database_url:
            self.db_url = database_url
        else:
            self.db_url = os.getenv("SUPABASE_POSTGRES_URL")
            if not self.db_url:
                raise ValueError(
                    "Database URL not found. Please set SUPABASE_POSTGRES_URL."
                )
        self.engine = create_engine(self.db_url)
        if os.getenv("ENV", "dev").lower() == "dev":
            self.destroy_db()
            self.create_db_and_tables()

    def destroy_db(self):
        """Destroy the database"""
        with self.engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f"""DO $$
DECLARE
    db_name text;
BEGIN
    FOR db_name IN
        SELECT datname FROM pg_database
        WHERE datistemplate = false AND datname <> 'postgres'
    LOOP
        EXECUTE format('DROP DATABASE IF EXISTS "%I";', db_name);
    END LOOP;
END$$;
""")
            )

    def create_db_and_tables(self):
        """Create the database and tables if in dev mode."""
        print("DEV MODE: Creating database and tables...")
        SQLModel.metadata.create_all(self.engine)
        print("Done.")

    def get_session(self) -> Session:
        """Get a SQLAlchemy session."""
        with Session(self.engine) as session:
            yield session

    def get_engine(self) -> Engine:
        """Get the SQLAlchemy engine."""
        return self.engine

    def upsert_many(
        self,
        session: Session,
        model_class: Type[SQLModel],
        data: List[SQLModel],
        preserve_existing: bool = False,
    ):
        """
        Performs a bulk "upsert" (INSERT ON CONFLICT UPDATE) operation.

        Args:
            session: The SQLAlchemy session to use.
            model_class: The SQLModel class of the objects.
            data: A list of SQLModel instances to upsert.
            preserve_existing: If True, only updates fields that are explicitly set (non-None)
                              in the incoming data objects, preserving existing values for other fields.
        """
        if not data:
            return

        # Convert models to dictionaries, filtering out None values if preserve_existing is True
        if preserve_existing:
            # Only include non-None values to avoid overwriting existing data
            dict_data = []
            for d in data:
                model_dict = d.model_dump(exclude_none=True)
                dict_data.append(model_dict)
        else:
            # Include all fields, potentially overwriting with None values
            dict_data = [d.model_dump() for d in data]

        stmt = insert(model_class).values(dict_data)

        # Detect primary key column names from SQLAlchemy Table metadata
        pk_cols = [col.name for col in model_class.__table__.primary_key.columns]
        if not pk_cols:
            raise ValueError(f"Model {model_class.__name__} has no primary key.")

        # Build dict of columns to update (exclude primary key cols)
        # When preserve_existing is True, we only include columns present in all objects
        if preserve_existing:
            # Get the set of fields that are explicitly set in each data object
            update_cols = {}
            for item in dict_data:
                for key, value in item.items():
                    if key not in pk_cols and key in stmt.excluded:
                        update_cols[key] = stmt.excluded[key]
        else:
            # Include all non-pk columns
            update_cols = {c.name: c for c in stmt.excluded if c.name not in pk_cols}

        stmt = stmt.on_conflict_do_update(
            index_elements=pk_cols,
            set_=update_cols,
        )
        session.execute(stmt)

    # ------------------ Session helper ------------------

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations.

        Usage:
            with db.session_scope() as session:
                session.add(obj)
                ...
        Commits on success, rolls back on exception.
        """
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def vector_search(
        self,
        embedding_vector,
        match_threshold=0.7,
        match_count=5,
        sender_email: Optional[str] = None,
    ) -> List[Message]:
        """Performs a semantic search using vector embeddings.

        Uses the match_documents SQL function to find semantically similar messages.

        Args:
            embedding_vector: The query embedding vector to search against
            match_threshold: Similarity threshold (0.0 to 1.0), higher means more similar
            match_count: Maximum number of results to return

        Returns:
            List of Message objects sorted by similarity (most similar first)
        """
        from sqlalchemy import text
        from common.schemas import Message

        with self.session_scope() as session:
            # Convert embedding to a format compatible with Postgres vector type
            if hasattr(embedding_vector, "tolist"):
                # Convert numpy arrays to list
                embedding_vector = embedding_vector.tolist()

            # Option 1: Using SQLModel's select and exec
            search = (
                select(Message.id, Message.body, Message.sender, Message.subject)
                .order_by(Message.body_embedding.l2_distance(embedding_vector))
                .limit(match_count)
            )

            if sender_email:
                search = search.where(Message.sender == sender_email)

            result = session.exec(search)

            # Simply return the results directly - they are already Message objects
            return result.all()
