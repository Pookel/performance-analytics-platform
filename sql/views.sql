PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_daily_kpis;
DROP VIEW IF EXISTS vw_variant_kpis;
DROP VIEW IF EXISTS vw_channel_kpis;
DROP VIEW IF EXISTS vw_country_kpis;

CREATE VIEW vw_daily_kpis AS
SELECT
  visit_date,
  variant,
  sessions,
  clicks,
  conversions,
  revenue,
  cost,
  profit,
  click_rate,
  conversion_rate,
  revenue_per_session,
  profit_per_session,
  roi
FROM mart_daily_kpis;

CREATE VIEW vw_variant_kpis AS
SELECT
  variant,
  COUNT(*) AS sessions,
  SUM(clicked) AS clicks,
  SUM(converted) AS conversions,
  SUM(revenue) AS revenue,
  SUM(cost) AS cost,
  SUM(profit) AS profit,
  CAST(SUM(clicked) AS REAL) / COUNT(*) AS click_rate,
  CAST(SUM(converted) AS REAL) / COUNT(*) AS conversion_rate,
  SUM(revenue) / COUNT(*) AS revenue_per_session,
  SUM(profit) / COUNT(*) AS profit_per_session,
  CASE WHEN SUM(cost) > 0 THEN SUM(profit) / SUM(cost) ELSE 0 END AS roi
FROM fact_sessions
GROUP BY variant;

CREATE VIEW vw_channel_kpis AS
SELECT
  channel,
  COUNT(*) AS sessions,
  SUM(clicked) AS clicks,
  SUM(converted) AS conversions,
  SUM(revenue) AS revenue,
  SUM(cost) AS cost,
  SUM(profit) AS profit,
  CAST(SUM(clicked) AS REAL) / COUNT(*) AS click_rate,
  CAST(SUM(converted) AS REAL) / COUNT(*) AS conversion_rate,
  SUM(revenue) / COUNT(*) AS revenue_per_session,
  SUM(profit) / COUNT(*) AS profit_per_session,
  CASE WHEN SUM(cost) > 0 THEN SUM(profit) / SUM(cost) ELSE 0 END AS roi
FROM fact_sessions
GROUP BY channel;

CREATE VIEW vw_country_kpis AS
SELECT
  u.country AS country,
  COUNT(*) AS sessions,
  SUM(s.clicked) AS clicks,
  SUM(s.converted) AS conversions,
  SUM(s.revenue) AS revenue,
  SUM(s.cost) AS cost,
  SUM(s.profit) AS profit,
  CAST(SUM(s.clicked) AS REAL) / COUNT(*) AS click_rate,
  CAST(SUM(s.converted) AS REAL) / COUNT(*) AS conversion_rate,
  SUM(s.revenue) / COUNT(*) AS revenue_per_session,
  SUM(s.profit) / COUNT(*) AS profit_per_session,
  CASE WHEN SUM(s.cost) > 0 THEN SUM(s.profit) / SUM(s.cost) ELSE 0 END AS roi
FROM fact_sessions s
JOIN dim_user u ON u.user_id = s.user_id
GROUP BY u.country;