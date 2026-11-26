-- Dedicated, private dispatcher: never returns Vault credentials.
CREATE SCHEMA IF NOT EXISTS radar_scheduler;
REVOKE ALL ON SCHEMA radar_scheduler FROM PUBLIC, anon, authenticated, service_role;
CREATE OR REPLACE FUNCTION radar_scheduler.dispatch_arash_website(workflow_file text)
RETURNS bigint LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE github_token text; request_id bigint;
BEGIN
  IF workflow_file NOT IN ('job-boards.yml', 'alten-pilot.yml', 'ferchau-radar.yml') THEN
    RAISE EXCEPTION 'Unsupported Arash website workflow';
  END IF;
  SELECT decrypted_secret INTO github_token FROM vault.decrypted_secrets
    WHERE name = 'github_job_radar_token' LIMIT 1;
  IF github_token IS NULL THEN RAISE EXCEPTION 'Arash scheduler credential missing'; END IF;
  SELECT net.http_post(
    url := 'https://api.github.com/repos/arashjafaria/arash-job-radar/actions/workflows/' || workflow_file || '/dispatches',
    headers := jsonb_build_object('Authorization','Bearer ' || github_token,
      'Accept','application/vnd.github+json','Content-Type','application/json'),
    body := '{"ref":"main"}'::jsonb
  ) INTO request_id;
  RETURN request_id;
END $$;
REVOKE ALL ON FUNCTION radar_scheduler.dispatch_arash_website(text) FROM PUBLIC, anon, authenticated, service_role;
-- Each workflow has its own non-cancelling concurrency group. Existing
-- LinkedIn/BMW/review/Maryam dispatchers and all histories remain untouched.
SELECT cron.schedule('arash-indeed-xing', '9 * * * *',
  $$SELECT radar_scheduler.dispatch_arash_website('job-boards.yml');$$);
SELECT cron.schedule('arash-alten-website', '17 * * * *',
  $$SELECT radar_scheduler.dispatch_arash_website('alten-pilot.yml');$$);
SELECT cron.schedule('arash-ferchau-website', '27 * * * *',
  $$SELECT radar_scheduler.dispatch_arash_website('ferchau-radar.yml');$$);
