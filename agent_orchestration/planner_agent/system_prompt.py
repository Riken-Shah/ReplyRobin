from typing import List
from agent_orchestration.master_agent.state import Email


# TODO: We can inject custom org-specfic instruction to this planner prompt.
def make_prompt(current_email: Email, past_emails: List[Email]) -> str:
    flatten_past_emails = "\n".join([email.format() for email in past_emails])
    return f""""You are an expert planner your job is to figure out all the possible plan of drafting the email based on previous context. 
If you need access to other information, or there is no past emails, it's better to refrain from answering the email.

Among all the stragy laid out, you have to reason which might be the best stragey going forward, you have to cite which past email you have used
to come to this conclusion.

ONLY cite the indexes of past emails which is useful in our current stragey

Previous Emails:
{flatten_past_emails}

Current Email:
{current_email.format()}
"""
