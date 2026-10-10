# Ten linear-source summands on the exact degree-41 public point

The exact W5 source gives **17 rational masks, 340 distinct projected subgroup
points, and 14 signed-Frobenius columns** across ten rotations on
`EC1N41Ckb1h7d5e80d3c4d0`. The [independent checked-Sage audit](sage_geometry_audit.json)
replayed every mask and projected group point against the frozen
[geometry census](geometry_result.json). Its ten-block signed source size is
34 per block, giving `34^10 / 549756390943 = 3755.08` expected raw-fiber
representations under the uniform-sum model. That value is a prediction,
not a relation measurement.

The ten-leaf balanced S3 formula passed a full known-assignment XCNF check
and exact raw group replay on a separately constructed target. The
[frozen protocol](protocol_v2.json), [control](control.json), and
[preflight receipt](preflight_v2/receipt.json) bind its source hashes and
input policy. The control formula has 27,037 variables, 47,777 CNF clauses,
11,285 native XOR rows, and 15,370 AND gates. A first decoder version
treated a constant circuit wire as a model variable; its
[failure receipt](preflight/failure.json) and source are retained, and the
versioned correction passed before the public query.

The one-worker public-point query used the same previously frozen N41
point as the seven-source comparison. Every source mask, sign, and middle
point was unpinned. Its formula has 26,896 variables, 47,462 CNF clauses,
11,249 native XOR rows, and 15,265 AND gates. CryptoMiniSat logged 1,013
search restarts and reached the parent solver cap. The
[public result](public/result.json), [search log](public/solver.stdout.txt),
and [terminal custody audit](public/terminal_audit.json) record
`CENSORED_TIME`, 115.426 seconds online, 115.169 seconds in the solver,
190,726,144 bytes sampled combined peak RSS, and zero verified relations
in this one attempt. These wall observations are exploratory on an
unisolated host.

The exact geometry and control show that the small factor base and ten-link
formula are well defined. The next experiment should use an exact native
group join on this same public point to check whether the predicted
representations exist, then select a decomposition kernel that can exploit
them without a full-width generic S3 search. A challenge-width W14 ten-source
SAT query is gated on that kernel or a successful comparable ordinary-query
control. The proposal retains `candidate_id: null` until the full relation,
rank, factor-log, and target pipeline is specified and measured.
