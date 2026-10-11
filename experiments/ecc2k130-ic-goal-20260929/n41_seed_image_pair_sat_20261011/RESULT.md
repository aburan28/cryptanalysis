# Source-image constraints inside the N41 target-conditioned circuit

The N41 two-pair circuit now enforces the seed-conditioned product image **during Boolean search**: each pair product is computed as `p=a²+sa`, with nonzero source masks `a` and `a+s`. The known public-row assignment satisfies the complete XCNF. In bounded unpinned searches, the positive middle point and two target-derived controls all reached `BOUNDED_UNKNOWN` at the 35-second parent cap. This test isolates a solver bottleneck: the product-image gate that rejected nine concrete relaxed witnesses in the [513-point panel](../n41_target_derived_join_panel_20261011/RESULT.md) does not by itself make these unpinned searches terminal.

## Exact circuit change

The seed bits remain free and both 41-bit pair reciprocals are free. Instead of assigning each pair an independent 11-bit product, the circuit assigns one six-bit source mask `a` and forms the second mask as `a+s`. It enforces `a≠0`, `a+s≠0`, and `s≠0`, then computes the exact product image `a²+sa` before the pair and target S3 equations. The corresponding relaxed circuit left the 11 product bits free. This source-image condition is necessary for an exact W6 pair; source rationality, folded-column compatibility, and curve signs remain separate checks.

The [frozen protocol](protocol.json) fixes the positive middle point and controls 23 and 229 from the seeded public-target panel. Both controls were relaxed group hits and exact transported-pair misses. The [construction source](circuit.py) and [full-assignment checker](prepare.py) are bound to their upstream arithmetic and fixture hashes. The [solver protocol](solver_protocol.json) fixes one CryptoMiniSat worker, a 30-second solver flag, a 35-second parent cap, and a 4-GiB combined RSS guard. The [terminal audit](audit.json) checks formula hashes, actual search restarts, raw logs, caps, and status interpretation.

| Unpinned middle-point query | Variables | AND gates | Clauses | Native XOR rows | XCNF bytes | Terminal status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Known positive | 3,186 | 1,916 | 5,879 | 1,164 | 185,896 | `BOUNDED_UNKNOWN`, 35.076 s |
| Target-derived control 23 | 3,191 | 1,916 | 5,879 | 1,169 | 186,991 | `BOUNDED_UNKNOWN`, 35.072 s |
| Target-derived control 229 | 3,183 | 1,916 | 5,879 | 1,161 | 187,050 | `BOUNDED_UNKNOWN`, 35.281 s |

Peak combined RSS was 69.4 MB for the positive and below 47 MB for each control. The positive formula has 72 more AND gates and 104 more total variables than the prior free-product derivative formula; computing the conditional product introduces auxiliary multiplication wires despite reducing the primary source choices. All three solver logs contain active restarts and no terminal SAT or UNSAT line. These are capped local stage diagnostics, with formula construction recorded separately in the protocol.

The next implementation should use the rank-`d-1` product image as a **conditional linear constraint** when a seed family is selected, then generate target-compatible pair outputs with native linear algebra. Re-encoding the same image as an additional bilinear multiplier has not cleared the unpinned N41 gate. The full method remains a component design (`candidate_id: null`).
