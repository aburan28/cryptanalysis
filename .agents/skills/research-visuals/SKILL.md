---
name: research-visuals
description: Create evidence-linked diagrams, graphs, reports, and PDFs for searches involving isogenies, curves, scalar rules, endomorphisms, or related ECDLP mechanisms.
---

# Research visuals and reports

Use for a substantive literature, theory, code, or experiment search for new
isogenies, curves, scalar rules, endomorphisms, or related ECDLP ideas. Read
`AGENTS.md` first. Preserve its exact candidate IDs, curve registry, run
records, measurement boundaries, and checked Sage launcher.

## Complete the search record

1. Write a dated Markdown report beside the relevant experiment or in `docs/`.
   State the question, scope, method, sources, exact curve/subgroup IDs, run
   IDs, positive and negative findings, uncertainty, and open checks. Label
   each claim proposed, derived, independently verified, or measured. For an
   isogeny record the source and target, degree, map/kernel and subgroup
   transport evidence; for a scalar rule record its domain, preconditions,
   formula, and independent check or counterexample.
2. Add at least one labeled diagram, plus a quantitative graph when the result
   has data to compare. Save editable source beside its
   SVG or other vector rendering. Label isogeny vertices with full curve IDs,
   edges with degrees and directions, and unverified links with their status. Give
   units, sample size, and uncertainty on quantitative plots. Link visual and
   supporting evidence from the report.
3. Build a PDF of the report containing the visual, using an available
   document tool such as Pandoc, Typst, or LaTeX. Keep source and PDF together
   and inspect the result for readable labels, figures, and citations. If PDF
   generation is blocked, retain complete source and name the blocker; never
   silently reuse an older PDF.

## Update the graph set

- Locate graphs affected by the search in the relevant experiment, including
  `experiments/volcano-ic/figures/`, and any affected paper or report figures.
  Update their canonical data or drawing source and regenerate rendered files
  in the same change as the underlying finding. Refresh a paper PDF when its
  cited conclusion or figure changes, following `paper/README.md`.
- Check `experiments/ic-candidate-catalog/curves.yaml` and the associated
  isogeny-route records before adding or connecting curves. Preserve immutable
  curve IDs and ordered routes. A proposed neighbor or conductor guess is not
  a verified edge; mark it as such and keep `ISO1` gated by the map and
  transport checks in `AGENTS.md`.
- If no new graphable fact survives review, record that outcome and list the
  graphs checked. Negative or inconclusive searches still get the report,
  diagram, and PDF. Do not change a canonical graph merely to imply progress.
- Recheck all changed figures against their cited run records and inspect the
  report/PDF together before completing the research change.
