# IC assumption graph

A conceptual dependency graph: which algorithms comprise index calculus for
ECDLP and which assumptions each rests on. Synthesis only (no new runs,
curves, or candidates).

- `REPORT-2026-10-06.md`: dated source-linked report (question, scope, method,
  stage walkthrough, positive/negative findings, canonical-graph checks,
  uncertainty, reproduce). Start here.
- `REPORT-2026-10-06.pdf`: the same report with embedded figures.
- `ic_pipeline.dot` / `ic_assumptions.dot`: editable Graphviz sources.
- `figures/ic_pipeline.svg`, `figures/ic_assumptions.svg`: zoomable vector
  renderings. Open the SVG in a browser and zoom for small text.
- `figures/ic_pipeline.pdf`, `figures/ic_assumptions.pdf`: the same figures
  for LaTeX inclusion.
- `figures.py`: generates `figures/assumption_status.pdf/.png` (status counts
  read from the DOT source, not hand-typed).
- `figures/assumption_status.pdf/.png`: quantitative companion (summary counts,
  not new measurements).

Rebuild:

```sh
cd experiments/ic-assumption-graph
dot -Tsvg ic_pipeline.dot -o figures/ic_pipeline.svg
dot -Tpdf ic_pipeline.dot -o figures/ic_pipeline.pdf
dot -Tsvg ic_assumptions.dot -o figures/ic_assumptions.svg
dot -Tpdf ic_assumptions.dot -o figures/ic_assumptions.pdf
python3 figures.py
pandoc REPORT-2026-10-06.md -o REPORT-2026-10-06.pdf \
  --pdf-engine=pdflatex -V geometry:margin=1in -V colorlinks:true
```
