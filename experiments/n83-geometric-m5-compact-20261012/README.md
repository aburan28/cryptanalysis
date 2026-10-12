# Constant-folded balanced N83 five-summand stage

This follow-up reuses the public point and workload `df4396f4d8fc` from
[the width-11/12 sequential experiment](../n83-geometric-m5-gate-20261012/README.md).
It compiles the fixed bits of each affine leaf x-coordinate as Boolean
constants and arranges the four factored S3 links as two leaf pairs, their
join, and the fifth leaf. All four cofactor preimages remain in the formula.
Any SAT model must still pass the exact five-point, signed, cofactor,
subgroup, factor-base membership, and public-sum replay. The independent
Sage verifier checks any relation in a separate polynomial-basis model.

The frozen [protocol](protocol.json) pairs shifted widths 13 and 12 on the
same target, with five million CryptoMiniSat conflicts, 600 seconds per
base, a 4 GiB sampled child-RSS stop, and at most three candidate models.
Width 12 also matches the prior sequential cell's point and limits for a
direct encoding comparison. Width 13 has 4,125 folded columns and 684,750
usable subgroup points before folding; width 12 has 2,130 columns and
353,580 points. Their exact key files and the original width-frontier
Sage replay are hash-bound. Index or factor-base logs are outside this
bounded point-decomposition stage.

These SAT leaves search the unrotated affine seeds. They reach 8,252
signed projected points at width 13 and 4,262 at width 12. Their distinct
five-subset first moments on a uniform target are
`1.3172215159550674e-7` and `4.8354509365184165e-9`, respectively. The
full-base values, `518.8513695245769` and `19.0465043281361`, include
independent Frobenius rotations that this formula does not select. The
[orbit-complete follow-up](../n83-geometric-m5-orbit-20261012/README.md)
adds those choices explicitly. Its [exhaustive coverage receipt](../n83-geometric-m5-orbit-20261012/coverage.json)
verifies the exact set sizes and canonical base keys.

The locked width-12 correctness control fixed five rational affine leaves
whose signed cofactor projections belong to the exact base. CryptoMiniSat
returned SAT, and exact point replay verified their public sum. The control
receipt retains its formula and solver output; the independent Sage replay
checks the same five-point relation in a polynomial-basis field.

The source-level shape screen gave 51,499 AND gates for balanced width 12,
versus 82,668 in the generic-bit sequential width-12 formula. This is a
constraint-count reduction; solver status and relation replay are recorded
in the terminal run receipts. CPU times on the shared local host are
exploratory.

Both ordinary cells reached their 600-second wall caps with
`external_timeout` and `bounded_unknown`. Width 13 used 51,798 AND gates,
155,811 CNF clauses, and 1,366 native XOR rows; its sampled solver peak
was 573,325,312 bytes. Width 12 used 51,499 gates, 154,920 clauses,
1,357 XOR rows, and 423,034,880 sampled solver bytes. The receipt verifier
passed all frozen source, input, XCNF, output, control, and phase checks.
Independent Sage replay passed the locked five-point control and recorded
`no_relation_to_replay` for both ordinary cells.

Reproduce in a fresh checkout:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/n83-geometric-m5-compact-20261012/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-compact-20261012/prepare.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-compact-20261012/run.py
/Volumes/SSD990/cryptanalysis/sage -python experiments/n83-geometric-m5-compact-20261012/verify_sage.py
python3 experiments/n83-geometric-m5-compact-20261012/verify.py
```

Each producer refuses to overwrite terminal artifacts. A timeout or conflict
cap remains `bounded_unknown`; a found relation requires full replay before
it contributes to an end-to-end factor-base comparison.
