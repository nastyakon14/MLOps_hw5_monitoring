import logging
import os
import threading
import time
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier

from preprocessing import load_state, transform


logger = logging.getLogger(__name__)

THRESHOLD = 0.5
MODELS_DIR = Path(os.getenv("MODELS_DIR", "/artifacts/models"))

_lock = threading.Lock()
_model = None
_version = None
_state = None


def _model_path(version: str) -> Path:
    return MODELS_DIR / f"my_catboost_{version}.cbm"


def _preproc_path(version: str) -> Path:
    return MODELS_DIR / f"my_catboost_{version}.preproc.json"


def ensure_model_ready(attempts: int = 30, pause_seconds: float = 2.0) -> str:
    """Ждёт, пока data_loader или DAG положит модель и состояние препроцессинга."""
    latest = MODELS_DIR / "latest.txt"
    for attempt in range(1, attempts + 1):
        if latest.exists():
            version = latest.read_text(encoding="utf-8").strip()
            if version and _model_path(version).exists() and _preproc_path(version).exists():
                logger.info("Каталог моделей готов, версия %s", version)
                return version
        logger.info("Ждём модель в %s (%s/%s)", MODELS_DIR, attempt, attempts)
        time.sleep(pause_seconds)
    raise FileNotFoundError(f"В {MODELS_DIR} нет пары latest.txt, cbm и preproc.json")


def _read_latest_version() -> str:
    latest = MODELS_DIR / "latest.txt"
    if not latest.exists():
        raise RuntimeError(f"Нет указателя модели: {latest}")
    version = latest.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError(f"Пустой указатель модели: {latest}")
    return version


def _load_model(version: str) -> CatBoostClassifier:
    path = _model_path(version)
    if not path.exists():
        raise FileNotFoundError(f"Файл модели {version} не найден: {path}")
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    model = CatBoostClassifier()
    model.load_model(str(path))
    logger.info("Загружена модель версии %s из %s", version, path)
    return model


def _current_model():
    """Возвращает модель и препроцессинг версии из latest.txt. Вызывать под _lock."""
    global _model, _version, _state
    version = _read_latest_version()
    if _model is None or version != _version:
        preproc_path = _preproc_path(version)
        if not preproc_path.exists():
            raise FileNotFoundError(f"Нет состояния препроцессинга для {version}: {preproc_path}")
        _model = _load_model(version)
        _state = load_state(preproc_path)
        _version = version
    return _model, _version, _state


def make_pred(raw_df, source_info="kafka"):
    with _lock:
        model, model_version, state = _current_model()
        transformed = transform(raw_df, state, keep_target=False)
        features = list(model.feature_names_)
        missing = [column for column in features if column not in transformed.columns]
        if missing:
            raise ValueError(f"Во входных данных нет признаков модели: {missing}")
        frame = transformed[features].copy()
        for idx in model.get_cat_feature_indices():
            column = features[idx]
            frame[column] = frame[column].astype(str)
        y_proba = model.predict_proba(frame)[:, 1]

    submission = pd.DataFrame({
        "score": y_proba,
        "fraud_flag": (y_proba > THRESHOLD).astype(int),
    })
    logger.info("Prediction complete for data from %s, model_version=%s", source_info, model_version)
    return submission, y_proba, model_version
