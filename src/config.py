# -*- coding: utf-8 -*-
"""
Created on Sun Feb 5 20:52:49 2026

@author: Melecia
"""

from pathlib import Path

# Project root is the parent folder of "src"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"

SQL_DIR = PROJECT_ROOT / "sql"

DB_PATH = PROCESSED_DIR / "analytics.db"
RAW_CSV = RAW_DIR / "ab_events.csv"

SCHEMA_SQL = SQL_DIR / "schema.sql"
VIEWS_SQL = SQL_DIR / "views.sql"