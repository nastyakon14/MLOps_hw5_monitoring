"""Сдвиг трёхмесячного окна обучения на один месяц вперёд."""

import logging
from datetime import date

import pandas as pd

from pipeline.settings import CURRENT_DATASET, PENDING_WINDOW, WINDOW_MONTHS

logger = logging.getLogger(__name__)


def slide_training_window(batch_info: dict) -> dict:
    """Добавляет новый месяц к текущему окну и выбрасывает самый старый.

    Читает current.parquet и parquet батча из batch_info. Новое окно пишет
    в pending_window.parquet и не заменяет current.parquet: замена происходит
    только после сохранения модели. Если месяц батча уже лежит в current.parquet,
    повторный запуск не выбрасывает ещё один старый месяц.
    Возвращает путь к новому окну и месяц добавленного батча.
    """
    if not CURRENT_DATASET.exists():
        raise FileNotFoundError(f"Нет исходного датасета {CURRENT_DATASET}")

    batch_month = date.fromisoformat(batch_info["batch_month"])
    current = pd.read_parquet(CURRENT_DATASET)
    batch = pd.read_parquet(batch_info["batch_path"])
    current["transaction_time"] = pd.to_datetime(current["transaction_time"])
    batch["transaction_time"] = pd.to_datetime(batch["transaction_time"])
    batch_period = pd.Timestamp(batch_month).to_period("M")
    current_periods = current["transaction_time"].dt.to_period("M")

    if (current_periods == batch_period).any():
        updated = current.sort_values("transaction_time")
        logger.info(
            "Месяц %s уже входит в current.parquet, окно повторно не сдвигается.",
            batch_period,
        )
    else:
        combined = pd.concat([current, batch], ignore_index=True)
        periods = combined["transaction_time"].dt.to_period("M")
        oldest = periods.min()
        updated = combined.loc[periods != oldest].sort_values("transaction_time")
        logger.info(
            "Окно после сдвига: %s строк, %s — %s. Удалён месяц %s.",
            len(updated),
            updated["transaction_time"].min(),
            updated["transaction_time"].max(),
            oldest,
        )

    month_count = updated["transaction_time"].dt.to_period("M").nunique()
    if month_count != WINDOW_MONTHS:
        raise RuntimeError(
            f"После сдвига в окне {month_count} месяцев, ожидалось {WINDOW_MONTHS}."
        )
    updated.to_parquet(PENDING_WINDOW, index=False)
    return {
        "dataset_path": str(PENDING_WINDOW),
        "batch_month": batch_month.isoformat(),
    }
