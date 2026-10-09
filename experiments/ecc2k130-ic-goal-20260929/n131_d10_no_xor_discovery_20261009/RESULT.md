# Preserve exact d10 CNF bridges through solver simplification

The frozen first d10/m15 precomputation query has an exact CNF bridge and
fill-limited XOR projection. On the unchanged query, CryptoMiniSat's default
XOR discovery recovered 3,062 XORs from CNF during simplification and then
reported a 46,201-row by 101,048-column XOR component, above its frozen
10,000-row and 15,000-column Gaussian limits. Thus the earlier 2,645-row
input geometry did not persist through that solver policy.

Proposal `Q20261009190000` changes only the solver policy to `--xor=0`, which
the installed solver describes as disabling discovery of long XORs. The
61,304 native XOR records in the projected input remain present. The exact
input hash is `86b670f38242a04e3aa25287285d218f3407131084b49a97e34ea435f2859b7e`;
the one precomputation point, seed `2026100618`, one worker, 4-GiB combined
RSS cap, matrix limits, and source formula are held fixed. Candidate and run
IDs are null because this is a same-query PDP solver-stage method screen, not
a complete IC pipeline. The 90-second preflight and 580-second full attempt
were both frozen in [protocol.json](protocol.json) before either solver launch.

The [independent preflight audit](preflight/independent_audit.json) checked
the protocol, formula and solver hashes, launched command, terminal solver
record, process drain, and raw logs. Three matrix initializations appeared
before the 90-second wall cap. None reported a rediscovered XOR or an
oversized component; the largest reported component stayed at 2,645 rows,
and the widest at 5,097 columns. The preflight ended `CENSORED_TIME` after
90.119 seconds of solver-stage wall time, with zero model/status lines and
407,011,328 bytes sampled peak combined RSS. The solver also logged 113
automatic poor-performance matrix disables, so preserved component geometry
does not imply that Gaussian elimination is useful for search.

The preflight gate for the full attempt requires at least two matrix
initializations, no rediscovered XORs, no oversized matrix, and a terminal
resource-bounded run. This gate passed. Any returned model in the full
attempt must satisfy the projected, bridge, and original XCNFs after reverse
lifting and then pass an independent installed-Sage group, factor-base, and
folded-row replay before it counts as a relation. The solver-stage clock
excludes source formula construction and the two exact transforms, so it is
not a one-target online IC time.
