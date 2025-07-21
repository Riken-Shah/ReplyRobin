from typing import Optional
from sqlalchemy import text
from common.schemas import CharacterProfile
from common.db import DB

def fetch_character_profile(db: DB, sender: str) -> Optional[CharacterProfile]:
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
        with db.session_scope() as session:
            result = (
                session.exec(text(sql_query), {"sender": sender})
                .mappings()
                .one_or_none()
            )

        if result:
            return CharacterProfile.model_validate(result)
        return None
      
     