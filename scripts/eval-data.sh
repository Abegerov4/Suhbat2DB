#!/usr/bin/env bash
# Данные для evals (docs/roles/07_evals.md): Spider 1.0 и BIRD dev → PostgreSQL в target-db.
# Наборы *.jsonl уже в git; скрипт нужен, чтобы воссоздать базы бенчмарков на новой машине.
set -euo pipefail
cd "$(dirname "$0")/.."
RAW=evals/data/raw
mkdir -p "$RAW" evals/data/spider evals/data/bird

if [ ! -f "$RAW/spider_data.zip" ]; then
  curl -L --fail -o "$RAW/spider_data.zip" \
    "https://drive.usercontent.google.com/download?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J&export=download&confirm=t"
fi
if [ ! -f "$RAW/bird_dev.zip" ]; then
  curl -L --fail -o "$RAW/bird_dev.zip" "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"
fi
echo "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b  $RAW/spider_data.zip" | shasum -a 256 -c
echo "cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630  $RAW/bird_dev.zip" | shasum -a 256 -c

[ -d evals/data/spider/spider_data ] || unzip -q "$RAW/spider_data.zip" -d evals/data/spider
if [ ! -d evals/data/bird/dev_20240627/dev_databases ]; then
  unzip -q "$RAW/bird_dev.zip" -d evals/data/bird
  unzip -q evals/data/bird/dev_20240627/dev_databases.zip -d evals/data/bird/dev_20240627
fi

cd backend
uv run python -m evals.benchdb spider   # базы из spider_subset.jsonl
uv run python -m evals.benchdb bird
uv run python -m evals.build_poisoned
