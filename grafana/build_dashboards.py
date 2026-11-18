#!/usr/bin/env python3
"""Собирает JSON дашбордов Grafana. Запускается один раз при подготовке репозитория."""

from __future__ import annotations

import json
from pathlib import Path


PROM = {"type": "prometheus", "uid": "prometheus"}
PG = {"type": "postgres", "uid": "postgres"}


def timeseries(panel_id, title, expr, x, y, w=12, h=8, legend="{{__name__}}", unit=None):
    if isinstance(expr, str):
        targets = [{"datasource": PROM, "expr": expr, "legendFormat": legend, "refId": "A"}]
    else:
        targets = [
            {
                "datasource": PROM,
                "expr": item["expr"],
                "legendFormat": item.get("legend", "{{__name__}}"),
                "refId": chr(65 + idx),
            }
            for idx, item in enumerate(expr)
        ]
    panel = {
        "datasource": PROM,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisBorderShow": False,
                    "axisCenteredZero": False,
                    "drawStyle": "line",
                    "fillOpacity": 12,
                    "lineWidth": 2,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": False,
                },
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": panel_id,
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "single", "sort": "none"},
        },
        "targets": targets,
        "title": title,
        "type": "timeseries",
    }
    if unit:
        panel["fieldConfig"]["defaults"]["unit"] = unit
    return panel


def heatmap(panel_id, title, expr, x, y, w=12, h=8):
    return {
        "datasource": PROM,
        "fieldConfig": {"defaults": {}, "overrides": []},
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": panel_id,
        "options": {
            "calculate": False,
            "cellGap": 1,
            "color": {"exponent": 0.5, "fill": "dark-orange", "mode": "scheme", "scheme": "Spectral", "steps": 64},
            "exemplars": {"color": "rgba(255,0,255,0.7)"},
            "filterValues": {"le": 1e-9},
            "legend": {"show": True},
            "rowsFrame": {"layout": "auto"},
            "tooltip": {"mode": "single", "showColorScale": False, "yHistogram": False},
            "yAxis": {"axisPlacement": "left", "reverse": False, "unit": "short"},
        },
        "targets": [
            {
                "datasource": PROM,
                "expr": expr,
                "format": "heatmap",
                "legendFormat": "{{le}}",
                "refId": "A",
            }
        ],
        "title": title,
        "type": "heatmap",
    }


def postgres_table(panel_id, title, sql, x, y, w=12, h=8):
    return {
        "datasource": PG,
        "fieldConfig": {
            "defaults": {
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": panel_id,
        "options": {"cellHeight": "sm", "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False}, "showHeader": True},
        "pluginVersion": "11.3.0",
        "targets": [
            {
                "datasource": PG,
                "editorMode": "code",
                "format": "table",
                "rawQuery": True,
                "rawSql": sql,
                "refId": "A",
            }
        ],
        "title": title,
        "type": "table",
    }


def postgres_bar(panel_id, title, sql, x, y, w=12, h=8, x_field=None, y_field=None):
    panel = {
        "datasource": PG,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"axisBorderShow": False, "fillOpacity": 80, "gradientMode": "none", "lineWidth": 1},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": panel_id,
        "options": {
            "barRadius": 0,
            "barWidth": 0.8,
            "fullHighlight": False,
            "groupWidth": 0.7,
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "orientation": "auto",
            "showValue": "auto",
            "stacking": "none",
            "tooltip": {"mode": "single", "sort": "none"},
            "xTickLabelRotation": 0,
            "xTickLabelSpacing": 0,
        },
        "pluginVersion": "11.3.0",
        "targets": [
            {
                "datasource": PG,
                "editorMode": "code",
                "format": "table",
                "rawQuery": True,
                "rawSql": sql,
                "refId": "A",
            }
        ],
        "title": title,
        "type": "barchart",
    }
    if x_field and y_field:
        panel["transformations"] = [
            {
                "id": "organize",
                "options": {"indexByName": {}, "renameByName": {}},
            }
        ]
    return panel


def postgres_timeseries(panel_id, title, sql, x, y, w=12, h=8, unit=None):
    panel = {
        "datasource": PG,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line",
                    "fillOpacity": 15,
                    "lineWidth": 2,
                    "pointSize": 5,
                    "showPoints": "never",
                    "spanNulls": False,
                },
                "mappings": [],
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": panel_id,
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "single", "sort": "none"},
        },
        "targets": [
            {
                "datasource": PG,
                "editorMode": "code",
                "format": "time_series",
                "rawQuery": True,
                "rawSql": sql,
                "refId": "A",
            }
        ],
        "title": title,
        "type": "timeseries",
    }
    if unit:
        panel["fieldConfig"]["defaults"]["unit"] = unit
    return panel


