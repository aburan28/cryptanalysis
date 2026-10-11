#!/usr/bin/env sh
# Regenerate every result, figure and the PDF for the speedup-search follow-up.
# Usage: ./run_all.sh [--skip-sss]   (SSS needs git/network or SSS_UPSTREAM_DIR)
set -eu
cd "$(dirname "$0")"
python3 selected_resieve.py
python3 batch_smooth.py
python3 nfs_density_window.py
python3 dyadic_reporter.py
if [ "${1:-}" != "--skip-sss" ]; then python3 sss_benchmark.py; fi
python3 pinpointing.py
python3 resultant_ranks.py
python3 transfer_checks.py
python3 s4_two_product.py
python3 s4_bench.py
python3 figures/make_figures.py
python3 build_pdf.py
