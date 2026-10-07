# Native point-path edge controls

The updated Rust source, edge protocol, and Sage fixture generator were
frozen in `f51babc8`. The checked repository Sage launcher generated the
fixture after saving `edge-runtime-info.json`. The fixture, receipt, and
native replay runner were frozen in `fc4a1401` before the recorded native
execution. The fixture SHA-256 is
`5b375ae82f5b24ce433ae1787374bb6ed064c3c958184312f4cd799ebe62732f`.

The 30 cases use three distinct nonidentity bases and scalars
`0,1,2,3,4,7,8,n−1,n,n+1`, where `n` is the secp256k1 subgroup order.
Sage independently supplied the short lattice representatives, width-four
digits, nine expected prepared seeds per case, final scalar points, and
operation counts. The updated native binary checked all **270 prepared
seeds**, **30 final outputs**, and all saved counts. It correctly returned
the curve identity for `0` and `n`. The same binary also replayed the
original **64 outputs and 576 prepared seeds** without mismatch. The
offline release binary SHA-256 is
`16a136c69e0c7cc2b90c1670a1eadc46db059c1a880a981e687951f99cf63f3e`.
`native-edge-result.json` retains the exact build and replay commands,
source/fixture/binary hashes, compiler and host details, raw output, and
exit codes.

This extends **point-path correctness** only. The native binary still
consumes Sage-produced short representatives and digits. Its cached
Jacobian addition explicitly rejects an exceptional equal-X input; the
control set did not exercise that branch. Secret-scalar safety and a full
scalar-input API are not established. The local host has no isolation
receipt, so `cpu_speedup_claim` remains `null`; there is no CPU speedup or
academic novelty claim.
