# n53 fixed-base rank restarts: verified cross-repository replay

The compact K220 source-curve base produced full rank and a verified logarithm
for one newly generated n53 public point in each of twelve held-out IC runs.
The paired signed-Frobenius rho reference verified the same logarithm in six
runs. The 400,000-probe restart reduced the median paired rank-probe count by
5.189% and increased the median paired complete-cold cost ratio to 1.020, so
it did not pass the frozen selection gate of at least 15% probe reduction
without higher cold cost. This bridge re-executes the Python group-arithmetic
rank, target, and rho verifiers against all archived held-out cells.

The evidence comes from merged
[crypto PR #1626](https://github.com/aburan28/crypto/pull/1626), pinned to
commit 9be831f4ec75c9a18334a67033333aeeb4b42fad. Its
[raw runs and frozen inputs](https://github.com/aburan28/crypto/tree/9be831f4ec75c9a18334a67033333aeeb4b42fad/research/notes/ecc2k130/n53_fixed_base_rank_restarts_20261010)
remain in crypto. [source.json](source.json) binds the exact commit, analysis,
registry, and verifier files. [replay.py](replay.py) archives that commit,
recomputes candidate and workload IDs, checks source and input hashes, reruns
the published 18-cell analyzer, then regenerates and compares 12 rank, 12
target, and six rho replay receipts. [REPLAY.json](REPLAY.json) records the
local result. The Rust executable hashes are frozen in the upstream run
records; the executables themselves are build artifacts and are not included
in this archive.

The field is GF(2^53) with polynomial exponents [53,6,2,1,0], and the
curve is y^2 + xy = x^3 + 1 with subgroup order 21044858204113. The
source curve has catalog ID EC1N53Ce0hb097de99be9a. The fixed base contains
23,320 distinct subgroup-usable points in 220 signed-Frobenius columns,
with BLAKE3 digest
7af2460c8b5a2c29f9d1aa7fefecbcde3a6ce761293d0dab0cecfc3bc980b973.
The public input is Q = [2939726529610565,1384157319972946]; every arm
returned scalar 11184763905218, checked by independent group arithmetic.
The control candidate is
IC1N53Ce0fb23320PDP4rootRCguidedLAgaussTDdirectISO0h3b66c9056640;
the cap candidate has suffix h7f0d28c1d4ff. The six rank seeds are
531053 through 531058; rho seeds are 530153 through 530158. These are six
paired rank/rho repetitions on **one** held-out Q, with six distinct workload
IDs recorded upstream.

| Arm | Verified runs | Total rank probes | Capped rank attempts | Median complete-cold IC ms | Median target-online ms | Maximum observed RSS bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Unbounded rank control | 6/6 | 112,462,789 | 0 | 9,015.370 | 2.704 | 349,863,936 |
| 400,000-probe restart | 6/6 | 105,307,017 | 10 | 8,994.088 | 2.634 | 350,552,064 |
| Signed-Frobenius rho, same Q | 6/6 | — | — | — | 180.754 | 19,628,032 |

The cold values include base/index preparation, every rank attempt, relation
checking, matrix construction and final linear algebra, target handling, and
scalar checking. The primary one-target online interval begins with
target-dependent work after reusable preparation and includes the five
exclusive query, PDP, relation-check, descent, and recovery-check phases.
The rho interval begins at target-dependent walk computation and ends after
scalar checking. All 18 cells exited successfully under one thread, a
60-second external wall cap, and a 16-GiB observed RSS cap. The upstream
analysis preserves each raw success, external wall, peak RSS, rank trace,
phase breakdown, source and executable hash, and independent replay receipt.

Median paired **observed** rho/IC online ratios were 70.753 for the control
and 60.865 for the restart arm. The host was a shared Apple T6041 without
the required isolation receipt, so the controlled online-speedup value
remains null. The six-draw descriptive bootstrap intervals upstream were
-0.877% to 14.026% for median paired probe reduction and 0.864 to 1.182
for the median paired cold ratio. The rank PDP stage itself consumed median
7,042.778 ms in the control and 6,928.441 ms with restarts, about 77% of
complete cold cost in each arm.

The previous cryptanalysis n53 [cold full-rank control](../ecc2k130-cold-fullrank-20261006/RESULT.md)
used a different signed-expanded support-index policy and reached its
180-second cap before a target record was emitted. Its archived status remains
valid for that policy. The compact K220 result closes the separate
source-curve fixed-base control cell: one public target, full rank, direct
target recovery, and same-point automorphism-aware rho. It leaves the
equal-useful-size original/descendant-native/transported/pullback comparison,
charged degree-263 route, and isolated timing comparison open.

The next rank-stage experiment should freeze a same-base, same-Q policy that
reduces cost per support probe or changes the pair-root index, then compare
complete cold and target-online costs. This follows the measured rank-PDP
share and the restart gate result; the equal-useful-size degree-263 bases
must use their own exact manifests and charged map costs.

Replay from a local crypto repository containing the pinned commit:

~~~sh
python3 experiments/ecc2k130-n53-fixed-base-rank-bridge-20261010/replay.py \
  --crypto-repo /absolute/path/to/crypto \
  --out experiments/ecc2k130-n53-fixed-base-rank-bridge-20261010/REPLAY.json
~~~

The script accepts a dirty or differently checked-out crypto repository
because it reads only the pinned Git commit. If the result file already
exists, it compares exact bytes and refuses a changed result.
