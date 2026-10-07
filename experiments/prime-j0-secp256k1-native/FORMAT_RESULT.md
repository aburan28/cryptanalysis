# Native seed-format comparison: correctness and isolated-run handoff

The two-arm native source was frozen in `66e06634`. A later frozen
change in `bcd281f1` removed an unnecessary digit scan from the
all-affine reference, and `6fd366f0` made correctness receipts writable
to a host-specific path. The final offline release binary SHA-256 is
`e0fabbe2419f13398db8e95586a7282521e83016093d06b7903e1fd492ff1295`.

The final no-timing correctness run passed **700 checks**: both formats
on all 64 original, 30 edge, and 256 held-out scalar/base inputs. Each
run recomputed the short representative and width-four digits in Rust,
checked all nine prepared seeds against Sage, and checked the final
scalar point. The cached-projective arm also matched its saved
stride/add/cache counts. `native-format-checks-v3.json` retains all
commands, raw output, exits, source/fixture hashes, compiler/host
details, and the binary hash.

The minimal one-use workload `bench-workload.json` contains **64 distinct
bases, one scalar per base**, and only the input point, scalar, and
independent expected output for each case. Its SHA-256 is
`30cb5ef3dc0190efe29851c89131af05913813799516fdcc0a534ec55d94360f`.
Both release benchmark modes accepted its first case and returned the
expected result; local timings were discarded. `make_isolated_manifest.py`
generated a 64-case, three-repetition paired manifest, and
`isolated_bench.require_manifest` passed its structural contract. That
local structural check used synthetic CPU/NUMA values on macOS; **host
isolation preflight and measurement have not run**.

On a prepared physical Linux host, build the crate there, run
`run_format_checks.py --output /workspace/receipts/native-format-host.json`
with `CA_NATIVE_TARGET_DIR` set to its build directory, and require its
`verified: true` result. Generate a manifest with the host's actual
cgroup, exclusive CPU set, one execution CPU, and NUMA node. Then run
`scripts/isolated_bench.py probe MANIFEST.json` and submit it only if
the strict preflight passes. The service alternates pair order and
preserves raw failures and noise-gate decisions.

The reference is the **all-affine format of the same width-four τ
method**, with one batch-normalization inversion. A passing comparison
would answer whether cached projective seeds help that controlled
format choice. It would not establish a win against the fastest
available secp256k1 implementation, secret-scalar safety, or academic
novelty. `cpu_speedup_claim` remains `null` until a qualifying receipt
exists.

The [seed-chain bound](SEED_CHAIN_BOUND.md) proves that the existing
nine-seed preparation has the minimum 72 `M+S` point-operation count
within its one-result double/τ/add graph, before two unit rotations.
Further preparation savings require a different point formula or digit
alphabet; this proof does not limit either.

The [x-only τ feasibility screen](XZ_TAU_RESULT.md) validates an XZ τ
map and a cheaper differential-add primitive on 1,024 controlled point
cases. A complete x-only scalar chain has not yet been constructed or
charged, so this is a primitive result only.

The [adjacent-pair reuse screen](PAIR_REUSE_RESULT.md) finds at most 15
repeated pair uses across the 64 distinct bases under the two simple
disjoint pairings.  This leaves little room for a one-use pair dictionary
to amortize its construction; combined point formulas remain open.
