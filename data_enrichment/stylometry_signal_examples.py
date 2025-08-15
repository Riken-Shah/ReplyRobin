from pydantic import BaseModel, Field
from typing import List, Optional
from db.schemas import ToneEnum


# Stylometry signals for a single message
class StylometrySignalsFromMessage(BaseModel):
    """Various stylometry signals extracted from a message."""

    message_id: str = Field(default=None)

    tone: Optional[ToneEnum] = Field(
        ToneEnum.NEUTRAL,
        description="Overall tone of the message, such as friendly, formal, or urgent",
    )

    greeting_phrases: Optional[List[str]] = Field(
        None,
        description="Common greetings used by the user, e.g., 'Hey team', 'Dear John', 'Hi all'.",
    )

    politeness_markers: Optional[List[str]] = Field(
        None,
        description="Phrases indicating politeness, e.g., 'Please', 'Kindly', 'Would you mind'.",
    )

    modal_verbs: Optional[List[str]] = Field(
        None,
        description="Softening verbs often used to express possibility or permission, e.g., 'might', 'could', 'should'.",
    )

    hedge_words: Optional[List[str]] = Field(
        None,
        description="Words used to reduce assertiveness, e.g., 'maybe', 'a bit', 'perhaps', 'seems'.",
    )

    boosters: Optional[List[str]] = Field(
        None,
        description="Words that intensify or emphasize certainty, e.g., 'definitely', 'certainly', 'absolutely'.",
    )

    mitigating_phrases: Optional[List[str]] = Field(
        None,
        description="Words that soften tone or de-escalate, e.g., 'just', 'only', 'sort of'.",
    )

    urgency_phrases: Optional[List[str]] = Field(
        None,
        description="Time-sensitive phrases that reflect urgency, e.g., 'asap', 'at your earliest convenience'.",
    )

    filler_words: Optional[List[str]] = Field(
        None,
        description="Conversational fillers, e.g., 'like', 'well', 'so', 'you know'. Often informal tone signals.",
    )

    question_phrases: Optional[List[str]] = Field(
        None,
        description="Common patterns when asking questions, e.g., 'Could you please', 'Would it be possible'.",
    )

    sentence_starters: Optional[List[str]] = Field(
        None,
        description="Frequent openers at the beginning of sentences or emails, e.g., 'Hope you're well', 'Just checking in'.",
    )

    passive_voice_patterns: Optional[List[str]] = Field(
        None,
        description="Patterns that indicate passive voice, e.g., 'It was done', 'The report was completed'.",
    )

    abbreviation_usage: Optional[List[str]] = Field(
        None,
        description="Preferred acronyms or abbreviations, e.g., 'FYI', 'ASAP', 'TBD', 'ETA'.",
    )

    discourse_markers: Optional[List[str]] = Field(
        None,
        description="Transition or coherence markers for structuring flow, e.g., 'That said', 'Moreover', 'By the way'.",
    )


# Stylometry container for multiple messages
class ExtractedStylometrySignals(BaseModel):
    """Extracted stylometry signals about multiple messages."""

    extracted_stylometry_signals: List[StylometrySignalsFromMessage] = Field(default=[])


