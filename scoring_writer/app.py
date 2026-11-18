import json
import logging
import os
import time

import psycopg2
from confluent_kafka import Consumer
from prometheus_client import Counter, Histogram, start_http_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

METRICS_PORT = int(os.getenv("METRICS_PORT", "8001"))
SCORE_BUCKETS = [i / 20.0 for i in range(21)]
WRITE_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)

WRITTEN_TOTAL = Counter(
    "score_sink_written_total",
    "Число скоров, записанных в PostgreSQL",
)
FRAUD_WRITTEN_TOTAL = Counter(
    "score_sink_fraud_total",
    "Число записанных транзакций с флагом фрода",
)
WRITE_SECONDS = Histogram(
    "score_sink_write_seconds",
    "Время одной записи скора в PostgreSQL",
    buckets=WRITE_BUCKETS,
)
WRITTEN_SCORE = Histogram(
    "score_sink_score",
    "Распределение скоров, попавших в базу",
    buckets=SCORE_BUCKETS,
)


def get_db_config():
    return {
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
        "database": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id SERIAL PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                score FLOAT NOT NULL,
                fraud_flag INT NOT NULL,
                model_version TEXT,
                us_state TEXT,
                merch TEXT,
                cat_id TEXT,
                amount FLOAT,
                is_night INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS model_version TEXT;")
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS us_state TEXT;")
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS merch TEXT;")
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS cat_id TEXT;")
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS amount FLOAT;")
        cur.execute("ALTER TABLE scores ADD COLUMN IF NOT EXISTS is_night INT;")
        cur.execute("CREATE INDEX IF NOT EXISTS scores_created_at_idx ON scores (created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS scores_us_state_idx ON scores (us_state);")
        cur.execute("CREATE INDEX IF NOT EXISTS scores_merch_idx ON scores (merch);")
        cur.execute("CREATE INDEX IF NOT EXISTS scores_cat_id_idx ON scores (cat_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS scores_model_version_idx ON scores (model_version);")
        conn.commit()
        logger.info("Таблица scores готова.")


def insert_score(conn, data):
    started = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scores (
                transaction_id, score, fraud_flag, model_version,
                us_state, merch, cat_id, amount, is_night
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                data["transaction_id"],
                data["score"],
                data["fraud_flag"],
                data.get("model_version"),
                data.get("us_state"),
                data.get("merch"),
                None if data.get("cat_id") is None else str(data.get("cat_id")),
                data.get("amount"),
                data.get("is_night"),
            ),
        )
        conn.commit()
    WRITE_SECONDS.observe(time.perf_counter() - started)
    WRITTEN_TOTAL.inc()
    WRITTEN_SCORE.observe(float(data["score"]))
    if int(data["fraud_flag"]) == 1:
        FRAUD_WRITTEN_TOTAL.inc()


def run_consumer():
    start_http_server(METRICS_PORT)
    logger.info("Prometheus метрики: порт %s", METRICS_PORT)

    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    scoring_topic = os.getenv("KAFKA_SCORING_TOPIC")
    consumer = Consumer(
        {
            "bootstrap.servers": kafka_bootstrap_servers,
            "group.id": "scoring-writer",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([scoring_topic])
    logger.info("Kafka %s, топик %s", kafka_bootstrap_servers, scoring_topic)

    conn = psycopg2.connect(**get_db_config())
    create_table(conn)

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error("Kafka error: %s", msg.error())
                continue
            try:
                data_list = json.loads(msg.value().decode("utf-8"))
                if not isinstance(data_list, list):
                    logger.error("Ожидался список, получен %s", type(data_list))
                    continue
                for data in data_list:
                    required = ["transaction_id", "score", "fraud_flag"]
                    if not all(key in data for key in required):
                        logger.error("Некорректный элемент: %s", data)
                        continue
                    insert_score(conn, data)
                    logger.info("Записано в БД: %s", data["transaction_id"])
            except json.JSONDecodeError as exc:
                logger.exception("Ошибка JSON: %s", exc)
            except Exception as exc:
                logger.exception("Ошибка обработки: %s", exc)
    except KeyboardInterrupt:
        logger.info("Писатель остановлен.")
    finally:
        consumer.close()
        conn.close()


if __name__ == "__main__":
    logger.info("Запуск потребителя и писателя в БД...")
    run_consumer()
