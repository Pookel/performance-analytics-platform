# -*- coding: utf-8 -*-
"""
analytics.py
Exports KPI CSVs and generates charts.

finance-aware metrics:
- Cost (simulated in transform.py)
- Profit
- ROI = profit / cost
"""

import math
import sqlite3

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.config import DB_PATH, OUTPUT_DIR, CHART_DIR


def z_test_two_proportions(x1: int, n1: int, x2: int, n2: int):
    """
    Two-proportion z-test.
    Returns p1, p2, z-score (no p-value).
    """
    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se if se > 0 else 0.0
    return p1, p2, z


def save_daily_rate_chart(df: pd.DataFrame, date_col: str, rate_col: str, title: str, outpath, day_interval: int = 7, rolling_window: int = 7) -> None:
    # Sort ensures lines plot in the correct time order
    d = df[[date_col, rate_col]].copy().sort_values(date_col)

    # Rolling mean smooths daily noise so trend is visible
    d["rolling_rate"] = d[rate_col].rolling(window=rolling_window, min_periods=1).mean()

    plt.figure(figsize=(11, 5))
    plt.plot(d[date_col], d[rate_col], linewidth=1.0, alpha=0.6, label="Daily")
    plt.plot(d[date_col], d["rolling_rate"], linewidth=2.0, label=f"{rolling_window}-day rolling avg")

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel(rate_col)

    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=day_interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    plt.xticks(rotation=45, ha="right")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=180)
    plt.close()


