from turtle import st
from common.schemas import IntentEnum
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import List
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from .stylometry_signal_examples import STYLOMETRY_EXAMPLES, ExtractedStylometrySignals
from common.schemas import Message
from common.schemas import ToneEnum
from typing import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
import uuid
import re
import time


class Example(TypedDict):
    """A representation of an example consisting of text input and expected tool calls.

    For extraction, the tool calls are represented as instances of pydantic model.
    """

    input: str  # This is the example text
    tool_calls: List[BaseModel]  # Instances of pydantic model that should be extracted


def tool_example_to_messages(example: Example) -> List[BaseMessage]:
    """Convert an example into a list of messages that can be fed into an LLM.

    This code is an adapter that converts our example to a list of messages
    that can be fed into a chat model.

    The list of messages per example corresponds to:

    1) HumanMessage: contains the content from which content should be extracted.
    2) AIMessage: contains the extracted information from the model
    3) ToolMessage: contains confirmation to the model that the model requested a tool correctly.

    The ToolMessage is required because some of the chat models are hyper-optimized for agents
    rather than for an extraction use case.
    """
    messages: List[BaseMessage] = [HumanMessage(content=example["input"])]
    tool_calls = []
    for tool_call in example["tool_calls"]:
        tool_calls.append(
            {
                "id": str(uuid.uuid4()),
                "args": tool_call.model_dump(),
                # The name of the function right now corresponds
                # to the name of the pydantic model
                # This is implicit in the API right now,
                # and will be improved over time.
                "name": tool_call.__class__.__name__,
            },
        )
    messages.append(AIMessage(content="", tool_calls=tool_calls))
    tool_outputs = example.get("tool_outputs") or [
        "You have correctly called this tool."
    ] * len(tool_calls)
    for output, tool_call in zip(tool_outputs, tool_calls):
        messages.append(ToolMessage(content=output, tool_call_id=tool_call["id"]))
    return messages


