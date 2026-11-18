"""Снимок текущего окна обучения для проверки качества."""

import logging

import pandas as pd

from pipeline.settings import CURRENT_DATASET, DQ_SNAPSHOT, TRAINING_DIR

logger = logging.getLogger(__name__)


def load_training_dataset() -> dict:
    """Копирует current.parquet в отдельный снимок и не меняет витрину.

    Читает файл окна, который собрал data_loader или обновила публикация модели.
    Пишет training_data/dq_snapshot.parquet. Повтор перезаписывает снимок
    и не удаляет строки исходного окна и labeled_transactions.
    Возвращает путь к снимку и число строк.
    """
    if not CURRENT_DATASET.exists():
        raise FileNotFoundError(f"Нет окна обучения: {CURRENT_DATASET}")
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(CURRENT_DATASET)
    frame.to_parquet(DQ_SNAPSHOT, index=False)
    logger.info("Снимок качества: %s строк, файл %s", len(frame), DQ_SNAPSHOT)
    return {"snapshot_path": str(DQ_SNAPSHOT), "rows": int(len(frame))}
