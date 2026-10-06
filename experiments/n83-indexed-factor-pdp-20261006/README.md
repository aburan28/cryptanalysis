# N83 indexed-factor point-decomposition gate

This pilot changes the Boolean representation of the five W3/W4 factor x
coordinates used in the [direct-point gate](../n83-direct-point-pdp-20261006/README.md).
The curve, exact measured base, four public raw target fibers, solver binary,
one-thread resource envelope, and deterministic group circuit are held fixed.
It is a point-decomposition stage proposal with `candidate_id: null`, not a
complete IC method.

Each factor chooses three strictly increasing normal-basis positions and a
fourth greater position or sentinel 83. The sentinel contributes zero. The
[indexed selector](indexed_factor.py) rejects unused binary codes and unordered
or repeated positions, so each W3/W4 mask has exactly one positional witness.
This replaces 83 free mask bits plus a cardinality circuit with four seven-bit
position codes and decoder clauses per factor. The group circuit still
enforces rational point lifts, nonzero factor x values, four regular affine
additions, and the exact raw target point. It still omits equal-x and identity
paths.

The [small-field control](test_indexed_factor.py) checks all 15 W3/W4 masks
over a normal basis of GF(2⁵), rejects four invalid position codes, and
compares the SAT circuit with all 43 finite curve targets for a fixed pair of
factor x values. All 4 reachable targets pass CNF/XOR and group replay; all
39 unreachable targets return UNSAT. This is an exact encoding control, not
an N83 search-performance result.

The [frozen protocol](protocol.json) retains the same N83 public fixture,
measured base with B = 1,936,390 and 11,665 folded columns, 120-second
internal solver cap, 900-second process-tree cap, and 2 GiB RSS cap as the
preceding direct-mask pilot. The first N83 gate pins only the five known
planted masks; sign bits and all intermediate points stay free. Any model
must pass every CNF/XOR row, integer-field group replay, and independent
checked-Sage replay. A public-only unpinned planted attempt is required
before an ordinary relation can support promotion. All bounded failures
remain costs, never zeroes or UNSAT claims.

Even a successful N83 PDP would be one stage. The default objective remains
one unseen target's verified online DLP after reusable index/log preparation,
paired with rho on the same point and isolated host. Factor logs, final
relation matrix, target descent, recovery replay, and same-point rho are not
provided by this pilot; their times and any speedup remain unknown.

## First N83 gate

The [pinned-factor run](runs/pinned_planted_f0_v1/receipt.json) returned
`BOUNDED_UNKNOWN` at CryptoMiniSat's 120-second internal limit. It built
606,796 variables, 585,565 AND gates, 1,823,055 CNF clauses, and 19,421
XOR rows; its XCNF occupies 46,038,785 bytes. The complete watchdog interval
was 126.839 seconds with no resource guard and 664.1 MB sampled peak RSS.
Its raw solver stdout is archived as deterministic gzip with a receipt hash.
This result supplies no model or UNSAT proof. The older direct-mask circuit
had 610,956 variables,
588,330 AND gates, 1,766,030 CNF clauses, and 22,201 XOR rows on the same
pinned raw fiber; these are circuit-size diagnostics, not a speed ratio.

The next [frozen control](sign_enum_protocol.json) tries all 32 sign-bit
assignments in public order on the same pinned-mask XCNF, with the sign wire
IDs independently regenerated from the selector source. Each branch has a
10-second solver limit and the whole sequence has a 600-second process-tree
wall limit. A found model still requires complete XCNF, group, and checked-
Sage replay before any unpinned search is promoted.

The [public-order sign run](runs/sign_enum_v1/receipt.json) found a
CNF/XOR- and integer-group-verified model at branch 17 after 17
solver-reported UNSAT branches, in 11.439 seconds for the complete run.
Its SAT model and raw stdout remain local because they contain the planted
witness; the 17 solver-reported UNSAT logs are archived with hashes. The
[independent checked-Sage replay](runs/sign_enum_v1/sage_replay.json) passed:
all five points lie on the curve and in the measured base after projection,
the four additions are regular, and the exact raw fiber maps to the public
subgroup target. This clears the pinned correctness control only.

The first [public-only unpinned planted attempt](runs/unpinned_planted_f0_v1/receipt.json)
returned `BOUNDED_UNKNOWN` at the same 120-second solver limit, in 137.047
seconds of complete process-tree wall time with 530.5 MB sampled peak RSS.
All five positional factor choices and signs were free; the started receipt
records no private-fixture input. No model or UNSAT proof was returned. The
four frozen ordinary raw fibers are the next bounded diagnostic, but no
natural-yield rate or complete IC claim can follow from this failed planted
search gate.
