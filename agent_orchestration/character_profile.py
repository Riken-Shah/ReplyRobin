from typing import Optional
from sqlalchemy import text
from db.schemas import CharacterProfile
from db.singleton import get_session_manager


def fetch_character_profile(sender: str) -> Optional[CharacterProfile]:
    """Fetches the character profile for a given sender from the database."""
    sql_query = """ 
 WITH base_stats AS (
  SELECT
      sender,
      COUNT(*) AS num_messages,
      -- Punctuation Style
      AVG(COALESCE((signals->>'ellipsis_frequency')::float, 0)) AS avg_ellipsis_frequency,
      AVG(COALESCE((signals->>'exclamation_density')::float, 0)) AS avg_exclamation_density,
      BOOL_OR(COALESCE((signals->>'uses_caps_for_emphasis')::boolean, false)) AS uses_caps_for_emphasis,
      BOOL_OR(COALESCE((signals->>'uses_inline_parentheses')::boolean, false)) AS uses_inline_parentheses,
      -- Linguistic patterns array lengths (with type checking)
      AVG(CASE 
          WHEN jsonb_typeof(signals->'intents') = 'array' 
          THEN jsonb_array_length(signals->'intents') 
          ELSE 0 
      END) AS avg_num_intents,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'greeting_phrases') = 'array' 
          THEN jsonb_array_length(signals->'greeting_phrases') 
          ELSE 0 
      END) AS avg_num_greeting_phrases,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'politeness_markers') = 'array' 
          THEN jsonb_array_length(signals->'politeness_markers') 
          ELSE 0 
      END) AS avg_num_politeness_markers,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'modal_verbs') = 'array' 
          THEN jsonb_array_length(signals->'modal_verbs') 
          ELSE 0 
      END) AS avg_num_modal_verbs,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'hedge_words') = 'array' 
          THEN jsonb_array_length(signals->'hedge_words') 
          ELSE 0 
      END) AS avg_num_hedge_words,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'boosters') = 'array' 
          THEN jsonb_array_length(signals->'boosters') 
          ELSE 0 
      END) AS avg_num_boosters,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'mitigating_phrases') = 'array' 
          THEN jsonb_array_length(signals->'mitigating_phrases') 
          ELSE 0 
      END) AS avg_num_mitigating_phrases,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'urgency_phrases') = 'array' 
          THEN jsonb_array_length(signals->'urgency_phrases') 
          ELSE 0 
      END) AS avg_num_urgency_phrases,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'filler_words') = 'array' 
          THEN jsonb_array_length(signals->'filler_words') 
          ELSE 0 
      END) AS avg_num_filler_words,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'emoji_usage') = 'array' 
          THEN jsonb_array_length(signals->'emoji_usage') 
          ELSE 0 
      END) AS avg_num_emoji,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'question_phrases') = 'array' 
          THEN jsonb_array_length(signals->'question_phrases') 
          ELSE 0 
      END) AS avg_num_question_phrases,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'sentence_starters') = 'array' 
          THEN jsonb_array_length(signals->'sentence_starters') 
          ELSE 0 
      END) AS avg_num_sentence_starters,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'passive_voice_patterns') = 'array' 
          THEN jsonb_array_length(signals->'passive_voice_patterns') 
          ELSE 0 
      END) AS avg_num_passive_patterns,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'abbreviation_usage') = 'array' 
          THEN jsonb_array_length(signals->'abbreviation_usage') 
          ELSE 0 
      END) AS avg_num_abbreviation_usage,
      AVG(CASE 
          WHEN jsonb_typeof(signals->'discourse_markers') = 'array' 
          THEN jsonb_array_length(signals->'discourse_markers') 
          ELSE 0 
      END) AS avg_num_discourse_markers,
      -- Most common tone
      MODE() WITHIN GROUP (ORDER BY signals->>'tone') AS most_common_tone
  FROM message
  WHERE sender = :sender AND signals IS NOT NULL
  GROUP BY sender
),

ranked_intents AS (
  SELECT sender, LOWER(w::text) AS intent, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'intents') AS w
  WHERE sender = :sender 
    AND signals->'intents' IS NOT NULL 
    AND jsonb_typeof(signals->'intents') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_intents AS (
  SELECT sender, ARRAY_AGG(intent ORDER BY freq DESC) AS top_intents
  FROM ranked_intents WHERE rk <= 10 GROUP BY sender
),

ranked_greeting_phrases AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'greeting_phrases') AS w
  WHERE sender = :sender 
    AND signals->'greeting_phrases' IS NOT NULL 
    AND jsonb_typeof(signals->'greeting_phrases') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_greeting_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_greeting_phrases
  FROM ranked_greeting_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_politeness_markers AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'politeness_markers') AS w
  WHERE sender = :sender 
    AND signals->'politeness_markers' IS NOT NULL 
    AND jsonb_typeof(signals->'politeness_markers') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_politeness_markers AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_politeness_markers
  FROM ranked_politeness_markers WHERE rk <= 10 GROUP BY sender
),

ranked_modal_verbs AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'modal_verbs') AS w
  WHERE sender = :sender 
    AND signals->'modal_verbs' IS NOT NULL 
    AND jsonb_typeof(signals->'modal_verbs') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_modal_verbs AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_modal_verbs
  FROM ranked_modal_verbs WHERE rk <= 10 GROUP BY sender
),

ranked_hedge_words AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'hedge_words') AS w
  WHERE sender = :sender 
    AND signals->'hedge_words' IS NOT NULL 
    AND jsonb_typeof(signals->'hedge_words') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_hedge_words AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_hedge_words
  FROM ranked_hedge_words WHERE rk <= 10 GROUP BY sender
),

ranked_boosters AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'boosters') AS w
  WHERE sender = :sender 
    AND signals->'boosters' IS NOT NULL 
    AND jsonb_typeof(signals->'boosters') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_boosters AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_boosters
  FROM ranked_boosters WHERE rk <= 10 GROUP BY sender
),

ranked_mitigating_phrases AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'mitigating_phrases') AS w
  WHERE sender = :sender 
    AND signals->'mitigating_phrases' IS NOT NULL 
    AND jsonb_typeof(signals->'mitigating_phrases') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_mitigating_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_mitigating_phrases
  FROM ranked_mitigating_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_urgency_phrases AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'urgency_phrases') AS w
  WHERE sender = :sender 
    AND signals->'urgency_phrases' IS NOT NULL 
    AND jsonb_typeof(signals->'urgency_phrases') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_urgency_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_urgency_phrases
  FROM ranked_urgency_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_filler_words AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'filler_words') AS w
  WHERE sender = :sender 
    AND signals->'filler_words' IS NOT NULL 
    AND jsonb_typeof(signals->'filler_words') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_filler_words AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_filler_words
  FROM ranked_filler_words WHERE rk <= 10 GROUP BY sender
),

ranked_emoji_usage AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'emoji_usage') AS w
  WHERE sender = :sender 
    AND signals->'emoji_usage' IS NOT NULL 
    AND jsonb_typeof(signals->'emoji_usage') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_emoji_usage AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_emoji_usage
  FROM ranked_emoji_usage WHERE rk <= 10 GROUP BY sender
),

ranked_question_phrases AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'question_phrases') AS w
  WHERE sender = :sender 
    AND signals->'question_phrases' IS NOT NULL 
    AND jsonb_typeof(signals->'question_phrases') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_question_phrases AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_question_phrases
  FROM ranked_question_phrases WHERE rk <= 10 GROUP BY sender
),

ranked_sentence_starters AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'sentence_starters') AS w
  WHERE sender = :sender 
    AND signals->'sentence_starters' IS NOT NULL 
    AND jsonb_typeof(signals->'sentence_starters') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_sentence_starters AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_sentence_starters
  FROM ranked_sentence_starters WHERE rk <= 10 GROUP BY sender
),

ranked_passive_voice_patterns AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'passive_voice_patterns') AS w
  WHERE sender = :sender 
    AND signals->'passive_voice_patterns' IS NOT NULL 
    AND jsonb_typeof(signals->'passive_voice_patterns') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_passive_voice_patterns AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_passive_voice_patterns
  FROM ranked_passive_voice_patterns WHERE rk <= 10 GROUP BY sender
),

ranked_abbreviation_usage AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'abbreviation_usage') AS w
  WHERE sender = :sender 
    AND signals->'abbreviation_usage' IS NOT NULL 
    AND jsonb_typeof(signals->'abbreviation_usage') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_abbreviation_usage AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_abbreviation_usage
  FROM ranked_abbreviation_usage WHERE rk <= 10 GROUP BY sender
),

ranked_discourse_markers AS (
  SELECT sender, LOWER(w::text) AS word, COUNT(*) AS freq,
         ROW_NUMBER() OVER (PARTITION BY sender ORDER BY COUNT(*) DESC) AS rk
  FROM message, LATERAL jsonb_array_elements_text(signals->'discourse_markers') AS w
  WHERE sender = :sender 
    AND signals->'discourse_markers' IS NOT NULL 
    AND jsonb_typeof(signals->'discourse_markers') = 'array'
  GROUP BY sender, LOWER(w::text)
),
top_discourse_markers AS (
  SELECT sender, ARRAY_AGG(word ORDER BY freq DESC) AS top_discourse_markers
  FROM ranked_discourse_markers WHERE rk <= 10 GROUP BY sender
)

SELECT
  b.*,
  t_int.top_intents,
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
LEFT JOIN top_intents t_int ON b.sender = t_int.sender
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
    with get_session_manager() as session:
        result = (
            session.execute(text(sql_query), {"sender": sender})
            .mappings()
            .one_or_none()
        )

    if result:
        return CharacterProfile.model_validate(result)
    return None
