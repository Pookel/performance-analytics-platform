# -*- coding: utf-8 -*-
"""
transform.py
Builds:
- dim_user (unique users)
- fact_sessions (session-level fact table, with finance fields)
- mart_daily_kpis (daily KPI mart)

Fix: prevent ML leakage by splitting cost into:
- cost_pre  : costs known before conversion (safe for ML features)
- cost      : total cost including conversion-linked COGS proxy (finance reporting)
"""

import sqlite3
import pandas as pd

from src.config import DB_PATH


def simulate_costs(row: pd.Series) -> tuple[float, float]:
    """
    Simulate per-session cost using simple business logic.

    We compute TWO costs:
    1) cost_pre (SAFE for ML): costs incurred regardless of conversion, and known during the session.
       - base traffic cost
       - channel acquisition/traffic cost
       - engagement cost (session length proxy)

    2) cost_total (FINANCE reporting): cost_pre + conversion-linked cost (COGS/fulfilment proxy).
       - This part depends on 'converted' and MUST NOT be used as an ML feature to predict 'converted'.

    Returns: (cost_pre, cost_total) rounded for reporting.
    """
    # Baseline per session cost (platform, tracking, overhead)
    base_cost = 0.15

    # Channel acquisition cost (paid_search costs more than organic)
    channel_cost = {
        "organic": 0.05,
        "referral": 0.07,
        "social": 0.10,
        "email": 0.08,
        "paid_search": 0.35,
    }.get(str(row["channel"]), 0.10)

    # Engagement cost: longer sessions imply more served content (cap to avoid runaway)
    session_seconds = float(row["session_seconds"])
    engagement_cost = min(session_seconds / 10000.0, 0.15)

    # SAFE portion: known regardless of whether a conversion happens
    cost_pre = base_cost + channel_cost + engagement_cost

    # Conversion-linked cost (COGS / fulfilment proxy) for finance reporting only
    revenue = float(row["revenue"])
    converted = int(row["converted"])

    # Cost rate can vary slightly by channel (paid_search can be costlier)
    cost_rate = 0.62 if str(row["channel"]) == "paid_search" else 0.58

    conversion_cost = (revenue * cost_rate) if converted == 1 else 0.0

    cost_total = cost_pre + conversion_cost

    return round(cost_pre, 2), round(cost_total, 2)


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
        # - cost_pre is safe for ML features
        # - cost is the total finance cost including conversion-linked component
        cost_cols = fact.apply(lambda r: pd.Series(simulate_costs(r), index=["cost_pre", "cost"]), axis=1)
        fact = pd.concat([fact, cost_cols], axis=1)

        fact["profit"] = (fact["revenue"] - fact["cost"]).round(2)

        # ROI definition: profit / cost (guard against divide by zero)
        fact["roi"] = fact.apply(
            lambda r: round(r["profit"] / r["cost"], 6) if r["cost"] > 0 else 0.0,
            axis=1
        )

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
        kpis["roi"] = kpis.apply(
            lambda r: round(r["profit"] / r["cost"], 6) if r["cost"] > 0 else 0.0,
            axis=1
        )

        conn.execute("DELETE FROM mart_daily_kpis;")
        kpis.to_sql("mart_daily_kpis", conn, if_exists="append", index=False)

        conn.commit()
        print("Built dim_user, fact_sessions (with finance metrics + cost_pre), mart_daily_kpis")
    finally:
        conn.close()


if __name__ == "__main__":
    main()