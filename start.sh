#!/usr/bin/env bash
set -euo pipefail
# Launch Streamlit (can add Jupyter if you want)
exec streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0
