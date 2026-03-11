# -*- coding: utf-8 -*-
"""
ml_conversion.py (FIXED)
- No manual upsampling (keeps probabilities realistic)
- Uses class_weight for imbalance handling
- Calibrates predicted probabilities (recommended for dashboard probability outputs)
"""

import sqlite3
from pathlib import Path

import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, classification_report


# -----------------------------
# Load data
# -----------------------------
def load_fact_sessions(db_path: Path) -> pd.DataFrame:
    query = """
    SELECT
      variant,
      device,
      channel,
      session_seconds,
      clicked,
      cost_pre,
      converted
    FROM fact_sessions;
    """
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


# -----------------------------
# Prepare features
# -----------------------------
def prepare_xy(df: pd.DataFrame):
    df = df.copy()

    for col in ["variant", "device", "channel"]:
        df[col] = df[col].astype("string").fillna("missing")

    df["session_seconds"] = pd.to_numeric(df["session_seconds"], errors="coerce").fillna(0)
    df["clicked"] = pd.to_numeric(df["clicked"], errors="coerce").fillna(0)
    df["cost_pre"] = pd.to_numeric(df["cost_pre"], errors="coerce").fillna(0.0)

    y = pd.to_numeric(df["converted"], errors="coerce").fillna(0).astype(int)

    X = df[["variant", "device", "channel", "session_seconds", "clicked", "cost_pre"]]
    return X, y


# -----------------------------
# Model pipeline
# -----------------------------
def build_pipeline() -> Pipeline:
    categorical = ["variant", "device", "channel"]
    numeric = ["session_seconds", "clicked", "cost_pre"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("num", "passthrough", numeric),
        ]
    )

    # Key change: class_weight handles imbalance without destroying probability calibration
    clf = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        max_depth=10,
        min_samples_leaf=20,
        class_weight="balanced_subsample",
    )

    return Pipeline(steps=[("prep", preprocessor), ("clf", clf)])


# -----------------------------
# Train + save
# -----------------------------
def train_and_save(db_path: Path, model_path: Path):
    df = load_fact_sessions(db_path)
    X, y = prepare_xy(df)

    # Stratify keeps class proportions stable in train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y if y.nunique() > 1 else None
    )

    base_pipe = build_pipeline()
    base_pipe.fit(X_train, y_train)

    # Calibrate probabilities for better "conversion probability" behavior
    # Uses the already-fitted pipeline as the base estimator.
    calibrated = CalibratedClassifierCV(base_pipe, method="isotonic", cv=3)
    calibrated.fit(X_train, y_train)

    y_pred = calibrated.predict(X_test)
    y_proba = calibrated.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)) if y.nunique() > 1 else 0.0,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "base_rate": float(y.mean()),
    }

    report = classification_report(y_test, y_pred, zero_division=0)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrated, model_path)

    return metrics, report


# -----------------------------
# Load model
# -----------------------------
def load_model(model_path: Path):
    return joblib.load(model_path)


# -----------------------------
# Predict
# -----------------------------
def predict_proba(
    model,
    variant: str,
    device: str,
    channel: str,
    session_seconds: int,
    clicked: int,
    cost_pre: float
) -> float:

    X_new = pd.DataFrame([{
        "variant": variant,
        "device": device,
        "channel": channel,
        "session_seconds": session_seconds,
        "clicked": clicked,
        "cost_pre": cost_pre,
    }])

    return float(model.predict_proba(X_new)[0, 1])