-- Decorative Paints × EMEA monthly gross margin %. Shows the Q1→Q2 2026 erosion
-- (the narrative the Finance track investigates). Runs as the app service principal.
-- Tables are referenced as schema.table; set the SQL warehouse's default catalog
-- to your workshop catalog (e.g. WORKSHOP_CATALOG) so these resolve. Portable.
SELECT date_format(m.month, 'yyyy-MM') AS month,
       ROUND(100 * SUM(m.gross_margin_eur) / NULLIF(SUM(m.revenue_eur), 0), 1) AS margin_pct
FROM akzo_finance.margin_actuals m
JOIN akzo_finance.products p
  ON p.sku = m.sku AND p.region = m.region
WHERE p.product_line = 'Decorative Paints' AND m.region = 'EMEA'
GROUP BY m.month
ORDER BY m.month
