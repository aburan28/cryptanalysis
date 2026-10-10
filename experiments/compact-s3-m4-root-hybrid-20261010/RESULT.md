# Q1425: exact pair-root lemmas remove the fixed-leaf intermediate bottleneck

Preseeding both exact S3 pair-root lemmas makes the four-leaf known-solution
controls solve in one CryptoMiniSat call at N53 and N83. The controls keep
their pair intermediates free; the lemmas restrict each intermediate to
the exact one or two roots for its fixed pair of leaves. The stage verifier
replayed the four-point group relation and exact base membership. On the
same instances, Q1419's `free_mids` SAT formulas had reached their
one-million-conflict caps without a model. This establishes a useful
structural improvement for the released-intermediate control.

The ordinary-target cells left all four factor-base leaves and both pair
intermediates free. They stopped before a first SAT model. No lazy root
lemma was called in those cells. Thus a complete-model callback cannot yet
couple the oracle to ordinary leaf search; the next implementation should
propagate roots when a *partial assignment fixes a leaf pair*.

## Exact instances and measured cells

The proposal remains `Q1425`, with `candidate_id: null`, `run_id: null`,
and `isogeny: none`. `B` counts exact subgroup-usable factor-base points
before sign/Frobenius folding; `K` is the folded column count. The ordinary
target and base digests are fixed in [`freeze.json`](freeze.json).

| Field, curve ID | Exact base | Mode | SAT S3 links / external links | PDP wall s | SAT wall s | Root calls | Result |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| N53 `EC1N53Ckb1hf77aab617904` | Q1301 W≤3, B=24,062, K=227 | `control_both_preseed` | 1 / 2 | 0.298 | 0.005 | 2 | verified four-point relation |
| N53, same curve/base | same | `ordinary_left_lazy` | 2 / 1 | 12.930 | 12.559 | 0 | `BOUNDED_UNKNOWN` |
| N53, same curve/base | same | `ordinary_both_lazy` | 1 / 2 | 13.043 | 12.772 | 0 | `BOUNDED_UNKNOWN` |
| N83 `EC1N83Ckb1h876c2921cb64` | Q1325 W≤5, B=30,977,592, K=186,612 | `control_both_preseed` | 1 / 2 | 0.372 | 0.012 | 2 | verified four-point relation |
| N83, same curve/base | same | `ordinary_left_lazy` | 2 / 1 | 23.881 | 23.402 | 0 | `BOUNDED_UNKNOWN` |
| N83, same curve/base | same | `ordinary_both_lazy` | 1 / 2 | 29.680 | 29.256 | 0 | `BOUNDED_UNKNOWN` |

Each case used one SAT thread, at most 17 solver calls, at most 16 root
refinements, and configured per-call limits of 100,000 conflicts and 25 CPU
seconds within a 90-second target-dependent wall envelope. The C API does
not expose the counter or exact stop reason. The four ordinary cells each
returned `BOUNDED_UNKNOWN` on the first call, so their relation-yield
rates are censored; zero found relations under these caps is not a
zero-yield estimate. The host had no isolation receipt, so wall-time
comparisons are exploratory. Their observed peak process RSS was below
604 MB. Per-case JSON receipts retain the exact phase clocks, input law,
field-API call counts, trace hash, and formula sizes.

Two external links halved the Boolean AND count relative to one external
link: 16,854 to 8,427 at N53 and 41,334 to 20,667 at N83. The
`control_both_preseed` cells used 26 field-multiplication API calls, four
inversions, and two traces to compute the two root sets at each degree;
these are public API calls, with no conversion to a common field-operation
unit. Ordinary cells invoked no root oracle because SAT returned no model.

## Work to the \(2^{61}\) target

There is no complete N131 \(2^x\) estimate for this method: ordinary
relation probability, cost per useful independent row, final matrix
solving, and target descent have not been measured. The Q1425 receipts
explicitly store `n131_complete_cold_work_log2: null` and
`n131_complete_online_one_target_work_log2: null`. Fitting an exponent to
the four capped searches would treat censored runs as solves.

The existing Q1416 **pure indexed-pair model** supplies a separate
conditional reference: about \(2^{89.36}\) logical pair actions, or
28.36 exponent bits over \(2^{61}\), under its uniform pair-key and
one-novel-row-per-match assumptions. Its \(2^{60.28}\)-byte minimum key
storage is for an uncompressed full index. Q1425 does not build that
index, so those values do not bound this hybrid solver. The current
method's gap to \(2^{61}\) is unknown.

## Verification and next gate

[`verify.py`](verify.py) checked all six receipts and traces, reconstructed
the formulas, recomputed every exact root and lemma-clause digest, and
replayed accepted four-point relations on the exact bases. Its summary is
[`verification.json`](verification.json). `test_lemma.py` exhaustively
checked the conditional lemma against direct S3 evaluation for every
nonzero pair and intermediate over GF(2^5), covering 420 zero-root,
31 one-root, and 510 two-root pairs.

The next experiment should make the oracle fire when a pair of leaves is
fixed *during* search, before a full SAT model. A viable implementation
needs a native propagator or an explicit assumption-and-branch scheduler
that reuses solver state. Gate it first on the Q1419 `free_mids` controls,
then require an unpinned ordinary relation at N53 and N83 on the exact
frozen bases. Count all failed attempts and root work before projecting
N131 cost.

The preserved [`pilot_v1`](pilot_v1/README.md) trace records the earlier
left-only preseed control as `BOUNDED_UNKNOWN`. Its result was returned
under the configured caps; the library did not identify which cap fired.
