from typing import Optional
import json
import re
from sqlalchemy import text
from character_agent.multi_agent import run_email_generation
from common.schemas import CharacterProfile, Org
from common.db import DB
from langchain_google_genai import ChatGoogleGenerativeAI





# Warning: This executes code locally, which can be unsafe when not sandboxed

class MimicAgent:
    def __init__(self, db: DB, org: Org):
        self.db = db
        self.org = org

    def fetch_character_profile(self, sender: str) -> Optional[CharacterProfile]:
        """Fetches the character profile for a given sender from the database."""
        sql_query = """ 
 WITH base_stats AS (
  SELECT
      sender,
      COUNT(*) AS num_messages,
      AVG(size_estimate) AS avg_size_estimate,
      AVG(LENGTH(cleaned_content)) AS avg_cleaned_length,
      AVG(ellipsis_frequency) AS avg_ellipsis_frequency,
      AVG(exclamation_density) AS avg_exclamation_density,
      BOOL_OR(uses_caps_for_emphasis) AS uses_caps_for_emphasis,
      BOOL_OR(uses_inline_parentheses) AS uses_inline_parentheses,
      AVG(COALESCE(array_length(hedge_words, 1), 0)) AS avg_num_hedge_words,
      AVG(COALESCE(array_length(modal_verbs, 1), 0)) AS avg_num_modal_verbs,
      AVG(COALESCE(array_length(boosters, 1), 0)) AS avg_num_boosters,
      AVG(COALESCE(array_length(politeness_markers, 1), 0)) AS avg_num_politeness_markers,
      AVG(COALESCE(array_length(passive_voice_patterns, 1), 0)) AS avg_num_passive_patterns,
      AVG(COALESCE(array_length(emoji_usage, 1), 0)) AS avg_num_emoji,
      AVG(COALESCE(array_length(question_phrases, 1), 0)) AS avg_num_question_phrases
  FROM message
  WHERE sender = :sender
  GROUP BY sender
),

-- Repeated pattern to extract top-N words for each stylistic feature
-- Replace "FEATURE_NAME" with each array field, e.g., greeting_phrases
ranked_greeting_phrases AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(greeting_phrases) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_greeting_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_greeting_phrases
  FROM ranked_greeting_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_politeness_markers AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(politeness_markers) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_politeness_markers AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_politeness_markers
  FROM ranked_politeness_markers WHERE rk <= 10 GROUP BY sender
),

ranked_modal_verbs AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(modal_verbs) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_modal_verbs AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_modal_verbs
  FROM ranked_modal_verbs WHERE rk <= 10 GROUP BY sender
),

ranked_hedge_words AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(hedge_words) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_hedge_words AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_hedge_words
  FROM ranked_hedge_words WHERE rk <= 10 GROUP BY sender
),

ranked_boosters AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(boosters) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_boosters AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_boosters
  FROM ranked_boosters WHERE rk <= 10 GROUP BY sender
),

ranked_mitigating_phrases AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(mitigating_phrases) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_mitigating_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_mitigating_phrases
  FROM ranked_mitigating_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_urgency_phrases AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(urgency_phrases) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_urgency_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_urgency_phrases
  FROM ranked_urgency_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_filler_words AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(filler_words) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_filler_words AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_filler_words
  FROM ranked_filler_words WHERE rk <= 10 GROUP BY sender
),

ranked_emoji_usage AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(emoji_usage) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_emoji_usage AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_emoji_usage
  FROM ranked_emoji_usage WHERE rk <= 10 GROUP BY sender
),

ranked_question_phrases AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(question_phrases) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_question_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_question_phrases
  FROM ranked_question_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_sentence_starters AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(sentence_starters) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_sentence_starters AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_sentence_starters
  FROM ranked_sentence_starters WHERE rk <= 10 GROUP BY sender
),

ranked_passive_voice_patterns AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(passive_voice_patterns) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_passive_voice_patterns AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_passive_voice_patterns
  FROM ranked_passive_voice_patterns WHERE rk <= 10 GROUP BY sender
),

ranked_abbreviation_usage AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(abbreviation_usage) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_abbreviation_usage AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_abbreviation_usage
  FROM ranked_abbreviation_usage WHERE rk <= 10 GROUP BY sender
),

ranked_discourse_markers AS (
  SELECT sender, LOWER(w) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL unnest(discourse_markers) AS w
  WHERE sender = :sender
  GROUP BY sender, LOWER(w)
),
top_discourse_markers AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_discourse_markers
  FROM ranked_discourse_markers WHERE rk <= 10 GROUP BY sender
)

SELECT
  b.*,
  t_gre.top_greeting_phrases,
  t_pol.top_politeness_markers,
  t_mod.top_modal_verbs,
  t_hed.top_hedge_words,
  t_boo.top_boosters,
  t_mit.top_mitigating_phrases,
  t_urg.top_urgency_phrases,
  t_fil.top_filler_words,
  t_emo.top_emoji_usage,
  t_que.top_question_phrases,
  t_sen.top_sentence_starters,
  t_pas.top_passive_voice_patterns,
  t_abb.top_abbreviation_usage,
  t_dis.top_discourse_markers
FROM base_stats b
LEFT JOIN top_greeting_phrases t_gre ON b.sender = t_gre.sender
LEFT JOIN top_politeness_markers t_pol ON b.sender = t_pol.sender
LEFT JOIN top_modal_verbs t_mod ON b.sender = t_mod.sender
LEFT JOIN top_hedge_words t_hed ON b.sender = t_hed.sender
LEFT JOIN top_boosters t_boo ON b.sender = t_boo.sender
LEFT JOIN top_mitigating_phrases t_mit ON b.sender = t_mit.sender
LEFT JOIN top_urgency_phrases t_urg ON b.sender = t_urg.sender
LEFT JOIN top_filler_words t_fil ON b.sender = t_fil.sender
LEFT JOIN top_emoji_usage t_emo ON b.sender = t_emo.sender
LEFT JOIN top_question_phrases t_que ON b.sender = t_que.sender
LEFT JOIN top_sentence_starters t_sen ON b.sender = t_sen.sender
LEFT JOIN top_passive_voice_patterns t_pas ON b.sender = t_pas.sender
LEFT JOIN top_abbreviation_usage t_abb ON b.sender = t_abb.sender
LEFT JOIN top_discourse_markers t_dis ON b.sender = t_dis.sender;
        """
        with self.db.session_scope() as session:
            result = (
                session.execute(text(sql_query), {"sender": sender})
                .mappings()
                .one_or_none()
            )

        if result:
            return CharacterProfile.model_validate(result)
        return None

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List
import os

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

