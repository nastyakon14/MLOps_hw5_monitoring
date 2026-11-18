"""Обучение CatBoost на новом окне."""

import logging
from datetime import datetime, timezone

import pandas as pd

from pipeline.settings import MODELS_DIR, ensure_fraud_src

logger = logging.getLogger(__name__)

RETRAIN_ITERATIONS = 150
RETRAIN_DEPTH = 6
RETRAIN_LEARNING_RATE = 0.1


def fit_catboost(preproc_info: dict) -> dict:
    """Обучает CatBoost на train и считает ROC-AUC и F1 на свежем месяце.

    Читает обработанные parquet и json состояния из preproc_info.
    Модель пишет во временный .cbm в каталоге моделей и не меняет latest.txt.
    Указатель месяца и current.parquet не обновляет: это делает публикация
    после записи файла. Повтор удаляет прошлые черновики .staging_*.cbm,
    пишет новый черновик и не меняет витрину.
    """
    ensure_fraud_src()
    from modeling import classification_metrics, fit_classifier
    from preprocessing import load_state, split_xy

    state = load_state(preproc_info["preproc_state"])
    train = pd.read_parquet(preproc_info["train_proc_path"])
    test = pd.read_parquet(preproc_info["test_proc_path"])
    x_train, y_train = split_xy(train, state)
    x_test, y_test = split_xy(test, state)
    model = fit_classifier(
        x_train,
        y_train,
        state["cat_features"],
        iterations=RETRAIN_ITERATIONS,
        depth=RETRAIN_DEPTH,
        learning_rate=RETRAIN_LEARNING_RATE,
    )
    proba = model.predict_proba(x_test)[:, 1]
    metrics = classification_metrics(y_test, proba)
    if metrics["roc_auc"] is None:
        logger.warning("В test одна метка, ROC-AUC не определён. F1=%.4f", metrics["f1"])
    else:
        logger.info(
            "Качество на test %s: ROC-AUC=%.4f, F1=%.4f",
            preproc_info["test_month"],
            metrics["roc_auc"],
            metrics["f1"],
        )

    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in MODELS_DIR.glob(".staging_*.cbm"):
        stale.unlink()
    staging_model = MODELS_DIR / f".staging_{version}.cbm"
    model.save_model(str(staging_model))
    logger.info("Черновик модели сохранён: %s", staging_model)
    return {
        "version": version,
        "staging_model": str(staging_model),
        "preproc_state": preproc_info["preproc_state"],
        "test_raw_path": preproc_info["test_raw_path"],
        "dataset_path": preproc_info["dataset_path"],
        "batch_month": preproc_info["batch_month"],
        "train_months": preproc_info["train_months"],
        "test_month": preproc_info["test_month"],
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "roc_auc": metrics["roc_auc"],
        "f1": metrics["f1"],
    }
