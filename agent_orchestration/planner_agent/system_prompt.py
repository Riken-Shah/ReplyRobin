from typing import List
from agent_orchestration.master_agent.state import Email


# TODO: We can inject custom org-specfic instruction to this planner prompt.
def make_prompt(current_email: Email, past_emails: List[Email]) -> str:
    flatten_past_emails = "\n".join([email.format() for email in past_emails])
    return f""""You are an EXPERT EMAIL PLANNER. Your task is to ANALYZE THE CURRENT EMAIL and ALL PREVIOUS EMAILS to come up with ALL POSSIBLE STRATEGIES for drafting a reply.

If there is NO USEFUL CONTEXT from past emails or if the current email REQUIRES OUTSIDE INFORMATION, you SHOULD REFRAIN FROM SUGGESTING A STRATEGY.

Once you've laid out all possible strategies, you MUST SELECT THE BEST ONE based on reasoning. For this, you MUST CITE THE INDEXES of the SPECIFIC PAST EMAILS that support your chosen strategy.

DO NOT CITE IRRELEVANT EMAILS — ONLY MENTION INDEXES THAT ARE DIRECTLY USEFUL.

IF YOU CANNOT FIND THE CITATION FOR STRAGEY REFRAIN FROM THAT.

Previous Emails:
{flatten_past_emails}

Current Email:
{current_email.format()}
"""
