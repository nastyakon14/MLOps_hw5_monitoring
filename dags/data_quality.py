"""DAG проверки качества окна обучения.

Файл только связывает задачи. Логика каждой задачи лежит в pipeline.quality.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from pipeline.quality.load_dataset import load_training_dataset
from pipeline.quality.publish_report import publish_dq_report
from pipeline.quality.run_checks import run_quality_checks


@dag(
    dag_id="data_quality",
    description="Раз в 5 минут проверяет окно обучения и публикует HTML-отчёт",
    schedule="*/5 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=15),
    default_args={"retries": 1, "retry_delay": timedelta(seconds=30)},
    tags=["mlops", "quality"],
    doc_md="""
### Качество данных

Проверяется сырое трёхмесячное окно `current.parquet`:

1. Ключевые поля без пропусков.
2. `target` только 0 или 1.
3. `amount` конечный и больше нуля.
4. Координаты клиента и мерчанта в географических пределах.
5. `gender` только M или F.
6. Доля фрода от 0.2% до 2%.
7. Время транзакций внутри 2018–2030.
8. В окне ровно три календарных месяца.
9. Дубликаты по ключу транзакции не чаще 1%.
10. В окне не меньше 1000 строк.

HTML пишется в `/opt/airflow/artifacts/dq_reports`, это соседний каталог к `/opt/airflow/artifacts/models`.
Витрина и модели отчётом не изменяются.
    """,
)
def data_quality():
    """Связывает снимок окна, расчёт правил и публикацию HTML."""
    loaded = task(load_training_dataset, task_id="load_training_dataset")()
    checked = task(run_quality_checks, task_id="run_quality_checks")(loaded)
    task(publish_dq_report, task_id="publish_dq_report")(checked)


data_quality()
