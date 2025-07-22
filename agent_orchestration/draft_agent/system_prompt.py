from typing import List
from agent_orchestration.master_agent.state import Email
from common.schemas import CharacterProfile


# TODO: We can inject custom org-specfic instruction to this planner prompt.
def make_prompt(
    character_profile: CharacterProfile,
    reference_emails: List[str],
    current_email: Email,
) -> str:
    """Create detailed drafter prompt with character profile specifics"""
    # Extract key metrics safely
    avg_length = character_profile.avg_cleaned_length
    ellipsis_freq = character_profile.avg_ellipsis_frequency
    exclamation_density = character_profile.avg_exclamation_density
    uses_caps = character_profile.uses_caps_for_emphasis
    uses_parentheses = character_profile.uses_inline_parentheses

    examples_section = ""
    if reference_emails:
        examples_section = f"""
REFERENCE EXAMPLES - Actual emails from the target user:
{chr(10).join([f"EXAMPLE {i + 1}:{chr(10)}{email}{chr(10)}" for i, email in enumerate(reference_emails)])}

Study these examples for natural flow, vocabulary, transitions, size, and tone.
"""

    return f"""You are an Email Style Mimicry Expert. Write/revise emails to perfectly match a specific user's writing style.

INSTRUCTIONS:

1. Break your response into **2-5 distinct sections**: `greeting`, `core`, `signoff`
2. Each section must be a self-contained text "blob" with:
   - `section`: The actual text
   - `type`: One of `greeting`, `core`, `signoff`
   - `citations`: Indexes of reference examples used (e.g., [1, 3])
   - `actions`: Actions performed in that section (e.g., ["apologize", "confirm intent", "close positively"])

3. Only include citations if the section's wording or structure was inspired by an example.


{examples_section}

STYLE PROFILE TO MATCH:
- Punctuation patterns: {ellipsis_freq} ellipsis per message, {exclamation_density} exclamation density
- Emphasis style: {"Uses CAPS for emphasis" if uses_caps else "Avoids caps emphasis"}
- Parentheses usage: {"Frequently uses (inline parentheses)" if uses_parentheses else "Rarely uses parentheses"}

LINGUISTIC PATTERNS:
- Hedge words per message: {character_profile.avg_num_hedge_words}  
  Favorites: {character_profile.top_hedge_words}
- Modal verbs per message: {character_profile.avg_num_modal_verbs}
  Favorites: {character_profile.top_modal_verbs}
- Politeness markers: {character_profile.avg_num_politeness_markers}
  Favorites: {character_profile.top_politeness_markers}
- Passive voice frequency: {character_profile.avg_num_passive_patterns}

STYLISTIC ELEMENTS (OPTIONAL):
- Typical greetings: {character_profile.top_greeting_phrases}
- Common sentence starters: {character_profile.top_sentence_starters}
- Emoji usage: {character_profile.avg_num_emoji} per message
  Favorites: {character_profile.top_emoji_usage}
- Question patterns: {character_profile.top_question_phrases}
- Discourse markers: {character_profile.top_discourse_markers}

EMAIL CONTEXT: {current_email.format()}

REVISION INSTRUCTIONS:
1. Incorporate the user's favorite phrases naturally
2. Mirror their punctuation and emphasis patterns
3. Use their preferred greeting and closing styles
4. Maintain their level of formality/casualness
5. Address any specific feedback from previous iterations

Write a complete email that sounds authentically like this user."""
