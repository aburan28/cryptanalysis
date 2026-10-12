# Round 58: ordered columns in sparse F4 matrices

Native sampling of the frozen `chain_filter` producer identifies sparse matrix
reduction and polynomial merging as substantial costs. This opt-in experiment
numbers the monomials in each symbolically closed matrix once, in descending
monomial order. Sparse rows then contain ascending column numbers, so their
leading column is the first entry. A bounded array maps columns to pivot slots.
The existing proof-aware XOR routine performs the same eliminations. Returned
rows are converted back to the original numeric monomial representation.

The column map is a bijection on the complete symbolic support. Applying it
commutes with polynomial XOR, and its first entry represents the same leader
that the baseline scans for. Input row order, pivot choices, proof operations,
output order, and charged term counts therefore remain unchanged. Boolean
field pairs, checked-chain pruning and the independent certificate checker
are unchanged. The differential audit requires identical completed proofs and
identical integer work traces, including failed budget prefixes.

Every matrix gets fresh coefficients, pivots and proof nodes. No target answer
or numerical elimination is reused. The indexed path has a fixed 262,144-column
cap; larger supports use the original sparse representation. A four-column
variant exercises both sides of the fallback in tests. The support map is
local to a matrix and is not assumed invariant across targets.

This is a representation optimization of F4, not a new F6 algorithm or an
asymptotic improvement to Gröbner basis computation. Stack samples are
diagnostic evidence. No speedup is established until a separate frozen,
load-qualified complete-query comparison includes conversion and verification.
All variants remain opt-in; application dispatch is unchanged.

Build with `python3 build.py`, run `python3 -m unittest -v test_columns`, then
`python3 validate.py --out /absolute/path/validation.json.gz` from this directory.
The build produces optimized and UBSan versions and locally compiles the
unchanged independent checker. Rebuild on each tested platform.
