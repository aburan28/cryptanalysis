# A projective S3 chart admits cancellation intermediates on paired Q1420 bases

The homogeneous third summation polynomial in [PROTOCOL.md](PROTOCOL.md)
extends the frozen six-summand Q1420 source and degree-263 descendant-native
circuits to four canonical identity-or-finite intermediate nodes. Checked
Sage and an independent binary group law agree on 497,084 ordered rational
x-class triples across four small-field settings, including identity and
two-torsion classes. On each N131 curve, the first W24 leaf and its inverse
cancel to the identity at the first pair node; the remaining four archived
leaves produce a finite target, and the Boolean circuit accepts that witness
while rejecting four one-bit mutations. This establishes an exact chart for
the exceptional branch omitted by the finite-intermediate parent circuit.

The paired projective XCNFs and solver transcripts are archived and independently
checked by [audit.py](audit.py) and [R1/audit.json](runs/R1/audit.json). Both
formulas use the same public Q1420 workload `eee7f6ee5f6b`, four raw target
lifts, six leaves, one-thread CryptoMiniSat 5.14.7, and a 120-second internal
solver cap. Source and descendant each have **B=16,772,828** distinct
subgroup-usable factor-base points before sign folding.

| Policy | Finite parent vars / clauses / XORs | Projective vars / clauses / XORs | Projective build wall / sampled peak RSS | Pilot wall / sampled peak RSS | Final conflicts | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Source W24 prefix | 336,141 / 340,070 / 221,374 | 362,270 / 374,836 / 236,085 | 4.173 s / 297,336,832 B | 123.390 s / 362,905,600 B | 148,225 | `BOUNDED_UNKNOWN` |
| Descendant-native W24 | 340,630 / 339,710 / 225,935 | 367,260 / 374,872 / 241,015 | 3.864 s / 304,611,328 B | 139.131 s / 372,621,312 B | 303,145 | `BOUNDED_UNKNOWN` |

Projective chart completion adds 26,129 source and 26,630 descendant variables,
34,766 and 35,162 ordinary clauses, and 14,711 and 15,080 native XORs,
respectively. Those additions are 7.77–7.82% of parent variables,
10.22–10.35% of parent clauses, and 6.65–6.67% of parent XORs. The
construction ran with a 300-second external wall and 4-GiB sampled-RSS guard;
both completed below the caps. The pilots used a 150-second external wall and
4-GiB sampled-RSS guard, exited 15 with explicit `s INDETERMINATE` terminal
lines, and did not trip either external guard. Solver versions, commands,
formula and binary hashes, stdout/stderr, and resource receipts are bound in
the audit. The host has no CPU-isolation receipt, so the sequential wall
figures remain exploratory stage measurements. `candidate_id`, verified
ordinary relation yield, novel rank, single-target online time, and paired
rho ratio are `null` in the run record.

The source transcript prints zero final Gaussian elimination calls on its
five reported components (at most 696×760). The descendant transcript prints
positive calls on components up to 847×903. These different solver paths, plus
the larger projective formulas, prevent a causal interpretation of the
conflict-count difference. The earlier finite-chart cells on the same inputs
reached 753,756 and 757,597 conflicts at the same internal cap, with their own
archived receipts in the [parent result](../ecc2k130-263-native-w24-m6-20261010/RESULT.md).

Three failed-producer events remain separate evidence rows. The initial source
invocation stopped at a stale solver-limit key before launch. The next source
invocation ran the solver and preserved its raw transcript but failed while
writing the receipt at a stale query-index key; its wrapper wall/RSS and exact
solver exit are unknown. A sandbox then denied the `ps` RSS preflight before
the amended source retry could launch. [AMENDMENT.md](AMENDMENT.md) froze the
one actual source solver retry with unchanged inputs and limits; its full
receipt is the source pilot row above. The descendant arm ran once. The raw
failure receipts and stdout are preserved under `runs/R1/` and checked by the
independent audit.

The next gate should force the archived N131 cancellation witness through a
full native-XOR SAT solve, decode the returned leaf signs, and replay the
actual group sum and cofactor-four projection. That tests end-to-end
exceptional-branch extraction rather than only Boolean evaluation. Once it
passes, freeze a matched finite/projective ordinary-query pair with identical
Gaussian settings and budgets before expanding to more public queries. A
natural relation and rank row, including failed attempts, is the promotion
criterion for Q1420.

Reproduce the archive and transcript audit with:

```sh
python3 -B experiments/ecc2k130-263-projective-s3-20261010/audit.py \
  --out /tmp/ecc2k130-projective-audit-replay.json
```

The archived `.xcnf.gz` files decompress byte-for-byte to the original solver
inputs; the audit recomputes SHA-256, XCNF headers, ordinary clauses, and
native-XOR counts while streaming the gzip data. All Sage controls were run
through the checked repository launcher, with the
[runtime receipt](runs/R1/runtime-info.json) retained before the measured
construction and solver stages.
