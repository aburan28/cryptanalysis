# Leased coefficients and reusable Macaulay layouts

Round101 connects compact packed ANF leases to the ring-only Macaulay layout
from round92. The Python query does not expand the lease into a dense coefficient
table, sort its masks, or construct polynomial sets. A new native decoder maps
each compact mask to the immutable support with charged binary searches.

The adapter rejects duplicate masks, masks outside the declared degree envelope,
invalid coefficient padding and shape mismatches. Each call allocates fresh
decoded equation indices, matrix rows, pivots and proof nodes. Only the symbolic
support, columns, multipliers and scatter map are reusable. A live lease remains
held through production, independent certification, proof materialization and
equation/curve replay. No target answer or numerical elimination state is reused.

The original dense-input Macaulay library remains an oracle in the tests. The
adapter preserves its ABI and hash-binds its generated source to round92. Both
optimized and UBSan libraries are rebuilt on each tested platform. The existing
portable F4 producer remains the default and the fallback.

## Frozen experiment

The panel contains two distinct six-variable planted PDP controls, all five
nine-variable and all five twelve-variable controls from the round100 panel,
and one dense twelve-variable MQ control. These are component diagnostics, not
natural relation-yield estimates or complete IC/rho results.

| Arm | Matrix attempt | Symbolic setup |
| --- | --- | --- |
| `baseline` | None; original F4 | Outside the query |
| `fresh2` | Multiplier degree two | Created inside the query, as a diagnostic ablation |
| `reused2` | Multiplier degree two | Ring-only layout prepared before the query |
| `reused3` | Multiplier degree three | Ring-only layout prepared before the query |

The input envelope degree is six for PDP and two for MQ, capped by the variable
count. These choices depend on the input family, not observed coefficients.
The fixed producer budget is 80 million logical work units; a matrix attempt
can consume at most 20 million. Failed matrix attempts and failed certificate
checks consume their respective shared budgets before F4 receives the remainder.
Producer counters describe different operations across algorithms and are not
CPU instruction counts or wall-time ratios.

Every arm uses completion-first, release-live independent certification. Limits
are two million proof nodes, 4096 matrix rows, 200 million checker work units,
and two million peak live proof terms. Twelve-variable degree-three layouts have
9269 rows and therefore retain an explicit row-budget failure followed by F4.
There is no silent removal of those cells from the comparison.

One fresh process performs each complete query. Initialization, reusable setup
and artifact serialization are outside the query timer; fresh target-dependent
coefficient descent, production, certification, proof materialization, bounded
extraction, independent equation/curve replay and lease teardown are inside.
The `fresh2` arm additionally charges symbolic layout creation and destruction;
it is not the target-independent-setup online policy. Process peak RSS includes
startup and artifact storage and is not labeled query-only memory.

Correctness controls run every cell in optimized and UBSan builds. Diagnostics
use one warmup and four predeclared rotating arm orders, retaining all process
failures and 60-second timeouts. The native-free audit independently checks the
derivation DAG, Boolean Gröbner basis and exact small Boolean zero set, validates
all reported live-proof accounting, compares `fresh2` with `reused2`, and compares
canonical bases whenever different algorithms both certify a result.

## Reproduction and claim boundary

```sh
python3 experiments/groebner-perf-20260924/round101/run_validation.py \
  --output leased-macaulay-evidence --diagnostics
```

The driver requires committed source bytes and uses the shared heavy-work lock.
The two-platform GitHub workflow runs correctness controls without claiming CPU
speedups. All local wall times remain exploratory; qualified, aggregate and IC
online speedups remain null until the required isolation and end-to-end gates
are met. This integration establishes neither a novel asymptotic algorithm nor
a generic GPU speedup. See `RESULTS.md` for the frozen panel's outcomes.
