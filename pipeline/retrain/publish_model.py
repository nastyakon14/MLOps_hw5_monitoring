"""Запись файла модели и фиксация окна после решения о раскатке."""

import json
import logging
import os
import shutil
from datetime import date
from pathlib import Path

from pipeline.db import advance_training_state, get_conn
from pipeline.settings import CURRENT_DATASET, MODELS_DIR

logger = logging.getLogger(__name__)


def _metrics_payload(train_info: dict, published: bool) -> dict:
    return {
        "version": train_info["version"],
        "published": published,
        "reason": train_info.get("reason"),
        "batch_month": train_info["batch_month"],
        "train_months": train_info["train_months"],
        "test_month": train_info["test_month"],
        "train_rows": train_info["train_rows"],
        "test_rows": train_info["test_rows"],
        "roc_auc": train_info["roc_auc"],
        "f1": train_info["f1"],
        "baseline_roc_auc": train_info.get("baseline_roc_auc"),
        "baseline_version": train_info.get("baseline_version"),
    }


def _place_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        os.replace(source, destination)
    elif not destination.exists():
        raise FileNotFoundError(f"Нет файла для записи: {source}")


def publish_model(train_info: dict) -> str:
    """Кладёт файл модели на диск и только потом двигает указатель месяца.

    Если gate_candidate разрешил раскатку, пишет my_catboost_<version>.cbm,
    рядом кладёт preproc.json и атомарно обновляет latest.txt.
    Если метрика хуже продовой, тот же файл уходит в models/rejected/,
    а latest.txt не меняется: скоринг остаётся на прежней версии.
    current.parquet и training_state обновляются только после записи файла.
    Повтор задачи не двигает окно второй раз: pending уже перенесён,
    а UPDATE training_state для того же месяца записывает те же даты.
    """
    if "promote" not in train_info:
        raise KeyError("Нет решения gate_candidate: поле promote отсутствует.")

    version = train_info["version"]
    promote = bool(train_info["promote"])
    staging_model = Path(train_info["staging_model"])
    preproc_src = Path(train_info["preproc_state"])
    if promote:
        directory = MODELS_DIR
    else:
        directory = MODELS_DIR / "rejected"
    directory.mkdir(parents=True, exist_ok=True)
    final_model = directory / f"my_catboost_{version}.cbm"
    final_preproc = directory / f"my_catboost_{version}.preproc.json"
    metrics_path = directory / f"my_catboost_{version}.metrics.json"

    _place_file(staging_model, final_model)
    if preproc_src.exists():
        shutil.copyfile(preproc_src, final_preproc)
    elif not final_preproc.exists():
        raise FileNotFoundError(f"Нет состояния препроцессинга: {preproc_src}")

    metrics_path.write_text(
        json.dumps(_metrics_payload(train_info, promote), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if promote:
        latest_tmp = MODELS_DIR / f".latest.{version}.txt"
        latest_tmp.write_text(version + "\n", encoding="utf-8")
        os.replace(latest_tmp, MODELS_DIR / "latest.txt")
        logger.info("Опубликована модель %s (%s)", version, final_model)
    else:
        logger.info("Модель %s не опубликована: %s", version, train_info.get("reason"))

    pending_window = Path(train_info["dataset_path"])
    if pending_window.exists():
        os.replace(pending_window, CURRENT_DATASET)
        logger.info("Окно обучения обновлено: %s", CURRENT_DATASET)
    elif not CURRENT_DATASET.exists():
        raise FileNotFoundError(f"Нет нового окна обучения: {pending_window}")
    else:
        logger.info("Окно уже перенесено в %s, повторно не сдвигаем.", CURRENT_DATASET)

    batch_month = date.fromisoformat(train_info["batch_month"])
    conn = get_conn()
    try:
        advance_training_state(conn, batch_month)
    finally:
        conn.close()
    if promote:
        return version
    return f"rejected:{version}"