def get_writer_prompt(character_profile: CharacterProfile, past_emails: str):
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an Author Profiling Agent designed to deeply analyze and replicate the writing style of a specific user based on their previous email communication.

You operate as part of a two-agent loop: the **Writer** and the **Reviewer**. Your job is to iteratively improve drafts until they convincingly match the author’s style.

The Writer synthesizes new emails based on the author's stylistic profile. The Reviewer evaluates those drafts against the profile and examples, and requests revisions if mismatches are detected.

## Your goals:
1. Accurately mimic the author's tone, structure, vocabulary, and stylistic quirks.
2. Identify and preserve core linguistic signals extracted from the author's past emails.
3. Ensure that generated emails remain purpose-driven, clear, and contextually accurate.
4. Prioritize convergence: with each iteration, the output should become more faithful to the original style.

Here is the character profile you need to mimic:
<character_profile>
{character_profile}
</character_profile>

Here are the past emails from the user:
<past_emails>
{past_emails}
</past_emails>
"""
            ),
            ("human", "Please rewrite the following draft to match the user's style.\n\nPrevious reviewer feedback (if any): {review}\n\nDraft to improve:\n{draft}"),
        ]
    )

def get_judge_prompt(character_profile: CharacterProfile, past_emails: str):
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Judge Agent, responsible for reviewing a draft email to see if it matches a user's writing style.

You will be given a character profile of the user, their past emails, and a draft email.

Your task is to evaluate the draft on the following parameters and provide a score from 1-10 for each, where 1 is a poor match and 10 is a perfect match:
- Tone
- Structure
- Vocabulary
- Stylistic Quirks (e.g., use of emoji, punctuation, capitalization)

After scoring, provide a final verdict on whether the email is 'approved' or 'rejected'. If rejected, provide specific feedback for the writer on how to improve the draft.

Here is the character profile:
<character_profile>
{character_profile}
</character_profile>

Here are the past emails from the user:
<past_emails>
{past_emails}
</past_emails>
"""
            ),
            ("human", "Please review the following draft and return ONLY a valid JSON object with the following schema:\n{\n  \"style_score\": float (0-1),\n  \"mismatched_features\": [str],\n  \"explanation\": str\n}\nNo additional keys.\n\nDraft:\n{draft}"),
        ]
    )

class AgentState(TypedDict):
    character_profile: CharacterProfile
    past_emails: str
    draft: str
    review: dict
    iteration: int


