"""Препроцессинг train и test состоянием, обученным только на train."""

import logging

import pandas as pd

from pipeline.settings import SPLITS_DIR, ensure_fraud_src

logger = logging.getLogger(__name__)


def preprocess_dataset(split_info: dict) -> dict:
    """Строит признаки отдельно для train и для свежего месяца.

    Медианы и списки частых категорий считаются по сырому train и сохраняются
    в splits/preproc_state.json. Тот же файл потом копируется рядом с моделью.
    Test этим состоянием только преобразуется, статистики по нему не пересчитываются.
    Повтор задачи перезаписывает parquet и json состояния, витрину и каталог моделей не трогает.
    """
    ensure_fraud_src()
    from preprocessing import fit_state, save_state, transform

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    train_raw = pd.read_parquet(split_info["train_raw_path"])
    test_raw = pd.read_parquet(split_info["test_raw_path"])
    state = fit_state(train_raw)
    train = transform(train_raw, state)
    test = transform(test_raw, state)
    state_path = SPLITS_DIR / "preproc_state.json"
    train_path = SPLITS_DIR / "train_proc.parquet"
    test_path = SPLITS_DIR / "test_proc.parquet"
    save_state(state, state_path)
    train.to_parquet(train_path, index=False)
    test.to_parquet(test_path, index=False)
    logger.info("После препроцессинга: train %s, test %s", train.shape, test.shape)
    return {
        "train_proc_path": str(train_path),
        "test_proc_path": str(test_path),
        "test_raw_path": split_info["test_raw_path"],
        "preproc_state": str(state_path),
        "dataset_path": split_info["dataset_path"],
        "batch_month": split_info["batch_month"],
        "train_months": split_info["train_months"],
        "test_month": split_info["test_month"],
    }
