-- Apply once in Supabase SQL Editor BEFORE deploying the Python change.
-- Old digest messages count as notifications, including records with false flags.
BEGIN;

ALTER TABLE public.arash_jobs
  ADD COLUMN IF NOT EXISTS decision_status text,
  ADD COLUMN IF NOT EXISTS decision_evidence jsonb,
  ADD COLUMN IF NOT EXISTS matcher_revision text,
  ADD COLUMN IF NOT EXISTS evaluated_at timestamptz,
  ADD COLUMN IF NOT EXISTS notification_status text;

CREATE TABLE IF NOT EXISTS public.arash_notification_history (
  source text NOT NULL,
  job_id text NOT NULL,
  token text NOT NULL,
  title_key text NOT NULL DEFAULT '',
  company_key text NOT NULL DEFAULT '',
  location_key text NOT NULL DEFAULT '',
  url_key text NOT NULL DEFAULT '',
  outcome text NOT NULL DEFAULT 'claimed',
  claimed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (source, job_id)
);
ALTER TABLE public.arash_notification_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.arash_notification_history FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.arash_notification_history TO service_role;
REVOKE DELETE, TRUNCATE ON public.arash_notification_history FROM service_role;

CREATE OR REPLACE FUNCTION public.job_notification_key(value text, kind text)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path = public, pg_temp AS $$
DECLARE result text := lower(coalesce(value, ''));
BEGIN
  IF kind = 'url' THEN
    RETURN rtrim(split_part(split_part(result, '?', 1), '#', 1), '/');
  END IF;
  IF kind = 'title' THEN
    result := regexp_replace(result, '\((m|w|d|f|x|all|gender|div|gn)[^)]*\)', ' ', 'g');
    result := replace(result, 'entwicklungsingenieur', 'development engineer');
    result := replace(result, 'testingenieur', 'test engineer');
    result := replace(result, 'systemingenieur', 'system engineer');
    result := replace(result, 'validierungsingenieur', 'validation engineer');
  ELSIF kind = 'company' THEN
    result := regexp_replace(result, '\m(gmbh|ag|se|kg|co|ltd|limited|inc|corp|corporation)\M', ' ', 'g');
    IF result ~ '^bmw( group)?\s*$' THEN result := 'bmw'; END IF;
  ELSIF kind = 'location' THEN
    result := replace(result, 'münchen', 'munich');
    result := replace(result, 'nürnberg', 'nuremberg');
  END IF;
  RETURN trim(regexp_replace(regexp_replace(result, '[^a-z0-9äöüß+]+', ' ', 'g'), '\s+', ' ', 'g'));
END $$;

-- Permanent import: rerunning this migration cannot delete/reset reservations.
INSERT INTO public.arash_notification_history
  (source, job_id, token, title_key, company_key, location_key, url_key, outcome)
SELECT source, job_id, 'legacy',
  public.job_notification_key(title, 'title'),
  public.job_notification_key(company, 'company'),
  public.job_notification_key(location, 'location'),
  public.job_notification_key(url, 'url'), 'delivered'
FROM public.arash_jobs
WHERE sent_to_telegram IS TRUE OR status = 'sent' OR status LIKE 'review_digest_sent%'
ON CONFLICT (source, job_id) DO NOTHING;

UPDATE public.arash_jobs SET sent_to_telegram = true, notification_status = 'delivered'
WHERE sent_to_telegram IS TRUE OR status = 'sent' OR status LIKE 'review_digest_sent%';

CREATE OR REPLACE FUNCTION public.claim_job_notification(p_source text, p_job_id text, p_token text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE job public.arash_jobs%ROWTYPE; previous public.arash_notification_history%ROWTYPE;
  tk text; ck text; lk text; uk text; duplicate_found boolean;
BEGIN
  -- Serializes reservations across BMW, LinkedIn, digests, and concurrent runs.
  PERFORM pg_advisory_xact_lock(hashtextextended('arash-job-notifications', 0));
  SELECT * INTO previous FROM public.arash_notification_history
    WHERE source = p_source AND job_id = p_job_id;
  IF FOUND THEN RETURN previous.token = p_token AND previous.outcome = 'claimed'; END IF;
  SELECT * INTO job FROM public.arash_jobs WHERE source = p_source AND job_id = p_job_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Notification requires a persisted job'; END IF;
  tk := public.job_notification_key(job.title, 'title');
  ck := public.job_notification_key(job.company, 'company');
  lk := public.job_notification_key(job.location, 'location');
  uk := public.job_notification_key(job.url, 'url');
  SELECT EXISTS(SELECT 1 FROM public.arash_notification_history h
    WHERE (uk <> '' AND h.url_key = uk)
      OR (tk <> '' AND ck <> '' AND h.title_key = tk AND h.company_key = ck
          AND (lk = '' OR h.location_key = '' OR lk = h.location_key
               OR position(lk in h.location_key) > 0 OR position(h.location_key in lk) > 0)))
    INTO duplicate_found;
  duplicate_found := duplicate_found OR job.sent_to_telegram IS TRUE
    OR coalesce(job.status = 'sent' OR job.status LIKE 'review_digest_sent%', false);
  INSERT INTO public.arash_notification_history
    (source, job_id, token, title_key, company_key, location_key, url_key, outcome)
  VALUES (p_source, p_job_id, p_token, tk, ck, lk, uk,
    CASE WHEN duplicate_found THEN 'suppressed' ELSE 'claimed' END);
  UPDATE public.arash_jobs SET notification_status =
    CASE WHEN duplicate_found THEN 'suppressed' ELSE 'claimed' END
    WHERE source = p_source AND job_id = p_job_id;
  RETURN NOT duplicate_found;
END $$;

CREATE OR REPLACE FUNCTION public.finish_job_notification(p_source text, p_job_id text, p_token text, p_delivered boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE result text;
BEGIN
  UPDATE public.arash_notification_history
    SET outcome = CASE WHEN p_delivered THEN 'delivered' ELSE 'uncertain' END
    WHERE source = p_source AND job_id = p_job_id AND token = p_token
      AND outcome IN ('claimed', CASE WHEN p_delivered THEN 'delivered' ELSE 'uncertain' END)
    RETURNING outcome INTO result;
  IF NOT FOUND THEN RETURN false; END IF;
  UPDATE public.arash_jobs SET notification_status = result,
    sent_to_telegram = coalesce(sent_to_telegram, false) OR p_delivered
    WHERE source = p_source AND job_id = p_job_id;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION public.preserve_job_delivery_history()
RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
  IF OLD.sent_to_telegram IS TRUE OR OLD.status = 'sent' OR OLD.status LIKE 'review_digest_sent%'
  THEN NEW.sent_to_telegram := true; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS preserve_job_delivery_history ON public.arash_jobs;
CREATE TRIGGER preserve_job_delivery_history BEFORE UPDATE ON public.arash_jobs
FOR EACH ROW EXECUTE FUNCTION public.preserve_job_delivery_history();

REVOKE ALL ON FUNCTION public.claim_job_notification(text, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.finish_job_notification(text, text, text, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_job_notification(text, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.finish_job_notification(text, text, text, boolean) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
