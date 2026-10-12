# Q1527: native quadratic gates compress the exact N53 and N83 S3 handoffs

Replacing every Tseitin AND triple with its native quadratic ANF equation
reduces the exact **N53 pinned** handoff from 15,615 to **9,997 equations**
and the exact **N83 pinned** handoff from 127,129 to **44,627 equations**.
The reductions are 5,618 and 82,502 rows respectively, with the same
variables, factor-base constraints, S3 link, and frozen complement points.
The pinned N53 solver assignment satisfies all 15,615 original XCNF rows
and independently replays the group relation. The unpinned N53 positive,
one ordinary N53, the pinned N83, and two ordinary N83 cells each reached
the 90-second wall cap. The new representation cuts formula size and N83
peak memory; it has not yet reduced ordinary search to a completed solve.

| Exact input | Q1525 clause ANF equations | Q1527 native gate equations | Q1527 status | Child user CPU s | Exploratory wall s | Peak RSS MiB | Conflict evidence |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| N53 pinned positive | 15,615 | **9,997** | `SAT_VERIFIED` | 0.093 | 0.189 | 11.2 | final 6,904 |
| N53 unpinned positive | 15,509 | **9,891** | `WALL_CAP` | 39.07 | 90.06 | 10.9 | periodic ≥100,000 |
| N53 ordinary | 15,509 | **9,891** | `WALL_CAP` | 68.11 | 90.09 | 10.7 | periodic ≥480,000 |
| N83 pinned positive | 127,129 | **44,627** | `WALL_CAP` | 72.57 | 90.08 | 50.5 | periodic ≥1,230,000 |
| N83 ordinary selected | 126,963 | **44,461** | `WALL_CAP` | 80.83 | 90.08 | 48.9 | periodic ≥850,000 |
| N83 ordinary holdout | 126,963 | **44,461** | `WALL_CAP` | 88.18 | 90.08 | 51.2 | periodic ≥850,000 |

The Q1525 baseline used the same six source XCNFs, binary, options, and
90-second wall boundary. Its N53 pinned solve reported the same 6,904
conflicts. Its N83 peak RSS values were 68.0–80.4 MiB; Q1527's were
48.9–51.2 MiB. The host has no isolation receipt, so CPU and wall ratios
are exploratory. The solver's requested 30-second CPU cap and child
30/35-second RLIMIT were not enforced on this Darwin host; the outer
90-second wall cap was effective. Periodic conflict counts are lower
bounds for capped rows, not terminal totals.

## Exact representation and identity

Q1519's circuit has **2,809** shared AND gates at N53 and **41,251** at
N83. [gate_convert.py](gate_convert.py) rebuilds each source formula,
checks its exact XCNF SHA-256, and replaces a gate's three contiguous
clauses with `z XOR (a AND b) XOR 1 = 1`, DPLL-ANF's XOR-one convention.
It retains every other clause and native XOR row. The two Lean-checked
identities in [FORMALIZATION.md](FORMALIZATION.md) prove the local gate
equivalence and its preservation inside a conjunctive formula. The
[validator](validate.py) also checks the truth table of every emitted gate,
regenerates and byte-compares all six archived ANF files, verifies source
and solver hashes, and independently replays the N53 positive model.

The N53 curve is `EC1N53Ckb1hf77aab617904`, with **B=24,062** actual
usable points and **K=227** folded columns. Its packed orbit-key digest is
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`;
Q1519's independently enumerated signed-point digest is
`356ebb34476f44b89d376e04fe4b03570a0a4cf3dfe0cd722309d7ea083ccc18`.
The N83 curve is `EC1N83Ckb1h876c2921cb64`, with **B=30,977,592**,
**K=186,612**, and point-file digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
This is proposal `Q1527`, a `PDP4sat` stage diagnostic with null candidate
and run IDs and `isogeny: "none"`.

The [protocol](protocol.json) froze the solver, six source and transformed
input hashes, order, and caps before the measured panel. The compressed
formula archives, [raw receipts](runs), [analysis](analysis.json), and
pre-protocol [smoke logs](smoke/README.md) retain every outcome. The smoke
N83 20-second cap has no mathematical UNSAT interpretation.

## Degree-131 work boundary

The three ordinary Q1527 rows supplied zero verified relations and zero
rank increments under their caps; cost per useful relation is censored.
Conflicts are not field multiplications or pair additions. Q1505's
separate conditional independent-first-pair scan model remains
`2^123.289` batch multiplication calls for N131 relation supply. Q1526's
separate conditional W≤7 full pair-index model is `2^86.185` counted
pair-add attempts. Neither includes every phase of one target in a common
unit. The fully charged N131 one-target `2^x` projection stays unset, so
this experiment supplies no challenge-run gate.

The next representation experiment should inline selected low-fanout AND
gate outputs into the ANF XOR rows, preserving the frozen handoffs and
original-formula replay. The current quadratic encoding retains almost
all AND output variables; that is a concrete remaining search dimension.
A target-conditioned second-pair search is still the algorithmic gate for
reducing relation-supply work rather than only circuit size.

Recheck the archived panel and Lean module with:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1527_native_gate_anf/validate.py
cd experiments/compact-s3-m4-20261003/q20261012_q1527_native_gate_anf/lean && lean Gate.lean
```