def dashboard(uid, title, panels, templating=None, annotations=None, refresh="1s", time_from="now-15m"):
    return {
        "annotations": {"list": annotations or []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "liveNow": True,
        "panels": panels,
        "refresh": refresh,
        "schemaVersion": 39,
        "tags": ["fraud", "mlops"],
        "templating": {"list": templating or []},
        "time": {"from": time_from, "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 1,
        "weekStart": "",
    }


def model_annotation():
    # Серия с новой меткой version существует сейчас и не существовала 30 секунд назад.
    # increase() здесь не подходит: счётчик создаётся сразу со значением 1 и дальше не растёт.
    expr = "fraud_scorer_model_reload_total unless fraud_scorer_model_reload_total offset 30s"
    return {
        "datasource": PROM,
        "enable": True,
        "expr": expr,
        "hide": False,
        "iconColor": "red",
        "name": "Смена версии модели",
        "step": "1s",
        "tagKeys": "version",
        "textFormat": "Скоринг перешёл на {{version}}",
        "titleFormat": "{{version}}",
    }


FILTER_SQL = """us_state IN (${us_state:sqlstring})
AND merch IN (${merch:sqlstring})"""


def processing():
    panels = [
        timeseries(
            1,
            "Скорость потока, TPS",
            "rate(fraud_scorer_processed_total[10s])",
            0,
            0,
            legend="обработано / с",
        ),
        timeseries(
            2,
            "Время обработки одной транзакции",
            [
                {
                    "expr": "rate(fraud_scorer_latency_seconds_sum[10s]) / rate(fraud_scorer_latency_seconds_count[10s])",
                    "legend": "среднее",
                },
                {
                    "expr": "histogram_quantile(0.95, rate(fraud_scorer_latency_seconds_bucket[30s]))",
                    "legend": "p95",
                },
            ],
            12,
            0,
            unit="s",
        ),
        timeseries(
            3,
            "Доля фрода (score > 0.5)",
            "fraud_scorer_fraud_share",
            0,
            8,
            legend="доля фрода",
            unit="percentunit",
        ),
        heatmap(
            4,
            "Распределение скоров во времени",
            "sum by (le) (increase(fraud_scorer_score_bucket[10s]))",
            12,
            8,
        ),
        timeseries(
            5,
            "Доля ночных транзакций",
            "rate(fraud_scorer_night_txn_total[30s]) / clamp_min(rate(fraud_scorer_processed_total[30s]), 1e-9)",
            0,
            16,
            legend="ночь / все",
            unit="percentunit",
        ),
        timeseries(
            6,
            "Ошибки скоринга",
            "rate(fraud_scorer_errors_total[30s])",
            12,
            16,
            legend="ошибок / с",
        ),
        postgres_table(
            7,
            "Скоры и доля фрода по версии модели (PostgreSQL)",
            """
SELECT
  COALESCE(model_version, 'unknown') AS model_version,
  COUNT(*) AS scores_count,
  ROUND(AVG(fraud_flag)::numeric, 4) AS fraud_share,
  ROUND(AVG(score)::numeric, 4) AS avg_score,
  MIN(created_at) AS first_seen,
  MAX(created_at) AS last_seen
FROM scores
GROUP BY 1
ORDER BY last_seen DESC;
""".strip(),
            0,
            24,
            w=24,
            h=8,
        ),
    ]
    return dashboard(
        "fraud-processing",
        "Обработка транзакций",
        panels,
        annotations=[model_annotation()],
    )


def sink():
    panels = [
        timeseries(
            1,
            "Скорость записи в PostgreSQL",
            "rate(score_sink_written_total[10s])",
            0,
            0,
            legend="записей / с",
        ),
        timeseries(
            2,
            "Время записи в базу",
            [
                {
                    "expr": "rate(score_sink_write_seconds_sum[10s]) / rate(score_sink_write_seconds_count[10s])",
                    "legend": "среднее",
                },
                {
                    "expr": "histogram_quantile(0.95, rate(score_sink_write_seconds_bucket[30s]))",
                    "legend": "p95",
                },
            ],
            12,
            0,
            unit="s",
        ),
        timeseries(
            3,
            "Число выявленного фрода",
            [
                {"expr": "score_sink_fraud_total", "legend": "накоплено"},
                {"expr": "rate(score_sink_fraud_total[30s])", "legend": "фрод / с"},
            ],
            0,
            8,
        ),
        heatmap(
            4,
            "Распределение записанных скоров",
            "sum by (le) (increase(score_sink_score_bucket[10s]))",
            12,
            8,
        ),
    ]
    return dashboard("fraud-sink", "Запись результатов", panels)


def host():
    panels = [
        timeseries(
            1,
            "CPU",
            [
                {
                    "expr": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[30s])) * 100)',
                    "legend": "busy %",
                }
            ],
            0,
            0,
            unit="percent",
        ),
        timeseries(
            2,
            "Память",
            [
                {"expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "legend": "использовано"},
                {"expr": "node_memory_MemAvailable_bytes", "legend": "доступно"},
            ],
            12,
            0,
            unit="bytes",
        ),
        timeseries(
            3,
            "Сеть",
            [
                {"expr": "rate(node_network_receive_bytes_total[30s])", "legend": "rx {{device}}"},
                {"expr": "rate(node_network_transmit_bytes_total[30s])", "legend": "tx {{device}}"},
            ],
            0,
            8,
            unit="Bps",
        ),
        timeseries(
            4,
            "Диск",
            [
                {"expr": "rate(node_disk_read_bytes_total[30s])", "legend": "read {{device}}"},
                {"expr": "rate(node_disk_written_bytes_total[30s])", "legend": "write {{device}}"},
            ],
            12,
            8,
            unit="Bps",
        ),
        timeseries(
            5,
            "Заполненность файловых систем",
            '1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})',
            0,
            16,
            w=24,
            legend="{{mountpoint}}",
            unit="percentunit",
        ),
    ]
    return dashboard("host-metrics", "Системные метрики", panels)


