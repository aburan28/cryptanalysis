# Canonical graph and registry review

Checked the existing crypto boundary ledger, `docs/index-calculus-scoreboard.html`,
`docs/ic/progress-timeline.json`, and `docs/performance-gains/data.json`. Their
rows concern IC/rho costs, historical experiments, and unrelated optimizations.
This run has no solver, timed comparison, candidate promotion, or new cost
measurement, so those data and rendered copies remain unchanged.

Checked crypto's `docs/curves/ic/curves.yaml`,
`docs/curves/jacobian-candidates.json`, and cryptanalysis's
`experiments/ic-candidate-catalog/curves.yaml` at source commit
`b76f7ef8a2a9658efcb4e8ba75006edab2d81cb5`. The catalog/mirror entries are
toy13 and the ECC2K-130 source/descendant; the Jacobian candidate has unresolved
curve binding. This study replays two already recorded crypto Koblitz fixtures;
it finalizes no new elliptic curve, isogeny route, or Jacobian construction.
Its exact representation records are local to this arithmetic replay and are
not substituted for archived differently encoded IDs. No catalog claim or
registry adapter is promoted.

The existing `figures/` and `experiments/volcano-ic/figures/` inventories cover
attack taxonomy and conductor/isogeny results. Neither an isogeny nor a
conductor/endomorphism result is added here. The new verified representation
links and product obstructions are drawn in this run's editable
`destinations.dot`, with SVG, PDF and PNG copies; recorded check counts have
their own source and vector graph.
