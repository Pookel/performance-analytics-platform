# -*- coding: utf-8 -*-
"""
main.py
Runs the full pipeline end-to-end.
Uses sys.executable so it runs correctly in venvs and on other machines.
"""

import sys
import subprocess

STEPS = [
    [sys.executable, "-m", "src.ingest"],
    [sys.executable, "-m", "src.load"],
    [sys.executable, "-m", "src.transform"],
    [sys.executable, "-m", "src.quality_checks"],
    [sys.executable, "-m", "src.analytics"],
]


def run_step(cmd: list[str]) -> None:
    print(f"\nRunning: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    for cmd in STEPS:
        run_step(cmd)
    print("\nPipeline complete. Check data/outputs/")


if __name__ == "__main__":
    main()