#!/bin/sh
# Build README.pdf from README.md with pandoc + pdflatex (run from anywhere).
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
pandoc README.md -o README.pdf --pdf-engine=pdflatex \
  -H figures/readme_pdf_header.tex \
  -V geometry:margin=1.4cm -V fontsize=10pt -V colorlinks=true -V linkcolor=blue -V urlcolor=blue \
  --resource-path=.
