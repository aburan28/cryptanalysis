# 3SUM-breakthrough vs index-calculus transfer analysis

Does the claimed subquadratic 3SUM (arXiv 2610.06783, Oct 5 2026) enable or
affect anything in this repo's IC program? Short answer: no, with three
independent blocking gaps documented. Analysis only (no code changes, no new
measurements).

- `REPORT-2026-10-07.md`: dated analysis note (claim, transfer gaps,
  query-model comparison, floors, falsification checklist + pending
  preregistered protocol, negative findings). Start here.
- `REPORT-2026-10-07.pdf`: the same note with the embedded figure.
- `transfer.dot`: editable Graphviz source of the breakage diagram.
- `figures/transfer.svg`: zoomable vector rendering.
- `figures/transfer.pdf`: the same figure for LaTeX inclusion.

Rebuild:

```sh
cd experiments/threesum-ic-transfer-20261007
dot -Tsvg transfer.dot -o figures/transfer.svg
dot -Tpdf transfer.dot -o figures/transfer.pdf
pandoc REPORT-2026-10-07.md -o REPORT-2026-10-07.pdf \
  --pdf-engine=pdflatex -V geometry:margin=1in -V colorlinks:true
```
