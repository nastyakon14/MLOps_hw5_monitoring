import json
import logging
import os
import sys
import time
from datetime import datetime

import pandas as pd
from confluent_kafka import Consumer
from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, Histogram, start_http_server

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from scorer import ensure_model_ready, make_pred


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/app/logs/service.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TRANSACTIONS_TOPIC = os.getenv("KAFKA_TRANSACTIONS_TOPIC", "transactions")
SCORING_TOPIC = os.getenv("KAFKA_SCORING_TOPIC", "scoring")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", "0.5"))
SCORE_BUCKETS = [i / 20.0 for i in range(21)]
AMOUNT_BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

PROCESSED_TOTAL = Counter(
    "fraud_scorer_processed_total",
    "Число транзакций, которые прошли скоринг",
)
ERROR_TOTAL = Counter(
    "fraud_scorer_errors_total",
    "Число сообщений, на которых скоринг упал",
)
LATENCY_SECONDS = Histogram(
    "fraud_scorer_latency_seconds",
    "Время обработки одной транзакции, секунды",
    buckets=LATENCY_BUCKETS,
)
SCORE_HIST = Histogram(
    "fraud_scorer_score",
    "Распределение скоров модели",
    buckets=SCORE_BUCKETS,
)
FRAUD_SHARE = Gauge(
    "fraud_scorer_fraud_share",
    "Доля транзакций со score выше порога с начала процесса",
)
MODEL_RELOAD_TOTAL = Counter(
    "fraud_scorer_model_reload_total",
    "Горячая подмена модели без перезапуска контейнера",
    ["version"],
)
NIGHT_TXN_TOTAL = Counter(
    "fraud_scorer_night_txn_total",
    "Ночные транзакции (22:00–06:00) после скоринга",
)
AMOUNT_HIST = Histogram(
    "fraud_scorer_amount",
    "Сумма обработанной транзакции",
    buckets=AMOUNT_BUCKETS,
)


def _parse_hour(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).hour
        except ValueError:
            continue
    try:
        return pd.to_datetime(value).hour
    except Exception:
        return None


def _is_night(payload: dict) -> int:
    hour = _parse_hour(payload.get("transaction_time"))
    if hour is None:
        return 0
    return int(hour >= 22 or hour < 6)


class ProcessingService:
    def __init__(self):
        self.consumer = Consumer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "group.id": "ml-scorer",
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe([TRANSACTIONS_TOPIC])
        self.producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        self.total_transactions = 0
        self.fraud_transactions = 0
        self._seen_model_version = None
        start_http_server(METRICS_PORT)
        logger.info("Prometheus метрики: порт %s", METRICS_PORT)

    def _record_model_version(self, model_version: str) -> None:
        if self._seen_model_version is None:
            self._seen_model_version = model_version
            return
        if model_version != self._seen_model_version:
            MODEL_RELOAD_TOTAL.labels(version=model_version).inc()
            logger.info("Модель сменилась: %s -> %s", self._seen_model_version, model_version)
            self._seen_model_version = model_version

    def process_message(self, msg) -> bool:
        started = time.perf_counter()
        try:
            data = json.loads(msg.value().decode("utf-8"))
            transaction_id = data["transaction_id"]
            payload = data["data"]
            input_df = pd.DataFrame([payload])
            submission, y_proba, model_version = make_pred(input_df, "kafka_stream")
            score = float(y_proba[0])
            fraud_flag = int(score > FRAUD_THRESHOLD)
            amount = float(payload.get("amount") or 0.0)
            is_night = _is_night(payload)

            PROCESSED_TOTAL.inc()
            SCORE_HIST.observe(score)
            AMOUNT_HIST.observe(max(amount, 0.0))
            if is_night:
                NIGHT_TXN_TOTAL.inc()
            self.total_transactions += 1
            if fraud_flag:
                self.fraud_transactions += 1
            FRAUD_SHARE.set(self.fraud_transactions / self.total_transactions)
            self._record_model_version(model_version)

            submission["transaction_id"] = transaction_id
            submission["model_version"] = model_version
            submission["us_state"] = payload.get("us_state")
            submission["merch"] = payload.get("merch")
            submission["cat_id"] = payload.get("cat_id")
            submission["amount"] = amount
            submission["is_night"] = is_night
            self.producer.produce(
                SCORING_TOPIC,
                value=submission.to_json(orient="records"),
            )
            self.producer.flush()
            return True
        except Exception as exc:
            ERROR_TOTAL.inc()
            logger.exception("Error processing message: %s", exc)
            return False
        finally:
            LATENCY_SECONDS.observe(time.perf_counter() - started)

    def process_messages(self):
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("Kafka error: %s", msg.error())
                continue
            self.process_message(msg)


if __name__ == "__main__":
    logger.info("Starting Kafka ML scoring service...")
    ensure_model_ready()
    service = ProcessingService()
    try:
        service.process_messages()
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
