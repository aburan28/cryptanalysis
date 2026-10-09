# Paired fixed-generator scalar benchmark handoff

The benchmark pair now evaluates the same public secp256k1 generator and
scalar in two complete native paths. The reference uses the conventional
`SecpFieldElement` Montgomery field, cached-projective width-four `tau`
digits, and its fixed inversion chain. The candidate uses the balanced
Eisenstein Montgomery field, width-two unit digits, deferred `tau` and
mixed addition, and the same `p-2` inversion chain translated to that
field. Every process handles exactly one scalar with fresh point tables.

The frozen workload has **86 distinct scalars**: 22 declared edge cases
and 64 nonzero scalars from Python seed `20261009`. The base is the
standard secp256k1 generator for every case. Expected affine points are
computed by the independent Python double-and-add group law in
`lazy_tau_screen.py`. The fixture SHA-256 is
`0b8f8f7db1d55e1f760884e086c92db74ba4a18f2791e5e3d9952d59dda1fe8a`.

## Timing and verification boundary

Both binaries load the fixture, validate and decode the fixed base, and
force curve-wide constants before the internal timer. The timer starts
before parsing that case's scalar. It includes short-representative
selection, digit recoding, one-use seed or orbit preparation, every point
step, affine inversion, conversion to the standard output encoding,
formatting, and the expected-point equality check. The check must pass
before `verified=1` is printed. The isolated runner also compares the
four frozen input fields and affine point string and hashes both binaries
and all listed source artifacts. No target-dependent point table is
shared across cases.

The two paths use different digit alphabets and point schedules; the
comparison tests their complete fixed-generator methods. The candidate
currently converts the final balanced Eisenstein coordinates to standard
hex using arbitrary-precision integers inside the timer, while the
reference uses native field serialization. That conversion cost is
charged to the candidate. Both inversion chains use 257 squarings and
14 field products. This is a public-scalar, variable-time experiment.

## Local correctness gate

From this directory:

```sh
cargo build --release --bins
PYTHONDONTWRITEBYTECODE=1 python3 run_eisenstein_pair_checks.py
```

The check mode emits no timing field. It recomputes every expected
point from the independent group law, launches each binary once per
case, and checks the exact curve, base, scalar, affine point, and
`verified=1` fields. The 86 cases produced **172 verified outputs**.
The checked conventional binary SHA-256 is
`310ce35fe6ed983ae088c1f38bfedd9e3423524dae93ca511ab2a4beac73c9e0`;
the Eisenstein binary SHA-256 is
`689f09551461038405620e5ec8a900797c35bdd9e65653ddab31a650e2bbc475`.

## Isolated host dispatch

Build both binaries on the target Linux host from this exact source
snapshot. Generate a manifest there using the host's actual exclusive
CPU partition and NUMA node. For example, after substituting the
verified host allocation:

```sh
python3 make_eisenstein_pair_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --conventional /workspace/cryptanalysis/experiments/prime-j0-secp256k1-native/target/release/prime-j0-secp256k1-native-replay \
  --eisenstein /workspace/cryptanalysis/experiments/prime-j0-secp256k1-native/target/release/eisenstein_fixed \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/eisenstein-pair.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe /workspace/isolated-bench/eisenstein-pair.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/eisenstein-pair.json
```

The manifest generator validates the runner's structural contract and
refuses to overwrite an existing manifest. The current RunPod CPU Pod
fails the [host isolation preflight](../../docs/ISOLATED_BENCHMARKS.md),
so it cannot promote a paired CPU timing ratio. The correctness gate
above and manifest structure can run locally without making a timing
claim.
