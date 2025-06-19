from common.schemas import IntentEnum
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import List
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from .intent_examples import INTENT_EXAMPLES, ExtractedIntents
from common.schemas import Message
from typing import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
import uuid
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


class IntentExtractor:
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

        You can use following intents:
        {INTENT_ENUM}
        """.format(INTENT_ENUM=[intent.value for intent in IntentEnum])

        self.__examples = INTENT_EXAMPLES

        self.__batch_size = 20  # Number of emails to process at once, adjust this based on model % efficiency

        # Initialize LLM
        if "gemini" in model:
            self.__llm = ChatGoogleGenerativeAI(model=model, api_key=api_key)
            self.__batch_size = 10
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
            schema=ExtractedIntents,
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

    def extract(self, msgs: List[Message]) -> List[Message]:
        """
        Extract intents from the messages.
        """
        # Filter out messages that already have intents
        msgs = [msg for msg in msgs if not msg.intents]
        if len(msgs) == 0:
            return msgs

        # Batch messages
        batched_msgs = [
            msgs[i : i + self.__batch_size]
            for i in range(0, len(msgs), self.__batch_size)
        ]

        print(f"Batched {len(msgs)} messages into {len(batched_msgs)} batches")

        intent_map = {}

        # Extract intents for each batch
        for batch in batched_msgs:
            # Build prompt with messages
            user_prompt = self.__build_prompt_with_messages(batch)
            result: ExtractedIntents = self.__runnable.invoke(
                {"text": user_prompt, "examples": self.__messages_history}
            )

            # Map extracted intents to messages by message ID
            if result.extracted_intents:
                intent_map.update(
                    {
                        intent.message_id: intent.intents
                        for intent in result.extracted_intents
                    }
                )

            # Add a delay to avoid rate limiting
            time.sleep(1.5)

        for msg in msgs:
            if msg.id in intent_map:
                msg.intents = intent_map[msg.id]
            else:
                # If no intents were extracted for this message, set default intent
                print(f"No intents extracted for message ID: {msg.id}")
                msg.intents = [IntentEnum.GENERAL_QUESTION]

        return msgs


if __name__ == "__main__":
    msgs = [
        Message(
            id="23",
            body="Hey team, I am facing an issue with the app. Can you please help me?",
        ),
        Message(
            id="24",
            body="I've already paid for the app, but I'm not able to login. Can you please help me?",
        ),
        Message(id="26", body="Do you want to but our produce?"),
    ]
    intent_extractor = IntentExtractor()
    intent_extractor.extract(msgs)
    print(msgs)
