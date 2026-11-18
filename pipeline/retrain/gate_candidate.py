"""Сравнение кандидата с моделью, которая сейчас указана в latest.txt."""

import logging
import os

import pandas as pd

from pipeline.settings import MODELS_DIR, ensure_fraud_src

logger = logging.getLogger(__name__)


def _score_production(test_raw_path: str) -> tuple[float | None, str | None]:
    latest = MODELS_DIR / "latest.txt"
    if not latest.exists():
        return None, None
    version = latest.read_text(encoding="utf-8").strip()
    if not version:
        return None, None
    model_path = MODELS_DIR / f"my_catboost_{version}.cbm"
    preproc_path = MODELS_DIR / f"my_catboost_{version}.preproc.json"
    if not model_path.exists() or not preproc_path.exists():
        return None, version

    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    from catboost import CatBoostClassifier

    from modeling import classification_metrics
    from preprocessing import load_state, split_xy, transform

    raw = pd.read_parquet(test_raw_path)
    state = load_state(preproc_path)
    transformed = transform(raw, state, keep_target=True)
    features, target = split_xy(transformed, state)
    model = CatBoostClassifier()
    model.load_model(str(model_path))
    ordered = features.loc[:, list(model.feature_names_)].copy()
    for idx in model.get_cat_feature_indices():
        column = model.feature_names_[idx]
        ordered[column] = ordered[column].astype(str)
    proba = model.predict_proba(ordered)[:, 1]
    metrics = classification_metrics(target, proba)
    return metrics["roc_auc"], version


def gate_candidate(train_info: dict) -> dict:
    """Решает, можно ли отдавать кандидата в прод.

    Читает сырой test-месяц и текущие my_catboost_<latest> вместе с его
    preproc.json. Обе модели оцениваются на одних и тех же сырых строках:
    кандидат — метрикой из обучения, прод — своим сохранённым препроцессингом.
    В каталог моделей и в training_state ничего не пишет.
    Повтор только заново сравнивает файлы и не сдвигает окно.
    Кандидат публикуется, если его ROC-AUC не строго ниже продового.
    Если продовой модели ещё нет или посчитать её ROC-AUC нельзя, кандидат проходит.
    """
    ensure_fraud_src()
    candidate_auc = train_info.get("roc_auc")
    if candidate_auc is not None:
        candidate_auc = float(candidate_auc)

    baseline_auc = None
    baseline_version = None
    try:
        baseline_auc, baseline_version = _score_production(train_info["test_raw_path"])
    except Exception:
        logger.exception("Не удалось посчитать ROC-AUC продовой модели, кандидат будет опубликован.")
        baseline_auc = None

    if baseline_auc is None:
        promote = candidate_auc is not None
        if promote:
            reason = "Продовой ROC-AUC нет, кандидат публикуется."
        else:
            reason = "ROC-AUC кандидата не определён, публикация остановлена."
    elif candidate_auc is None:
        promote = False
        reason = "ROC-AUC кандидата не определён, продовая модель остаётся."
    elif candidate_auc < baseline_auc:
        promote = False
        reason = (
            f"ROC-AUC кандидата {candidate_auc:.4f} ниже продовой "
            f"{baseline_version} ({baseline_auc:.4f})."
        )
    else:
        promote = True
        reason = (
            f"ROC-AUC кандидата {candidate_auc:.4f} не ниже продовой "
            f"{baseline_version} ({baseline_auc:.4f})."
        )

    logger.info("Решение о раскатке: promote=%s. %s", promote, reason)
    decision = dict(train_info)
    decision["roc_auc"] = candidate_auc
    decision["promote"] = promote
    decision["baseline_roc_auc"] = baseline_auc
    decision["baseline_version"] = baseline_version
    decision["reason"] = reason
    return decision