class Agent:
    def __init__(self, character_profile, past_emails):
        self.character_profile = character_profile
        self.past_emails = past_emails

    def writer_node(self, state: AgentState):
        writer_prompt = get_writer_prompt(self.character_profile, self.past_emails)
        writer_chain = writer_prompt | llm
        response = writer_chain.invoke({
            "draft": state["draft"],
            "character_profile": self.character_profile,
            "past_emails": self.past_emails,
            "review": json.dumps(state.get("review", {})) or "None"
        })
        return {"draft": response.content, "iteration": state["iteration"] + 1}

    def judge_node(self, state: AgentState):
        judge_prompt = get_judge_prompt(self.character_profile, self.past_emails)
        judge_chain = judge_prompt | llm
        response = judge_chain.invoke({
            "draft": state["draft"],
            "character_profile": self.character_profile,
            "past_emails": self.past_emails
        })

        raw = response.content.strip()
        # Extract JSON substring in case model wraps it in markdown/code fences
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = "{}"

        try:
            review_dict = json.loads(json_str)
        except json.JSONDecodeError:
            review_dict = {
                "style_score": 0.0,
                "mismatched_features": [],
                "explanation": "Failed to parse judge response."
            }

        return {"review": review_dict}

    def should_continue(self, state: AgentState):
        # Stop if maximum iterations reached or quality threshold met
        if state["iteration"] >= 4:
            return END
        if state.get("review", {}).get("style_score", 0) >= 0.9:
            return END
        return "judge_node"


def run_agent(character_profile: CharacterProfile, past_emails: str, initial_draft: str):
    agent = Agent(character_profile, past_emails)

    workflow = StateGraph(AgentState)
    workflow.add_node("writer_node", agent.writer_node)
    workflow.add_node("judge_node", agent.judge_node)

    workflow.add_edge(START, "writer_node")
    workflow.add_edge("writer_node", "judge_node")
    workflow.add_conditional_edges(
        "judge_node",
        agent.should_continue,
        {
            END: END,
            "judge_node": "writer_node",
        }
    )

    graph = workflow.compile()

    initial_state = {
        "character_profile": character_profile,
        "past_emails": past_emails,
        "draft": initial_draft,
        "review": {},
        "iteration": 0,
    }

    events = graph.stream(initial_state)
    for s in events:
        print(s)
        print("----")


if __name__ == "__main__":
    db = DB()
    org = Org(email="support@karo.chat")
    agent = MimicAgent(db, org)
    profile = agent.fetch_character_profile("support@karo.chat")

    # print("Profile: ", profile)

    # if profile:
    #     # In a real scenario, you would fetch these from your database
    #     past_emails = """Email 1: Hey team, let's sync up on the Q3 roadmap tomorrow at 10am. I've added a few points to the agenda. Cheers, Mustafa
    #     Email 2: Hi all, I've attached the latest designs for the new feature. Please provide feedback by EOD. Thanks, Mustafa"""
    #     initial_draft = "Dear team, I would like to schedule a meeting for tomorrow to discuss our Q3 roadmap. I have prepared an agenda for this meeting -- discuss our numbers, stats and growth. Please let me know your availability. Best, Mustafa"

    #     run_agent(profile, past_emails, initial_draft)
    # else:
    #     print("Could not find character profile for the given sender.")
    
    past_emails_1 = """
    Hey, thank you for reaching out Shaxzod!
    Apologies that you’re facing this issue.

    I believe this is a number from Uzbekistan. The service we are using for sending OTPs might be facing an issue. We have forced it to send all OTPs to Uzbek numbers.

    Kindly try again now. 

    Have a wonderful day Shaxzod :)

    Regards,
    Mustafa Yusuf
    """.strip().replace("\n", "")
    past_emails_2 = """
    Hey Paul,

    I'm sorry for the inconvenience. Could you share Walter's country code? And 
    please try again our communication partner were 

    Regards,
    Mustafa Yusuf
    """.strip().replace("\n", "")

    print("Fetching character profile...")
    print("Character profile: ", profile)
    profile.avg_cleaned_length =100
    required_intents = ["Appologize for inconvenience", "Suggest alternative solution via WhatsApp", "Ask for any other issues"]
    result = run_email_generation(character_profile=profile, past_emails=[past_emails_1, past_emails_2], initial_request="Write an email to Aryan that OTP via SMS is unavailable for Pakistan", email_context="Following up on a project deadline", required_intents=required_intents)
    print("Final Draft: ", result.get("final_draft"))
    print("Total Iterations: ", result.get("total_iterations"))