# -*- coding: utf-8 -*-
"""
app.py
Streamlit dashboard for experiment insights with finance-aware metrics.

Reads from SQLite views created by your pipeline:
- vw_daily_kpis
- vw_variant_kpis
- vw_channel_kpis

Shows:
- Revenue, Cost, Profit, ROI
- Trend charts (conversion, ROI, profit)
- Tables (daily, variant, channel)
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import DB_PATH


def db_exists(path: Path) -> bool:
    """Return True if the SQLite database exists."""
    return path.exists()


@st.cache_data
def read_sql(query: str) -> pd.DataFrame:
    """
    Read a SQL query into a DataFrame.
    Cached for performance so the dashboard stays snappy.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def safe_ratio(numerator: float, denominator: float) -> float:
    """Prevent divide-by-zero in ROI or rate calculations."""
    return float(numerator / denominator) if denominator and denominator != 0 else 0.0


def main() -> None:
    st.set_page_config(page_title="Experiment Insights", layout="wide")

    st.title("Performance Analytics Dashboard")
    st.caption("Self-service KPIs and finance-aware performance metrics from SQLite.")

    # Guard: database must exist
    if not db_exists(DB_PATH):
        st.error("Database not found. Run the pipeline first: python -m src.main")
        st.stop()

    # Load BI-ready views (created in sql/views.sql)
    daily = read_sql("SELECT * FROM vw_daily_kpis ORDER BY visit_date, variant;")
    variant = read_sql("SELECT * FROM vw_variant_kpis ORDER BY variant;")
    channel = read_sql("SELECT * FROM vw_channel_kpis ORDER BY sessions DESC;")

    # Convert date for filtering + charting
    daily["visit_date"] = pd.to_datetime(daily["visit_date"], errors="coerce")

    # -----------------------------
    # Sidebar filters
    # -----------------------------
    st.sidebar.header("Filters")

    min_date = daily["visit_date"].min()
    max_date = daily["visit_date"].max()

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])

    daily_f = daily[(daily["visit_date"] >= start_date) & (daily["visit_date"] <= end_date)].copy()

    variants = sorted(daily_f["variant"].dropna().unique().tolist())
    selected_variants = st.sidebar.multiselect("Variant", options=variants, default=variants)

    if selected_variants:
        daily_f = daily_f[daily_f["variant"].isin(selected_variants)].copy()

    # Note: daily view has no channel dimension, so channel filter applies to channel table only
    channels = sorted(channel["channel"].dropna().unique().tolist())
    selected_channels = st.sidebar.multiselect("Channel", options=channels, default=channels)
    channel_f = channel[channel["channel"].isin(selected_channels)].copy() if selected_channels else channel.copy()

    st.sidebar.caption("Channel filter affects channel table only (daily KPIs are by date + variant).")

    # -----------------------------
    # Top metrics (from daily filtered)
    # -----------------------------
    total_revenue = float(daily_f["revenue"].sum())
    total_cost = float(daily_f["cost"].sum())
    total_profit = float(daily_f["profit"].sum())
    total_roi = safe_ratio(total_profit, total_cost)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", f"{total_revenue:,.2f}")
    c2.metric("Cost", f"{total_cost:,.2f}")
    c3.metric("Profit", f"{total_profit:,.2f}")
    c4.metric("ROI (Profit / Cost)", f"{total_roi:.3f}")
    
    # Quick interpretation helper for non-technical reviewers
    st.caption("ROI can be negative when costs are incurred but revenue is low or zero (for example, sessions with spend but no conversion).")

    st.divider()

    # -----------------------------
    # Layout: summaries + charts
    # -----------------------------
    left, right = st.columns((1, 1))

    with left:
        st.subheader("Variant Summary (overall)")
        st.dataframe(variant, use_container_width=True)

        st.subheader("Channel Summary (filtered)")
        st.dataframe(channel_f, use_container_width=True)

    with right:
        st.subheader("Daily Conversion Rate (by Variant)")
        conv_pivot = daily_f.pivot_table(index="visit_date", columns="variant", values="conversion_rate", aggfunc="mean")
        st.line_chart(conv_pivot)

        st.subheader("Daily ROI (by Variant)")
        roi_pivot = daily_f.pivot_table(index="visit_date", columns="variant", values="roi", aggfunc="mean")
        st.line_chart(roi_pivot)

        st.subheader("Daily Profit (total)")
        profit_ts = daily_f.groupby("visit_date", as_index=True)["profit"].sum().sort_index()
        st.line_chart(profit_ts)

    st.divider()

    # -----------------------------
    # Drill-down tables
    # -----------------------------
    st.subheader("Daily KPIs (filtered)")
    daily_show = daily_f.copy()
    daily_show["visit_date"] = daily_show["visit_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(daily_show, use_container_width=True)

    st.subheader("Channel KPIs (filtered)")
    st.dataframe(channel_f, use_container_width=True)

    st.caption("If you change code/schema, rerun: python -m src.main to rebuild the database and views.")


if __name__ == "__main__":
    main()