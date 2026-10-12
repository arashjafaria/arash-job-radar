-- Run after deploying review-digest.yml. Reusing the name updates the job.
SELECT cron.schedule(
  'arash-review-digest',
  '3-59/15 * * * *',
  $$SELECT public.trigger_arash_github_workflow('review-digest.yml');$$
);
