# -*- coding: utf-8 -*-
"""
Created on Sun Feb 5 21:37:22 2026

@author: Melecia

transform.py
Builds:
- dim_user (unique users)
- fact_sessions (session-level fact table, now with cost/profit/roi)
- mart_daily_kpis (daily KPI mart, now with profit and ROI)

Cost is simulated to make the project feel finance-aware.
"""

import sqlite3
import pandas as pd

from src.config import DB_PATH


def simulate_cost(row: pd.Series) -> float:
    """
    Simulate per-session cost using simple business logic:
    - Base traffic cost for every session
    - Channel uplift (paid_search costs more than organic)
    - If converted, add a cost that scales with revenue (COGS style)

    This is intentionally simple and explainable for interviews.
    """
    base_cost = 0.15  # baseline per session cost (platform, tracking, etc.)

    # Channel cost multipliers
    channel_cost = {
        "organic": 0.05,
        "referral": 0.07,
        "social": 0.10,
        "email": 0.08,
        "paid_search": 0.35,
    }.get(str(row["channel"]), 0.10)

    # Engagement adds a tiny cost (longer sessions imply more served content)
    engagement_cost = min(float(row["session_seconds"]) / 10000.0, 0.15)

    # If a conversion happened, add a revenue-linked cost (fulfillment / COGS proxy)
    revenue = float(row["revenue"])
    converted = int(row["converted"])

    # Cost rate can vary slightly by channel (paid_search can be costlier)
    cost_rate = 0.62 if str(row["channel"]) == "paid_search" else 0.58

    conversion_cost = (revenue * cost_rate) if converted == 1 else 0.0

    total_cost = base_cost + channel_cost + engagement_cost + conversion_cost

    # Round for clean reporting
    return round(total_cost, 2)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        raw = pd.read_sql_query("SELECT * FROM raw_visits", conn)

        # dim_user: unique users by user_id
        dim_user = raw[["user_id", "country"]].drop_duplicates(subset=["user_id"])
        conn.execute("DELETE FROM dim_user;")
        dim_user.to_sql("dim_user", conn, if_exists="append", index=False)

        # fact_sessions: one row per session
        fact = raw[
            [
                "user_id",
                "variant",
                "visit_date",
                "device",
                "channel",
                "session_seconds",
                "clicked",
                "converted",
                "revenue",
            ]
        ].copy()

        # Finance fields
        fact["cost"] = fact.apply(simulate_cost, axis=1)
        fact["profit"] = (fact["revenue"] - fact["cost"]).round(2)

        # ROI definition: profit / cost (guard against divide by zero)
        fact["roi"] = fact.apply(lambda r: round(r["profit"] / r["cost"], 6) if r["cost"] > 0 else 0.0, axis=1)

        conn.execute("DELETE FROM fact_sessions;")
        fact.to_sql("fact_sessions", conn, if_exists="append", index=False)

        # mart_daily_kpis: aggregated daily KPIs by date + variant
        kpis = (
            fact.groupby(["visit_date", "variant"], as_index=False)
            .agg(
                sessions=("user_id", "count"),
                clicks=("clicked", "sum"),
                conversions=("converted", "sum"),
                revenue=("revenue", "sum"),
                cost=("cost", "sum"),
                profit=("profit", "sum"),
            )
        )

        kpis["click_rate"] = (kpis["clicks"] / kpis["sessions"]).round(6)
        kpis["conversion_rate"] = (kpis["conversions"] / kpis["sessions"]).round(6)
        kpis["revenue_per_session"] = (kpis["revenue"] / kpis["sessions"]).round(6)
        kpis["profit_per_session"] = (kpis["profit"] / kpis["sessions"]).round(6)
        kpis["roi"] = kpis.apply(lambda r: round(r["profit"] / r["cost"], 6) if r["cost"] > 0 else 0.0, axis=1)

        conn.execute("DELETE FROM mart_daily_kpis;")
        kpis.to_sql("mart_daily_kpis", conn, if_exists="append", index=False)

        conn.commit()
        print("Built dim_user, fact_sessions (with finance metrics), mart_daily_kpis")
    finally:
        conn.close()


if __name__ == "__main__":
    main()