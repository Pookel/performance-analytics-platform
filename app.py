# -*- coding: utf-8 -*-
"""
app.py
Streamlit dashboard for experiment insights with business metrics.

Reads from SQLite views created by your pipeline:
- vw_daily_kpis
- vw_variant_kpis
- vw_channel_kpis

Shows:
- Revenue, Cost, Profit, ROI (styled KPI cards)
- Executive Summary (BI-style cards + highlighted winners + next action)
- Spend efficiency metrics
- Trend charts (Altair)
- Drill-down tables
- ML Layer: Conversion prediction + interpretation + recommended actions
- Decision Simulator: Forecast expected conversions, revenue, profit, ROI
- Export to PDF report button
"""

import io
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import altair as alt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from src.config import DB_PATH, PROJECT_ROOT
from src.ml_conversion import train_and_save, load_model, predict_proba

alt.data_transformers.disable_max_rows()


# -----------------------------
# Helpers
# -----------------------------
def db_exists(path: Path) -> bool:
    return path.exists()


@st.cache_data
def read_sql(query: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator and denominator != 0 else 0.0


def format_money(x: float) -> str:
    return f"{x:,.2f}"


def band_label(p: float, baseline: float) -> str:
    if baseline <= 0:
        return "Unknown"

    capped = min(float(p), float(baseline) * 4.0)
    ratio = capped / float(baseline)

    if ratio < 0.8:
        return "Low"
    if ratio < 1.2:
        return "Moderate"
    if ratio < 2.0:
        return "High"
    return "Very high"


def interpretation_text(p: float, baseline: float) -> str:
    out_of_100 = int(round(p * 100))
    label = band_label(p, baseline)
    base_pct = baseline * 100 if baseline else 0.0
    return (
        f"{label} likelihood. Out of 100 similar sessions, about {out_of_100} may convert. "
        f"Baseline conversion rate in your filtered data is {base_pct:.2f}%."
    )


def recommended_actions(p: float, baseline: float) -> list[str]:
    label = band_label(p, baseline)

    if label == "Low":
        return [
            "Focus on click-through first (creative, targeting, offer).",
            "If this is paid traffic, review spend because conversions are unlikely at this level.",
            "Test a clearer landing page message and reduce friction.",
        ]

    if label == "Moderate":
        return [
            "Baseline level. Run tests to lift conversion (landing page, offer, targeting).",
            "Keep spend controlled while you test improvements.",
            "Track cost per conversion to protect profitability.",
        ]

    if label == "High":
        return [
            "Above baseline. Scale gradually and watch ROI daily.",
            "Keep testing to confirm the uplift holds over time.",
            "Monitor profit per conversion so scaling does not dilute returns.",
        ]

    return [
        "Strong signal relative to baseline. This is a candidate for scaling.",
        "Increase budget gradually and track ROI daily.",
        "Run controlled tests to confirm performance is repeatable.",
    ]


def line_chart_variants(df: pd.DataFrame, y_col: str, title: str, y_title: str) -> alt.Chart:
    axis_cfg = alt.Axis(format="%Y-%m-%d", labelAngle=-45, tickCount=10)
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X("visit_date:T", title="Date", axis=axis_cfg),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            color=alt.Color("variant:N", title="Variant"),
            tooltip=[
                alt.Tooltip("visit_date:T", title="Date"),
                alt.Tooltip("variant:N", title="Variant"),
                alt.Tooltip(f"{y_col}:Q", title=y_title),
            ],
        )
        .properties(title=title, height=270)
        .interactive()
    )


def line_chart_total(df: pd.DataFrame, y_col: str, title: str, y_title: str) -> alt.Chart:
    axis_cfg = alt.Axis(format="%Y-%m-%d", labelAngle=-45, tickCount=10)
    return (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X("visit_date:T", title="Date", axis=axis_cfg),
            y=alt.Y(f"{y_col}:Q", title=y_title),
            tooltip=[
                alt.Tooltip("visit_date:T", title="Date"),
                alt.Tooltip(f"{y_col}:Q", title=y_title),
            ],
        )
        .properties(title=title, height=270)
        .interactive()
    )


