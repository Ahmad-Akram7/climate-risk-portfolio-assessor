#!/usr/bin/env bash
# ./run.sh setup | dashboard | api | test | cli <portfolio.csv>   (needs uv: https://docs.astral.sh/uv/)
set -e
cd "$(dirname "$0")"
case "$1" in
  setup) uv sync --locked && echo "Done. Use ./run.sh dashboard" ;;
  dashboard) uv run --locked streamlit run app/dashboard.py --server.port 8502 ;;
  api) uv run --locked uvicorn api.main:app --port 8000 --reload ;;
  test) CRPA_OFFLINE=1 uv run --locked pytest -q ;;
  cli) shift; uv run --locked python -m src.orchestrator "$@" ;;
  *) echo "usage: ./run.sh setup|dashboard|api|test|cli <csv>"; exit 1 ;;
esac
