# P-256 isogeny search

This experiment turns a proposed search for exceptional curves in the NIST
P-256 isogeny class into a reproducible experiment. It separates structural
facts, reusable discovery work, per-instance mapping cost, and Pollard-rho walk
speed instead of treating scalar-multiplication benchmarks as ECDLP results.

## First structural result

For P-256,

```text
t = p + 1 - n
D_pi = t^2 - 4p
     = -455213823400003756884736869668539463648899917731097708475249543966132856781915
```

The repository contains and verifies the complete factorization

```text
|D_pi| =
  3
  * 5
  * 456597257999
  * 1428624589419343516204097
  * 46523541035814968339936406074986559003387.
```

The factors are distinct and their primality is checked with recursive
Pocklington certificates and deterministic 64-bit Miller-Rabin leaves. Since
`D_pi` is a fundamental discriminant,

```text
Z[pi] = O_K.
```

Consequently every curve in the `F_p`-isogeny class has the same maximal
endomorphism order. There are no vertical volcano levels to explore. The CM
field is neither `Q(sqrt(-3))` nor `Q(i)`, excluding `j = 0`, `j = 1728`, and
extra geometric automorphisms. A non-scalar endomorphism has norm at least
`ceil(|D_pi|/4)`, a 256-bit lower bound, so a useful low-degree GLV-style
endomorphism is also excluded.

The remaining search is therefore a horizontal class-group search for:

- an explicit low-cost path from P-256;
- measurable constant-factor arithmetic improvements; or
- evidence for a genuinely non-generic ECDLP algorithm.

Absence of such a result in a finite traversal is not proof that none exists.

## Frozen exploratory result

The protocol and first run were developed together, so the frozen run is
**retrospective and exploratory**, not a held-out speed experiment. The exact
structural conclusions do not depend on host timing. On the unisolated initial
host, five baseline trials averaged 139,559 canonical rho iterations/s with a
nominal 95% interval of 137,887–141,232 iterations/s. This is a Python control
measurement only. No isogenous candidate was timed, no mapping cost was
measured, and no ECDLP speedup is claimed. The toy control recovered scalar
4242 in 55 iterations.

The frozen artifacts are in [`results/initial`](results/initial), the experiment
contract is [`protocol.json`](protocol.json), and the run accounting is
[`receipt-initial.json`](receipt-initial.json). Verify them with:

```bash
python scripts/verify_frozen.py
```

## Sage depth-one result

A SageMath 10.6 run on 2026-10-06 retained six explicit horizontal neighbors:
one each of degrees 3 and 5, and two each of degrees 11 and 13. All have
geometric automorphism order 2. A seven-trial, order-balanced rho comparison
found no significant speedup; every neighbor's paired 95% interval contained
`1.0`. The largest point estimate was `1.028x` with interval
`0.971x–1.089x`.

The full candidate maps, raw forward/reverse order-bias diagnostics, corrected
benchmark, and claim limits are frozen in
[`results/sage-depth-one-20261006`](results/sage-depth-one-20261006). This is a
six-neighbor depth-one result, not an exhaustive class-group search, and path
evaluation was not timed in that run. The later mapping follow-up below measures
it for the strongest retained candidates.

## Depth-two and depth-three follow-up

The next run reached 24 curves through depth two and 56 through depth three.
All 17 new depth-two neighbors were screened in order-balanced blocks. One
unadjusted screening interval barely excluded `1.0`, but a fresh 20-trial,
two-second holdout rejected it and the other two screening leaders. No holdout
interval excluded `1.0`; no candidate advances.

The 32 new depth-three curves retained verified explicit paths and exposed no
exceptional automorphisms. They were not subjected to another non-isolated
Python timing sweep because the complete depth-two screen and holdout found no
reproducible effect. Raw registries, screening blocks, holdout results, costs,
class-number computation failures, and claim limits are frozen in
[`results/sage-depth-three-20261006`](results/sage-depth-three-20261006).

## Widened one-hop result

A complementary direct-neighbor scan covered every ramified or split prime
degree through 47. It added 14 curves beyond the depth-three registry and
brought the combined explicit total to 70 unique curves. All 14 new one-hop
curves were screened in balanced P-256 control blocks; no paired 95% interval
excluded `1.0`. The best estimate was `1.026x` with interval
`0.996x–1.057x`, so no holdout was triggered.

The registry, raw timing blocks, receipt, and verifier are frozen in
[`results/sage-wide-depth-one-20261006`](results/sage-wide-depth-one-20261006).
Across the three Sage runs, 37 distinct neighbors have now been timed. Per-key
evaluation for the strongest screening candidate is included in the follow-up.

## Mapping-cost and native follow-up

The three depth-two holdout leaders and the strongest widened one-hop point
estimate were evaluated end to end through their retained maps. Mapping both
`P` and `Q` cost 0.65–0.97 ms per public key in Sage, or fewer than 681
iterations of the measured native rho kernel. Reusable map parsing cost less
than 0.19 seconds for each selected path.

