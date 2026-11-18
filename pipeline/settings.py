"""Общие пути артефактов обучения, поставки батчей и отчётов качества."""

import os
import sys
from pathlib import Path

TRAINING_DIR = Path(os.getenv("TRAINING_DATA_DIR", "/opt/airflow/training_data"))
MODELS_DIR = Path(os.getenv("MODELS_DIR", "/opt/airflow/artifacts/models"))
DQ_REPORTS_DIR = Path(os.getenv("DQ_REPORTS_DIR", "/opt/airflow/artifacts/dq_reports"))
FRAUD_SRC = os.getenv("FRAUD_SRC", "/opt/airflow/fraud_src")

CURRENT_DATASET = TRAINING_DIR / "current.parquet"
PENDING_WINDOW = TRAINING_DIR / "pending_window.parquet"
BATCHES_DIR = TRAINING_DIR / "batches"
SPLITS_DIR = TRAINING_DIR / "splits"
SUPPLY_BATCH = TRAINING_DIR / "supply_batch.parquet"
DQ_SNAPSHOT = TRAINING_DIR / "dq_snapshot.parquet"

WINDOW_MONTHS = 3
SAMPLE_SIZE = 100_000
HISTORY_YEARS = 3


def ensure_fraud_src() -> None:
    if FRAUD_SRC not in sys.path:
        sys.path.insert(0, FRAUD_SRC)
