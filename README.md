# -*- coding: utf-8 -*-
"""
Created on Sun Feb 5 21:19:48 2026

@author: Melecia
"""

# Marketing Data Pipeline + Experiment Insights (Python + SQL + SQLite)

## Overview
A small marketing analytics data stack that demonstrates:
- Ingestion (raw CSV)
- Loading into SQLite
- Transformations into modeled dim/fact tables
- KPI mart for self-service reporting
- Data quality checks
- A/B test analysis on conversion
- CSV outputs plus charts

## Tech
Python, Pandas, SQLite, SQL, Matplotlib

## Repo layout
- data/raw: raw CSV
- data/processed: SQLite database
- data/outputs: reports and charts
- src: pipeline scripts
- sql: schema and BI-friendly views

## Run
Run files in this order:
1) python src/ingest.py
2) python src/load.py
3) python src/transform.py
4) python src/quality_checks.py
5) python src/analytics.py

Or run everything:
python -m src.main

## Outputs
- data/processed/marketing.db
- data/outputs/variant_kpis.csv
- data/outputs/ab_test_summary.csv
- data/outputs/daily_kpis.csv
- data/outputs/channel_kpis.csv
- data/outputs/charts/daily_conversion_rate_variant_A.png
- data/outputs/charts/daily_conversion_rate_variant_B.png
- data/outputs/charts/revenue_by_channel.png
- data/outputs/charts/conversion_rate_by_channel.png

## Tables
- raw_visits
- dim_user
- fact_sessions
- mart_daily_kpis

## Views (BI-ready)
- vw_daily_kpis
- vw_variant_kpis
- vw_channel_kpis
- vw_country_kpis

## CV bullets (Projects)
**Marketing Data Pipeline & Experimentation (Python, SQL, SQLite)**
- Built an end-to-end ETL pipeline (raw CSV to modeled tables to KPI mart) enabling self-service conversion and revenue reporting
- Performed A/B conversion analysis using statistical testing and automated report exports and charts for decision-making