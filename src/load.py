# -*- coding: utf-8 -*-
"""
Created on Sun Feb 5 21:33:06 2026

@author: Melecia
load.py
Initialises SQLite tables and loads the raw CSV into raw_visits.
Applies views after schema load.
"""

import sqlite3
import pandas as pd

from src.config import DB_PATH, RAW_CSV, SCHEMA_SQL, VIEWS_SQL


def init_db(conn: sqlite3.Connection) -> None:
    # Recreate schema each run for clean, repeatable demos
    with SCHEMA_SQL.open("r", encoding="utf-8") as f:
        conn.executescript(f.read())


def apply_views(conn: sqlite3.Connection) -> None:
    if VIEWS_SQL.exists():
        with VIEWS_SQL.open("r", encoding="utf-8") as f:
            conn.executescript(f.read())


def load_raw(conn: sqlite3.Connection) -> None:
    df = pd.read_csv(RAW_CSV)

    # Defensive typing to avoid SQLite surprises
    df["visit_date"] = df["visit_date"].astype(str)
    df["session_seconds"] = df["session_seconds"].fillna(0).astype(int)
    df["clicked"] = df["clicked"].fillna(0).astype(int)
    df["converted"] = df["converted"].fillna(0).astype(int)
    df["revenue"] = df["revenue"].fillna(0.0).astype(float)

    df.to_sql("raw_visits", conn, if_exists="append", index=False)


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        # Disable FK checks for schema reset + bulk load
        conn.execute("PRAGMA foreign_keys = OFF;")

        init_db(conn)      # drops/creates tables
        load_raw(conn)     # loads raw_visits
        apply_views(conn)

        conn.commit()
        print(f"Loaded raw data into {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()