class StyloMetrySignalExtractor:
    def __init__(
        self,
        model="gemini-1.5-flash",
        api_key="",
    ):
        self.__system_prompt = """
        You are an expert extraction algorithm. 
        Only extract relevant information from the email .
        If you do not know the value of an attribute asked
        to extract, return null for the attribute's value.

        You can use following tone:
        {TONE_ENUM} 
        """.format(TONE_ENUM=[tone.value for tone in ToneEnum])

        self.__examples = STYLOMETRY_EXAMPLES

        self.__batch_size = 20  # Number of emails to process at once, adjust this based on model % efficiency

        # Initialize LLM
        if "gemini" in model:
            self.__llm = ChatGoogleGenerativeAI(model=model, api_key=api_key)
            self.__batch_size = 5
        else:
            pass
            # self.__llm = ChatOpenAI(model=model, api_key=api_key)

        self.__prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.__system_prompt),
                MessagesPlaceholder("examples"),
                ("human", "{text}"),
            ]
        )

        # Messages History
        self.__messages_history = []

        # Load examples
        self.__load_examples()

        # Initialize runnable
        self.__runnable = self.__prompt | self.__llm.with_structured_output(
            schema=ExtractedStylometrySignals,
            # method="function_calling",
            include_raw=False,
        )

    def __load_examples(self):
        """
        Load examples into the prompt so that the LLM can learn from them.
        """
        for text, tool_call in self.__examples:
            self.__messages_history.extend(
                tool_example_to_messages({"input": text, "tool_calls": [tool_call]})
            )

        example_emails = [
            Message(id="example_1", body=text) for text, _ in self.__examples
        ]
        example_prompt = self.__build_prompt_with_messages(example_emails)

        example_prompt = self.__prompt.invoke(
            {"text": example_prompt, "examples": self.__messages_history}
        )

        for message in example_prompt.messages:
            # print(f"{message.type}: {message}")
            pass

    def __build_prompt_with_messages(self, msgs: List[Message]) -> str:
        """
        Build a prompt with the messages.
        """
        prompt = ""
        for msg in msgs:
            prompt += f"Message ID: {msg.id}: Message:{msg.body}\n"

        return prompt

    @staticmethod
    def __extract_emojis(text):
        """
        Extract all emojis from the given text.

        Args:
            text (str): Input text containing emojis

        Returns:
            list: List of all emojis found in the text
        """
        # Unicode ranges for emojis
        emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f700-\U0001f77f"  # alchemical symbols
            "\U0001f780-\U0001f7ff"  # geometric shapes
            "\U0001f800-\U0001f8ff"  # supplemental arrows
            "\U0001f900-\U0001f9ff"  # supplemental symbols & pictographs
            "\U0001fa00-\U0001fa6f"  # chess symbols
            "\U0001fa70-\U0001faff"  # symbols & pictographs extended-A
            "\U00002702-\U000027b0"  # dingbats
            "\U000024c2-\U0000257f"  # enclosed characters
            "\U00002600-\U000026ff"  # miscellaneous symbols
            "\U00002700-\U000027bf"  # dingbats
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002b05-\U00002b07"  # arrows
            "\U00002934-\U00002935"  # arrows
            "\U00003030"  # wavy dash
            "\U0000303d"  # part alternation mark
            "\U0000fe0f"  # variation selector
            "\U0000200d"  # zero width joiner
            "\U0000203c"  # double exclamation mark
            "\U00002049"  # exclamation question mark
            "\U00002122"  # trade mark
            "\U00002139"  # information
            "\U00002194-\U00002199"  # arrows
            "\U000021a9-\U000021aa"  # arrows
            "]",
            flags=re.UNICODE,
        )

        # Find all emojis in the text
        emojis = emoji_pattern.findall(text)

        return emojis

    def extract(self, msgs: List[Message]) -> List[Message]:
        """
        Extract stylometry signals from the messages."""

        # Filter out messages that already have stylometry signals
        msgs = [msg for msg in msgs if not msg.tone]
        if len(msgs) == 0:
            return msgs

        # Batch messages
        batched_msgs = [
            msgs[i : i + self.__batch_size]
            for i in range(0, len(msgs), self.__batch_size)
        ]

        print(f"Batched {len(msgs)} messages into {len(batched_msgs)} batches")

        stylometry_signals_map = {}

        # Extract stylometry signals for each batch
        for batch in batched_msgs:
            # Build prompt with messages
            user_prompt = self.__build_prompt_with_messages(batch)
            try:
                result: ExtractedStylometrySignals = self.__runnable.invoke(
                    {"text": user_prompt, "examples": self.__messages_history}
                )
            except Exception as e:
                print(f"Error extracting stylometry signals: {e}")
                continue

            # Map extracted stylometry signals to messages by message ID
            if result.extracted_stylometry_signals:
                stylometry_signals_map.update(
                    {
                        signal.message_id: signal
                        for signal in result.extracted_stylometry_signals
                    }
                )

            # Add a delay to avoid rate limiting
            time.sleep(1.5)

        for msg in msgs:
            if msg.id in stylometry_signals_map:
                msg.tone = stylometry_signals_map[msg.id].tone
                msg.greeting_phrases = stylometry_signals_map[msg.id].greeting_phrases
                msg.politeness_markers = stylometry_signals_map[
                    msg.id
                ].politeness_markers
                msg.modal_verbs = stylometry_signals_map[msg.id].modal_verbs
                msg.hedge_words = stylometry_signals_map[msg.id].hedge_words
                msg.boosters = stylometry_signals_map[msg.id].boosters
                msg.mitigating_phrases = stylometry_signals_map[
                    msg.id
                ].mitigating_phrases
                msg.urgency_phrases = stylometry_signals_map[msg.id].urgency_phrases
                msg.filler_words = stylometry_signals_map[msg.id].filler_words
                msg.question_phrases = stylometry_signals_map[msg.id].question_phrases
                msg.sentence_starters = stylometry_signals_map[msg.id].sentence_starters
                msg.passive_voice_patterns = stylometry_signals_map[
                    msg.id
                ].passive_voice_patterns
                msg.abbreviation_usage = stylometry_signals_map[
                    msg.id
                ].abbreviation_usage
                msg.discourse_markers = stylometry_signals_map[msg.id].discourse_markers
                msg.emoji_usage = self.__extract_emojis(msg.body)
            else:
                # If no stylometry signals were extracted for this message, log
                print(f"No stylometry signals extracted for message ID: {msg.id}")

        return msgs


if __name__ == "__main__":
    msgs = [
        Message(
            id="23",
            body="Hey Ramesh, So sorry to head that API is not working for you. We have indeifneifed the issue and fixed. It should work for you now. ",
        )
    ]
    signal_extractor = StyloMetrySignalExtractor()
    signal_extractor.extract(msgs)
    print(msgs)
