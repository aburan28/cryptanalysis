# Local validation (cloud-agent VM; diagnostics only)

All runs here used the cloud-agent VM, a shared 4-vCPU Intel Xeon guest
with rustc 1.97.0; the runner pins 1.99.0. Some processes ran concurrently,
so none of these times is timing evidence. They check correctness and give
rough sizes.

## Derivation and tests

- `make_tablefilter_source.py` reproduces the table-filter producer's frozen
  digest `70233510...`. The stack edits then apply with every counted
  replacement matching, and the derived producer has digest `83b58988...`.
  It builds with no warnings in the producer.
- `cargo test --release --locked --bins`: all 13 producer tests pass, plus
  the 4 tuned-rho tests. The new `stacked_tests` cover the following:
  - Feistel `invert` over whole domains, including the real S, and the fold
    map's counts and bijectivity.
  - On a 9-orbit n = 83 base, every index variant matches the unfolded
    32-byte reference: 32-byte folded, 32-byte folded and planted, compact
    unfolded, compact folded, compact folded and planted, compact folded
    with lift in the index build, and filter folded. Each variant rebuilds
    the same states, has the same key -> value map and gives the same
    digests.
  - On 24 planted four-point targets, run in four (canonicalizer, order)
    combinations, every folded arm on every probe loop returns the
    reference relation (`PIPE_OFF` and `PIPE_PREFETCH` on the 32-byte table;
    `PIPE_COMPACT`; `PIPE_FILTER`). The folded arms' probes are equal to
    each other and ≤ the unfolded ones. The planted identity
    `probes + audit = unfolded probes` holds, and skips are exercised.

## Full K600, Q0 (one process each, cached table)

| arm | relation | probes | scalar | setup + online (diagnostic) | peak RSS |
| --- | --- | ---: | --- | ---: | ---: |
| pP (`cP`: base, unfolded) | [77273, 22971, 54962, 62539] | 1,988,184 | 3141592653589793 | 75.9 s (first run), 83.8 s (smoke) | 5,544 MiB |
| stack (`cS`: compact, fold) | same | 1,987,852 (one skipped state) | same | 30.6 s, 32.8 s | 1,788 MiB |

Both arms reproduce the archived Feistel relation and scalar, and the
archived probes for pP. The stack's probe count is the state fold's cF on
Q0. Both reproduce B's index digests: logical-state blake3 `baf46d5a...`,
table map sum `be14a80705232396`, xor `8132bdcfd619010f`, 29,878,182
entries.

## Rank stage on the 16-byte table (exactness; `rank_exactness_local.json`)

Rank seed 101, full K600, to full rank:

- **kS:** 16-byte table, fold, lift, Feistel, `KIC_RANK_PROBE=target`,
  which is the compact loop.
- **kR:** the state fold's kN setting: 32-byte table, fold, lift, Feistel,
  `KIC_RANK_PROBE=off`.

Both reach rank 600 in 600 attempts with no failures and 1,000,454,051
probes. They give the same `rank_relations_blake3` (`de271a96...`) and
identical per-attempt probe vectors, and both write a factor-log table equal
to B's archived table, log for log. A third kS process through `arm.py`
(on s000) gives the same digest and B's table, with no issues. So the
rank stage's relations, attempts and table are unchanged by the 16-byte
table and the pipeline. As a diagnostic, run concurrently: kS 333 s
against kR 607 s.

## Runner, wrapper, gates and verifier on segments O1 and C1

`run_schedule.py --segments O1,C1` ran 11 rows, all valid
(`diagnostics_O1_C1.json`). `verify_receipt.py --correctness-only` then
reported (`correctness_O1_C1.json`):

- every executed row valid;
- one scalar per point across all IC arms and rT, replayed in the oracle;
- one relation per point across every IC process;
- the probe identities hold;
- Q0 matches the archived Feistel identity;
- the receipt matches the schedule.

The rank checks have no rows here. `check_log_table.py` passes
(`log-table-check.json`).

Diagnostic cold (setup + online) on s000, in seconds:

| cP | cSmF | cSmS | cSX | cSF | cS | cSaa | cSI |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 75.2 | 70.3 | 40.1 | 49.4 | 33.7 | 32.0 | 32.6 | 23.7 |

On s000 no mate state came before its representative, so every arm made
1,627,469 probes.