def set_ui_styles() -> None:
    st.markdown(
        """
        <style>
        .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 6px; }
        .card {
            border-radius: 14px;
            padding: 14px 14px 12px 14px;
            border: 1px solid rgba(0,0,0,0.08);
            background: white;
            box-shadow: 0 1px 10px rgba(0,0,0,0.04);
        }
        .card .label { font-size: 0.85rem; opacity: 0.75; margin-bottom: 6px; }
        .card .value { font-size: 1.55rem; font-weight: 700; line-height: 1.2; }
        .card .sub { font-size: 0.82rem; opacity: 0.70; margin-top: 6px; }

        .accent-green { border-left: 6px solid #1f9d55; }
        .accent-red   { border-left: 6px solid #e03131; }
        .accent-blue  { border-left: 6px solid #1c7ed6; }
        .accent-gray  { border-left: 6px solid #495057; }

        .panel-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 8px; }
        .pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.80rem;
            font-weight: 600;
            background: rgba(28,126,214,0.10);
            color: #1c7ed6;
            margin-left: 8px;
        }
        .good { background: rgba(31,157,85,0.12); color: #1f9d55; }
        .warn { background: rgba(224,49,49,0.12); color: #e03131; }
        .info { background: rgba(73,80,87,0.10); color: #495057; }

        .next-action {
            border-radius: 14px;
            padding: 14px;
            border: 1px solid rgba(0,0,0,0.08);
            background: linear-gradient(135deg, rgba(28,126,214,0.10), rgba(31,157,85,0.08));
            box-shadow: 0 1px 10px rgba(0,0,0,0.04);
        }
        .next-action h4 { margin: 0 0 6px 0; }
        .next-action p { margin: 0; opacity: 0.85; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, accent_class: str, sub: str = "") -> str:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f"""
    <div class="card {accent_class}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {sub_html}
    </div>
    """


def pick_best_row(df: pd.DataFrame, metric_col: str, ascending: bool = False):
    if df is None or df.empty or metric_col not in df.columns:
        return None
    d = df.dropna(subset=[metric_col]).copy()
    if d.empty:
        return None
    return d.sort_values(metric_col, ascending=ascending).iloc[0]


def df_preview_text(df: pd.DataFrame, max_rows: int = 6) -> list[str]:
    if df is None or df.empty:
        return ["(no data)"]
    preview = df.head(max_rows).copy()
    return preview.to_string(index=False).splitlines()


def revenue_per_conversion_for_selection(
    daily_df: pd.DataFrame,
    selected_variant: str,
    selected_channel: str | None = None,
    smoothing_k: float = 10.0
) -> float:
    """
    Returns revenue-per-conversion for the selected variant (and channel if daily_df has it).
    Uses smoothing so tiny conversion counts don't explode the number.
    """
    if daily_df is None or daily_df.empty:
        return 0.0

    df = daily_df.copy()

    if "revenue" not in df.columns or "conversions" not in df.columns:
        return 0.0

    # Filter to variant
    if "variant" in df.columns:
        df = df[df["variant"].astype(str) == str(selected_variant)]

    # If daily includes channel, filter to channel too
    if selected_channel is not None and "channel" in df.columns:
        df = df[df["channel"].astype(str) == str(selected_channel)]

    rev = float(df["revenue"].sum())
    conv = float(df["conversions"].sum())

    if rev <= 0:
        return 0.0

    return rev / (conv + float(smoothing_k))


def export_pdf_report(
    *,
    title: str,
    generated_on: str,
    filters_line: str,
    kpis: dict,
    executive: dict,
    spend: dict,
    variant_df: pd.DataFrame,
    channel_df: pd.DataFrame,
    simulator: dict,
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4

    x = 2.0 * cm
    y = height - 2.0 * cm
    line_h = 0.55 * cm

    def draw_line(txt: str, bold: bool = False):
        nonlocal y
        if y < 2.0 * cm:
            c.showPage()
            y = height - 2.0 * cm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if not bold else 11)
        c.drawString(x, y, txt[:140])
        y -= line_h

    draw_line(title, bold=True)
    draw_line(f"Generated: {generated_on}")
    draw_line(filters_line)
    draw_line("")

    draw_line("Top KPIs", bold=True)
    draw_line(f"Revenue: {kpis['revenue']}")
    draw_line(f"Cost: {kpis['cost']}")
    draw_line(f"Profit: {kpis['profit']}")
    draw_line(f"ROI (Profit/Cost): {kpis['roi']}")
    draw_line("")

    draw_line("Executive Summary", bold=True)
    draw_line(f"Profit leader: {executive.get('profit_leader','N/A')}")
    draw_line(f"Conversion leader: {executive.get('conversion_leader','N/A')}")
    draw_line(f"Best ROI channel: {executive.get('best_roi_channel','N/A')}")
    draw_line(f"Next best action: {executive.get('next_action','N/A')}")
    draw_line("")

    draw_line("Spend Efficiency", bold=True)
    draw_line(f"Cost per conversion: {spend['cost_per_conversion']}")
    draw_line(f"Revenue per conversion: {spend['revenue_per_conversion']}")
    draw_line(f"Profit per conversion: {spend['profit_per_conversion']}")
    draw_line("")

    draw_line("Variant Summary (preview)", bold=True)
    for ln in df_preview_text(variant_df, max_rows=6):
        draw_line(ln)
    draw_line("")

    draw_line("Channel Summary (preview)", bold=True)
    for ln in df_preview_text(channel_df, max_rows=7):
        draw_line(ln)
    draw_line("")

    draw_line("Decision Simulator (latest inputs/results)", bold=True)
    draw_line(simulator.get("inputs", ""))
    draw_line(simulator.get("used_rate", ""))
    draw_line(simulator.get("expected_conversions", ""))
    draw_line(simulator.get("expected_revenue", ""))
    draw_line(simulator.get("expected_cost", ""))
    draw_line(simulator.get("expected_profit", ""))
    draw_line(simulator.get("expected_roi", ""))

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# -----------------------------
# App
# -----------------------------
def main() -> None:
    st.set_page_config(page_title="Experiment Insights", layout="wide")
    set_ui_styles()

    st.title("Performance Analytics Dashboard")
    st.caption(
        "Self-service KPIs and finance-aware performance metrics from SQLite, "
        "with business insights, forecasting, and an ML prediction layer."
    )

    if not db_exists(DB_PATH):
        st.error("Database not found. Run the pipeline first: py -m src.main")
        st.stop()

    model_path = PROJECT_ROOT / "models" / "conversion_model.joblib"

    daily = read_sql("SELECT * FROM vw_daily_kpis ORDER BY visit_date, variant;")
    variant = read_sql("SELECT * FROM vw_variant_kpis ORDER BY variant;")
    channel = read_sql("SELECT * FROM vw_channel_kpis ORDER BY sessions DESC;")

    if daily is None or daily.empty:
        st.error("vw_daily_kpis returned no rows. Run the pipeline and confirm the views exist.")
        st.stop()

    daily["visit_date"] = pd.to_datetime(daily["visit_date"], errors="coerce")

    # -----------------------------
    # Sidebar filters
    # -----------------------------
    st.sidebar.header("Filters")

    min_date = daily["visit_date"].min()
    max_date = daily["visit_date"].max()

    if pd.isna(min_date) or pd.isna(max_date):
        st.error("visit_date has no valid dates. Check vw_daily_kpis.visit_date values.")
        st.stop()

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

    channels = sorted(channel["channel"].dropna().unique().tolist())
    selected_channels = st.sidebar.multiselect("Channel", options=channels, default=channels)
    channel_f = channel[channel["channel"].isin(selected_channels)].copy() if selected_channels else channel.copy()

    st.sidebar.caption("Channel filter affects channel summary/table only. Daily KPIs are by date + variant.")

    # -----------------------------
    # Top KPI cards
    # -----------------------------
    total_revenue = float(daily_f["revenue"].sum())
    total_cost = float(daily_f["cost"].sum())
    total_profit = float(daily_f["profit"].sum())
    total_roi = safe_ratio(total_profit, total_cost)
    total_conversions = float(daily_f["conversions"].sum())
    total_sessions = float(daily_f["sessions"].sum()) if "sessions" in daily_f.columns else 0.0
    overall_conv_rate = safe_ratio(total_conversions, total_sessions)

    kpi_html = f"""
    <div class="kpi-grid">
        {kpi_card("Revenue", format_money(total_revenue), "accent-green", "Total revenue in filter window")}
        {kpi_card("Cost", format_money(total_cost), "accent-red", "Total cost in filter window")}
        {kpi_card("Profit", format_money(total_profit), "accent-blue", "Revenue minus cost")}
        {kpi_card("ROI (Profit / Cost)", f"{total_roi:.3f}", "accent-gray", "Higher is better")}
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    st.caption("ROI can be negative when costs are incurred but revenue is low or zero.")

    # -----------------------------
    # Spend Efficiency
    # -----------------------------
    st.subheader("Spend Efficiency")

    cost_per_conversion = safe_ratio(total_cost, total_conversions)
    revenue_per_conversion = safe_ratio(total_revenue, total_conversions)
    profit_per_conversion = safe_ratio(total_profit, total_conversions)

    e1, e2, e3 = st.columns(3)
    e1.metric("Cost per conversion", format_money(cost_per_conversion))
    e2.metric("Revenue per conversion", format_money(revenue_per_conversion))
    e3.metric("Profit per conversion", format_money(profit_per_conversion))

    st.divider()

    # -----------------------------
    # Executive Summary
    # -----------------------------
    st.markdown(
        '<div class="panel-title">Executive Summary <span class="pill">Auto insights</span></div>',
        unsafe_allow_html=True,
    )

    best_profit_var = pick_best_row(variant, "profit", ascending=False)
    best_conv_var = pick_best_row(variant, "conversion_rate", ascending=False)
    best_roi_ch = pick_best_row(channel_f, "roi", ascending=False)
    worst_roi_ch = pick_best_row(channel_f, "roi", ascending=True)

    profit_leader = f"Variant {best_profit_var['variant']}" if best_profit_var is not None else "N/A"
    conv_leader = f"Variant {best_conv_var['variant']}" if best_conv_var is not None else "N/A"
    best_channel = str(best_roi_ch["channel"]) if best_roi_ch is not None else "N/A"
    worst_channel = str(worst_roi_ch["channel"]) if worst_roi_ch is not None else "N/A"

    if best_roi_ch is not None and worst_roi_ch is not None and best_channel != worst_channel:
        next_action = f"Scale {best_channel} first (best ROI). Review {worst_channel} spend if ROI stays weak."
        action_badge = "good"
    elif best_roi_ch is not None:
        next_action = f"Best ROI channel right now is {best_channel}. Scale gradually and monitor ROI daily."
        action_badge = "info"
    else:
        next_action = "Apply filters and compare channels by ROI to decide where to scale and where to fix inefficiency."
        action_badge = "info"

    s1, s2, s3 = st.columns(3)
    s1.markdown(kpi_card("Profit leader", profit_leader, "accent-blue"), unsafe_allow_html=True)
    s2.markdown(kpi_card("Conversion leader", conv_leader, "accent-green"), unsafe_allow_html=True)
    s3.markdown(kpi_card("Best ROI channel", best_channel, "accent-gray"), unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="next-action">
            <h4>Next best action <span class="pill {action_badge}">Recommendation</span></h4>
            <p>{next_action}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # -----------------------------
    # Export to PDF
    # -----------------------------
    st.header("Export")
    st.caption("Download a PDF snapshot of KPIs, executive summary, spend efficiency, key tables, and simulator outputs.")

    filters_line = (
        f"Filters: {start_date.date()} to {end_date.date()} | "
        f"Variants: {', '.join(selected_variants) if selected_variants else 'all'} | "
        f"Channels: {', '.join(selected_channels) if selected_channels else 'all'}"
    )

    if "sim_export_payload" not in st.session_state:
        st.session_state["sim_export_payload"] = {
            "inputs": "Variant: -, Channel: -",
            "used_rate": "Conversion rate used: -",
            "expected_conversions": "Expected conversions: -",
            "expected_revenue": "Expected revenue: -",
            "expected_cost": "Expected cost: -",
            "expected_profit": "Expected profit: -",
            "expected_roi": "Expected ROI: -",
        }

    pdf_bytes = export_pdf_report(
        title="Performance Analytics Dashboard Report",
        generated_on=str(date.today()),
        filters_line=filters_line,
        kpis={
            "revenue": format_money(total_revenue),
            "cost": format_money(total_cost),
            "profit": format_money(total_profit),
            "roi": f"{total_roi:.3f}",
        },
        executive={
            "profit_leader": profit_leader,
            "conversion_leader": conv_leader,
            "best_roi_channel": best_channel,
            "next_action": next_action,
        },
        spend={
            "cost_per_conversion": format_money(cost_per_conversion),
            "revenue_per_conversion": format_money(revenue_per_conversion),
            "profit_per_conversion": format_money(profit_per_conversion),
        },
        variant_df=variant,
        channel_df=channel_f,
        simulator=st.session_state["sim_export_payload"],
    )

    st.download_button(
        label="Export PDF report",
        data=pdf_bytes,
        file_name="performance_analytics_report.pdf",
        mime="application/pdf",
        use_container_width=False,
    )

    st.divider()

    # -----------------------------
    # Performance summaries
    # -----------------------------
    st.header("Performance Summaries")

    if best_profit_var is not None and "profit" in best_profit_var.index:
        st.success(
            f"Best profit variant: Variant {best_profit_var['variant']} "
            f"(profit = {format_money(float(best_profit_var['profit']))})"
        )

    st.subheader("Variant Summary (overall)")
    st.dataframe(variant, use_container_width=True)

    if best_roi_ch is not None and "roi" in best_roi_ch.index:
        st.success(f"Best ROI channel: {best_channel} (ROI = {float(best_roi_ch['roi']):.3f})")
    if worst_roi_ch is not None and "roi" in worst_roi_ch.index:
        st.warning(f"Lowest ROI channel: {worst_channel} (ROI = {float(worst_roi_ch['roi']):.3f})")

    st.subheader("Channel Summary (filtered)")
    st.dataframe(channel_f, use_container_width=True)

    st.divider()

    # -----------------------------
    # Trends
    # -----------------------------
    st.header("Trends")

    daily_plot = daily_f.dropna(subset=["visit_date"]).copy()
    daily_plot["visit_date"] = pd.to_datetime(daily_plot["visit_date"], errors="coerce")
    daily_plot = daily_plot.sort_values("visit_date")

    conv_chart = line_chart_variants(daily_plot, "conversion_rate", "Daily Conversion Rate (by Variant)", "Conversion rate")
    roi_chart = line_chart_variants(daily_plot, "roi", "Daily ROI (by Variant)", "ROI")

    profit_ts = daily_plot.groupby("visit_date", as_index=False)["profit"].sum().rename(columns={"profit": "total_profit"})
    revenue_ts = daily_plot.groupby("visit_date", as_index=False)["revenue"].sum().rename(columns={"revenue": "total_revenue"})

    profit_chart = line_chart_total(profit_ts, "total_profit", "Daily Profit (total)", "Total profit")
    revenue_chart = line_chart_total(revenue_ts, "total_revenue", "Daily Revenue (total)", "Total revenue")

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.altair_chart(conv_chart, use_container_width=True)
    with r1c2:
        st.altair_chart(roi_chart, use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.altair_chart(profit_chart, use_container_width=True)
    with r2c2:
        st.altair_chart(revenue_chart, use_container_width=True)

    st.divider()

    # -----------------------------
    # Drill-down tables
    # -----------------------------
    st.header("Drill-down Tables")

    st.subheader("Daily KPIs (filtered)")
    daily_show = daily_plot.copy()
    daily_show["visit_date"] = daily_show["visit_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(daily_show, use_container_width=True)

    st.subheader("Channel KPIs (filtered)")
    st.dataframe(channel_f, use_container_width=True)

    st.divider()

    # -----------------------------
    # ML Layer
    # -----------------------------
    st.header("ML: Conversion Prediction")

    st.caption(
        "Train a model from fact_sessions to predict conversion probability using variant, device, channel, "
        "session_seconds, clicked, and cost_pre (pre-conversion cost)."
    )

    col_train, col_status = st.columns([1, 2])

    with col_train:
        if st.button("Train / Re-train Model"):
            try:
                metrics, report = train_and_save(DB_PATH, model_path)
                st.success("Model trained and saved successfully.")
                st.json(metrics)
                st.text(report)
            except Exception as e:
                st.error(f"Training failed: {e}")

    with col_status:
        if model_path.exists():
            st.info(f"Model available: {model_path}")
        else:
            st.warning("No saved model yet. Click 'Train / Re-train Model' first.")

    st.subheader("Predict conversion probability for a new session")

    with st.form("predict_form"):
        p_variant = st.selectbox("Variant", ["A", "B"])
        p_device = st.selectbox("Device", ["mobile", "desktop", "tablet"])
        p_channel = st.selectbox("Channel", ["organic", "paid_search", "email", "social", "referral"])
        p_session_seconds = st.number_input("Session seconds", min_value=0, value=180)
        p_clicked = st.selectbox("Clicked", [0, 1])
        p_cost_pre = st.number_input("Cost (pre-conversion)", min_value=0.0, value=0.50)
        submitted = st.form_submit_button("Predict")

    if submitted:
        try:
            model = load_model(model_path)
            p = float(
                predict_proba(
                    model=model,
                    variant=str(p_variant),
                    device=str(p_device),
                    channel=str(p_channel),
                    session_seconds=int(p_session_seconds),
                    clicked=int(p_clicked),
                    cost_pre=float(p_cost_pre),
                )
            )

            st.markdown("---")
            m1, m2, m3 = st.columns([1, 1, 2])
            m1.metric("Conversion probability", f"{p:.2%}")
            m2.metric("Out of 100 sessions", f"{int(round(p * 100))} convert")
            m3.metric("Likelihood band", band_label(p, overall_conv_rate))

            st.subheader("Interpretation")
            st.write(interpretation_text(p, overall_conv_rate))

            st.subheader("Recommended actions")
            for rec in recommended_actions(p, overall_conv_rate):
                st.write(f"- {rec}")

        except Exception as e:
            st.error(f"Prediction failed: {e}")

    st.divider()

    # -----------------------------
    # Decision Simulator (ONLY ONE, INSIDE main)
    # -----------------------------
    st.header("Decision Simulator")

    st.caption(
        "Forecast expected conversions, revenue, profit, and ROI for a chosen variant and channel. "
        "This helps teams decide where to scale and what to fix."
    )

    baseline_conv_rate = float(overall_conv_rate)
    baseline_roi = float(total_roi)

    sim_left, sim_right = st.columns([1, 1])

    with sim_left:
        sim_variant = st.selectbox("Variant", ["A", "B"], key="sim_variant")
        sim_channel = st.selectbox(
            "Channel", ["organic", "paid_search", "email", "social", "referral"], key="sim_channel"
        )
        monthly_sessions = st.number_input("Monthly sessions", min_value=0, value=20000, step=1000)

        avg_cost_per_session = st.number_input(
            "Avg cost per session (pre-conversion)",
            min_value=0.0,
            value=0.50,
            step=0.05,
        )

        sim_device = st.selectbox("Assumed device", ["mobile", "desktop", "tablet"], key="sim_device")
        sim_clicked = st.selectbox("Assumed clicked", [0, 1], key="sim_clicked")
        sim_session_seconds = st.number_input("Assumed session seconds", min_value=0, value=180, step=10)

        use_ml = st.checkbox("Use ML to estimate conversion rate", value=True)

    with sim_right:
        if use_ml and model_path.exists():
            try:
                model = load_model(model_path)
                sim_conversion_rate = float(
                    predict_proba(
                        model=model,
                        variant=str(sim_variant),
                        device=str(sim_device),
                        channel=str(sim_channel),
                        session_seconds=int(sim_session_seconds),
                        clicked=int(sim_clicked),
                        cost_pre=float(avg_cost_per_session),
                    )
                )
            except Exception:
                sim_conversion_rate = float(baseline_conv_rate)
        else:
            sim_conversion_rate = float(baseline_conv_rate)

        sim_conversion_rate = max(0.0, min(sim_conversion_rate, 1.0))

        cost_floor = 0.01
        avg_cost_per_session_sane = max(float(avg_cost_per_session), cost_floor)

        rev_per_conv_used = revenue_per_conversion_for_selection(
            daily_df=daily_f,
            selected_variant=str(sim_variant),
            selected_channel=str(sim_channel),
            smoothing_k=10.0,
        )

        if rev_per_conv_used <= 0:
            rev_per_conv_used = float(total_revenue) / (float(total_conversions) + 10.0) if total_revenue > 0 else 0.0

        expected_conversions = float(monthly_sessions) * sim_conversion_rate
        expected_revenue = expected_conversions * float(rev_per_conv_used)
        expected_cost = float(monthly_sessions) * float(avg_cost_per_session_sane)
        expected_profit = expected_revenue - expected_cost
        expected_roi = safe_ratio(expected_profit, expected_cost)

        st.subheader("Forecast results")

        f1, f2 = st.columns(2)
        f1.metric("Expected conversions", f"{expected_conversions:,.0f}")
        f2.metric("Expected conversion rate", f"{sim_conversion_rate:.2%}")

        f3, f4 = st.columns(2)
        f3.metric("Expected revenue", format_money(expected_revenue))
        f4.metric("Expected cost", format_money(expected_cost))

        f5, f6 = st.columns(2)
        f5.metric("Expected profit", format_money(expected_profit))
        f6.metric("Expected ROI (Profit / Cost)", f"{expected_roi:.3f}")

        st.subheader("Quick read")

        if expected_profit <= 0 or expected_roi <= 0:
            st.error("Unprofitable forecast. Fix conversion rate or reduce cost before scaling.")
        elif expected_roi < 0.10:
            st.warning("Low ROI forecast. Improve performance before scaling.")
        elif baseline_roi > 0 and expected_roi < baseline_roi:
            st.warning("ROI is positive but below your recent filtered ROI. Consider improving before scaling.")
        else:
            st.success("Healthy ROI forecast relative to recent performance. Candidate to scale while monitoring daily.")

        st.caption(
            "Note: ROI is not affected by monthly sessions alone, because revenue and cost scale together. "
            "Monthly sessions changes profit size, not the ROI ratio."
        )
        st.caption(
            "Revenue-per-conversion is smoothed and (where possible) estimated for the selected variant and channel "
            "to avoid unrealistic forecasts when conversions are very low."
        )

        st.session_state["sim_export_payload"] = {
            "inputs": (
                f"Variant: {sim_variant}, Channel: {sim_channel} | Monthly sessions: {int(monthly_sessions):,} | "
                f"Avg cost/session: {float(avg_cost_per_session_sane):.2f}"
            ),
            "used_rate": f"Conversion rate used: {sim_conversion_rate:.2%}",
            "expected_conversions": f"Expected conversions: {expected_conversions:,.0f}",
            "expected_revenue": f"Expected revenue: {format_money(expected_revenue)}",
            "expected_cost": f"Expected cost: {format_money(expected_cost)}",
            "expected_profit": f"Expected profit: {format_money(expected_profit)}",
            "expected_roi": f"Expected ROI: {expected_roi:.3f}",
        }


if __name__ == "__main__":
    main()