from common.db import DB
from common.schemas import Org, Message
import talon
from talon import quotations
from talon.signature.bruteforce import extract_signature
from typing import List
from .intent_extractor import IntentExtractor
from .stylometry_signal_extractor import StyloMetrySignalExtractor
from os import getenv


class Processor:
    def __init__(self, db: DB, org: Org):
        # Initialize talon
        talon.init()

        self.db = db
        self.org = org

        self.model_name = "gemini-1.5-flash"
        self.__gemini_api_key = getenv("GEMNI_API_KEY")
        self.intent_extractor = IntentExtractor(model=self.model_name, api_key=self.__gemini_api_key)

        self.stylometry_signal_extractor = StyloMetrySignalExtractor(model=self.model_name, api_key=self.__gemini_api_key)

    def process(self, msgs: List[Message]):
        """
        For all the message we will extract,
        `cleaned_content` - message stripped of quotes, starting and ending signatures
        `intents` - list of intent - each intent should be atomic i.e it should not be able to decompose into sub-intents

        Additonaly for message written by customer reps and founders we will try to extract additonal stylometry signals.
        This will later help us in building a strong character profile when writting drafts.

        --- IMPLEMENTATION ---
        For `cleaned_content` we will use regex based and progrmattic approach to strip quotes, starting and ending signatures.
        This will help us save us lot in token cost.

        For `intents` we will do batch of email usually with the LLM which has long context (gemini 1.5 flash or similar models)
        We will supply it few zero shot examples with the enum of intents, we will supply it with 10-20 emails and ask it to extract intents from them.
        Goal is to keep output tokens as low as possible, this will further help us reduce our costs.

        For stylometry signals we will batch user emails and do the similr extractions flow.
        """
        customer_messages: List[Message] = []
        user_messages: List[Message] = []

        # Extract clean content
        for msg in msgs:
            msg.cleaned_content = self.__extract_clean_content(msg.body)

        # Extract intents
        self.intent_extractor.extract(msgs)

        # Split into user / customer messages
        for msg in msgs:
            if msg.sender == self.org.email:
                user_messages.append(msg)
            else:
                customer_messages.append(msg)

        # Extract stylometry signals
        self.stylometry_signal_extractor.extract(user_messages)

        # Upsert all messages to the database after processing
        with self.db.session_scope() as session:
            self.db.upsert_many(session, Message, msgs)
            print(f"Upserted {len(msgs)} messages to the database")

    def __extract_clean_content(self, content: str) -> str:
        """
        Extract clean content from the message.

        Strip quotes, starting and ending signatures.
        """

        print("conetn: ", content)

        # We are currently using talon's bruteforce method to extract signature, to avoid extra overhead SVM computation.
        stripped_signature, _ = extract_signature(content)

        if self.__is_html(content):
            return quotations.extract_from(stripped_signature, content_type="text/html")
        else:
            return quotations.extract_from(stripped_signature)

    @staticmethod
    def __is_html(text: str) -> bool:
        """
        Check if the text is HTML.
        """
        # Skip if text is empty or None
        if not text:
            return False

        # Quick check for common HTML indicators
        if any(
            indicator in text
            for indicator in ["<html", "<body", "<div", "<p", "<span", "<!DOCTYPE"]
        ):
            return True

        # More thorough check with regex
        import re

        html_pattern = re.compile(r"<\s*[a-zA-Z]+.*?>|<\s*/\s*[a-zA-Z]+\s*>")
        return bool(html_pattern.search(text))


if __name__ == "__main__":
    p = Processor(None, None)

    email_body = """
Thanks Sasha, I can't go any higher and is why I limited it to the
homepage.

John Doe
via mobile
"""

    print(p.extract_clean_content(email_body))
