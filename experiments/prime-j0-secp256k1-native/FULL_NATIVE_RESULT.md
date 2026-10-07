# Native variable-time scalar-input replay

The native scalar reduction and width-four recoder were frozen in
`98328303` before release replay. They use arbitrary-precision integer
arithmetic and the exact subgroup order, endomorphism eigenvalue, and
Gauss-reduced lattice basis from the earlier checked Sage result. The
replay computes each short `a+bτ` representative and every digit in
Rust, then feeds the **native digits** to the native point path.

The offline locked release binary passed the 64-case original panel and
30-case zero/order edge panel: **94 representative checks, 94 digit-stream
checks, 846 prepared seed checks, and 94 output checks**. Every saved
stride/add/cache count matched Sage. `native-full-result.json` retains
the exact source and fixture hashes, build command, compiler/host details,
raw exits, and binary SHA-256
`00b416151d7e8f9439313dddddf232c10ae6cd97ede70438f9522b8e81f16910`.

A separate held-out protocol and generator were frozen in `43443d26`
before Sage produced 256 fresh full-width scalars across eight bases.
The fixture and replay runner were frozen in `ff8a1584`. The **same
binary** passed all **256 representatives, 256 digit streams, 2,304 seed
points, 256 final outputs, and evaluator counts**. The fixture SHA-256
is `73d0e94aa439d48dbba79fb9b88b460fbca7c0982e814c66c6387e5dfa9a6bce`.
`native-fresh-result.json` retains its raw execution and provenance.

This establishes correctness for these **350 scalar inputs** on physical
ARM64 macOS. The implementation is variable time, exposes its scalar
input through a replay executable, and has not undergone secret-scalar
review. Exceptional cached additions still require a control. The host
has no isolation receipt and no native operation was timed; both
`cpu_speedup_claim` and `academic_novelty_claim` remain `null`.
