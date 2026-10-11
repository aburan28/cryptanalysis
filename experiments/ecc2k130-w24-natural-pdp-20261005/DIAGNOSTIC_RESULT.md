# W24 planted-witness localization: both witness classes matter

The exact v1 S3-chain XCNF **does admit** the predeclared six-point curve
witness. Pinning all six field inverses and four partial-sum u values returned
SAT in 0.518 seconds with zero conflicts, and independent checked Sage replay
verified a raw six-point sum in the selected `[4]` fiber. With only one
witness class pinned, the bounded search still found no model. This verifies
the known witness path through the circuit but does not measure natural
decomposition yield or establish a complete index-calculus candidate.

The [diagnostic protocol](DIAGNOSTIC_PROTOCOL.md) and
[configuration](DIAGNOSTIC_CONFIG.json) were committed and pushed before
these planted-only runs. Every variant starts from the same v1 XCNF,
SHA-256 `2e2748a557e1ca7a1773ee14fedc910410db7bf2c1dda2ab076ae9c248fba877`,
and adds only the stated unit clauses. The parent has 91,861 variables,
50,208 AND gates and 40,197 native-XOR rows. The exact base masks, planted
raw points, selected torsion fiber, solver 5.14.7 binary, one worker, seed
zero, and 4 GiB monitored RSS cap are identical across variants.

| Strict variant | Added unit clauses | SAT result | Monitored process wall | Independent Sage result |
| --- | ---: | --- | ---: | --- |
| [Both inverse and intermediate pinned](runs/v2-strict-both/receipt.json) | 1,310 | SAT, 0 conflicts | 0.518 s | [PASS_PLANTED_GROUP_REPLAY](runs/v2-strict-both/sage_replay.json) |
| [Inverses pinned only](runs/v2-strict-inverse/receipt.json) | 786 | External 30 s cutoff, no solver status or model | 30.082 s | [NO_MODEL_REPLAYED](runs/v2-strict-inverse/sage_replay.json) |
| [Intermediates pinned only](runs/v2-strict-intermediate/receipt.json) | 524 | `INDETERMINATE` at 100,001 conflicts | 14.636 s | [NO_MODEL_REPLAYED](runs/v2-strict-intermediate/sage_replay.json) |

The inverse-only timeout has no UNSAT meaning; its solver did not return a
final conflict count. The intermediate-only run hit the conflict bound while
well within the external wall limit. The fast both-pinned answer is an oracle
correctness control, not evidence that an unpinned solver can discover the
relation. Since neither single-class variant succeeded, this bound cannot
attribute the v1 failure to inverse search alone or intermediate search
alone. The next solver design should remove *both* costly unknown classes:
screen an exact rational-W24 mask recognizer in place of six inverse
witnesses, and compare an eliminated/compact S7 or pair-root formulation
against four free intermediate u coordinates. These are proposals; they
need a new frozen protocol and controlled stage runs before any conclusion.

The first diagnostic implementation allowed a 15-second outer-watchdog
grace beyond the stated 30-second solver limit. Its both-pinned run
[passed](runs/v2-original-both/receipt.json) in 0.548 seconds; the
[inverse-only run](runs/v2-inverse-overrun/receipt.json) was killed at
45.060 seconds with no solver status. The overrun is preserved as a raw
failure and **excluded from the strict comparison**. The watchdog was
corrected to kill at the 30-second process wall, after which all three
variants above were rerun in protocol order. The old and strict XCNF bytes
are identical within each pin variant; the only source difference was the
outer timeout comparison. [Source reconstruction](verify_original_source.py)
verifies both original source hashes from the final code and the exact
one-line change; its [machine receipt](source_reconstruction.json) is retained.

All five raw XCNF and solver logs are losslessly compressed in their run
directories. [Archive verification](verify_diagnostic_archives.py) checks
each decompressed hash and byte count, runtime receipt, solver output, Sage
replay binding, and strict source digest; its
[machine receipt](archive_verification.json) is retained. The checked Sage launcher was used
for every runtime receipt and independent group replay. The host was not
CPU-isolated; process wall measurements are exploratory diagnostics, not
controlled speedup ratios. No frozen natural target was attempted. Useful
relation rank, final matrix cost, target logarithm, online wall time,
paired rho result, speedup, and `candidate_id` remain `null`.

From the repository root, run `python3
experiments/ecc2k130-w24-natural-pdp-20261005/verify_diagnostic_archives.py`
and `python3
experiments/ecc2k130-w24-natural-pdp-20261005/verify_original_source.py`.
For a fresh independent group replay, use `./sage -python
experiments/ecc2k130-w24-natural-pdp-20261005/replay_sage.py --run-dir
experiments/ecc2k130-w24-natural-pdp-20261005/runs/v2-strict-both`
after copying that run directory to a fresh path and removing only the
copied `sage_replay.json`, since replay output is intentionally write-once.