A matched native comparison then put P-256 and all four candidates on the same
fixed-limb Montgomery field code, complete general-`a` projective formulas,
64-way batch normalization, and native scalar-coefficient tracking. Fifteen
one-second trials per curve found no significant speedup: every paired 95%
interval contained `1.0`. The largest point estimate was `1.0031x`, with
interval `0.9847x–1.0217x`.

The raw mapping and native results, exact cost boundaries, receipt, and claim
limits are frozen in
[`results/sage-mapping-20261006`](results/sage-mapping-20261006). This focused
retest closes the per-key accounting gap for four leaders; it does not make the
70-curve traversal exhaustive over the isogeny class.

## Full retained-registry native screen

The same native backend then screened the remaining 65 explicitly reached
neighbors in 11 root-controlled, position-balanced blocks. Two unadjusted
screening intervals excluded `1.0`, for degree-17 and degree-23 paths. A fresh
30-trial, two-second holdout rejected both: their paired estimates were
`1.0069x` (CI `0.9923x–1.0217x`) and `1.0030x` (CI
`0.9879x–1.0183x`).

Combining this screen with the focused four-curve panel, all 69 retained
non-root curves now have matched native measurements and none has a
reproducible advantage. The complete block artifacts, holdout, receipt, and
verifier are frozen in
[`results/sage-native-full-screen-20261006`](results/sage-native-full-screen-20261006).
This covers the explicit 70-curve registry, not the entire isogeny class.

## Complete one-hop enumeration through degree 199

Every ramified or split rational prime degree through 199 is now explicitly
enumerated. The standard division-polynomial route exhausted an 8 GiB PARI
stack at degree 137, but a lower-memory modular-polynomial method reproduced
the legacy degree-103 maps exactly and recovered both explicit neighbors at
every remaining degree. Peak RSS was about 293 MiB. The combined registry now
contains 98 curves.

The 28 additions beyond degree 47 were all screened with the matched native
backend. No paired 95% interval triggered a holdout, so all 97 retained
non-root curves now have native measurements and no reproducible speedup
remains. The completed registries, superseded stack-overflow tracebacks,
modular-method regression check, native screens, receipt, and verifier are in
[`results/sage-wide-depth-one-199-20261006`](results/sage-wide-depth-one-199-20261006).
This is complete for the classified degrees through 199, not for larger prime
degrees or the entire isogeny class. Per-key evaluation of the new maps was not
timed.

## Low-degree paths through depth five

The complementary cheap-path search now covers every curve first reached in at
most five horizontal steps of degrees 3, 5, 11, and 13. It contains 168 curves;
deduplication against the 98-curve prior union contributed 112 new neighbors
and raised the combined explicit registry to P-256 plus 209 distinct neighbors.

All 112 additions received root-controlled matched-native rho measurements.
Six unadjusted 0.5-second screening intervals triggered a fresh 30-trial,
two-second holdout. None reproduced: the largest holdout estimate was `1.0153x`
with paired 95% interval `0.9945x–1.0366x`. Thus all 209 retained non-root
curves have now been measured in the matched native backend, with zero
reproducible speedups.

