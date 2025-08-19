from pydantic import BaseModel
from typing import List

# from db.schemas import IntentEnum
from typing import Optional
from enum import Enum
from db.schemas import IntentEnum
from pydantic import Field


class MessageWithIntent(BaseModel):
    """Message with intent."""

    message_id: str = Field(default=None)
    intents: List[IntentEnum] = Field(default=[])


class ExtractedIntents(BaseModel):
    """Extracted intent about multiple messages."""

    extracted_intents: List[MessageWithIntent] = Field(default=[])


INTENT_EXAMPLES = [
    (
        """Message ID: example_1: Message:Hey Nelly,

It looks like there's an issue with delivering the OTP to you. Can you make sure you have your country code mentioned with your phone number? E.g. +27XXXXXXXXXX. 

If you don't get an SMS, as a backup, we attempt to send it via WhatsApp if the SMS fails. Would you be open to installing WhatsApp and receiving the OTP there instead?

Unfortunately, this happens randomly and is beyond our control at the moment, as we don't have a dedicated South African number—this increases the chances of SMS OTPs failing.""",
        ExtractedIntents(
            extracted_intents=[
                MessageWithIntent(
                    message_id="example_1",
                    intents=[IntentEnum.ACCOUNT_HELP],
                ),
            ],
        ),
    ),
    (
        """Message ID: example_2: Message:Hey Pulin, I spent almost 6 hours on this, but it keeps failing with an obscure error.

I'm afraid it might not be a quick fix, so I'll let it be and see if the solution comes naturally (it usually does).

I'm working on a shortcut that asks for the contact first and then the text as two separate shortcuts. I hope that works.

Apologies for the inconvenience. The code used to work, but it stopped working with a recent iOS version.

Regards,
Mustafa Yusuf""",
        ExtractedIntents(
            extracted_intents=[
                MessageWithIntent(
                    message_id="example_2",
                    intents=[IntentEnum.REPORT_BUG],
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
Mustafa""",
        ExtractedIntents(
            extracted_intents=[
                MessageWithIntent(
                    message_id="example_3",
                    intents=[IntentEnum.ASK_HOW_TO, IntentEnum.FEEDBACK_POSITIVE],
                ),
            ],
        ),
    ),
]
