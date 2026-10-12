# XYZZ accumulation for the U14 unit-orbit scalar format

The U14 unit-orbit format now has a native XYZZ accumulator that reuses its
frozen digit atlas and point table. This changes the mixed-addition arithmetic
while retaining the same scalar representation and table payload. The
established [XYZZ formulas](https://hyperelliptic.org/EFD/g1p/auto-shortw-xyzz.html)
use `8M+2S` per generic affine mixed addition. On the 129-case U14 fixture,
the digit stream has 1,677 generic additions; the symbolic count is 16,770
field products with squares charged as products, compared with 18,447 for
the current Jacobian path. This count is an arithmetic diagnostic; the native
path still uses the general `Pair::mul` balance routine at each multiplication.

The standalone Cargo package assembles the upstream binary source and U14
module at build time, then appends the XYZZ code. It leaves the shared U14
implementation intact. `--scalar-unit-orbit-u14-xyzz-fixed` reads hexadecimal
scalars from standard input and emits one JSON result per scalar. The same
binary also accepts the upstream Jacobian fixture modes and the XYZZ
`--benchmark-scalar-unit-orbit-u14-xyzz-fixed-case FIXTURE INDEX` mode. The
benchmark interval starts before scalar recoding and ends after affine
conversion and expected-point assertion; table construction and scalar input
parsing are recorded as preparation outside that interval.

## Correctness receipt

The native checker compares all 129 outputs with the independent secp256k1
fixture and checks `0`, `1`, the subgroup order `n`, and `n+1`. It also checks
one benchmark-mode dispatch, including the same expected point and all fields
required by the isolated runner. Raw output, source hashes, executable hash,
and fixture hash are retained in `xyzz-native-check.json` and its companion
files. The mathematical formula and full digit-stream checks are in
`xyzz-formula-result.json` and `xyzz-u14-replay-result.json`.

From the repository root:

```sh
CARGO_TARGET_DIR=/tmp/prime-j0-xyzz-target cargo build --offline --release \
  --manifest-path experiments/prime-j0-xyzz-20261009/Cargo.toml
python3 experiments/prime-j0-xyzz-20261009/check_native_xyzz.py \
  --binary /tmp/prime-j0-xyzz-target/release/prime-j0-xyzz-experiment \
  --output /tmp/xyzz-native-check.json
```

The paired CPU panel should use the same release binary for U14 Jacobian and
U14 XYZZ, identical fixture points, alternating order, and a strict
host-isolation receipt from `scripts/isolated_bench.py`. The existing RunPod
CPU Pod fails that host preflight; its local wall times are not used for a
speedup result. The next implementation experiment is to fuse deferred
balancing into the XYZZ operations, preserving this exact-output checker.
