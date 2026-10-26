-- DESIGN TEMPLATE ONLY. NOT DEPLOYED OR EXECUTED IN PRODUCTION.
-- PostgreSQL example. Do not run until production repository, legal/privacy
-- review, API auth/rate limiting, retention and deletion policies are approved.
-- anon_session_id is pseudonymous and may still be personal data.
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.proba_career_interest_events (
    event_id uuid PRIMARY KEY,
    experiment_id text NOT NULL,
    anon_session_id uuid NOT NULL,
    profession_id text NOT NULL CHECK (
       profession_id IN (
          'project_manager', 'system_analyst', 'financial_analyst',
          'internet_marketer', 'python_developer', 'frontend_developer',
          'data_scientist'
       )
    ),
    placement_variant text NOT NULL,
    card_position smallint NOT NULL CHECK (card_position BETWEEN 1 AND 7),
    occurred_at timestamptz NOT NULL,
    event_type text NOT NULL CHECK (
       event_type IN ('card_impression', 'card_open', 'waitlist_intent')
    ),
    accepted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS proba_interest_window_idx
ON analytics.proba_career_interest_events (
    experiment_id, occurred_at, profession_id
);

CREATE INDEX IF NOT EXISTS proba_interest_session_idx
ON analytics.proba_career_interest_events (
    experiment_id, anon_session_id, profession_id, occurred_at
);

-- Safe default: browser clients get NO direct select/insert/update privileges.
-- If using Supabase, RLS must be configured as well. This example enables RLS
-- with NO policies; only an appropriately secured backend service role should
-- handle ingestion. Grant permissions separately after review.
ALTER TABLE analytics.proba_career_interest_events ENABLE ROW LEVEL SECURITY;

-- Do not export/store raw email, IP address, user agent, questionnaire answers
-- or linked personal profiles in this table. Configure retention separately;
-- do not assume the absence of names means GDPR is inapplicable.
