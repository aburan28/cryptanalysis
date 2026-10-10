# Q1429: specialize the fixed-output right-pair S3 link

Q1428's second exact-root oracle supplies a concrete right-pair output
`v` before SAT. In the remaining equation `S3(x2,x3,v)=0`, products
with `v` are linear, so constructing the formula with constant `v`
should remove two of three nonlinear multiplications. Q1429 compares
three encodings on **the same output value**: Q1428's factored link
with variable output and assumptions (`variable_factored`), the
factored link with literal constants (`fixed_factored`), and the direct
S3 link with literal constants (`fixed_direct`). The mathematical
leaf domain is identical: two nonzero, normal-basis-weight-bounded raw
x coordinates. All three are checked against the same exact root and
four-point group relation.

The inputs are Q1428's exact N53 and N83 curves, bases, public targets,
two control fixtures, anchor 0, and lift schedule. N53 is
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062/K=227, ordinary
workload `74f2979b3e68`. N83 is `EC1N83Ckb1h876c2921cb64`,
Q1325 W≤5, B=30,977,592/K=186,612, workload `bab50a1e5f66`.
For a known-solution control, the right output is selected from the
fixture; its leaves remain free during the measured call. For an
ordinary query, all three variants use the first deterministic outer
root branch of Q1428's anchor 0. The known output is a correctness
and satisfiable-search diagnostic; only the ordinary cells inform
natural relation search. `Q1429` remains a proposal with null
candidate/run IDs and `isogeny: "none"` (`ISO0`).

The paired grid has 12 cells: two degrees, control/ordinary, and three
formula variants. One CryptoMiniSat thread receives at most 10 CPU
seconds, 100,000 conflicts, and 30 target-dependent wall seconds per
cell. Each receipt charges anchor selection, exact outer-root join,
formula construction, solver loading, SAT search, and relation checks.
The exact native conflict, propagation, and decision counters and
memory peak are retained. `BOUNDED_UNKNOWN` is censored. Wall-time
ratios are exploratory without a host isolation receipt. The grid
uses one fixed output per ordinary anchor; it is not a complete target
query. Full N131 work accounting requires ordinary relation yield,
rank novelty, final matrix work, target descent, and scalar replay in
one common unit.
