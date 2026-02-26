PRAGMA foreign_keys = ON;

-- Drop children first, then parents (avoids FK constraint failures)
DROP TABLE IF EXISTS mart_daily_kpis;
DROP TABLE IF EXISTS fact_sessions;
DROP TABLE IF EXISTS dim_user;
DROP TABLE IF EXISTS raw_visits;

CREATE TABLE raw_visits (
  user_id TEXT NOT NULL,
  variant TEXT NOT NULL CHECK (variant IN ('A','B')),
  visit_date TEXT NOT NULL,
  device TEXT NOT NULL,
  channel TEXT NOT NULL,
  country TEXT NOT NULL,
  session_seconds INTEGER NOT NULL,
  clicked INTEGER NOT NULL CHECK (clicked IN (0,1)),
  converted INTEGER NOT NULL CHECK (converted IN (0,1)),
  revenue REAL NOT NULL
);

CREATE TABLE dim_user (
  user_id TEXT PRIMARY KEY,
  country TEXT NOT NULL
);

-- Fact table with finance-aware metrics
CREATE TABLE fact_sessions (
  session_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  visit_date TEXT NOT NULL,
  device TEXT NOT NULL,
  channel TEXT NOT NULL,
  session_seconds INTEGER NOT NULL,
  clicked INTEGER NOT NULL,
  converted INTEGER NOT NULL,
  revenue REAL NOT NULL,

  -- Added fields
  cost REAL NOT NULL,
  profit REAL NOT NULL,
  roi REAL NOT NULL,

  FOREIGN KEY(user_id) REFERENCES dim_user(user_id)
);

-- Daily KPI mart  includes finance totals + ROI
CREATE TABLE mart_daily_kpis (
  visit_date TEXT NOT NULL,
  variant TEXT NOT NULL,
  sessions INTEGER NOT NULL,
  clicks INTEGER NOT NULL,
  conversions INTEGER NOT NULL,

  revenue REAL NOT NULL,
  cost REAL NOT NULL,
  profit REAL NOT NULL,

  click_rate REAL NOT NULL,
  conversion_rate REAL NOT NULL,
  revenue_per_session REAL NOT NULL,
  profit_per_session REAL NOT NULL,
  roi REAL NOT NULL,

  PRIMARY KEY (visit_date, variant)
);