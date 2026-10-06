# EC arithmetic optimizations survey

What makes this repository's elliptic-curve arithmetic fast, layer by layer,
with the measured effect of each optimization. Survey only (no code changes,
no new measurements).

- `REPORT-2026-10-06.md`: dated source-linked survey (question, scope, method,
  layer walkthrough, negative findings, canonical-graph checks, open checks).
  Start here.
- `REPORT-2026-10-06.pdf`: the same report with embedded figures.
- `opt_layers.dot` / `ec_optimizations.dot`: editable Graphviz sources.
- `figures/opt_layers.svg`, `figures/ec_optimizations.svg`: zoomable vector
  renderings. Open the SVG in a browser and zoom for small text.
- `figures/opt_layers.pdf`, `figures/ec_optimizations.pdf`: the same figures
  for LaTeX inclusion.
- `figures.py`: plots `figures/speedups.pdf/.png` (headline ratios quoted
  verbatim from committed docs, not new measurements).
- `figures/speedups.pdf/.png`: quantitative companion.

Rebuild:

```sh
cd experiments/ec-arithmetic-optimizations
dot -Tsvg opt_layers.dot -o figures/opt_layers.svg
dot -Tpdf opt_layers.dot -o figures/opt_layers.pdf
dot -Tsvg ec_optimizations.dot -o figures/ec_optimizations.svg
dot -Tpdf ec_optimizations.dot -o figures/ec_optimizations.pdf
python3 figures.py
pandoc REPORT-2026-10-06.md -o REPORT-2026-10-06.pdf \
  --pdf-engine=pdflatex -V geometry:margin=1in -V colorlinks:true
```
