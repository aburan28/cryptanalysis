# F6 chain-length and independent curve-sum controls

This experiment tests the exact bitplane separator on S3 chains with three
through six summands. It compares every target abscissa in GF(2^9) with the
packed separator and with an independent enumeration of curve sums. The latter
enumerates all points whose abscissa is in the declared low-bit factor-base
range, includes both signs, adds them in the curve group, and records the
reachable final abscissae. It does not use the S3 equation solver or its
bitplanes. Every satisfiable candidate also passes original-equation and
curve-point replay.

The frozen panel has four chains with three-bit summand coordinates and one
three-summand chain with four-bit coordinates. All 512 abscissae are tested
for each chain. The four-bit, four- through six-summand cases are retained as
explicit expected state-cap controls at the current 21-variable local bag
limit. The test will fail if a capped case is silently accepted, a candidate
status differs from either independent comparator, or a satisfiable witness
fails either replay.

Build the pinned F6 predecessor chain, including the bitplane library, then
run `validate.py --output /path/to/report.json.gz`. In this checkout, the
script verifies that the executed source files match committed source. A
separate `--runtime-root` permits a byte-identical already-built worktree;
the binary receipt and source hashes are retained in the report. The result
is a structural and correctness experiment, so `timing_eligible` is false.
Its table size depends on the terminal boundary width, while static-message
setup and witness storage still grow with chain length and local factor width.
These finite controls do not establish a new general asymptotic bound.
