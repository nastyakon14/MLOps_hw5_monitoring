#!/usr/bin/env bash
# Копирует текущую прод-модель под новое имя и обновляет latest.txt.
# Скоринг подхватывает файл без перезапуска. На дашборде «Обработка транзакций»
# появляется красная отметка с именем версии примерно на 30 секунд.
set -euo pipefail
VERSION="${1:-manual-$(date +%H%M%S)}"
docker compose exec -T fraud_detector python - "$VERSION" <<'PY'
import shutil
import sys
from pathlib import Path

version = sys.argv[1]
models = Path("/artifacts/models")
current = (models / "latest.txt").read_text(encoding="utf-8").strip()
src_model = models / f"my_catboost_{current}.cbm"
src_preproc = models / f"my_catboost_{current}.preproc.json"
if not src_model.exists() or not src_preproc.exists():
    raise SystemExit(f"Нет файлов текущей модели {current}")
dst_model = models / f"my_catboost_{version}.cbm"
dst_preproc = models / f"my_catboost_{version}.preproc.json"
shutil.copy2(src_model, dst_model)
shutil.copy2(src_preproc, dst_preproc)
(models / "latest.txt").write_text(version, encoding="utf-8")
print(f"{current} -> {version}")
PY
echo "Новая версия опубликована. Откройте Grafana, дашборд «Обработка транзакций»."
