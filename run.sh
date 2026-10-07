#!/usr/bin/env bash
# ./run.sh setup | dashboard | api | test | cli <portfolio.csv>
set -e
cd "$(dirname "$0")"
case "$1" in
  setup) python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && echo "Done. Use ./run.sh dashboard" ;;
  dashboard) .venv/bin/streamlit run app/dashboard.py --server.port 8502 ;;
  api) .venv/bin/uvicorn api.main:app --port 8000 --reload ;;
  test) CRPA_OFFLINE=1 .venv/bin/python -m pytest -q ;;
  cli) shift; .venv/bin/python -m src.orchestrator "$@" ;;
  *) echo "usage: ./run.sh setup|dashboard|api|test|cli <csv>"; exit 1 ;;
esac
