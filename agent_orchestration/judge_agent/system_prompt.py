from typing import List, Dict
from agent_orchestration.master_agent.state import Email


# TODO: We can inject custom org-specfic instruction to this judge prompt.
def make_prompt(
    character_profile: Dict, reference_emails: List[str], current_email: Email
) -> str:
    """Create comprehensive judge evaluation prompt with intent checking"""

    ref_email_section = ""
    if reference_emails:
        email_list = "\n   ".join([f"- {email}" for email in reference_emails])
        ref_email_section = f"""
5. INTENT FULFILLMENT (Weight: 20%)
   Check if the email fulfills ALL required intents based on reference emails:
   {email_list}
   - Score 10/10 if ALL intents are clearly addressed
   - Score 8/10 if most intents addressed but some could be clearer
   - Score 6/10 if some intents missing or poorly addressed
   - Score 4/10 or lower if major intents are missing or unclear
"""

    return f"""You are a Style Matching Evaluator. Provide detailed scoring of how well the draft matches the target user's writing style AND fulfills the required intent.

EVALUATION CRITERIA - Score each section 0-10:

1. STRUCTURE (Weight: 15%)
   - Appropriate paragraph structure
   - Overall email organization

2. LINGUISTIC PATTERNS (Weight: 30%)
   - Hedge words: Target {character_profile.avg_num_hedge_words}
     Should use: {character_profile.top_hedge_words}
   - Modal verbs: Target {character_profile.avg_num_modal_verbs}
     Should use: {character_profile.top_modal_verbs}
   - Politeness: Target {character_profile.avg_num_politeness_markers}
     Should use: {character_profile.top_politeness_markers}
   - Passive voice: Target {character_profile.avg_num_passive_patterns}

3. STYLISTIC ELEMENTS (Weight: 20%)
   - Greeting matches: {character_profile.top_greeting_phrases}
   - Sentence starters: {character_profile.top_sentence_starters}
   - Punctuation: Ellipsis {character_profile.avg_ellipsis_frequency}, Exclamation {character_profile.avg_exclamation_density}
   - Caps usage: {"Should use CAPS for emphasis" if character_profile.uses_caps_for_emphasis else "Should avoid CAPS"}
   - Emoji usage: {character_profile.avg_num_emoji} per message

4. AUTHENTICITY (Weight: 15%)
   - Natural flow and rhythm
   - Maintains user's personality
   - Uses typical discourse markers: {character_profile.top_discourse_markers}
   - Sounds genuinely like the user

CURRENT EMAIL WE ARE REPLYING TO: {current_email.format()}

{ref_email_section}

SCORING INSTRUCTIONS:
- Score each category individually (0-10)
- DO NOT calculate weighted average yourself - just provide the individual scores
- Provide detailed reasoning for each score

FORMAT YOUR RESPONSE EXACTLY AS:
SCORE BREAKDOWN:
- Structure: X/10 (reason)
- Linguistic Patterns: X/10 (reason)  
- Stylistic Elements: X/10 (reason)
- Authenticity: X/10 (reason)
- Intent Fulfillment: X/10 (reason)

DETAILED FEEDBACK:
[Specific areas to improve with examples and suggestions]

FOCUS AREAS FOR NEXT ITERATION:
[List 2-3 most critical improvements needed]"""
