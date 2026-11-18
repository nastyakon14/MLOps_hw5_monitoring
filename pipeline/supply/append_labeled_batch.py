"""Дозапись подготовленного месячного батча в размеченную витрину."""

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from pipeline.db import copy_labeled_frame, get_conn, month_end_exclusive

logger = logging.getLogger(__name__)


def append_labeled_batch(batch_info: dict) -> dict:
    """Дописывает parquet батча в конец labeled_transactions.

    Читает путь и месяц из batch_info. Существующие строки не обновляет и не удаляет.
    Если в этом календарном месяце строки уже есть, повторная вставка пропускается:
    ретрай задачи не дублирует батч и не сдвигает горизонт витрины второй раз.
    Возвращает путь, месяц и число строк месяца в витрине.
    """
    batch_path = Path(batch_info["batch_path"])
    if not batch_path.exists():
        raise FileNotFoundError(f"Нет файла батча для загрузки: {batch_path}")

    frame = pd.read_parquet(batch_path)
    batch_month = date.fromisoformat(batch_info["batch_month"])
    month_end = month_end_exclusive(batch_month)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM labeled_transactions
                WHERE transaction_time >= %s
                  AND transaction_time < %s
                """,
                (batch_month, month_end),
            )
            already = int(cur.fetchone()[0])
        if already:
            logger.info(
                "Месяц %s уже есть в витрине, строк %s. Повторная вставка пропущена.",
                batch_info["batch_month"],
                already,
            )
            return {
                "batch_path": batch_info["batch_path"],
                "batch_month": batch_info["batch_month"],
                "rows": already,
            }
        copy_labeled_frame(conn, frame)
    finally:
        conn.close()
    logger.info(
        "Месяц %s добавлен в витрину, строк: %s",
        batch_info["batch_month"],
        len(frame),
    )
    return {
        "batch_path": batch_info["batch_path"],
        "batch_month": batch_info["batch_month"],
        "rows": int(len(frame)),
    }
