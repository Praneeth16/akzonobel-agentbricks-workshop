-- Top at-risk EMEA accounts in the latest month (the Commercial track narrative).
-- Runs as the app service principal. Tables are referenced as schema.table; set the
-- SQL warehouse's default catalog to your workshop catalog so these resolve. Portable.
SELECT a.account_name,
       a.segment,
       ROUND(c.churn_score, 3) AS churn_score,
       c.complaint_count,
       c.nps
FROM akzo_commercial.churn_signals c
JOIN akzo_commercial.accounts a
  ON a.account_id = c.account_id
WHERE a.region = 'EMEA'
  AND c.month = (SELECT MAX(month) FROM akzo_commercial.churn_signals)
ORDER BY c.churn_score DESC
LIMIT 8
