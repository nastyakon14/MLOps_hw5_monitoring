import os

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score


def classification_metrics(y_true, proba, threshold: float = 0.5) -> dict:
    """Считает ROC-AUC и F1 по вероятностям положительного класса."""
    target = pd.Series(y_true).astype(int)
    scores = np.asarray(proba, dtype=float)
    predicted = (scores >= threshold).astype(int)
    f1 = float(f1_score(target, predicted, zero_division=0))
    if target.nunique() < 2:
        roc_auc = None
    else:
        roc_auc = float(roc_auc_score(target, scores))
    return {"roc_auc": roc_auc, "f1": f1}


def fit_classifier(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    cat_features: list[str],
    iterations: int = 100,
    depth: int = 6,
    learning_rate: float = 0.1,
):
    """Обучает CatBoost на CPU и возвращает модель с именами колонок."""
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=iterations,
        depth=depth,
        learning_rate=learning_rate,
        loss_function="Logloss",
        eval_metric="AUC",
        auto_class_weights="Balanced",
        random_seed=42,
        allow_writing_files=False,
        verbose=50,
    )
    present = [column for column in cat_features if column in x_train.columns]
    model.fit(x_train, y_train, cat_features=present)
    return model
