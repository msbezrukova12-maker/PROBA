-- DEMONSTRATION ONLY. PostgreSQL syntax. Do not execute on production without
-- creating and validating the event schema and obtaining privacy/legal approval.
-- Source table assumed: analytics_events(event_id,anon_session_id,
-- event_time,profession_id,experiment_variant,event_name).
-- Each counted unit is a SESSION, not a unique person.
WITH events_filtered AS (
  SELECT DISTINCT
    anon_session_id, profession_id, experiment_variant, event_name
  FROM analytics_events
  WHERE event_name IN ('card_impression','card_open','waitlist_intent')
    AND event_time >= :window_start
    AND event_time < :window_end
), session_funnel AS (
  SELECT
    anon_session_id, profession_id, experiment_variant,
    MAX(CASE WHEN event_name='card_impression' THEN 1 ELSE 0 END) AS shown,
    MAX(CASE WHEN event_name='card_open' THEN 1 ELSE 0 END) AS opened,
    MAX(CASE WHEN event_name='waitlist_intent' THEN 1 ELSE 0 END) AS interested
  FROM events_filtered
  GROUP BY anon_session_id, profession_id, experiment_variant
)
SELECT
  profession_id,
  experiment_variant,
  SUM(shown) AS sessions_shown,
  SUM(CASE WHEN shown=1 THEN opened ELSE 0 END) AS sessions_opened,
  SUM(CASE WHEN shown=1 THEN interested ELSE 0 END) AS sessions_interested,
  ROUND(100.0 * SUM(CASE WHEN shown=1 THEN opened ELSE 0 END)
      / NULLIF(SUM(shown), 0), 2) AS open_rate_pct,
  ROUND(100.0 * SUM(CASE WHEN shown=1 THEN interested ELSE 0 END)
      / NULLIF(SUM(shown), 0), 2) AS intent_rate_pct
FROM session_funnel
GROUP BY profession_id, experiment_variant
ORDER BY sessions_interested DESC, profession_id;