def save_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, outpath, top_n: int = 10, sort_desc: bool = True) -> None:
    d = df.sort_values(y, ascending=not sort_desc).head(top_n)

    plt.figure(figsize=(11, 5))
    plt.bar(d[x].astype(str), d[y])

    plt.title(title)
    plt.xlabel(x)
    plt.ylabel(y)

    plt.xticks(rotation=45, ha="right")
    plt.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(outpath, dpi=180)
    plt.close()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        # -----------------------------
        # Variant KPIs + A/B summary
        # -----------------------------
        variant_df = pd.read_sql_query(
            """
            SELECT variant,
                   COUNT(*) AS sessions,
                   SUM(clicked) AS clicks,
                   SUM(converted) AS conversions,
                   SUM(revenue) AS revenue,
                   SUM(cost) AS cost,
                   SUM(profit) AS profit
            FROM fact_sessions
            GROUP BY variant
            ORDER BY variant;
            """,
            conn,
        )

        variant_df["click_rate"] = variant_df["clicks"] / variant_df["sessions"]
        variant_df["conversion_rate"] = variant_df["conversions"] / variant_df["sessions"]
        variant_df["revenue_per_session"] = variant_df["revenue"] / variant_df["sessions"]
        variant_df["profit_per_session"] = variant_df["profit"] / variant_df["sessions"]
        variant_df["roi"] = variant_df.apply(lambda r: r["profit"] / r["cost"] if r["cost"] > 0 else 0.0, axis=1)

        a = variant_df[variant_df["variant"] == "A"].iloc[0]
        b = variant_df[variant_df["variant"] == "B"].iloc[0]

        p1, p2, z = z_test_two_proportions(int(a["conversions"]), int(a["sessions"]), int(b["conversions"]), int(b["sessions"]))

        summary = {
            "A_sessions": int(a["sessions"]),
            "B_sessions": int(b["sessions"]),
            "A_conversion_rate": float(p1),
            "B_conversion_rate": float(p2),
            "lift_B_vs_A": float((p2 - p1) / p1) if p1 > 0 else None,
            "z_score": float(z),
            "A_profit": float(a["profit"]),
            "B_profit": float(b["profit"]),
            "A_roi": float(a["profit"] / a["cost"]) if float(a["cost"]) > 0 else 0.0,
            "B_roi": float(b["profit"] / b["cost"]) if float(b["cost"]) > 0 else 0.0,
        }

        # -----------------------------
        # Daily KPIs
        # -----------------------------
        daily_df = pd.read_sql_query(
            """
            SELECT visit_date,
                   variant,
                   COUNT(*) AS sessions,
                   SUM(clicked) AS clicks,
                   SUM(converted) AS conversions,
                   SUM(revenue) AS revenue,
                   SUM(cost) AS cost,
                   SUM(profit) AS profit
            FROM fact_sessions
            GROUP BY visit_date, variant
            ORDER BY visit_date, variant;
            """,
            conn,
        )

        daily_df["click_rate"] = daily_df["clicks"] / daily_df["sessions"]
        daily_df["conversion_rate"] = daily_df["conversions"] / daily_df["sessions"]
        daily_df["revenue_per_session"] = daily_df["revenue"] / daily_df["sessions"]
        daily_df["profit_per_session"] = daily_df["profit"] / daily_df["sessions"]
        daily_df["roi"] = daily_df.apply(lambda r: r["profit"] / r["cost"] if r["cost"] > 0 else 0.0, axis=1)

        daily_df["visit_date"] = pd.to_datetime(daily_df["visit_date"])

        # -----------------------------
        # Channel KPIs
        # -----------------------------
        channel_df = pd.read_sql_query(
            """
            SELECT channel,
                   COUNT(*) AS sessions,
                   SUM(clicked) AS clicks,
                   SUM(converted) AS conversions,
                   SUM(revenue) AS revenue,
                   SUM(cost) AS cost,
                   SUM(profit) AS profit
            FROM fact_sessions
            GROUP BY channel
            ORDER BY sessions DESC;
            """,
            conn,
        )

        channel_df["click_rate"] = channel_df["clicks"] / channel_df["sessions"]
        channel_df["conversion_rate"] = channel_df["conversions"] / channel_df["sessions"]
        channel_df["revenue_per_session"] = channel_df["revenue"] / channel_df["sessions"]
        channel_df["profit_per_session"] = channel_df["profit"] / channel_df["sessions"]
        channel_df["roi"] = channel_df.apply(lambda r: r["profit"] / r["cost"] if r["cost"] > 0 else 0.0, axis=1)

        # -----------------------------
        # Save CSV outputs
        # -----------------------------
        variant_df.to_csv(OUTPUT_DIR / "variant_kpis.csv", index=False)
        pd.DataFrame([summary]).to_csv(OUTPUT_DIR / "ab_test_summary.csv", index=False)

        daily_out = daily_df.copy()
        daily_out["visit_date"] = daily_out["visit_date"].dt.strftime("%Y-%m-%d")
        daily_out.to_csv(OUTPUT_DIR / "daily_kpis.csv", index=False)

        channel_df.to_csv(OUTPUT_DIR / "channel_kpis.csv", index=False)

        # -----------------------------
        # Daily trend charts
        # -----------------------------
        for v in ["A", "B"]:
            d = daily_df[daily_df["variant"] == v].copy()

            save_daily_rate_chart(
                df=d,
                date_col="visit_date",
                rate_col="conversion_rate",
                title=f"Daily Conversion Rate (Variant {v})",
                outpath=CHART_DIR / f"daily_conversion_rate_variant_{v}.png",
                day_interval=7,
                rolling_window=7,
            )

            save_daily_rate_chart(
                df=d,
                date_col="visit_date",
                rate_col="roi",
                title=f"Daily ROI (Variant {v})",
                outpath=CHART_DIR / f"daily_roi_variant_{v}.png",
                day_interval=7,
                rolling_window=7,
            )

        # -----------------------------
        # Channel charts
        # -----------------------------
        save_bar_chart(channel_df, x="channel", y="revenue", title="Revenue by Channel", outpath=CHART_DIR / "revenue_by_channel.png")
        save_bar_chart(channel_df, x="channel", y="profit", title="Profit by Channel", outpath=CHART_DIR / "profit_by_channel.png")
        save_bar_chart(channel_df, x="channel", y="roi", title="ROI by Channel", outpath=CHART_DIR / "roi_by_channel.png")

        print("Saved outputs to data/outputs/")
        print("A/B test summary:", summary)

    finally:
        conn.close()


if __name__ == "__main__":
    main()