def variable(name, label, sql):
    return {
        "allValue": None,
        "current": {"selected": True, "text": "All", "value": "$__all"},
        "datasource": PG,
        "definition": sql,
        "hide": 0,
        "includeAll": True,
        "label": label,
        "multi": True,
        "name": name,
        "options": [],
        "query": sql,
        "refresh": 2,
        "regex": "",
        "skipUrlSync": False,
        "sort": 1,
        "type": "query",
    }


def business():
    density_sql = f"""
SELECT
  to_char(LEAST(width_bucket(score, 0.0, 1.0, 20), 20) * 0.05 - 0.05, 'FM0.00') AS bucket_start,
  COUNT(*)::float / NULLIF(SUM(COUNT(*)) OVER (), 0) AS density
FROM scores
WHERE $__timeFilter(created_at)
  AND {FILTER_SQL}
GROUP BY 1
ORDER BY 1;
""".strip()
    # Фиксированные бакеты по 10 секунд: $__interval Grafana вроде '10s' PostgreSQL как interval не принимает.
    tps_sql = f"""
SELECT
  $__timeGroupAlias(created_at, '10s'),
  COUNT(*)::float / 10.0 AS tps
FROM scores
WHERE $__timeFilter(created_at)
  AND {FILTER_SQL}
GROUP BY 1
ORDER BY 1;
""".strip()
    cat_sql = """
SELECT
  COALESCE(cat_id, 'unknown') AS cat_id,
  AVG(fraud_flag::float) AS fraud_rate
FROM (
  SELECT cat_id, fraud_flag
  FROM scores
  ORDER BY created_at DESC
  LIMIT 1000
) recent
GROUP BY 1
ORDER BY fraud_rate DESC;
""".strip()
    night_sql = """
SELECT
  $__timeGroupAlias(created_at, $__interval),
  AVG(CASE WHEN COALESCE(is_night, 0) = 1 THEN fraud_flag ELSE NULL END)::float AS night_fraud_share,
  AVG(CASE WHEN COALESCE(is_night, 0) = 0 THEN fraud_flag ELSE NULL END)::float AS day_fraud_share
FROM scores
WHERE $__timeFilter(created_at)
GROUP BY 1
ORDER BY 1;
""".strip()
    amount_sql = """
SELECT
  $__timeGroupAlias(created_at, $__interval),
  AVG(CASE WHEN fraud_flag = 1 THEN amount END) AS fraud_avg_amount,
  AVG(CASE WHEN fraud_flag = 0 THEN amount END) AS legit_avg_amount
FROM scores
WHERE $__timeFilter(created_at)
GROUP BY 1
ORDER BY 1;
""".strip()
    panels = [
        postgres_bar(1, "Плотность распределения скоров", density_sql, 0, 0, w=12, h=9),
        postgres_timeseries(2, "TPS обработки выбранных транзакций", tps_sql, 12, 0, w=12, h=9),
        postgres_bar(3, "Средняя доля фрода по cat_id в последних 1000 транзакциях", cat_sql, 0, 9, w=12, h=9),
        postgres_timeseries(
            4,
            "Доля фрода ночью и днём",
            night_sql,
            12,
            9,
            w=12,
            h=9,
            unit="percentunit",
        ),
        postgres_timeseries(5, "Средний чек фродовых и легитимных транзакций", amount_sql, 0, 18, w=24, h=8),
    ]
    templating = [
        variable(
            "us_state",
            "Штат",
            "SELECT DISTINCT us_state FROM scores WHERE us_state IS NOT NULL ORDER BY 1;",
        ),
        variable(
            "merch",
            "Мерчант",
            "SELECT DISTINCT merch FROM scores WHERE merch IS NOT NULL ORDER BY 1;",
        ),
    ]
    return dashboard(
        "fraud-business",
        "Бизнес-аналитика фрода",
        panels,
        templating=templating,
        refresh="5s",
        time_from="now-30m",
    )


def main():
    out = Path(__file__).resolve().parent / "dashboards"
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "processing.json": processing(),
        "sink.json": sink(),
        "host.json": host(),
        "business.json": business(),
    }
    for name, payload in files.items():
        path = out / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