The registry, all explicit paths, 19 screening blocks, holdout, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-five-20261006`](results/sage-low-degree-depth-five-20261006).
This is a depth-five result for four low degrees, not a full class-group
enumeration. Per-key evaluation of the added paths was not timed.

## Resumed low-degree paths through depth seven

The frozen depth-five frontier was resumed through depths six and seven without
duplicating prior candidate records. It added 176 curves—80 at depth six and 96
at depth seven—with no overlap against the prior 210-curve union. The combined
explicit registry now contains P-256 plus 385 distinct neighbors.

All additions were screened with the matched native backend while pinned to a
CPU separate from the concurrent class-group computation. One unadjusted screen
hit triggered a fresh 30-trial, two-second holdout and did not reproduce: its
estimate was `0.9886x` with paired 95% interval `0.9628x–1.0151x`. All 385
retained non-root curves now have native measurements and zero reproducible
speedups.

The delta registry, 30 screening blocks, holdout, receipt, and verifier are
frozen in
[`results/sage-low-degree-depth-seven-20261006`](results/sage-low-degree-depth-seven-20261006).
This remains a bounded low-degree traversal, not the entire isogeny class, and
per-key map evaluation was not timed for the additions.

## Resumed low-degree paths through depth nine

The depth-seven frontier was next extended through depths eight and nine. It
added 240 curves—112 at depth eight and 128 at depth nine—with no overlap
against the prior 386-curve union. The combined explicit registry now contains
P-256 plus 625 distinct neighbors.

All additions were screened on the CPU-separated matched native backend. Six
unadjusted screening hits triggered a fresh 30-trial, two-second holdout. None
reproduced: the largest holdout estimate was `1.0312x` with paired 95% interval
`0.9975x–1.0660x`. All 625 retained non-root curves now have native
measurements and zero reproducible speedups.

The delta registry, 40 screening blocks, holdout, receipt, and verifier are
frozen in
[`results/sage-low-degree-depth-nine-20261006`](results/sage-low-degree-depth-nine-20261006).
This remains a bounded low-degree traversal, not the entire isogeny class, and
per-key map evaluation was not timed for the additions.

## Resumed low-degree paths through depth eleven

The next extension reached 144 curves at depth ten and 160 at depth eleven,
with no overlap against the prior 626-curve union. The combined explicit
registry now contains P-256 plus 929 distinct neighbors, each with its complete
ordered path, edge maps, short-model isomorphisms, and transported generator.

All 304 additions received CPU-separated matched-native measurements. Eight
unadjusted short-screen hits entered a fresh 30-trial, two-second holdout, and
none reproduced. The largest holdout point estimate was `1.0220x` with paired
95% interval `0.9918x-1.0531x`; all 929 retained non-root curves now have
native measurements and zero reproducible iteration-rate improvements.

The delta registry, 51 screening blocks, holdout, typed transfer assessment,
receipt, and verifier are frozen in
[`results/sage-low-degree-depth-eleven-20261006`](results/sage-low-degree-depth-eleven-20261006).
This remains a bounded traversal over degrees 3, 5, 11, and 13. The default
exact class-group computation continues separately, and its unsuccessful and
running attempts are recorded in
[`results/sage-class-group-20261006/attempts.json`](results/sage-class-group-20261006/attempts.json).
Per-key map evaluation was not timed for the 304 additions, and the ordinary
host does not satisfy the repository's isolation gate for a promoted timing
claim.

## Resumed low-degree paths through depth thirteen

The next extension added 176 curves at depth twelve and 192 at depth thirteen,
again with no overlap against the prior union. The combined explicit registry
now contains P-256 plus 1,297 distinct neighbors, all with complete ordered
paths and transported generators.

All 368 additions received matched-native measurements in 62 root-controlled
blocks. Sixteen unadjusted short-screen hits entered a fresh 30-trial,
two-second holdout, and none reproduced. The largest holdout point estimate
was `1.0179x` with paired 95% interval `0.9920x-1.0445x`; all 1,297 retained
non-root curves now have native measurements and zero reproducible
iteration-rate improvements.

The delta registry, raw blocks, holdout, transfer assessment, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-thirteen-20261006`](results/sage-low-degree-depth-thirteen-20261006).
This is still a bounded degree-3/5/11/13 traversal. The exact class-group job
remained active after more than seven hours when this stage was frozen, and
per-key map evaluation was not timed for the 368 additions.

## Resumed low-degree paths through depth fifteen

The next two shells added 208 curves at depth fourteen and 224 at depth
fifteen, with no overlap against the prior union. The combined explicit
registry now contains P-256 plus 1,729 distinct neighbors.

All 432 additions received matched-native measurements in 72 root-controlled
blocks. Seven unadjusted short-screen hits entered a fresh 30-trial,
two-second holdout, and none reproduced. The largest holdout estimate was
`1.0151x` with paired 95% interval `0.9878x-1.0431x`; all 1,729 retained
non-root curves now have native measurements and zero reproducible
iteration-rate improvements.

