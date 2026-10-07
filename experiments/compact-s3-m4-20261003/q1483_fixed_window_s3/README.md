# Q1483: fixed-window compact S3 search

The [pre-registered design](design_protocol.json) makes one controlled change
to Q1482's exact window-base search: it selects the cyclic window beginning
at position zero for each of the four leaves before SAT search. Every Q1482
planted witness lies in this slice, so the unpinned planted cells have known
solutions. The ordinary N53/N83 public points and target-preimage lists stay
byte-identical to Q1482. The exact Q1481 usable base sizes and set digests
also stay fixed.

This removes uncertainty about window positions from the Boolean search and
allows the native theory to see only `d` free leaf coordinates. It restricts
the accepted relations to one orientation of each leaf. At N131 that is a
small part of the full Frobenius orbit-union base, so even a successful N83
slice cannot be projected as full-base N131 yield or a complete solve.
Q1483 remains a `Q` proposal with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`.
