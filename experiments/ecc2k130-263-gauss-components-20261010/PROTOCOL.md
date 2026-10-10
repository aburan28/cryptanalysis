# Q1420 native-XOR component-selection gate

The previous wide-Gaussian Q1420 run admitted five large matrices on each
source/degree-263 descendant ordinary Q0 circuit, entered search, and reached
the 150-second wall cap. A read-only screen of the raw native-XOR graph
showed a component containing all 144 W24 selector input bits below several
larger components dominated by projective-S3 inputs. This gate asks which
matrices CryptoMiniSat actually selects when admission is restricted, and
whether the smaller selector-size window changes capped search, memory, or
verified relation status. Raw graph components are only a predictor:
CryptoMiniSat's preprocessing may change their sizes and order.

The exact frozen inputs are the archived `source_wz_only` and
`descendant_native_wz_only` XCNFs for the first public query of workload
`eee7f6ee5f6b`. Both W24 bases have `B=16,772,828` subgroup-usable points
before sign folding. `source.json` pins the parent commit, XCNF archives,
named-input and formula receipts, prior wide runner/auditor, binary, and
resource caps. `component.py` records the raw native-XOR connected components
and named-input distribution on both curves. The four matrix policies are:

| Label | Max rows | Max columns | Max matrices | Auto-disable Gauss |
| --- | ---: | ---: | ---: | ---: |
| `default` | 2,000 | 1,000 | 5 | 1 |
| `selector_window` | 8,000 | 12,000 | 1 | 0 |
| `largest` | 20,000 | 30,000 | 1 | 0 |
| `all_five` | 20,000 | 30,000 | 5 | 0 |

These labels describe CLI limits, not the matrix actually selected; the
auditor reads dimensions and counts from each transcript. Both curves receive
each policy in the listed order. Every cell uses one thread, CryptoMiniSat
5.14.7, native-XOR XCNF, a 2,000-conflict cap, 120-second internal time
limit, 180-second external wall guard, and sampled 4-GiB RSS guard. There is
one attempt per cell. The conflict cap is a common *search diagnostic*, not
an equal-work metric across Gaussian policies; record process CPU, wall,
memory, Gaussian selection, final conflicts, restart trajectory, and all
failures. The host lacks a CPU-isolation receipt, so timing ratios remain
exploratory.

Commit `PROTOCOL.md`, `source.json`, `component.py`, `experiment.py`, and
`audit.py` before generating component receipts or solver cells. Then run
`python3 -B .../component.py --write` and
`python3 -B .../experiment.py freeze`; commit both curves' component
inventories and the eight exact input/policy hashes before launching solvers.
Run `python3 -B .../experiment.py all` in an environment that permits the
`ps` RSS sampler; preserve a failed preflight separately from solver search.
Finally run `python3 -B .../audit.py --write` to verify inputs, complete
transcripts, caps, matrix selections, and any SAT assignment's native XORs
and signed group sum for the exact public query.

The decision is evidence-gated. If the 8,000-row window selects the raw
selector component and improves a verifiable outcome or search trajectory
without greater charged cost, carry that policy to held-out ordinary queries
and relation/rank accounting. If it selects a different component, report
that directly and avoid attributing an effect to selectors. If all cells are
capped, use the component inventory to design a direct selector-derived
field-linear propagation experiment; matrix admission alone is insufficient.
No one-query solver-stage status is promoted to a full IC candidate or a
single-target online IC/rho comparison.
