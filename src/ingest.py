# -*- coding: utf-8 -*-
"""
ingest.py
Creates a synthetic A/B dataset and saves it under data/raw.

Updated version:
- Stronger, more realistic signal for click and conversion
- Wider spread in conversion probabilities
- Better separation between high-intent and low-intent sessions
- Designed so ML outputs and simulator results change more noticeably
"""

import csv
import random
from datetime import datetime, timedelta

from src.config import RAW_CSV


def clamp(value: float, low: float, high: float) -> float:
    """Keep a probability inside a valid range."""
    return max(low, min(value, high))


def main(rows: int = 6000, seed: int = 42) -> None:
    random.seed(seed)

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

            device = random.choices(
                devices,
                weights=[0.60, 0.32, 0.08]
            )[0]

            channel = random.choices(
                channels,
                weights=[0.38, 0.24, 0.16, 0.14, 0.08]
            )[0]

            country = random.choices(
                countries,
                weights=[0.35, 0.18, 0.16, 0.11, 0.10, 0.10]
            )[0]

            # Session length
            # Paid + email traffic tends to be more intentional than social
            base_session = random.randint(20, 700)

            if channel == "email":
                base_session += random.randint(40, 140)
            elif channel == "paid_search":
                base_session += random.randint(20, 100)
            elif channel == "social":
                base_session -= random.randint(0, 40)

            if device == "desktop":
                base_session += random.randint(30, 120)
            elif device == "tablet":
                base_session += random.randint(10, 50)

            session_seconds = max(10, min(base_session, 1200))

            # -----------------------------
            # Click probability
            # -----------------------------
            click_p = 0.05

            # Channel effect
            if channel == "email":
                click_p += 0.10
            elif channel == "paid_search":
                click_p += 0.07
            elif channel == "organic":
                click_p += 0.03
            elif channel == "referral":
                click_p += 0.02
            elif channel == "social":
                click_p += 0.00

            # Device effect
            if device == "desktop":
                click_p += 0.03
            elif device == "tablet":
                click_p += 0.01

            # Variant effect
            if variant == "B":
                click_p += 0.03

            # Engagement proxy
            if session_seconds > 120:
                click_p += 0.02
            if session_seconds > 300:
                click_p += 0.03
            if session_seconds > 600:
                click_p += 0.03

            click_p = clamp(click_p, 0.01, 0.45)
            clicked = 1 if random.random() < click_p else 0

            # -----------------------------
            # Conversion probability
            # -----------------------------
            conv_p = 0.005

            # Strongest signal: click intent
            if clicked:
                conv_p += 0.10

            # Channel intent
            if channel == "email":
                conv_p += 0.05
            elif channel == "paid_search":
                conv_p += 0.03
            elif channel == "organic":
                conv_p += 0.02
            elif channel == "referral":
                conv_p += 0.015
            elif channel == "social":
                conv_p += 0.005

            # Device effect
            if device == "desktop":
                conv_p += 0.02
            elif device == "tablet":
                conv_p += 0.01

            # Engagement effect
            if session_seconds > 120:
                conv_p += 0.015
            if session_seconds > 300:
                conv_p += 0.02
            if session_seconds > 600:
                conv_p += 0.02

            # Experiment uplift
            if variant == "B":
                conv_p += 0.025

            conv_p = clamp(conv_p, 0.001, 0.30)
            converted = 1 if random.random() < conv_p else 0

            # -----------------------------
            # Revenue
            # -----------------------------
            revenue = 0.0
            if converted:
                revenue = random.uniform(20, 180)

                if channel == "email":
                    revenue *= 1.10
                elif channel == "paid_search":
                    revenue *= 1.05

                if device == "desktop":
                    revenue *= 1.08

                if variant == "B":
                    revenue *= 1.08

                revenue = round(revenue, 2)

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