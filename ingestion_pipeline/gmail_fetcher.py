# Standard Library
from datetime import datetime
from typing import List, Optional
import base64  # Added for decoding message bodies
import re  # For regex fallback cleaning
from email.message import EmailMessage


# Third-party Libraries
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
from datetime import timezone
import httplib2
from google_auth_httplib2 import AuthorizedHttp

# Local Modules
# from common.db import DB
from db.schemas import Org, Thread, Message
from .semantic_effort.vector_embeeding import VectorEmbeddingProcess
import numpy as np
from typing import Tuple, Union
from local_auth.manage_secret_file import get_secret_file

SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.readonly"]

CHUNK_SIZE = 1000  # bulk-upsert slice


class GmailClient:
    """GmailClient handles everything releated to GMAIL for us.

    Parameters
    ----------
    org : Org
        Organisation definition + Gmail credentials.
    embedding_process: VectorEmbeddingProcess
        Any embedding class deried from VectorEmbeddingProcess
        used for semantic search
    """

    def __init__(
        self,
        org: Org,
        embedding_process: VectorEmbeddingProcess | None = None,
    ):
        self.org = org

        creds = Credentials.from_authorized_user_file(
            get_secret_file(org.email), SCOPES
        )
        # Create an authorized HTTP client for longer timeouts for large threads
        http = httplib2.Http(timeout=120)  # Timeout in seconds
        authed_http = AuthorizedHttp(creds, http=http)
        self.service = build("gmail", "v1", http=authed_http)

        self.__inital_sync = self.org.page_tokens is None
        self.__embedding_process = embedding_process

    def resume_threads_fetch(
        self,
    ) -> Tuple[List[Thread], List[Message], Union[str, None]]:
        """
        This function is responsible to give us paginated (from source if no next token found)
        Threads and there respected Messages.
        """
        # Build the inital query and then use nextPageToken to get continous updated threads + messages
        query_parts: List[str] = []

        # This is optional if you want to build scoped dataset with only few sender
        # if self.org.preferred_emails:
        #     senders_query = " ".join(self.org.preferred_emails)
        #     query_parts.append(f"from:{senders_query}")

        if self.org.cutoff_date:
            query_parts.append(f"after:{self.org.cutoff_date.strftime('%Y-%m-%d')}")

        query: str = " ".join(query_parts)

        try:
            # First fetch all the threads, using the page_token

            # Note: There could be good chance that last few threads
            # gets duplicated everytime we run if there are no new
            # threads
            thread_refs: list[dict] = []
            page_token = self.org.get_page_token("threads")
            fetched = 0
            last_page_token = None  # Store not-null page token
            while True:
                page_refs, page_token = self._list_threads(query, page_token)
                thread_refs.extend(page_refs)
                fetched += len(page_refs)
                if page_token:
                    last_page_token = page_token
                if not page_token or (self.__inital_sync and fetched >= 100):
                    break
            print(f"Found {len(thread_refs)} candidate threads")

            if not thread_refs:
                print("No new threads to process.")
                return [], [], last_page_token

            thread_models: List[Thread] = []
            message_models: List[Message] = []

            now_timestamp = datetime.now(timezone.utc)

            # Now fetch each thread in detail, this is individual API call for each thread,
            # fetches all the messages
            for ref in thread_refs:
                try:
                    thread_detail = self._fetch_thread_detail(ref["id"])
                    messages = thread_detail.get("messages", [])

                    thread_obj = Thread(
                        id=thread_detail["id"],
                        message_count=len(messages),
                        last_sync=datetime.now(),
                        history_id=int(thread_detail.get("historyId", 0)),
                        org_id=self.org.email,
                        created_at=now_timestamp,
                        updated_at=now_timestamp,
                    )
                    thread_models.append(thread_obj)

                    previous_message_id = None
                    # Parse recipients
                    # recipient for in header_info.get("recipients", []) # parse {support@karo.chat}

                    for msg in messages:
                        # Extract all header information using the comprehensive function
                        header_info = self._extract_comprehensive_headers(msg)
                        clean_body = self._parse_payload_to_text(msg["payload"])
                        from sqlalchemy import null

                        recipients_emails = header_info.get("recipients", [])

                        message_obj = Message(
                            id=msg["id"],
                            org_id=self.org.email,
                            thread_id=thread_detail["id"],
                            label_ids=msg.get("labelIds", []),
                            history_id=msg.get("historyId", ""),
                            internal_date=datetime.fromtimestamp(
                                int(msg.get("internalDate", ""))
                                / 1000  # Convert ms to seconds
                            ),
                            size_estimate=msg.get("sizeEstimate", 0),
                            raw_content=clean_body,
                            # Email header fields
                            subject=header_info.get("subject"),
                            sender=header_info.get("sender"),
                            receiver=recipients_emails,
                            # Additional metadata
                            parent_message_id=previous_message_id,
                            embeeding=self.__embedding_process.embed(
                                clean_body
                            ).tolist(),
                            created_at=now_timestamp,
                            updated_at=now_timestamp,
                            signals=null(),
                        )
                        message_models.append(message_obj)

                        previous_message_id = message_obj.id

                except HttpError as thr_err:
                    print(f"Failed to fetch thread {ref['id']}: {thr_err}")
                except (ValueError, TypeError) as e:
                    print(f"Error processing thread {ref.get('id')}: {e}")

            return thread_models, message_models, last_page_token
        except HttpError as error:
            print(f"An error occurred while listing threads: {error}")
            return []

    # ------------------------------------------------------------------
    # Helper API calls with retry + type-hints
    # ------------------------------------------------------------------

    def create_thread_draft(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> dict:
        """Create a draft for new thread or existing thread.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body content
            thread_id: Existing thread ID to reply to (optional, creates new thread if None)
            from_email: Sender email (optional, uses authenticated user if None)
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)

        Returns:
            dict: The draft object containing the message details
        """
        if thread_id:
            print(f"Creating draft for existing thread: {thread_id}")
        else:
            print(f"Creating thread draft with subject: {subject}")

        for attempt in range(3):
            try:
                # Create the email message
                msg = EmailMessage()
                msg.set_content(body)
                msg["To"] = to_email
                msg["Subject"] = subject

                # Set sender if provided
                if from_email:
                    msg["From"] = from_email

                # Add CC recipients if provided
                if cc:
                    msg["Cc"] = ", ".join(cc)

                # Add BCC recipients if provided
                if bcc:
                    msg["Bcc"] = ", ".join(bcc)

                # Encode the message
                encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()

                # Create the draft payload
                create_message = {"message": {"raw": encoded_message}}

                # Add thread ID if replying to existing thread
                if thread_id:
                    create_message["message"]["threadId"] = thread_id

                # Create the draft
                req = (
                    self.service.users()
                    .drafts()
                    .create(userId="me", body=create_message)
                )

                result = req.execute()

                print(f"Draft created with ID: {result.get('id')}")
                print(f"Thread ID will be: {result.get('message', {}).get('threadId')}")

                return result

            except HttpError as err:
                print(f"Create thread draft attempt {attempt + 1} failed: {err}")
                if attempt == 2:
                    raise
                import time

                time.sleep(2**attempt)

    def _list_threads(
        self,
        query: str,
        page_token: str | None = None,
        label_ids: Optional[List[str]] = None,
    ) -> tuple[list[dict], str | None]:
        print("Listing threads with query: {}".format(query))
        """List threads page with basic retry. Returns (threads, nextPageToken)."""
        print(
            "Listing threads with query: {}; Page Token: {}".format(query, page_token)
        )
        for attempt in range(3):
            try:
                req = (
                    self.service.users()
                    .threads()
                    .list(
                        userId="me",
                        maxResults=10,
                        q=query,
                        pageToken=page_token,
                    )
                )
                resp = req.execute()
                return resp.get("threads", []), resp.get("nextPageToken")
            except HttpError as err:
                print(f"List threads attempt {attempt + 1} failed: {err}")
                if attempt == 2:
                    raise
                import time

                time.sleep(2**attempt)

    def _fetch_thread_detail(self, thread_id: str) -> Thread:
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

    def _generate_embeddings(self, text: str) -> np.ndarray:
        return self.__embedding_process.embed(text)

    # ------------------------------------------------------------------
    # Message cleanup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_email_body(text: str) -> str:
        """Strip quoted replies and signatures from *text*.

        Approach:
        1.  Regex fallback as a safety net if talon processing fails
        """

        # We might need quoted and reply headers for character profiling, but we'll
        # provide a way to remove them if desired
        # --- Minimal regex fallback ---
        # Drop everything after typical reply header
        text = re.split(r"\nOn .*wrote:", text)[0]
        # Remove quoted lines beginning with '>'
        text = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith(">")
        )
        # Remove signature separator "-- " or "--\n"
        text = text.split("\n--\n")[0].split("\n-- \n")[0]

        return text.strip()

    @staticmethod
    def _extract_email_from_header(header_value: str) -> str:
        """Extract email from a header value in the format: 'Name <email@example.com>'"""
        if not header_value:
            return ""

        # Find the part in angle brackets
        match = re.search(r"<([^>]+)>", header_value)
        if match:
            return match.group(1)  # Return just the email part
        return header_value  # Return the whole value if no angle brackets

    @staticmethod
    def _extract_comprehensive_headers(message: dict) -> dict:
        """Extract all relevant headers from an email message.

        This function extracts email headers including:
        - Subject
        - Sender
        - Reply-To
        - Recipients (To)
        - CC Recipients
        - BCC Recipients (when available)
        - Message-ID
        - References
        - In-Reply-To
        - Importance/Priority

        Args:
            message (dict): The message object from Gmail API

        Returns:
            dict: Dictionary containing all extracted header fields
        """
        headers = {}
        payload = message.get("payload", {})
        message_headers = payload.get("headers", [])

        # Initialize lists for array fields
        headers["recipients"] = []
        headers["cc_recipients"] = []
        headers["bcc_recipients"] = []
        headers["references"] = []

        # Extract header values
        for header in message_headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")

            if name == "subject":
                headers["subject"] = value
            elif name == "from":
                headers["sender"] = GmailClient._extract_email_from_header(value)
            elif name == "reply-to":
                headers["reply_to"] = GmailClient._extract_email_from_header(value)
            elif name == "to":
                # Split multiple recipients and extract emails
                recipients = [
                    GmailClient._extract_email_from_header(r.strip())
                    for r in value.split(",")
                    if r.strip()
                ]
                headers["recipients"] = recipients
            elif name == "cc":
                cc_recipients = [
                    GmailClient._extract_email_from_header(r.strip())
                    for r in value.split(",")
                    if r.strip()
                ]
                headers["cc_recipients"] = cc_recipients
            elif name == "bcc":
                bcc_recipients = [
                    GmailClient._extract_email_from_header(r.strip())
                    for r in value.split(",")
                    if r.strip()
                ]
                headers["bcc_recipients"] = bcc_recipients
            elif name == "message-id":
                # Remove angle brackets if present
                msg_id = value.strip()
                if msg_id.startswith("<") and msg_id.endswith(">"):
                    msg_id = msg_id[1:-1]
                headers["message_id"] = msg_id
            elif name == "references":
                # Split multiple references and clean them
                refs = [ref.strip() for ref in value.split() if ref.strip()]
                # Remove angle brackets if present
                refs = [
                    ref[1:-1] if ref.startswith("<") and ref.endswith(">") else ref
                    for ref in refs
                ]
                headers["references"] = refs
            elif name == "in-reply-to":
                in_reply_to = value.strip()
                if in_reply_to.startswith("<") and in_reply_to.endswith(">"):
                    in_reply_to = in_reply_to[1:-1]
                headers["in_reply_to"] = in_reply_to
            elif name in ("importance", "x-priority", "priority"):
                headers["importance"] = value

        return headers
