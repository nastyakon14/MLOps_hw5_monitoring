"""Публикация HTML-отчёта качества рядом с каталогом моделей."""

import html
import logging
import os
from datetime import datetime, timezone

from pipeline.settings import DQ_REPORTS_DIR

logger = logging.getLogger(__name__)


def render_html(report: dict, generated_at: str) -> str:
    rows = []
    for item in report["checks"]:
        status = "PASS" if item["passed"] else "FAIL"
        color = "#146c43" if item["passed"] else "#b02a37"
        rows.append(
            "<tr>"
            f"<td>{html.escape(item['id'])}</td>"
            f"<td>{html.escape(item['title'])}</td>"
            f"<td style=\"color:{color};font-weight:600\">{status}</td>"
            f"<td>{html.escape(item['observed'])}</td>"
            f"<td>{html.escape(item['expected'])}</td>"
            "</tr>"
        )
    overall_ok = report["passed"] == report["total"]
    overall = "PASS" if overall_ok else "FAIL"
    overall_color = "#146c43" if overall_ok else "#b02a37"
    body = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Data quality {html.escape(generated_at)}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 32px; color: #1c1c1c; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 10px; vertical-align: top; }}
    th {{ background: #f4f1ea; text-align: left; }}
  </style>
</head>
<body>
  <h1>Качество окна обучения</h1>
  <p>Сформирован: {html.escape(generated_at)}</p>
  <p>Снимок: {html.escape(report["snapshot_path"])}</p>
  <p>Строк: {report["rows"]}. Правил пройдено: {report["passed"]} из {report["total"]}.</p>
  <p>Итог: <span style="color:{overall_color};font-weight:700">{overall}</span></p>
  <table>
    <thead>
      <tr><th>Правило</th><th>Название</th><th>Статус</th><th>Факт</th><th>Ожидание</th></tr>
    </thead>
    <tbody>
      {body}
    </tbody>
  </table>
</body>
</html>
"""


def publish_dq_report(report: dict) -> str:
    """Пишет HTML-отчёт в каталог рядом с моделями.

    Читает результат проверок. Создаёт dq_reports/dq_report_<время>.html
    и атомарно заменяет dq_reports/latest.html. Датасет, витрину и файлы
    моделей не меняет. Повтор добавляет новый отчёт и обновляет latest.html,
    предыдущие отчёты и строки окна не удаляет.
    Возвращает путь к новому отчёту.
    """
    DQ_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    document = render_html(report, generated_at)
    final_path = DQ_REPORTS_DIR / f"dq_report_{stamp}.html"
    temporary = DQ_REPORTS_DIR / f".dq_report_{stamp}.html"
    temporary.write_text(document, encoding="utf-8")
    os.replace(temporary, final_path)
    latest_tmp = DQ_REPORTS_DIR / f".latest.{stamp}.html"
    latest_tmp.write_text(document, encoding="utf-8")
    os.replace(latest_tmp, DQ_REPORTS_DIR / "latest.html")
    logger.info("Отчёт качества записан: %s", final_path)
    return str(final_path)
