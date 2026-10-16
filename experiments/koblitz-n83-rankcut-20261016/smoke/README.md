# Local validation (cloud-agent VM; diagnostics only)

Everything here ran on the cloud-agent VM, a shared 4-vCPU Intel Xeon
guest at 2.1 GHz with transparent huge pages set to `madvise` and rustc
1.97.0; the runner pins 1.99.0. Some processes ran concurrently. **None of
these times is timing evidence.** They check correctness, show where a
probe's time goes on this machine, and give rough sizes.

## Derivation and tests

- `make_stacked_source.py` (the stacked experiment's `make_online_source.py`,
  verbatim) reproduces the stacked producer's frozen digest `83b58988...`.
  The eight rank-cut edits then apply with every counted replacement
  matching, giving the producer `c390733e...`. `restore.py` re-derives it
  and checks every pin. The producer builds with no warnings.
- `cargo test --release --locked --bins` (`cargo-test-summary.txt`): all 15
  producer tests pass, plus the 4 tuned-rho tests, plus `lift2`'s 24.
  The two new `rankcut_tests` are:
  - `point_addition_pairs_are_the_s3_roots`: on 4,000 random pairs of
    base-generated points, the S3 solver's pair equals
    {x(T + R), x(T - R)}, and the recovered y is +-y(R).
  - `padd_loops_find_the_s3_relation_with_the_s3_probes`: on 40 planted
    four-point targets, run in three settings (folded with the Feistel
    order, folded with the left-major order, and unfolded), `PIPE_PADD`,
    `PIPE_PADD_PLANT` and `PIPE_PADD_SWAPPED` return the compact S3 loop's
    relation, intermediates, probe count, root calls and relation checks.
    `PIPE_PADD_SWAPPED` emits every pair in the other order, so the
    exact-order resolution at hits is exercised. The test asserts that
    swaps occurred.

## Full K600 rank stages against the archive (`rank_exactness_local.json`)

Rank seed 101, point s000 of the stacked panel: the same inputs as run
38862448935's kS serial 42. These were three concurrent processes,
`KIC_RANK_SOLVE` = `s3` (kS), `padd` (kR) and `padd_plant` (kRX).

| arm | rank, attempts | relation digest | per-attempt probes | root calls | factor-log table | target relation, scalar, probes | rank stage (diagnostic) | ns per probe (diagnostic) |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| kS | 600, 600 | `de271a96...` = archive | = archive (600 of 600) | = archive | = B's | = archive | 365.8 s | 365.4 |
| kR | 600, 600 | `de271a96...` = archive | = archive | = archive | = B's | = archive | 261.7 s | 261.4 |
| kRX | 600, 600 | `de271a96...` = archive | = archive | = archive | = B's | = archive | 430.6 s | 430.2 |

- kR resolved 600 hits exactly. 325 of them were pairs whose emitted order
  differed from the S3 order and were evaluated in the S3 order. No state
  fell back, and no input was exceptional.
- kRX compared all 500,277,354 candidates of its rank stage with the S3
  roots and found no difference. That is every candidate solve of the
  1,000,454,051 probes.
- On this VM, the rank stage under the candidate is 1.40x faster than the
  baseline, run concurrently. This is a diagnostic only. The runner's
  per-probe split differs: its table lookups are cheaper, because huge pages
  are always on there.

## Profile (`profile_local.json`, `profile.patch`)

The patch adds two env-guarded diagnostics (`KIC_PROF`, `KIC_PROF2`) to a
scratch copy of the stacked producer; it is not part of any frozen producer.
On the first rank target of seed 101, with 20,000 states (6.64 M probes) and
three rounds, cumulative ns per probe:

- inputs 9-15;
- + batched S3 solve: 120-142;
- + normal-basis maps: 142-166;
- + lift_scan keys: 207-213;
- + prefetch and lookup: 356-396.

The producer's compact loop on the same states took 316-375 ns per probe.
The point-addition partners, with output in the normal basis, took 79-95
instead of 129-163 ns per probe for the solve. The whole loop took 231-246
against 325-381 in the same processes. The pairs matched the S3 pairs as
sets on 498,000 candidates. Inlining the carry-less multiply (a global
`+pclmulqdq` build) moved the solve by about 5-10%, inside the noise.

## Runner, wrapper, gates and verifier (`diagnostics_O1_C1_K1.json`)

- `run_schedule.py --segments O1,C1`: 6 rows, all valid.
  - Q0: cS and cR both give the archived relation [77273, 22971, 54962,
    62539] and scalar 3141592653589793, with 1,987,852 probes.
  - s000: cS, cR and cRI give one relation and 686,577 probes, and rT gives
    the same scalar.
  - `verify_receipt.py --correctness-only` passes every check
    (`correctness_O1_C1.json`), including the oracle replay.
- `run_schedule.py --segments K1 --max-runs-per-segment 2` (the first two
  shuffled K1 rows, kRaa and kR; new rank seed 201): both rows are valid.
  - Both reach full rank, write B's table and give one relation digest
    (`b1f4bd32...`), one per-attempt probe vector and one root-call count.
    Each resolved 600 hits, 283 of them swapped.
  - The rank gates pass (`correctness_K1_two_rows.json`).
- `check_log_table.py` passes (`log-table-check.json`).
- The verifier's statistics path was also run on synthetic rows: a planted
  1.35x rank effect on the prior's attempt times. It returned R = 1.3077
  [1.3061, 1.3094], passed the A/A control, and gave "improvement".
