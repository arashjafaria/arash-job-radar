-- Extend the same global reservation lock to FERCHAU website/LinkedIn aliases.
CREATE OR REPLACE FUNCTION public.claim_job_notification(p_source text, p_job_id text, p_token text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
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
  IF ck ~ '^alten( |$)' THEN
    -- Same transaction/lock as every LinkedIn and website reservation.
    -- Conservative title similarity may suppress uncertain duplicates.
    SELECT duplicate_found OR EXISTS(
      SELECT 1 FROM public.arash_notification_history h
      LEFT JOIN public.arash_jobs old ON old.source=h.source AND old.job_id=h.job_id
      WHERE h.company_key ~ '^alten( |$)' AND (
        (coalesce(nullif(job.decision_evidence->>'requisition_id', ''),
             substring(job.decision_evidence->>'description' from '(?i)\mREF[0-9]+[A-Z]?\M')) IS NOT NULL
         AND coalesce(nullif(job.decision_evidence->>'requisition_id', ''),
             substring(job.decision_evidence->>'description' from '(?i)\mREF[0-9]+[A-Z]?\M')) =
             coalesce(nullif(old.decision_evidence->>'requisition_id', ''),
             substring(old.decision_evidence->>'description' from '(?i)\mREF[0-9]+[A-Z]?\M')))
        OR (
          (lk='' OR h.location_key='' OR position(lk in h.location_key)>0 OR position(h.location_key in lk)>0)
          AND (
            public.alten_notification_title(tk)=public.alten_notification_title(h.title_key)
            OR (
              SELECT count(*)::numeric / greatest(
                cardinality(regexp_split_to_array(public.alten_notification_title(tk), ' ')),
                cardinality(regexp_split_to_array(public.alten_notification_title(h.title_key), ' ')), 1) >= 0.75
              FROM (
                SELECT DISTINCT unnest(regexp_split_to_array(public.alten_notification_title(tk), ' ')) AS word
                INTERSECT
                SELECT DISTINCT unnest(regexp_split_to_array(public.alten_notification_title(h.title_key), ' ')) AS word
              ) words
            )
          )
        )
      )
    ) INTO duplicate_found;
  END IF;
  IF ck ~ '^ferchau( |$)' THEN
    SELECT duplicate_found OR EXISTS (
      SELECT 1 FROM public.arash_notification_history h
      LEFT JOIN public.arash_jobs old ON old.source=h.source AND old.job_id=h.job_id
      WHERE h.company_key ~ '^ferchau( |$)' AND (
        (substring(coalesce(job.decision_evidence->>'requisition_id','') || ' ' ||
             coalesce(job.decision_evidence->>'description','')
             from '(?i)(?:FE|LI)([0-9]{2}-[0-9]{5}-[A-Z0-9_-]+)') =
         substring(coalesce(old.decision_evidence->>'requisition_id','') || ' ' ||
             coalesce(old.decision_evidence->>'description','')
             from '(?i)(?:FE|LI)([0-9]{2}-[0-9]{5}-[A-Z0-9_-]+)'))
        OR ((lk='' OR h.location_key='' OR position(lk in h.location_key)>0 OR position(h.location_key in lk)>0)
          AND tk<>'' AND h.title_key<>'' AND (
            SELECT count(*)::numeric / greatest(
              cardinality(regexp_split_to_array(tk, ' ')),
              cardinality(regexp_split_to_array(h.title_key, ' ')), 1) >= 0.75
            FROM (
              SELECT DISTINCT unnest(regexp_split_to_array(tk, ' ')) AS word
              INTERSECT
              SELECT DISTINCT unnest(regexp_split_to_array(h.title_key, ' ')) AS word
            ) words
          ))
      )
    ) INTO duplicate_found;
  END IF;
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
END $function$
;
REVOKE ALL ON FUNCTION public.claim_job_notification(text,text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_job_notification(text,text,text) TO service_role;

