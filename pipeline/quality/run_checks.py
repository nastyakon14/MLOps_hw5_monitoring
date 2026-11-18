"""Правила качества сырого окна обучения."""

import logging

import numpy as np
import pandas as pd

from pipeline.settings import WINDOW_MONTHS

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["transaction_time", "amount", "target", "merch", "cat_id", "gender"]
DUPLICATE_KEYS = ["transaction_time", "merch", "amount", "name_1", "lat", "lon"]
FRAUD_RATE_MIN = 0.002
FRAUD_RATE_MAX = 0.02
MIN_ROWS = 1000
TIME_MIN = pd.Timestamp("2018-01-01")
TIME_MAX = pd.Timestamp("2030-01-01")


def _result(check_id: str, title: str, passed: bool, observed: str, expected: str) -> dict:
    return {
        "id": check_id,
        "title": title,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
    }


def _mask_all(mask: pd.Series) -> bool:
    if len(mask) == 0:
        return False
    return bool(mask.fillna(False).all())


def evaluate_checks(frame: pd.DataFrame) -> list[dict]:
    """Проверяет снимок окна и возвращает список правил с фактом и ожиданием."""
    checks = []

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    null_counts = {
        column: int(frame[column].isna().sum())
        for column in REQUIRED_COLUMNS
        if column in frame.columns
    }
    checks.append(
        _result(
            "required_fields",
            "Ключевые поля заполнены",
            not missing and all(count == 0 for count in null_counts.values()) and len(frame) > 0,
            f"нет колонок: {missing or '—'}; пропуски: {null_counts or '—'}",
            "Колонки transaction_time, amount, target, merch, cat_id, gender есть, пропусков в них нет.",
        )
    )

    if "target" in frame.columns:
        target = pd.to_numeric(frame["target"], errors="coerce")
        target_ok = target.notna() & target.isin([0, 1])
        foreign = sorted(set(target.dropna().unique().tolist()) - {0, 1})
        checks.append(
            _result(
                "target_domain",
                "Целевая переменная бинарная",
                _mask_all(target_ok),
                f"посторонние значения: {foreign or '—'}; пропусков: {int(target.isna().sum())}",
                "Каждое значение target равно 0 или 1.",
            )
        )
        rate = float(target.mean()) if target.notna().any() else float("nan")
        rate_ok = rate == rate and FRAUD_RATE_MIN <= rate <= FRAUD_RATE_MAX
        checks.append(
            _result(
                "fraud_rate",
                "Доля фрода в допустимом диапазоне",
                rate_ok,
                f"{rate:.4%}" if rate == rate else "не определена",
                "Доля target=1 от 0.2% до 2%.",
            )
        )
    else:
        checks.append(
            _result(
                "target_domain",
                "Целевая переменная бинарная",
                False,
                "колонки target нет",
                "Каждое значение target равно 0 или 1.",
            )
        )
        checks.append(
            _result(
                "fraud_rate",
                "Доля фрода в допустимом диапазоне",
                False,
                "колонки target нет",
                "Доля target=1 от 0.2% до 2%.",
            )
        )

    if "amount" in frame.columns:
        amount = pd.to_numeric(frame["amount"], errors="coerce")
        amount_ok = amount.notna() & np.isfinite(amount.to_numpy(dtype=float)) & (amount > 0)
        checks.append(
            _result(
                "amount_positive",
                "Сумма транзакции положительная",
                _mask_all(amount_ok),
                f"неположительных или пустых: {int((~amount_ok.fillna(False)).sum())} из {len(frame)}",
                "amount конечный и строго больше нуля в каждой строке.",
            )
        )
    else:
        checks.append(
            _result(
                "amount_positive",
                "Сумма транзакции положительная",
                False,
                "колонки amount нет",
                "amount конечный и строго больше нуля в каждой строке.",
            )
        )

    coord_columns = ["lat", "lon", "merchant_lat", "merchant_lon"]
    coord_missing = [column for column in coord_columns if column not in frame.columns]
    if coord_missing:
        checks.append(
            _result(
                "coordinates_range",
                "Координаты в географических пределах",
                False,
                f"нет колонок: {coord_missing}",
                "lat и merchant_lat в [-90, 90], lon и merchant_lon в [-180, 180], пропусков нет.",
            )
        )
    else:
        lat_ok = pd.to_numeric(frame["lat"], errors="coerce").between(-90, 90)
        lon_ok = pd.to_numeric(frame["lon"], errors="coerce").between(-180, 180)
        merchant_lat_ok = pd.to_numeric(frame["merchant_lat"], errors="coerce").between(-90, 90)
        merchant_lon_ok = pd.to_numeric(frame["merchant_lon"], errors="coerce").between(-180, 180)
        coords_ok = lat_ok & lon_ok & merchant_lat_ok & merchant_lon_ok
        checks.append(
            _result(
                "coordinates_range",
                "Координаты в географических пределах",
                _mask_all(coords_ok),
                f"строк вне диапазона или с пропуском: {int((~coords_ok.fillna(False)).sum())}",
                "lat и merchant_lat в [-90, 90], lon и merchant_lon в [-180, 180], пропусков нет.",
            )
        )

    if "gender" in frame.columns:
        gender_ok = frame["gender"].notna() & frame["gender"].astype(str).isin(["M", "F"])
        unexpected = sorted(set(frame["gender"].dropna().astype(str).unique()) - {"M", "F"})
        checks.append(
            _result(
                "gender_vocabulary",
                "Пол из фиксированного словаря",
                _mask_all(gender_ok),
                f"посторонние значения: {unexpected or '—'}; пропусков: {int(frame['gender'].isna().sum())}",
                "gender принимает только значения M и F.",
            )
        )
    else:
        checks.append(
            _result(
                "gender_vocabulary",
                "Пол из фиксированного словаря",
                False,
                "колонки gender нет",
                "gender принимает только значения M и F.",
            )
        )

    if "transaction_time" in frame.columns:
        timestamps = pd.to_datetime(frame["transaction_time"], errors="coerce")
        time_ok = timestamps.notna() & (timestamps >= TIME_MIN) & (timestamps < TIME_MAX)
        if timestamps.notna().any():
            observed_time = f"{timestamps.min()} — {timestamps.max()}"
        else:
            observed_time = "время не разобрано"
        checks.append(
            _result(
                "event_time_bounds",
                "Время транзакции в рабочем диапазоне",
                _mask_all(time_ok),
                observed_time,
                "Каждый transaction_time разбирается и лежит в [2018-01-01, 2030-01-01).",
            )
        )
        months = sorted(timestamps.dt.to_period("M").dropna().unique().astype(str))
        checks.append(
            _result(
                "fixed_month_window",
                "В окне фиксированное число месяцев",
                len(months) == WINDOW_MONTHS,
                f"{len(months)}: {', '.join(months) if months else '—'}",
                f"В снимке ровно {WINDOW_MONTHS} календарных месяца.",
            )
        )
    else:
        checks.append(
            _result(
                "event_time_bounds",
                "Время транзакции в рабочем диапазоне",
                False,
                "колонки transaction_time нет",
                "Каждый transaction_time разбирается и лежит в [2018-01-01, 2030-01-01).",
            )
        )
        checks.append(
            _result(
                "fixed_month_window",
                "В окне фиксированное число месяцев",
                False,
                "колонки transaction_time нет",
                f"В снимке ровно {WINDOW_MONTHS} календарных месяца.",
            )
        )

    duplicate_missing = [column for column in DUPLICATE_KEYS if column not in frame.columns]
    if duplicate_missing or len(frame) == 0:
        checks.append(
            _result(
                "duplicate_transactions",
                "Дубликаты транзакций редки",
                False,
                f"нет колонок: {duplicate_missing or '—'}",
                "Доля дублей по transaction_time, merch, amount, name_1, lat, lon не выше 1%.",
            )
        )
    else:
        duplicate_rate = float(frame.duplicated(DUPLICATE_KEYS).mean())
        checks.append(
            _result(
                "duplicate_transactions",
                "Дубликаты транзакций редки",
                duplicate_rate <= 0.01,
                f"{duplicate_rate:.4%}",
                "Доля дублей по transaction_time, merch, amount, name_1, lat, lon не выше 1%.",
            )
        )

    checks.append(
        _result(
            "minimum_rows",
            "В окне достаточно строк",
            len(frame) >= MIN_ROWS,
            str(len(frame)),
            f"Не меньше {MIN_ROWS} строк.",
        )
    )
    return checks


def run_quality_checks(dataset_info: dict) -> dict:
    """Считает правила качества по снимку окна.

    Читает parquet из dataset_info. В витрину, окно обучения и каталог моделей
    ничего не пишет. Повтор читает тот же или обновлённый снимок и заново
    возвращает результат, не удаляя строки датасета.
    """
    frame = pd.read_parquet(dataset_info["snapshot_path"])
    checks = evaluate_checks(frame)
    passed = sum(1 for item in checks if item["passed"])
    logger.info("Проверки качества: %s из %s успешны, строк %s", passed, len(checks), len(frame))
    return {
        "snapshot_path": dataset_info["snapshot_path"],
        "rows": int(len(frame)),
        "passed": int(passed),
        "total": int(len(checks)),
        "checks": checks,
    }
