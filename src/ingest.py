# -*- coding: utf-8 -*-
"""
Created on Sun Feb 5 21:32:06 2026

@author: Melecia
"""
# -*- coding: utf-8 -*-
"""
ingest.py
Creates a synthetic A/B dataset and saves it under data/raw.
Removed hard-coded paths.
"""

import csv
import random
from datetime import datetime, timedelta

from src.config import RAW_CSV


def main(rows: int = 6000, seed: int = 42) -> None:
    # Seed makes the data reproducible (same dataset each run)
    random.seed(seed)

    # Ensure raw folder exists
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)

    start = datetime(2025, 12, 1)
    devices = ["mobile", "desktop", "tablet"]
    channels = ["organic", "paid_search", "email", "social", "referral"]
    countries = ["ZA", "GB", "DE", "FR", "NL", "ES"]

    with RAW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "user_id",
                "variant",
                "visit_date",
                "device",
                "channel",
                "country",
                "session_seconds",
                "clicked",
                "converted",
                "revenue",
            ]
        )

        for i in range(1, rows + 1):
            user_id = f"U{i:06d}"
            variant = "A" if random.random() < 0.5 else "B"

            dt = start + timedelta(days=random.randint(0, 60))
            visit_date = dt.strftime("%Y-%m-%d")

            device = random.choices(devices, weights=[0.65, 0.30, 0.05])[0]
            channel = random.choices(channels, weights=[0.40, 0.25, 0.15, 0.12, 0.08])[0]
            country = random.choices(countries, weights=[0.35, 0.20, 0.15, 0.10, 0.10, 0.10])[0]

            # Engagement proxy
            base_session = random.randint(20, 900)
            session_seconds = base_session + (30 if device == "desktop" else 0)

            # Click probability influenced by channel and variant
            click_p = 0.08
            if channel == "email":
                click_p += 0.05
            if channel == "paid_search":
                click_p += 0.03
            if variant == "B":
                click_p += 0.01
            clicked = 1 if random.random() < click_p else 0

            # Conversion probability depends on click, engagement, and variant
            conv_p = 0.01
            if clicked:
                conv_p += 0.05
            if session_seconds > 240:
                conv_p += 0.01
            if variant == "B":
                conv_p += 0.006
            converted = 1 if random.random() < conv_p else 0

            revenue = 0.0
            if converted:
                # Slight uplift on B to make experiment interesting
                revenue = round(random.uniform(10, 220) * (1.03 if variant == "B" else 1.0), 2)

            writer.writerow(
                [
                    user_id,
                    variant,
                    visit_date,
                    device,
                    channel,
                    country,
                    session_seconds,
                    clicked,
                    converted,
                    revenue,
                ]
            )

    print(f"Created: {RAW_CSV} with {rows} rows")


if __name__ == "__main__":
    main()