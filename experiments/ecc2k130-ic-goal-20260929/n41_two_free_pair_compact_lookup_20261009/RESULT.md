# Exact two-free-pair completion finds the N41 public row; compact lookup is slower in the matched run

The frozen target-dependent solver found an eight-point relation for the public
N41 point after **513,088** admissible first-two-pair residuals in **44.004 s**
online wall time. An independent checked-Sage replay verified all eight base
points, subgroup memberships, signed-Frobenius columns, and their exact sum.
The same-host rerun of the original exact lookup found the identical row and
residual index in **32.222 s**. The compact lookup therefore has no measured
stage speed advantage in this comparison.

## Exact method and frozen input

The instance is `EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2)[t]/(t^41+t^3+1)`, with `y²+xy=x³+1`, subgroup order
`549756390943`, public `Q=(1458168294740,1672312028033)`, four W6
same-rotation pair domains, `B=256` actual usable base points, and `K=26`
signed/Frobenius columns. Each pair domain has 1,956 exact distinct-column
states and 978 distinct x coordinates. The search executable receives only
this public target and the frozen base input; no row, pair output, or scalar
is fixed in the search path. [Protocol v2](protocol_v2.json) binds the code,
binary, input, control, target, and one-worker limits before the retained
public run.

For each first-two-pair prefix, the solver forms `R=Q-U0-U1` and leaves the
last two pair domains free. It batches 978 field inversions, derives both
possible x coordinates for the required third pair output, tests membership
in the other exact pair-output domain, then checks full group points and all
eight folded columns. The change under test replaced the original
`unordered_map` x-set with a contiguous 2,048-slot exact open-address table.
The [positive and negative residual controls](diagnostic_v2.json) both pass.

## Retained runs and accounting

| Public target method | Status | Admissible residuals | Online wall | Peak RSS | Row audit |
| --- | --- | ---: | ---: | ---: | --- |
| Compact x lookup, frozen v2 | `VERIFIED_RAW_ROW` | 513,088 | 44.004 s | 2,523,136 B | checked Sage `PASS` |
| Original x lookup, matched rerun | `VERIFIED_RAW_ROW` | 513,088 | 32.222 s | 2,736,128 B | same exact row |

The compact run charged **43.874 s** to the two-free-pair completion probes,
**0.130 s** to prefix generation and loop work, and **792 ns** to its final
internal group replay; these exclusive counters sum to the saved
`44,004,303,666 ns` online interval. The source records six exact group hits;
the first five reuse a folded column, and the sixth is the accepted row.
The independent [Sage audit](sage_audit.json) runs after the online interval.
Both methods ran on the same public point, input, one worker, 120-second cap,
and 4-GiB limit. Their CPU times are exploratory because this host lacks the
required isolation receipt. The [matched baseline protocol](matched_baseline_protocol.json)
and [receipt verifier](verification.json) retain source and binary hashes,
run order, equal rows, failures, and accounting.

The first compact execution printed a row after 50.494 s but wrote an empty
result file when the SSD was full. That execution is recorded as
`OUTPUT_WRITE_FAILURE_EMPTY_RECEIPT`; its zero-byte
[file](public_search.json) is retained. The writer was then changed to check
the stream after close. [Source v1](native_compact_v1.cpp), its
[binary](native_compact), and [first protocol](protocol.json) preserve the
failed attempt. [Source v2](native_compact.cpp), its [binary](native_compact_v2),
and the [complete public result](public_search_v2.json) are the independently
audited attempt. Compilation used `/private/tmp` for temporary files and the
run wrote its result there before the 1,097-byte receipt was copied into
this directory. The [checked-Sage runtime receipt](sage_runtime_info.json)
was saved before the audit.

## N131 transfer and next experiment

The literal source builds four complete `PairState` vectors before the
target query. The exact W18 geometry has at least **34,448,654,064**
distinct-column pair states per domain. Even one bit per state needs
**4,306,081,758 bytes** for one domain, exceeding the 4-GiB cap by
**11,114,462 bytes** before point coordinates or indexes. The
[source-bound transfer audit](transfer_gate.json) therefore records
`FAIL_N131_EXPLICIT_PAIR_MEMORY_GATE`. The public N41 result is a valid
target-conditioned search control, while this literal implementation cannot
enter the frozen N131 W18 relation gate.

The next constructive test should replace explicit pair-state vectors with
an implicit target-bound generator. A specific candidate is to connect the
existing exact joint-linear pair inverse to a two-free-pair S3 eliminant and
measure whether the public target rejects entire symbolic seed-sum families
before either free pair is enumerated. The N41 test should freeze the public
point, unpinned row search, 120-second/4-GiB cap, and independently replayed
relation. An N131 query needs a source-bound six-pair work and memory
projection under 600 seconds and 4 GiB first. This experiment remains
proposal `Q20261009223300`; complete-pipeline candidate and run IDs are null.

## Reproduction

The [verifier](verify.py) checks all retained hashes, the empty first receipt,
both complete public results, exact row equality, phase sum, Sage audit, and
N131 arithmetic. Run it with `PYTHONDONTWRITEBYTECODE=1 python3 verify.py` from
this directory. The independent row audit is [audit.py](audit.py); launch any
new Sage replay from the repository root with `./sage -python` after saving
`./sage --runtime-info`. The first-run producers refuse to overwrite their
receipts, so use fresh output paths for repetitions.
