"""
Train the churn proxy model using IBM Telco Customer Churn dataset.
Saves model bundle to backend/models/churn_model.pkl

Usage:
    cd backend
    python -m scripts.train_churn
"""
from __future__ import annotations

import io
import logging
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODEL_DIR / "churn_model.pkl"
MODEL_VERSION = "v1.0"

DATASET_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)

FEATURE_NAMES = [
    "tenure_months",
    "monthly_charge",
    "contract_type",
    "payment_method",
    "count_failed_payments",
    "total_payments",
    "failure_rate",
]


def _download_dataset() -> pd.DataFrame:
    """Download the IBM Telco churn dataset."""
    try:
        import urllib.request
        logger.info("Downloading dataset from %s", DATASET_URL)
        with urllib.request.urlopen(DATASET_URL, timeout=30) as resp:
            content = resp.read()
        df = pd.read_csv(io.BytesIO(content))
        logger.info("Downloaded %d rows", len(df))
        return df
    except Exception as exc:
        logger.error("Failed to download dataset: %s", exc)
        raise


def _prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Map Telco dataset columns to our feature schema."""
    df = df.copy()

    # Target
    df["Churn"] = df["Churn"].map({"Yes": 1, "No": 0})
    df = df.dropna(subset=["Churn"])

    # TotalCharges may have spaces
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0)

    # tenure → tenure_months
    df["tenure_months"] = df["tenure"].astype(float)

    # MonthlyCharges → monthly_charge
    df["monthly_charge"] = df["MonthlyCharges"].astype(float)

    # Contract type: Month-to-month → 0, One year → 0.5, Two year → 1
    contract_map = {"Month-to-month": 0.0, "One year": 0.5, "Two year": 1.0}
    df["contract_type"] = df["Contract"].map(contract_map).fillna(0.0)

    # PaymentMethod encoding
    pm_map = {
        "Electronic check": 0.0,
        "Mailed check": 1.0,
        "Bank transfer (automatic)": 2.0,
        "Credit card (automatic)": 3.0,
    }
    df["payment_method"] = df["PaymentMethod"].map(pm_map).fillna(0.0)

    # Proxy failed payments from monthly vs total charges discrepancy
    df["total_payments"] = (df["TotalCharges"] / df["MonthlyCharges"].replace(0, 1)).round().astype(float)
    df["count_failed_payments"] = (df["tenure_months"] - df["total_payments"]).clip(lower=0)
    df["failure_rate"] = df["count_failed_payments"] / df["tenure_months"].replace(0, 1)

    X = df[FEATURE_NAMES].fillna(0.0)
    y = df["Churn"].astype(int)
    return X, y


def train(use_gbm: bool = False) -> None:
    """Train and save the churn model."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = _download_dataset()
    X, y = _prepare_features(df)

    logger.info("Feature matrix shape: %s, churn rate: %.2f%%", X.shape, y.mean() * 100)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    if use_gbm:
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", GradientBoostingClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42
            )),
        ])
        model_name = "GradientBoosting"
    else:
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=42)),
        ])
        model_name = "LogisticRegression"

    logger.info("Training %s...", model_name)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)

    logger.info("Test AUC: %.4f", auc)
    logger.info("\n%s", classification_report(y_test, y_pred))

    bundle = {
        "model": model,
        "feature_names": FEATURE_NAMES,
        "version": MODEL_VERSION,
        "model_type": model_name,
        "test_auc": auc,
    }

    joblib.dump(bundle, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":
    use_gbm = "--gbm" in sys.argv
    train(use_gbm=use_gbm)

