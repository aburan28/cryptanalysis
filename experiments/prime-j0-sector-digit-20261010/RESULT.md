# Canonical-sector digits replace four nearest-norm evaluations

Mode 130 uses three interval tests to choose the nearest signed
Eisenstein digit of a canonical unit-orbit residue at radix 512 or
1024. It retains the same 64,314,112-byte affine point table,
fourteen-window schedule, grouped gauge, and scalar representative as
mode 129. The [proof](PROOF.md) gives the exact sector boundaries and
row-zero tie rule. The implementation and [protocol](PROTOCOL.md) were
committed as `e7e7176d` before the new scalar panel was generated.

## Correctness and resource record

| Check | Recorded result |
| --- | ---: |
| Independent canonical-sector enumeration | 43,692 radix-512 and 174,764 radix-1024 digits matched the old norm rule |
| Equal-norm corner cases resolved by tie rule | 86 and 171, respectively |
| Exhaustive mode 129 versus mode 130 residue comparison | 1,310,720 / 1,310,720 digit, orbit ID, and unit code triples matched |
| Separately built affine point-table entries | Every entry matched |
| New scalar holdout | 4,096 / 4,096 matched points, representatives, fourteen choices, and operation counters |
| Independent binary point replay | First 128 / 128 new outputs matched |
| Frozen fixture | 129 / 129 expected points verified in each mode |
| Native release suite | 87 / 87 passed |
| Retained table bytes, each mode | 64,314,112 |
| Local one-process peak RSS, mode 129 | 273,776,640 bytes |
| Local one-process peak RSS, mode 130 | 272,678,912 bytes |

The [fresh input record](fresh-inputs.json) uses seed `20261010130` and
fixes 4,096 unsigned scalars with SHA-256
`24708c93cba06a9c0deb0d51d2befd9144f6ed845c6fd1162b9cb6147afe287d`.
Their reduced values are unique and disjoint from eleven earlier
panels. The [algebra check](algebra-check.log) independently enumerates
the old four-corner routine, including its tie behavior. The
[release log](native-tests.log) contains the holdout's per-scalar
gauge-product counts; the decoded-byte SHA-256 is
`ccaf9e51c10ae8abfcbfa8c26386296d82c894edb1cfda61fd37c4b55caf0ec2`.

The [verification receipt](verification.json) has SHA-256
`ade67fc307fb0f1ce48ed9addd6f54ed4e1d757fc2810af3301f6113341c36e3`.
It reports `status: passed`, no problems, 50 source/input hashes, 18 raw
output hashes, and release binary SHA-256
`aa1d5ca94afa137a08b0cc20ef53ccbdbe6b912ab5567bd9956d28ed04a4d1fe`.
The [x86 target check](x86-cross-check.json) passed a Rustup-stable
release compilation for `x86_64-unknown-linux-gnu` on this ARM64 macOS
host; it is a compile check. Remote Linux execution is serialized
through the RunPod runner.

The single-process RSS figures and raw local online timers are
diagnostics from a contended host. A measured online speed comparison
requires the paired Linux [isolation panel](ISOLATED_PANEL.md) with a
passing host preflight and noise gates. The arithmetic operation and
table counts are unchanged; the prospective gain is recoding cost.

Unit-symmetric digit sets and GLV recoding are established in
[earlier research](https://eprint.iacr.org/2013/705.pdf), and
[another implementation](https://docs.rs/zakura-pasta-curves/latest/pasta_curves/glv/index.html)
uses six-unit orbit quotienting. The contribution here is the explicit
sector rule for this canonical point-only U14 table, its proof, and
the verified integration with the existing secp256k1 evaluator.
