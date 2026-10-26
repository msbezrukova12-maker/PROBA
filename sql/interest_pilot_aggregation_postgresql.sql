-- POSTGRESQL EXAMPLE. Not executed against PROBA production.
-- $1 = experiment_id (text)
-- $2 = analysis_start (timestamptz, inclusive)
-- $3 = analysis_end (timestamptz, exclusive)
-- Unit: distinct anonymous SESSIONS exposed to each career card, not people.
-- Attribution: open/intent within 24 hours AFTER the first visible impression.
-- A session may contribute to multiple professions (paired observations).
WITH roles(profession_id) AS (
  VALUES ('project_manager'), ('system_analyst'), ('financial_analyst'),
         ('internet_marketer'), ('python_developer'), ('frontend_developer'),
         ('data_scientist')
),
events AS (
  SELECT event_id, experiment_id, anon_session_id,
         profession_id, placement_variant, card_position, occurred_at, event_type
  FROM analytics.proba_career_interest_events
  WHERE experiment_id = $1
),
assignments AS (
  -- QC elsewhere must reject sessions with more than one placement_variant.
  SELECT DISTINCT placement_variant FROM events
),
first_exposure AS (
  SELECT anon_session_id, profession_id, placement_variant,
         occurred_at AS first_seen_at, card_position,
         ROW_NUMBER() OVER (
           PARTITION BY anon_session_id, profession_id
           ORDER BY occurred_at, event_id
         ) AS first_rank
  FROM events
  WHERE event_type = 'card_impression'
    AND occurred_at >= $2 AND occurred_at < $3
),
session_flags AS (
  SELECT i.anon_session_id, i.profession_id, i.placement_variant,
         MAX(CASE WHEN o.event_type='card_open' THEN 1 ELSE 0 END) AS opened,
         MAX(CASE WHEN o.event_type='waitlist_intent' THEN 1 ELSE 0 END) AS intended
  FROM first_exposure i
  LEFT JOIN events o ON
       o.anon_session_id = i.anon_session_id
   AND o.profession_id = i.profession_id
   AND o.placement_variant = i.placement_variant
   AND o.event_type IN ('card_open','waitlist_intent')
   AND o.occurred_at >= i.first_seen_at
   AND o.occurred_at <= i.first_seen_at + INTERVAL '24 hours'
  WHERE i.first_rank = 1
  GROUP BY i.anon_session_id, i.profession_id, i.placement_variant
),
counts AS (
  SELECT profession_id, placement_variant,
         COUNT(*) AS sessions_exposed,
         SUM(opened) AS sessions_opened,
         SUM(intended) AS sessions_intent
  FROM session_flags
  GROUP BY profession_id, placement_variant
)
SELECT r.profession_id, a.placement_variant,
       COALESCE(c.sessions_exposed, 0) AS sessions_exposed,
       COALESCE(c.sessions_opened, 0) AS sessions_opened,
       COALESCE(c.sessions_intent, 0) AS sessions_intent,
       ROUND(c.sessions_opened::numeric /
             NULLIF(c.sessions_exposed, 0), 5) AS session_open_rate,
       ROUND(c.sessions_intent::numeric /
             NULLIF(c.sessions_exposed, 0), 5) AS session_intent_rate
FROM roles r CROSS JOIN assignments a
LEFT JOIN counts c ON
     c.profession_id = r.profession_id
 AND c.placement_variant = a.placement_variant
ORDER BY a.placement_variant, r.profession_id;

-- IMPORTANT:
-- 1. SQL returns NULL rate, not 0%, for missing exposure.
-- 2. No A/B treatment effect is identified by simply sorting these rates.
-- 3. Validate randomized exposure, session eligibility, bot/duplicate traffic,
--    timestamp clocks and assignment consistency BEFORE interpretation.
-- 4. Wilson intervals and exploratory QC are implemented by the offline script.
