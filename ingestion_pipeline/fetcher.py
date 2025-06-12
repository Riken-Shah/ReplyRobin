# Standard Library
from datetime import datetime
from pickle import FALSE
from typing import List
import base64  # Added for decoding message bodies
import re  # For regex fallback cleaning

# Third-party Libraries
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
from sqlmodel import TIMESTAMP  # Added for HTML to text conversion

try:
    from email_reply_parser import EmailReplyParser  # Best-in-class quoted-text remover
except ImportError:  # Optional dependency
    EmailReplyParser = None

# Local Modules
from ingestion_pipeline.db import DB
from ingestion_pipeline.schemas import Org, Thread, Message

SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.readonly"]

CHUNK_SIZE = 1000  # bulk-upsert slice


class Fetcher:
    """Service class that pulls email threads + messages for a single Org.

    Parameters
    ----------
    db : DB
        Database accessor (provides session + helpers).
    org : Org
        Organisation definition + Gmail credentials.
    service : googleapiclient.discovery.Resource | None
        Optional Gmail service – injected for easier unit-testing.
    """

    def __init__(self, db: DB, org: Org, service: Resource | None = None):
        self.db = db
        self.org = org

        if service is not None:
            self.service = service
        else:
            creds = Credentials.from_authorized_user_file(self.org.creds_file, SCOPES)
            self.service = build("gmail", "v1", credentials=creds)

    def initial_fetch(self) -> List[Thread]:
        """
        This function is responsible for fetching all the inital emails from the org provided gmail.
        It fetches all the threads, messages and stores them in our postgres database. Once that's done next step of proccesing is begin.
        """
        print("Fetching emails for org:", self.org.name)

        query_parts: List[str] = ["from:me"]
        if self.org.end_date:
            query_parts.append(f"after:{self.org.end_date.strftime('%Y-%m-%d')}")
        if self.org.preferred_emails:
            senders_query = " ".join(self.org.preferred_emails)
            query_parts.append(f"from:{senders_query}")
        query: str = " ".join(query_parts)

        try:
            # ---- Thread listing with pagination + retries ----
            thread_refs: list[dict] = []
            page_token: str | None = None
            fetched = 0
            while True:
                page_refs, page_token = self._list_threads(query, page_token)
                thread_refs.extend(page_refs)
                fetched += len(page_refs)
                if not page_token or fetched >= self.org.max_thread_count:
                    break
            print(f"Found {len(thread_refs)} candidate threads")

            if not thread_refs:
                print("No new threads to process.")
                return []

            thread_models: List[Thread] = []
            message_models: List[Message] = []

            for ref in thread_refs:
                try:
                    thread_detail = self._fetch_thread_detail(ref["id"])
                    messages = thread_detail.get("messages", [])

                    thread_obj = Thread(
                        id=thread_detail["id"],
                        message_count=len(messages),
                        last_synced_at=datetime.utcnow(),
                        history_id=int(thread_detail.get("historyId", 0)),
                    )
                    thread_models.append(thread_obj)

                    for msg in messages:
                        message_obj = Message(
                            id=msg["id"],
                            thread_id=thread_detail["id"],
                            label_ids=msg.get("labelIds", []),
                            history_id=msg.get("historyId", ""),
                            internal_date=datetime.fromtimestamp(
                                int(msg.get("internalDate", ""))
                                / 1000  # Convert ms to seconds
                            ),
                            size_estimate=msg.get("sizeEstimate", 0),
                            body=self._parse_payload_to_text(
                                msg["payload"]
                            ),  # Consider decoding this
                        )
                        print(message_obj.internal_date)
                        message_models.append(message_obj)

                except HttpError as thr_err:
                    print(f"Failed to fetch thread {ref['id']}: {thr_err}")
                except (ValueError, TypeError) as e:
                    print(f"Error processing thread {ref.get('id')}: {e}")

            # ---- Bulk upsert in manageable chunks ----
            with self.db.session_scope() as session:
                for i in range(0, len(thread_models), CHUNK_SIZE):
                    self.db.upsert_many(
                        session, Thread, thread_models[i : i + CHUNK_SIZE]
                    )
                if thread_models:
                    print(f"Persisted {len(thread_models)} threads.")

                for i in range(0, len(message_models), CHUNK_SIZE):
                    self.db.upsert_many(
                        session, Message, message_models[i : i + CHUNK_SIZE]
                    )
                if message_models:
                    print(f"Persisted {len(message_models)} messages.")

            return thread_models

        except HttpError as error:
            print(f"An error occurred while listing threads: {error}")
            return []

    # ------------------------------------------------------------------
    # Helper API calls with retry + type-hints
    # ------------------------------------------------------------------

    def _list_threads(
        self, query: str, page_token: str | None = None
    ) -> tuple[list[dict], str | None]:
        """List threads page with basic retry. Returns (threads, nextPageToken)."""
        for attempt in range(3):
            try:
                req = (
                    self.service.users()
                    .threads()
                    .list(userId="me", maxResults=self.org.max_thread_count, q=query)
                )
                if page_token:
                    req = req.pageToken(page_token)
                resp = req.execute()
                return resp.get("threads", []), resp.get("nextPageToken")
            except HttpError as err:
                print(f"List threads attempt {attempt + 1} failed: {err}")
                if attempt == 2:
                    raise
                import time

                time.sleep(2**attempt)

    def _fetch_thread_detail(self, thread_id: str) -> dict:
        """Fetch a single thread with retry and minimal fields."""
        for attempt in range(3):
            try:
                return (
                    self.service.users()
                    .threads()
                    .get(userId="me", id=thread_id, format="full")
                    .execute()
                )
            except HttpError as err:
                print(f"Fetch thread {thread_id} attempt {attempt + 1} failed: {err}")
                if attempt == 2:
                    raise
                import time

                time.sleep(2**attempt)
        return {}  # should not reach here

    def _parse_payload_to_text(self, payload: dict) -> str:
        """Parse the payload of a message and return its text content.

        The Gmail API represents messages as a tree of *parts*. Each part has a
        ``mimeType`` and may itself contain further ``parts`` (for multipart/*)
        or a ``body`` with base-64url encoded ``data``.

        Strategy
        --------
        1.  Walk the part tree depth-first until we find **text/plain**. Return
            the first plain-text segment encountered – this is usually the clean
            human-readable content.
        2.  If no plain-text is present, fall back to **text/html** and strip
            the markup with *BeautifulSoup*.
        3.  Ignore attachments and other binary parts (images, application/* …).
        """

        def _decode_body(body_dict: dict) -> str:
            """Decode the base64url body safely -> UTF-8 string."""
            data = body_dict.get("data", "")
            if not data:
                return ""
            # The API uses URL-safe base64 without padding.
            missing_padding = len(data) % 4
            if missing_padding:
                data += "=" * (4 - missing_padding)
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            except (ValueError, UnicodeDecodeError):
                return ""

        # Depth-first search for text/plain → html fallback
        html_fallback: str | None = None
        stack: list[dict] = [payload]
        while stack:
            part = stack.pop()
            mime_type = part.get("mimeType", "").lower()

            # Multipart container – push its children on the stack
            if mime_type.startswith("multipart/"):
                # Process children in reverse so that natural order is preserved when using stack pop()
                stack.extend(reversed(part.get("parts", [])))
                continue

            # Single leaf part
            if mime_type.startswith("text/plain"):
                text = _decode_body(part.get("body", {}))
                if text:
                    return self._clean_email_body(text)
            elif mime_type.startswith("text/html") and html_fallback is None:
                html_fallback = _decode_body(part.get("body", {}))

        if html_fallback:
            # Convert HTML -> plain text
            soup = BeautifulSoup(html_fallback, "html.parser")
            return self._clean_email_body(soup.get_text(separator=" ", strip=True))

        return ""  # Nothing readable found

    # ------------------------------------------------------------------
    # Message cleanup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_email_body(text: str) -> str:
        """Strip quoted replies and signatures from *text*.

        Preference order:
        1.  Use `email_reply_parser` when available – handles reply headers,
            quotation, signatures.
        2.  Regex fallback for environments where the package is missing.
        """

        if EmailReplyParser is not None:
            try:
                text = EmailReplyParser.read(text)
            except Exception:
                pass  # fall back to regex below if parser fails

        # We might need quoted and reply headers for chatracter profiling, so keeping them for now.
        # --- Minimal regex fallback ---
        # # Drop everything after typical reply header
        # text = re.split(r"\nOn .*wrote:", text)[0]
        # # Remove quoted lines beginning with '>'
        # text = "\n".join(
        #     line for line in text.splitlines() if not line.lstrip().startswith(">")
        # )
        # # Remove signature separator "-- " or "--\n"
        # text = text.split("\n--\n")[0].split("\n-- \n")[0]

        return text.strip()
