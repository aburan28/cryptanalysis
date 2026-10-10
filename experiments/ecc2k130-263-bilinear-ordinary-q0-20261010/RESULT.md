# Free-selector Q1420 bilinear-leaf gate identifies selector search as the next bottleneck

On the exact first public-target query of workload `eee7f6ee5f6b`, both
selector-weighted W24 circuits entered CryptoMiniSat search on the source and
degree-263 descendant curves, and all four attempts reached their frozen
limits with `BOUNDED_UNKNOWN`. The [independent archive audit](runs/R1/audit.json)
checked every formula and transcript, including 939, 561, 654, and 642 printed
restart rows in run order. This is the ordinary-query counterpart to the
[fixed-leaf result](../ecc2k130-263-bilinear-leaf-20261010/RESULT.md):
the leaf-product rewrite made several fixed-coordinate releases satisfiable,
but that status change did not carry across this free-selector gate. The
result directs the next PDP experiment to selector search and its coupling
to the x/inverse words, before scaling a held-out query stream.

The [precommitted protocol](PROTOCOL.md) and source commit `38b8dc6c3` pin
the single public target, four verified raw x-lifts per curve, six free W24
selectors, four projective S3 intermediates, one-thread CryptoMiniSat 5.14.7,
and the 120-second internal / 150-second external / 4-GiB RSS limits. The
source and descendant each retain `B=16,772,828` distinct subgroup-usable
factor-base points before sign folding. Each named-input encoder reproduced
the archived projective-S3 comparator byte for byte before building a
variant. The four complete XCNFs, named-input maps, formula receipts, and
[checked Sage runtime information](runs/R1/runtime-info.json) were committed
as `52d8c791b`, before the first solver launch. Formula and transcript hashes
are in [runs/R1](runs/R1).

| Curve | Circuit | Variables | Ordinary clauses | Native XORs | Total constraints | Added constraints vs comparator | Status | Solver wall s | Search evidence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| Source | archived projective S3 | 362,270 | 374,836 | 236,085 | 610,921 | reference | `BOUNDED_UNKNOWN` | 123.390 | 148,225 final conflicts |
| Source | `wz_only` | 367,382 | 397,300 | 233,709 | 631,009 | 3.288% | `BOUNDED_UNKNOWN` | 129.212 | 939 restart rows; 444,165 final conflicts |
| Source | `both_products` | 554,780 | 367,510 | 431,037 | 798,547 | 30.712% | `BOUNDED_UNKNOWN` | 121.899 | 654 restart rows; 248,257 final conflicts |
| Descendant | archived projective S3 | 367,260 | 374,872 | 241,015 | 615,887 | reference | `BOUNDED_UNKNOWN` | 139.131 | 303,145 final conflicts |
| Descendant | `wz_only` | 372,360 | 397,336 | 238,627 | 635,963 | 3.260% | `BOUNDED_UNKNOWN` | 121.152 | 561 restart rows; 192,770 final conflicts |
| Descendant | `both_products` | 555,852 | 367,546 | 432,049 | 799,595 | 29.828% | `BOUNDED_UNKNOWN` | 150.074 | 642 restart rows; external wall guard |

The source and descendant `wz_only` cells and source `both_products` cell
exited 15 with `s INDETERMINATE`; descendant `both_products` was killed by the
150-second external wall guard after live restart progress. Sampled peak RSS
was 342.9, 368.5, 460.7, and 459.4 MB, respectively, below the guard. The
first unprivileged source/`wz_only` invocation failed at the sandbox's `ps`
RSS preflight **before solver launch**; its distinct
[`PRODUCER_FAILURE` receipt](runs/R1/source_wz_only_sandbox_preflight.json)
records that event. The guarded run then used the frozen input unchanged.

Each observed cell contains one capped target-dependent PDP attempt and zero
verified decompositions. These censored outcomes do not estimate the true
decomposition probability or prove a target unsatisfiable. There is no
relation row to insert, so novel rank is `null`; final matrix work and online
target recovery also remain unmeasured for this proposal (`candidate_id:
null`). The host lacks a CPU-isolation receipt and each cell ran once, so
wall values are exploratory diagnostics; the paired outcome is the audited
solver status. Formula build receipts include a byte-for-byte comparator
rebuild and therefore are not isolated construction timings for the new
circuits. The [parent projective result](../ecc2k130-263-projective-s3-20261010/RESULT.md)
preserves the comparator's setup and raw transcripts.

The next controlled experiment should use the already verified six-distinct
leaf witness to release one entire selector/x/inverse block at a time, at
both early and late S3 positions. Freeze a 4/8/12/16/20/24-bit selector
freedom ladder and compare the parent, `wz_only`, and `both_products` circuits
on the same signed target under a modest matched cap. This locates where
free selector search overwhelms the z-side propagation gain. If some ladder
steps verify SAT, test the resulting pivot or branching policy on held-out
ordinary queries, charging failed attempts and full relation/rank checks.
The larger `both_products` formula should advance only if its selector-freedom
behavior justifies its 29.8–30.7% constraint overhead.

Reproduce the archive-only audit with:

```sh
python3 -B experiments/ecc2k130-263-bilinear-ordinary-q0-20261010/audit.py
```