The delta registry, raw blocks, holdout, transfer assessment, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-fifteen-20261006`](results/sage-low-degree-depth-fifteen-20261006).
This is still a bounded degree-3/5/11/13 traversal. The exact class-group job
remained active after more than eight hours when this checkpoint was frozen,
and per-key map evaluation was not timed for the 432 additions.

## Class-wide model eligibility audit

A deterministic follow-up closes several standard arithmetic-model loopholes.
Every curve in the class has the same odd prime group order, with no rational
two- or three-torsion. Consequently no member has an `F_p` Montgomery or twisted
Edwards model, and exceptional short-Weierstrass coefficients would require the
already-excluded `j = 0` or `j = 1728`.

Because `p = 3 mod 4`, every nonzero short-Weierstrass `a` is `F_p`-isomorphic
to a model with `a = 1` or `a = 3`. P-256 itself has a verified map from
`a = -3` to `a = 1`, so small-`a` specialization is not a neighbor-only
advantage. Replaying the normalization over the depth-seventeen delta verified
all 497 models and transported generators: 245 map to `a = 1` and 252 to
`a = 3`.

The unchanged native benchmark also has no candidate-dependent formula branch:
each timed complete addition performs the same three full multiplications by
`a` and two by `3b`. The certificate, source hash, typed obligations, and claim
limits are frozen in
[`results/model-eligibility-20261006`](results/model-eligibility-20261006).
This rules out those standard model shortcuts, not unknown formula families or
non-generic ECDLP algorithms.

## Resumed low-degree paths through depth seventeen

The next extension added 240 curves at depth sixteen and 256 at depth seventeen,
with no overlap against the prior union. The combined explicit registry now
contains P-256 plus 2,225 distinct neighbors, each with its ordered path, edge
maps, model isomorphisms, and transported generator.

All 496 additions received matched-native measurements in 83 root-controlled
blocks. Eight unadjusted short-screen hits entered a fresh 30-trial, two-second
holdout. None reproduced. The largest holdout point estimate was `1.0097x` with
paired 95% interval `0.9899x-1.0300x`; all 2,225 retained non-root curves now
have native measurements and zero reproducible iteration-rate improvements.

The registry, 83 raw screening blocks, holdout, candidate-model audit, failure
ledger, transfer assessment, receipt, and verifier are frozen in
[`results/sage-low-degree-depth-seventeen-20261006`](results/sage-low-degree-depth-seventeen-20261006).
The first launch failed before Sage import because Docker `vfs` storage filled
the writable layer; the exact traceback and successful CPU-separated recovery
are retained. This remains a bounded degree-3/5/11/13 traversal, not the whole
isogeny class. The exact class-group job remained active after more than 9.6
hours at this checkpoint, and per-key map evaluation was not timed for the 496
additions.

## Prospectively frozen low-degree paths through depth nineteen

The next extension was frozen in
[`protocol-depth-nineteen-20261007.json`](protocol-depth-nineteen-20261007.json)
before candidate generation. It added 272 curves at depth eighteen and 288 at
depth nineteen with no overlap against the prior union, raising the explicit
registry to P-256 plus 2,785 neighbors.

All 560 additions received matched-native measurements in 94 root-controlled
blocks. Seven unadjusted short-screen hits, with point estimates from `1.0522x`
through `1.1092x`, entered the mandatory fresh 30-trial, two-second holdout.
None reproduced. The largest holdout estimate was `1.0137x` with paired 95%
interval `0.9919x-1.0360x`; all 2,785 retained non-root curves now have native
measurements and zero reproducible iteration-rate improvements.

The depth-19 deterministic audits verify all 561 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
Discovery took 249.93 seconds, screening blocks 2,534.45 seconds, and the fresh
holdout 493.11 seconds. Per-key evaluation of the new paths on `P` and `Q`
remains unmeasured, and host-wide isolation remains unverified.

The registry, 94 raw blocks, holdout, audits, preserved command/path failures,
transfer assessment, receipt, summary, and verifier are frozen in
[`results/sage-low-degree-depth-nineteen-20261007`](results/sage-low-degree-depth-nineteen-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration. The exact class-group job remained active after more than 12.8
hours with no result file at this checkpoint.

## Prospectively frozen low-degree paths through depth twenty-one

The next extension was frozen in
[`protocol-depth-twenty-one-20261007.json`](protocol-depth-twenty-one-20261007.json)
before candidate generation. It added 304 curves at depth twenty and 320 at
depth twenty-one with no overlap against the prior union, raising the explicit
registry to P-256 plus 3,409 neighbors.

All 624 additions received matched-native measurements in 104 root-controlled
blocks. Five unadjusted short-screen hits, with point estimates from `1.0280x`
through `1.0925x`, entered the mandatory fresh 30-trial, two-second holdout.
None reproduced. The largest holdout estimate was `0.9982x` with paired 95%
interval `0.9812x-1.0155x`; all 3,409 retained non-root curves now have native
measurements and zero reproducible iteration-rate improvements.

The depth-21 deterministic audits verify all 625 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
Discovery took 280.22 seconds, screening blocks 2,829.02 seconds, and the fresh
holdout 369.78 seconds. Per-key evaluation of the new paths on `P` and `Q`
remains unmeasured, and host-wide isolation remains unverified.

The registry, 104 canonical raw blocks, seven separately retained interrupted
blocks, holdout, audits, failure ledger, transfer assessment, receipt, summary,
and verifier are frozen in
[`results/sage-low-degree-depth-twenty-one-20261007`](results/sage-low-degree-depth-twenty-one-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration. The exact class-group job remained active after more than 14.0
hours with no result file at this checkpoint.

## Prospectively frozen low-degree paths through depth twenty-three

The next extension was frozen in
[`protocol-depth-twenty-three-20261007.json`](protocol-depth-twenty-three-20261007.json)
before candidate generation. It added 336 curves at depth twenty-two and 352
at depth twenty-three with no overlap against the prior union, raising the
explicit registry to P-256 plus 4,097 neighbors.

All 688 additions received matched-native measurements in 115 root-controlled
blocks. Eighteen unadjusted short-screen hits, with point estimates from
`1.0076x` through `1.0880x`, entered the mandatory fresh 30-trial, two-second
holdout. None reproduced. The largest holdout estimate was `1.0239x` with
paired 95% interval `0.9996x-1.0488x`; all 4,097 retained non-root curves now
have native measurements and zero reproducible iteration-rate improvements.

The depth-23 deterministic audits verify all 689 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
Discovery took 297.17 seconds, screening blocks 3,109.16 seconds, and the fresh
holdout 1,171.19 seconds. Per-key evaluation of the new paths on `P` and `Q`
remains unmeasured, and host-wide isolation remains unverified.

The registry, 115 raw blocks, holdout, audits, invocation ledger, transfer
assessment, receipt, summary, and verifier are frozen in
[`results/sage-low-degree-depth-twenty-three-20261007`](results/sage-low-degree-depth-twenty-three-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration. The exact class-group job remained active after more than 15.4
hours with no result file at this checkpoint.

## Prospectively frozen low-degree paths through depth twenty-five

The next extension was frozen in
[`protocol-depth-twenty-five-20261007.json`](protocol-depth-twenty-five-20261007.json)
before candidate generation. It added 368 curves at depth twenty-four and 384
at depth twenty-five with no overlap against the prior union, raising the
explicit registry to P-256 plus 4,849 neighbors.

All 752 additions received matched-native measurements in 126 root-controlled
blocks. Fifteen unadjusted short-screen hits, with point estimates from
`1.0297x` through `1.1238x`, entered the mandatory fresh 30-trial, two-second
holdout. One remained positive: `1.0198x` with paired 95% interval
`1.0035x-1.0364x`. The local host failed the repository isolation gate, so
this is an exploratory follow-up trigger, not a controlled speedup claim.

The complete retained path for that candidate was also evaluated on both P-256
ECDLP points. The measured per-key transfer was `0.011433` seconds on average
with 95% interval `0.011025-0.011841` seconds; the endpoint generator and
discrete-log relation verified. Reusable map parsing took `0.451857` seconds.

The depth-25 deterministic audits verify all 753 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
Discovery took 353.42 seconds, screening blocks 3,402.38 seconds, and the fresh
holdout 986.14 seconds. The exact class-group job remained active after more
than 17.0 hours with no result file at this checkpoint.

The deterministic registry archive and manifest, 126 raw blocks, holdout,
mapping measurement, failed isolation probe, audits, complete invocation
ledger, transfer assessment, receipt, summary, and verifier are frozen in
[`results/sage-low-degree-depth-twenty-five-20261007`](results/sage-low-degree-depth-twenty-five-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth twenty-seven

The next extension was frozen in
[`protocol-depth-twenty-seven-20261007.json`](protocol-depth-twenty-seven-20261007.json)
before candidate generation. It added 400 curves at depth twenty-six and 416
at depth twenty-seven with no overlap against the prior union, raising the
explicit registry to P-256 plus 5,665 neighbors.

All 816 additions received matched-native measurements in 136 root-controlled
blocks. Fourteen unadjusted short-screen hits, with point estimates from
`1.0282x` through `1.0963x`, entered the mandatory fresh 30-trial, two-second
holdout. None reproduced. The largest holdout estimate was `1.0151x` with
paired 95% interval `0.9924x-1.0384x`. No new P,Q path evaluation was triggered;
the separate depth-25 exploratory positive and its charged mapping cost remain
open for isolated replay.

The depth-27 deterministic audits verify all 817 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
Discovery took 355.19 seconds, screening blocks 3,692.46 seconds, and the fresh
holdout 924.89 seconds. The exact class-group job remained active after more
than 18.6 hours with no result file at this checkpoint.

The 136,960,010-byte working registry is preserved as a deterministic
54,404,154-byte gzip archive with both hashes and a byte-identical repack
certificate. The archive and manifest, 136 raw blocks, holdout, failed
isolation probe, audits, invocation ledger, transfer assessment, receipt,
summary, and verifier are frozen in
[`results/sage-low-degree-depth-twenty-seven-20261007`](results/sage-low-degree-depth-twenty-seven-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth twenty-nine

The next extension was frozen in
[`protocol-depth-twenty-nine-20261007.json`](protocol-depth-twenty-nine-20261007.json)
before candidate generation. It added 432 curves at depth twenty-eight and 448
at depth twenty-nine with no overlap against the prior union, raising the
explicit registry to P-256 plus 6,545 neighbors.

All 880 additions received matched-native measurements in 147 root-controlled
blocks. Nineteen unadjusted short-screen hits, with point estimates from
`1.0201x` through `1.0908x`, entered the mandatory fresh 30-trial, two-second
holdout. None reproduced. The largest holdout estimate was `1.0070x` with
paired 95% interval `0.9892x-1.0250x`. No new P,Q path evaluation was triggered;
the separate depth-25 exploratory positive and its charged mapping cost remain
open for isolated replay.

The depth-29 deterministic audits verify all 881 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
The best new coefficient bounds were 246 operations lower and 350 upper.
Discovery took 405.35 seconds, screening blocks 3,983.80 seconds, and the fresh
holdout 1,232.82 seconds. The exact class-group job remained active after more
than 20.48 hours with no result file at this checkpoint.

The 158,987,198-byte working registry is preserved as a deterministic
63,137,630-byte gzip archive with both hashes and a byte-identical repack
certificate. The archive and manifest, 147 raw blocks, holdout, failed
isolation probe, audits, complete invocation ledger including failed commands,
transfer assessment, receipt, summary, and verifier are frozen in
[`results/sage-low-degree-depth-twenty-nine-20261007`](results/sage-low-degree-depth-twenty-nine-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth thirty-one

The next extension was frozen in
[`protocol-depth-thirty-one-20261007.json`](protocol-depth-thirty-one-20261007.json)
before candidate generation. It added 464 curves at depth thirty and 480 at
depth thirty-one with no overlap against the prior union, raising the explicit
registry to P-256 plus 7,489 neighbors.

All 944 additions received matched-native measurements in 158 root-controlled
blocks. Ten unadjusted short-screen hits, with point estimates from `1.0234x`
through `1.0717x`, entered the mandatory fresh 30-trial, two-second holdout.
None reproduced. The largest holdout estimate was `1.0074x` with paired 95%
interval `0.9749x-1.0411x`. No new P,Q path evaluation was triggered; the
separate depth-25 exploratory positive and its charged mapping cost remain open
for isolated replay.

The depth-31 deterministic audits verify all 945 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
The best new coefficient bounds were 240 operations lower and 354 upper.
Discovery took 419.27 seconds, screening blocks 4,278.83 seconds, and the fresh
holdout 678.76 seconds. The exact class-group job remained active after more
than 22.26 hours with no result file at this checkpoint.

The 182,657,444-byte working registry is preserved as a deterministic
72,521,111-byte gzip archive with both hashes and a byte-identical repack
certificate. The archive and manifest, 158 raw blocks, holdout, failed
isolation probe, audits, complete invocation ledger, transfer assessment,
receipt, summary, and verifier are frozen in
[`results/sage-low-degree-depth-thirty-one-20261007`](results/sage-low-degree-depth-thirty-one-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth thirty-three

The next extension was frozen in
[`protocol-depth-thirty-three-20261007.json`](protocol-depth-thirty-three-20261007.json)
before candidate generation. It added 496 curves at depth thirty-two and 512 at
depth thirty-three with no overlap against the prior union, raising the explicit
registry to P-256 plus 8,497 neighbors.

All 1,008 additions received matched-native measurements in 168 root-controlled
blocks. Twelve unadjusted short-screen hits, with point estimates from `1.0311x`
through `1.1230x`, entered the mandatory fresh 30-trial, two-second holdout.
None reproduced. The largest holdout estimate was `0.9940x` with paired 95%
interval `0.9694x-1.0193x`. No new P,Q path evaluation was triggered; the
separate depth-25 exploratory positive and its charged mapping cost remain open
for isolated replay.

The depth-33 deterministic audits verify all 1,009 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
The best new coefficient bounds were 244 operations lower and 355 upper.
Discovery took 487.76 seconds, screening blocks 4,574.98 seconds, and the fresh
holdout 801.23 seconds. The exact class-group job remained active after more
than 24.20 hours with no result file at this checkpoint.

The 207,970,047-byte working registry is preserved as a deterministic
82,555,485-byte gzip archive with both hashes and a byte-identical repack
certificate. The archive and manifest, 168 raw blocks, holdout, failed
isolation probe, audits, complete invocation ledger including the denied first
status-check invocation, transfer assessment, receipt, summary, and verifier
are frozen in
[`results/sage-low-degree-depth-thirty-three-20261007`](results/sage-low-degree-depth-thirty-three-20261007).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth thirty-five

The next extension was frozen in
[`protocol-depth-thirty-five-20261008.json`](protocol-depth-thirty-five-20261008.json)
before candidate generation. It added 528 curves at depth thirty-four and 544 at
depth thirty-five with no overlap against the prior union, raising the explicit
registry to P-256 plus 9,569 neighbors.

All 1,072 additions received matched-native measurements in 179 root-controlled
blocks. Sixteen unadjusted short-screen hits, with point estimates from
`1.0278x` through `1.0910x`, entered the mandatory fresh 30-trial, two-second
holdout. One reproduced: `p256-j-69e859…d189e` measured `1.0219x` with paired
95% interval `1.0012x-1.0431x`. This is a small exploratory effect, not a
dramatic or controlled speedup. The complete 34-edge path was replayed on both
ECDLP points: reusable map parsing took 0.5334 seconds and per-key P,Q mapping
averaged 0.014246 seconds with 95% interval 0.014042-0.014450 seconds. The
endpoint generator and discrete-log relation verified.

The depth-35 deterministic audits verify all 1,073 delta models and transported
generators, exact conductor `1` and level-zero horizontal paths for every
addition, and zero normalized-`3b` candidates passing the 32-operation gate.
The best new coefficient bounds were 243 operations lower and 345 upper.
Discovery took 460.68 seconds, accepted screening blocks 4,842.21 seconds, and
the fresh holdout 1,047.34 seconds. The local host failed the isolation gate, so
the positive timing requires replay on a qualifying host.

An execution-environment restart interrupted an earlier screen after 155 blocks
and stopped the exact class-group process after 128,200.21 seconds without a
result or checkpoint. Those failed artifacts and costs are preserved and
excluded from accepted timing evidence. A clean full screen replaced the
partial run, and the exact class-group computation restarted from its original
configuration; its depth-35 checkpoint was running after 6,225.22 seconds.

The 234,925,716-byte working registry is preserved as a deterministic
93,239,950-byte gzip archive with both hashes and a byte-identical repack
certificate. The archive and manifest, 179 accepted raw blocks, 155 excluded
interrupted blocks, holdout, mapping benchmark, failed isolation probe, audits,
complete invocation ledger, transfer assessment, receipt, summary, and verifier
are frozen in
[`results/sage-low-degree-depth-thirty-five-20261008`](results/sage-low-degree-depth-thirty-five-20261008).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

## Prospectively frozen low-degree paths through depth thirty-seven

The next extension was frozen in
[`protocol-depth-thirty-seven-20261008.json`](protocol-depth-thirty-seven-20261008.json)
before candidate generation. It added 560 curves at depth thirty-six and 576 at
depth thirty-seven with no overlap against the prior union, raising the explicit
registry to P-256 plus 10,705 neighbors.

All 1,136 additions received matched-native measurements in 190 root-controlled
blocks. Fourteen unadjusted short-screen hits, with point estimates from
`1.0130x` through `1.1056x`, entered the mandatory fresh 30-trial, two-second
holdout. Two reproduced: `p256-j-de71f2…3bb50` measured `1.018507x` with paired
95% interval `1.001429x-1.035876x`, and `p256-j-6aeef1…80245` measured
`1.015784x` with interval `1.000181x-1.031630x`. These are small exploratory
effects, not dramatic or controlled speedups.

Both complete paths were replayed on P and Q. Their per-key transfer means were
0.015213 and 0.016061 seconds for 36 and 37 edges, respectively; every endpoint
generator and discrete-log relation verified. The local host failed the
isolation gate, so both candidates require replay on a qualifying host.

The deterministic audits verify all 1,137 delta models and transported
generators, Frobenius-order conductor `1`, endomorphism-ring conductor `1`, and
level-zero horizontal paths for every addition. Zero normalized-`3b` candidates
passed the 32-operation gate. Discovery took 490.29 seconds, accepted screening
blocks 5,133.19 seconds, and the fresh holdout 924.20 seconds. A managed
environment transition interrupted an earlier screen after six complete blocks;
those artifacts are preserved and excluded. The restarted exact class-group
calculation remained active after 15,118.68 seconds with no result file.

The 263,524,621-byte working registry compresses to one deterministic
104,574,880-byte gzip stream, published as three ordered sub-50 MiB shards with
per-shard, concatenated-stream, and uncompressed hashes plus a byte-identical
repack certificate. The shards and manifest, 190 accepted raw blocks, six
excluded interrupted blocks, holdout, two mapping benchmarks, failed isolation
probe, audits, invocation ledger, transfer assessment, receipt, summary, and
verifier are frozen in
[`results/sage-low-degree-depth-thirty-seven-20261008`](results/sage-low-degree-depth-thirty-seven-20261008).
This remains a bounded degree-3/5/11/13 traversal, not a complete class-group
enumeration.

Registries whose compressed form fits GitHub's single-blob limit are frozen with
[`scripts/freeze_large_json.py`](scripts/freeze_large_json.py). Larger registries
use [`scripts/freeze_large_json_sharded.py`](scripts/freeze_large_json_sharded.py),
which splits the same deterministic level-9 gzip byte stream into ordered
48 MiB shards. The manifest binds every shard, the concatenated compressed
stream, and the uncompressed JSON by byte count and SHA-256. Verification can
repack byte-for-byte or materialize the exact original JSON for later Sage and
native benchmarking.

## Full-registry normalized-coefficient audit

The complete 2,226-curve retained union was reconstructed from fourteen frozen
candidate registries and normalized to the certified `a = 1` or `a = 3` models.
Every fourth-root certificate and transported generator verified. The audit then
ranked the normalized `3b` constant used twice by each complete addition.

P-256's normalized coefficient has 251 bits, popcount 125, and a binary
double-and-add bound of 374 field additions/doublings. The smallest retained
coefficient still has 243 bits, giving an unavoidable addition-chain lower bound
of 242 operations. The best binary bound is 352 operations, and the minimum
popcount is 100. Consequently zero curves pass the conservative 32-operation
gate for implementing a coefficient-specialized native formula.

The full metrics, input hashes, cost model, receipt, summary, and verifier are
frozen in
[`results/coefficient-cost-audit-20261007`](results/coefficient-cost-audit-20261007).
No wall-time speedup is claimed: this is a deterministic eligibility screen, and
no candidate advanced to a native benchmark. It closes the retained-registry
small-constant route, not other coordinate systems, formula families, deeper
paths, or unknown algorithms.

## Full-registry conductor audit

Yes: the endomorphism-ring conductor is now attached explicitly to all 10,706
curves in the current retained registry. This is an exact derivation rather
than 10,706 independent numeric measurements. Each record recomputes
`t = p + 1 - n` and `D_pi = t^2 - 4p`; the complete certificate-verified
factorization shows that `D_pi` is fundamental. For every ordinary curve `E`
in the class,

```text
Z[pi] subseteq End(E) subseteq O_K,
Z[pi] = O_K,
therefore End(E) = O_K and f_End(E) = 1.
```

Consequently `v_l(f_End(E)) = 0` for every rational prime `l`. The audit also
checks the continuity and endpoint of each retained explicit path and labels
all 270,002 stored path-edge occurrences horizontal, with both endpoints at
level zero. There are no vertical edges or alternate conductor levels to
search in this isogeny class.

The first 2,226 consolidated per-curve rows, per-edge classifications, input
hashes, receipt, summary, and deterministic verifier are frozen in
[`results/conductor-audit-20261007`](results/conductor-audit-20261007). This
class-wide conductor conclusion does not enumerate the entire isogeny class
and does not establish an ECDLP speedup; the explicit curve registry remains
bounded. The depth-19, depth-21, depth-23, depth-25, depth-27, depth-29,
depth-31, depth-33, depth-35, and depth-37 extension directories repeat the exact certificate and
retain explicit rows for their respective 560, 624, 688, 752, 816, 880, 944,
1,008, 1,072, and 1,136 additions. Together with the consolidated snapshot, these incremental
audits cover the current registry without implying that the older snapshot
itself contains later rows.

Primary background for the order classification is Waterhouse,
[*Abelian varieties over finite fields*](https://www.numdam.org/item/ASENS_1969_4_2_4_521_0/),
and for the horizontal/vertical isogeny-volcano interpretation, Sutherland,
[*Isogeny volcanoes*](https://doi.org/10.2140/obs.2013.1.507).

## Quick start

Python 3.11 or newer is required.

```bash
cd experiments/p256-isogeny-search-20261005
python -m pip install -e .
p256-isogeny run --output-dir runs/latest --seconds 1 --trials 3
```

The run creates:

- `structural-report.json`: exact invariants and eliminated structures;
- `benchmark.json`: repeated rho iteration measurements with a 95% interval;
- `toy-rho.json`: a completed small-curve collision and recovered logarithm;
- `summary.md`: a compact human-readable report.

To independently rediscover the discriminant factorization rather than verify
the checked certificate:

```bash
p256-isogeny analyze --refactor
```

This can take several minutes.

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

## Horizontal exploration with SageMath

The first useful rational prime degrees are classified from the Kronecker
symbol `(D_pi / ell)`. Up to 13:

- `3, 5` are ramified and give one horizontal direction;
- `11, 13` split and give two horizontal directions;
- `2, 7` are inert and give no horizontal edge.

With SageMath installed:

```bash
sage -python scripts/explore_sage.py \
  --ells 3,5,11,13 \
  --depth 2 \
  --max-nodes 100 \
  --output data/candidates/generated/depth-2.json