# === Stylometry Examples ===
STYLOMETRY_EXAMPLES = [
    (
        """Message ID: example_1: Message:Thanks for sharing and spotting that Paul. v1.0.1 which is now live on the App Store fixes it. 
So silly of me to miss it! 

Hope you're enjoying the app and its experience!

Message ID: example_2: Message:Hey Pulin, I spent almost 6 hours on this, but it keeps failing with an obscure error.

I'm afraid it might not be a quick fix, so I'll let it be and see if the solution comes naturally (it usually does).

I'm working on a shortcut that asks for the contact first and then the text as two separate shortcuts. I hope that works.

Apologies for the inconvenience. The code used to work, but it stopped working with a recent iOS version.

Regards,
Mustafa Yusuf
""",
        ExtractedStylometrySignals(
            extracted_stylometry_signals=[
                StylometrySignalsFromMessage(
                    message_id="example_1",
                    tone=ToneEnum.FRIENDLY,
                    greeting_phrases=["Thanks for sharing"],
                    politeness_markers=["Thanks"],
                    modal_verbs=[],
                    hedge_words=[],
                    boosters=[],
                    mitigating_phrases=["so silly of me", "Hope"],
                    urgency_phrases=[],
                    filler_words=["so"],
                    question_phrases=[],
                    sentence_starters=["Thanks for sharing", "Hope you’re enjoying"],
                    passive_voice_patterns=["is now live on the App Store"],
                    abbreviation_usage=["v1.0.1"],
                    discourse_markers=[],
                ),
                StylometrySignalsFromMessage(
                    message_id="example_2",
                    tone=ToneEnum.APOLOGETIC,
                    greeting_phrases=["Hey Pulin"],
                    politeness_markers=["Apologies"],
                    modal_verbs=["might", "will", "hope"],
                    hedge_words=["almost", "usually"],
                    boosters=[],
                    mitigating_phrases=["I'm afraid", "might not", "let it be"],
                    urgency_phrases=[],
                    filler_words=["so"],
                    question_phrases=[],
                    sentence_starters=[
                        "Hey Pulin",
                        "I'm afraid",
                        "I'm working on",
                        "Apologies for the inconvenience",
                    ],
                    passive_voice_patterns=[
                        "it keeps failing",
                        "it used to work",
                        "it stopped working",
                    ],
                    abbreviation_usage=["iOS"],
                    discourse_markers=[],
                ),
            ],
        ),
    ),
    (
        """Message ID: example_3: Message:Hi Jihad,

Thank you for reaching out! I'm so glad you love the WhatsApp integration—it's my favorite too!

Karo integrates seamlessly with Apple Reminders. To enable it:
1. Go to the Home Screen in Karo.
2. Tap the icon in the top left and select Apple Reminders.

This integration syncs tasks from Apple Reminders into Karo, and updates are sent back to Apple Reminders when you or someone you delegate to acts on them.

Please note, tasks created in Karo don't sync to Apple Reminders to avoid duplicate notifications and any confusion. This approach ensures you can continue creating tasks in Apple Reminders and delegate them easily using Karo while keeping everything in sync.

Let us know if you have any other questions or feedback. Wishing you a fantastic end to 2024 and a happy, prosperous new year, Jihad!

Best regards,
Mustafa

Message ID: example_4: Message:Hi team,

Just wanted to follow up quickly on the API rate limit issue we observed yesterday. It seems like the backend might be throttling unexpectedly.

Could you please confirm if there were any recent changes to the rate limiter logic?

Also, kindly ensure the fallback queue gets triggered in such cases. I know things have been hectic, so no worries if you haven’t had the chance yet.

FYI, I’ve rolled back to the last stable deployment as a precaution.

Best,
Riken
""",
        ExtractedStylometrySignals(
            extracted_stylometry_signals=[
                StylometrySignalsFromMessage(
                    message_id="",
                    tone=ToneEnum.FRIENDLY,
                    greeting_phrases=["Hi Jihad"],
                    politeness_markers=[
                        "Thank you",
                        "Please",
                        "Let us know",
                        "Best regards",
                    ],
                    modal_verbs=["can", "don’t", "ensures"],
                    hedge_words=[],
                    boosters=["so glad"],
                    mitigating_phrases=["just", "to avoid"],
                    urgency_phrases=[],
                    filler_words=["so"],
                    question_phrases=[
                        "Let us know if you have any other questions or feedback"
                    ],
                    sentence_starters=[
                        "Hi Jihad",
                        "Thank you for reaching out",
                        "Please note",
                        "Let us know",
                        "Wishing you",
                    ],
                    passive_voice_patterns=[
                        "are sent back",
                        "tasks created in Karo don’t sync",
                    ],
                    abbreviation_usage=[],
                    discourse_markers=["Please note"],
                ),
                StylometrySignalsFromMessage(
                    message_id="",
                    tone=ToneEnum.DIPLOMATIC,
                    greeting_phrases=["Hi team"],
                    politeness_markers=["Could you please", "kindly", "Best"],
                    modal_verbs=["might", "could", "haven’t"],
                    hedge_words=["seems like", "might", "if"],
                    boosters=[],
                    mitigating_phrases=["just", "no worries", "as a precaution"],
                    urgency_phrases=[],
                    filler_words=["just", "so"],
                    question_phrases=[
                        "Could you please confirm",
                        "if there were any recent changes",
                    ],
                    sentence_starters=[
                        "Hi team",
                        "Just wanted to follow up",
                        "Could you please",
                        "Also, kindly ensure",
                        "FYI, I’ve rolled back",
                    ],
                    passive_voice_patterns=["gets triggered"],
                    abbreviation_usage=["API", "FYI"],
                    discourse_markers=["Also", "FYI"],
                ),
            ],
        ),
    ),
]
