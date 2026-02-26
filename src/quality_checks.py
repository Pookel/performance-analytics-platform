# -*- coding: utf-8 -*-
"""
quality_checks.py
Lightweight data quality checks to confirm:
- Tables are populated
- Core constraints hold (variants, non-negative values)
- Finance-aware rules hold (cost/profit/roi consistency)
"""

import sqlite3
from src.config import DB_PATH


def assert_true(condition: bool, msg: str) -> None:
    """Raise a clear error if a data rule fails."""
    if not condition:
        raise AssertionError(msg)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # Table not empty checks
        cur.execute("SELECT COUNT(*) FROM raw_visits;")
        assert_true(cur.fetchone()[0] > 0, "raw_visits is empty")

        cur.execute("SELECT COUNT(*) FROM fact_sessions;")
        assert_true(cur.fetchone()[0] > 0, "fact_sessions is empty")

        cur.execute("SELECT COUNT(*) FROM mart_daily_kpis;")
        assert_true(cur.fetchone()[0] > 0, "mart_daily_kpis is empty")

        # Valid domain checks
        cur.execute("SELECT COUNT(*) FROM fact_sessions WHERE variant NOT IN ('A','B');")
        assert_true(cur.fetchone()[0] == 0, "Invalid variants found")

        cur.execute("SELECT COUNT(*) FROM fact_sessions WHERE session_seconds < 0;")
        assert_true(cur.fetchone()[0] == 0, "Negative session_seconds found")

        # Non-negative money checks
        cur.execute("SELECT COUNT(*) FROM fact_sessions WHERE revenue < 0;")
        assert_true(cur.fetchone()[0] == 0, "Negative revenue found")

        cur.execute("SELECT COUNT(*) FROM fact_sessions WHERE cost < 0;")
        assert_true(cur.fetchone()[0] == 0, "Negative cost found")

        # Business logic consistency checks
        cur.execute("SELECT COUNT(*) FROM fact_sessions WHERE converted = 0 AND revenue > 0;")
        assert_true(cur.fetchone()[0] == 0, "Revenue > 0 when converted = 0")

        # Profit should equal revenue - cost (allow tiny rounding differences)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM fact_sessions
            WHERE ABS(profit - (revenue - cost)) > 0.02;
            """
        )
        assert_true(cur.fetchone()[0] == 0, "Profit mismatch (profit != revenue - cost)")

        # ROI should equal profit / cost when cost > 0 (allow small rounding differences)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM fact_sessions
            WHERE cost > 0 AND ABS(roi - (profit / cost)) > 0.0001;
            """
        )
        assert_true(cur.fetchone()[0] == 0, "ROI mismatch (roi != profit / cost)")

        print("All data quality checks passed")

    finally:
        conn.close()


if __name__ == "__main__":
    main()