sage -python scripts/benchmark_interleaved.py \
  --candidates data/candidates/generated/depth-2.json \
  --seconds 2 \
  --trials 7 \
  --output runs/sage/benchmark.json
```

Each candidate retains:

- its short-Weierstrass coefficients and mapped P-256 generator;
- every edge degree and kernel polynomial;
- the isogeny and model-isomorphism rational maps;
- elapsed reusable discovery time and total path degree;
- a separate placeholder for the two per-instance map evaluations.

The `P-256 Sage horizontal search` GitHub Actions workflow exposes the same search as
a manual, parameterized job and uploads both candidates and benchmark results.

## Interpreting the benchmark

The reference implementation runs parallel `r`-adding walks. It batch-normalizes
their projective points with one inversion per batch, ensuring that partition
choices depend on canonical affine `x` and define a legitimate rho iteration.
For a prime-order group its generic expected work is reported as

```text
sqrt(pi*n/2)
```

before automorphism quotients. Candidate speed is compared using the identical
walk and repeated wall-clock trials. The comparative script warms every
candidate, rotates execution order so a full block puts every curve in every
timing position, and reports a paired Student-t interval for each per-trial
log-rate ratio against P-256. The security change attributable to a
constant-factor rate difference is `log2(candidate_rate / baseline_rate)` bits.

The benchmark intentionally reports these cost categories separately:

1. discovery and reusable precomputation;
2. per-instance evaluation of the explicit path on `P` and `Q`;
3. ECDLP walk iterations on the candidate.

An end-to-end P-256 speedup must include all three. The Python implementation is
control code, not a claim about the fastest available P-256 attack; serious
candidates should be reproduced in an optimized constant-quality backend.

## Repository layout

```text
src/p256_isogeny_search/   exact analysis, curve arithmetic, rho harness
data/candidates/           versioned candidate/path interchange files
scripts/explore_sage.py    explicit horizontal path explorer
scripts/benchmark_mapping_sage.py  retained-map P,Q cost benchmark
tests/                     structural and collision regression tests
../../suite/examples/p256_isogeny_native_bench.rs  matched native rho benchmark
../../.github/workflows/   path-scoped CI and manual Sage exploration
```

## Scope

This is cryptanalytic research tooling. It does not implement signing, key
generation, or production cryptography. The in-tree elliptic-curve arithmetic
is variable-time and must not process secrets in a real system.

This experiment complements the broader Rust profiler in
[`suite/src/cryptanalysis/p256_structural.rs`](../../suite/src/cryptanalysis/p256_structural.rs).
That module covers twist and extension-field structure; this experiment adds a
certified complete Frobenius-discriminant factorization, explicit horizontal
path retention, and separate discovery/mapping/ECDLP cost accounting.
