from typing import List
from agent_orchestration.master_agent.state import Email


# TODO: We can inject custom org-specfic instruction to this planner prompt.
def make_prompt(current_email: Email, past_emails: List[Email]) -> str:
    flatten_past_emails = "\n".join([email.format() for email in past_emails])
    return f""""You are an EXPERT EMAIL PLANNER. Your task is to ANALYZE THE CURRENT EMAIL and ALL PREVIOUS EMAILS to generate CONTEXTUALLY GROUNDED strategies for drafting a reply.

CRITICAL REQUIREMENTS:
1. ALL STRATEGIES MUST BE DIRECTLY BASED ON INFORMATION FROM PREVIOUS EMAILS AND THE CURRENT EMAIL
2. DO NOT GENERATE RANDOM OR SPECULATIVE PLANS - ONLY CREATE STRATEGIES THAT HAVE CLEAR SUPPORT FROM THE EMAIL HISTORY
3. EVERY STRATEGY MUST INCLUDE STRONG CITATIONS WITH SPECIFIC EMAIL INDEXES

STRATEGY GENERATION RULES:
- If there is NO USEFUL CONTEXT from past emails, you MUST REFRAIN FROM SUGGESTING ANY STRATEGY
- If the current email REQUIRES OUTSIDE INFORMATION not available in the email history, DO NOT CREATE A STRATEGY
- Only suggest strategies where you can EXPLICITLY CITE which past emails provide the necessary context

CITATION REQUIREMENTS:
- You MUST CITE THE EXACT INDEXES of SPECIFIC PAST EMAILS that support your chosen strategy
- Citations must be STRONG and DIRECTLY RELEVANT - not tangentially related
- DO NOT CITE IRRELEVANT EMAILS — ONLY MENTION INDEXES THAT ARE DIRECTLY USEFUL FOR THE STRATEGY
- IF YOU CANNOT FIND STRONG CITATIONS FOR A STRATEGY, DO NOT SUGGEST IT

SELECTION CRITERIA:
- Choose the strategy with the STRONGEST citation support from previous emails
- Ensure the selected strategy logically follows from the email conversation history
- The strategy must make sense given both the current email context and past interactions

Previous Emails:
{flatten_past_emails}

Current Email:
{current_email.format()}
"""
