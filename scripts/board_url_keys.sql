-- Preserve Indeed job identity while removing tracking parameters.
CREATE OR REPLACE FUNCTION public.job_notification_key(value text, kind text)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path = public, pg_temp AS $$
DECLARE result text := lower(coalesce(value, ''));
BEGIN
  IF kind = 'url' THEN
    IF result ~ '^https?://(de|www)\.indeed\.com/'
       AND result ~ '[?&](jk|vjk)=[a-z0-9]+' THEN
      RETURN 'https://de.indeed.com/viewjob?jk=' ||
        substring(result from '[?&](?:jk|vjk)=([a-z0-9]+)');
    END IF;
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
