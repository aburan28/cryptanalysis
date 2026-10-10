# A free-selector identity validates on both curves; field-linear factoring cuts descendant XOR literals

The exact W24 identity `alpha*x*z=(x+alpha)^2` was added to leaf 0 while
all 24 selector bits remained free. On the equal-`B=16,772,828` source
and oriented degree-263 descendant factor bases, both strengthened
fixed-witness controls were `SAT_VERIFIED_GROUP`. The paired ordinary Q0
source and descendant solves, with and without the identity, all entered
search and reached the 2,000-conflict cap as `BOUNDED_UNKNOWN`. The
[independent audit](runs/R1/audit.json) replays the frozen full inputs,
every added AND/XOR record, four complete SAT models, and their exact
six-leaf group sums.

The source curve is `EC1N131Ckb1h136f03e58c98`; the descendant is
`EC1N131Cbinh833014327b07` on `IW1E263d1hadee4e69fa3d`. Workload
`eee7f6ee5f6b` supplies the first public Q0 point. Both W24 bases
have 16,772,828 distinct usable points before orbit folding. Q1420
remains a proposal with `candidate_id: null`.

The [protocol](PROTOCOL.md), [source pins](source.json), producer, and
auditor were committed in `7409a7afa` before the first eight formula
hashes were frozen in `54a8f5030`. A sandbox denial of `ps` stopped the
first launch before any solver subprocess began. The [failure receipt](runs/R1/launch_failure.json)
and first manifest are preserved. The Darwin `libproc` sampler was
committed in `2a6ba67fe`, and all eight *identical* formula hashes were
reconstructed and refrozen with the corrected runner hash in
`84fb25cf1` before search. The final [cell manifest](runs/R1/cells.json)
has SHA-256 `1fbdc7ca4746fbfdb9bd27814212b7bc199fc69b377c5bf9c922fac9967260bb`;
the source manifest SHA-256 is
`da551faa90286fb0f1ce1aa8ebf601aa9eeb1303889266f3a7f67a6584ae56e7`.

The control inputs reuse the archived x0 fixed-witness unit clauses.
Ordinary Q0 has **zero extra unit clauses** in either arm: six W24
selectors and the choice among four raw target lifts remain free. The
group auditor enumerates signs after solving.
For each `x0[i]&z0[j]`, the strengthened XCNF adds a Tseitin variable
and three clauses, then 131 native-XOR field-output equations. This adds
17,161 variables, 51,483 ordinary clauses, and 131 native-XOR records,
or 51,614 constraints. The source has `alpha=1`; the descendant's
`alpha` has Hamming weight 69 in the fixed polynomial basis.

All cells used pinned CryptoMiniSat 5.14.7, one thread, native XORs,
the same default Gaussian limits for ordinary Q0, and a sampled 4-GiB
RSS guard. Controls had 20,000 conflicts and 30/40-second
internal/external wall caps. Ordinary Q0 had 2,000 conflicts and
120/45-second caps. Construction times include archive decompression,
hash verification, and full-input assembly. The solver interval starts
at subprocess launch; model audit is separate. The [runtime receipt](runs/R1/runtime-info.json)
records the environment and lack of host-wide CPU isolation.

| Cell | Audited status | Construction wall s | Solver wall s | Child CPU s | Peak sampled RSS MiB | Final conflicts |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Source control, base | `SAT_VERIFIED_GROUP` | 0.050 | 3.952 | 0.462 | 133.77 | 0 |
| Source control, identity | `SAT_VERIFIED_GROUP` | 2.055 | 5.839 | 0.557 | 130.36 | 0 |
| Descendant control, base | `SAT_VERIFIED_GROUP` | 0.191 | 3.304 | 0.485 | 131.59 | 0 |
| Descendant control, identity | `SAT_VERIFIED_GROUP` | 4.262 | 5.578 | 0.584 | 141.55 | 0 |
| Source ordinary Q0, base | `BOUNDED_UNKNOWN` | 0.052 | 21.851 | 1.732 | 168.66 | 2,001 |
| Source ordinary Q0, identity | `BOUNDED_UNKNOWN` | 0.696 | 13.888 | 1.227 | 170.12 | 2,001 |
| Descendant ordinary Q0, base | `BOUNDED_UNKNOWN` | 0.624 | 12.703 | 1.387 | 149.78 | 2,002 |
| Descendant ordinary Q0, identity | `BOUNDED_UNKNOWN` | 4.170 | 28.163 | 3.040 | 192.38 | 2,001 |

The four ordinary cells spent 82.71 seconds in recorded construction
plus solver wall intervals: 35.230 seconds for the two base cells and
46.918 seconds for the two strengthened cells. Across all eight cells,
that sum was 107.378 seconds. Each ordinary cell printed 11 restart
rows and a final conflict count. One query per curve and one run per arm
on an unisolated host do not support a CPU speed ratio. The zero verified
ordinary rows leave novel rank unavailable; matrix work and target
descent were not invoked in this panel.

Each of the four control models passed its *complete* XCNF, including
359,658 ordinary clauses and 225,325 native XORs in the source base
control, or 411,141 and 225,456 with the identity. Descendant counts
were 359,100/229,902 and 410,583/230,033. Every control replayed the
archived six masks, four finite S3 intermediates, and the exact all-plus
signed target. The independent tail check reconstructed 17,161 gates
and 131 field equations for each strengthened cell using a different
field-reduction order. The first auditor invocation had a Python
module-name collision before checking any row; its [failure record](runs/R1/audit_import_failure.json)
and the successful audit before the stronger tail check are retained.

The [factorization calculation](runs/R1/factorization_model.json) gives
a concrete next encoding. Introduce `y=alpha*x` as 131 GF(2)-linear
equations and impose `y*z=x^2+alpha^2`. This is equivalent to the
tested identity because `alpha` is fixed and nonzero. For source
`alpha=1`, the direct product uses 42,941 XOR-literal occurrences;
factoring adds 131 map occurrences to the same 42,941 product
occurrences, so it offers no size advantage. For dense descendant
`alpha`, the direct product uses **1,013,646** occurrences, while the
factored map and product use **8,029 + 42,941 = 50,970**, a 19.887-fold
exact reduction in those occurrences. Both encodings retain 17,161
AND gates; the factored one adds 131 linear variables and 131 XOR
equations. Arithmetic equality passed on all 16 frozen curve/mask
pairs. These counts predict an encoding-size reduction, not a solver-time
or IC improvement.

The next controlled PDP gate is to implement that field-linear factoring
for the descendant, compare exact paired Q0 and held-out ordinary queries
under the same caps, and charge every attempt and verified row before
testing rank. The full feasibility study still requires the equal-size
four-base comparison, charged n37/n41/n53 logarithm recoveries and
matched rho, and explicit n131 transfer accounting.

Replay the analytical count and archived-input audit with:

```sh
python3 -B experiments/ecc2k130-263-free-identity-20261010/factorization_model.py --write
python3 -B experiments/ecc2k130-263-free-identity-20261010/audit.py --write
```
