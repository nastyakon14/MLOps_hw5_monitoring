import json
from pathlib import Path

import numpy as np
import pandas as pd

MIN_CATEGORY_COUNT = 20
MEDIAN_COLUMNS = ["amount", "population_city", "lat", "lon", "merchant_lat", "merchant_lon"]
CAT_FEATURES = ["merch", "cat_id", "gender", "one_city", "us_state", "jobs"]
NUMERIC_FEATURES = [
    "log_amount",
    "amount_to_population",
    "distance_km",
    "abs_lat_delta",
    "abs_lon_delta",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "is_night",
    "day_of_month",
    "population_filled",
    "lat_filled",
    "lon_filled",
    "merchant_lat_filled",
    "merchant_lon_filled",
]
EARTH_RADIUS_KM = 6371.0


def _median(series: pd.Series) -> float:
    value = pd.to_numeric(series, errors="coerce").median()
    if pd.isna(value):
        return 0.0
    return float(value)


def _frequent_values(series: pd.Series) -> list[str]:
    text = series.fillna("__MISSING__").astype(str)
    counts = text.value_counts()
    kept = counts[counts >= MIN_CATEGORY_COUNT].index.tolist()
    return sorted(kept)


def fit_state(frame: pd.DataFrame) -> dict:
    """Считает статистики препроцессинга только по обучающим строкам.

    Медианы числовых полей и списки частых категорий сохраняются вместе с моделью.
    Тестовый месяц и онлайн-транзакции этими статистиками не обновляют состояние.
    """
    medians = {}
    for column in MEDIAN_COLUMNS:
        if column in frame.columns:
            medians[column] = _median(frame[column])
        else:
            medians[column] = 0.0
    keep = {}
    for column in CAT_FEATURES:
        if column in frame.columns:
            keep[column] = _frequent_values(frame[column])
        else:
            keep[column] = []
    return {
        "medians": medians,
        "keep": keep,
        "min_category_count": MIN_CATEGORY_COUNT,
        "cat_features": list(CAT_FEATURES),
        "features": list(NUMERIC_FEATURES) + list(CAT_FEATURES),
    }


def save_state(state: dict, path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _fill(frame: pd.DataFrame, column: str, medians: dict) -> pd.Series:
    return _numeric(frame, column).fillna(float(medians[column]))


def _distance_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1_r = np.radians(lat1.to_numpy(dtype=float))
    lon1_r = np.radians(lon1.to_numpy(dtype=float))
    lat2_r = np.radians(lat2.to_numpy(dtype=float))
    lon2_r = np.radians(lon2.to_numpy(dtype=float))
    east = (lon2_r - lon1_r) * np.cos((lat1_r + lat2_r) / 2.0)
    north = lat2_r - lat1_r
    return EARTH_RADIUS_KM * np.sqrt(east * east + north * north)


def _bucket(frame: pd.DataFrame, column: str, keep: list[str]) -> pd.Series:
    if column not in frame.columns:
        raw = pd.Series("__MISSING__", index=frame.index)
    else:
        raw = frame[column].fillna("__MISSING__").astype(str)
    allowed = set(keep)
    return pd.Series(np.where(raw.isin(list(allowed)), raw.to_numpy(), "__RARE__"), index=frame.index)


def transform(frame: pd.DataFrame, state: dict, keep_target: bool = True) -> pd.DataFrame:
    """Превращает сырые транзакции в матрицу признаков сохранённого состояния.

    Редкие и незнакомые категории схлопываются в __RARE__. Пропуски чисел
    заменяются медианами обучающей выборки. Целевая колонка добавляется только
    если она есть во входе и keep_target=True.
    """
    medians = state["medians"]
    amount = _fill(frame, "amount", medians).clip(lower=0)
    population = _fill(frame, "population_city", medians)
    lat = _fill(frame, "lat", medians)
    lon = _fill(frame, "lon", medians)
    merchant_lat = _fill(frame, "merchant_lat", medians)
    merchant_lon = _fill(frame, "merchant_lon", medians)
    timestamps = pd.to_datetime(frame["transaction_time"], errors="coerce")
    hour = timestamps.dt.hour.fillna(0).astype(float)
    dow = timestamps.dt.dayofweek.fillna(0).astype(float)
    day = timestamps.dt.day.fillna(1).astype(float)
    turn = 2.0 * np.pi
    values = {
        "log_amount": np.log1p(amount.to_numpy(dtype=float)),
        "amount_to_population": (amount / (population + 1.0)).to_numpy(dtype=float),
        "distance_km": _distance_km(lat, lon, merchant_lat, merchant_lon),
        "abs_lat_delta": (lat - merchant_lat).abs().to_numpy(dtype=float),
        "abs_lon_delta": (lon - merchant_lon).abs().to_numpy(dtype=float),
        "hour_sin": np.sin(turn * hour.to_numpy(dtype=float) / 24.0),
        "hour_cos": np.cos(turn * hour.to_numpy(dtype=float) / 24.0),
        "dow_sin": np.sin(turn * dow.to_numpy(dtype=float) / 7.0),
        "dow_cos": np.cos(turn * dow.to_numpy(dtype=float) / 7.0),
        "is_night": ((hour >= 22.0) | (hour < 6.0)).astype(int).to_numpy(),
        "day_of_month": day.to_numpy(dtype=float),
        "population_filled": population.to_numpy(dtype=float),
        "lat_filled": lat.to_numpy(dtype=float),
        "lon_filled": lon.to_numpy(dtype=float),
        "merchant_lat_filled": merchant_lat.to_numpy(dtype=float),
        "merchant_lon_filled": merchant_lon.to_numpy(dtype=float),
    }
    keep = state["keep"]
    for column in CAT_FEATURES:
        values[column] = _bucket(frame, column, keep.get(column, [])).to_numpy()
    output = pd.DataFrame(values, index=frame.index)
    output = output.loc[:, state["features"]]
    if keep_target and "target" in frame.columns:
        output["target"] = pd.to_numeric(frame["target"], errors="coerce").to_numpy()
    return output


def split_xy(frame: pd.DataFrame, state: dict) -> tuple[pd.DataFrame, pd.Series]:
    """Отделяет target от признаков и приводит категории к строкам."""
    if "target" not in frame.columns:
        raise ValueError("В датасете нет колонки target")
    missing = [column for column in state["features"] if column not in frame.columns]
    if missing:
        raise ValueError(f"После препроцессинга нет признаков: {missing}")
    features = frame.loc[:, state["features"]].copy()
    for column in state["cat_features"]:
        features[column] = features[column].astype(str)
    target = frame["target"].astype(int)
    return features, target
