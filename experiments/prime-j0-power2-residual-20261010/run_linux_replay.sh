#!/usr/bin/env bash
set -euo pipefail

expected=${1:?expected commit SHA required}
[[ $expected =~ ^[0-9a-f]{40}$ ]]
work=$(mktemp -d /workspace/experiment-runs/prime-j0-power2-residual-linux-XXXXXX)
printf 'artifact_dir=%s\nexpected_commit=%s\ntiming_class=correctness_only\n' "$work" "$expected" | tee "$work/manifest.txt"
uname -a > "$work/uname.txt"
lscpu > "$work/lscpu.txt"
rustc --version > "$work/rustc-version.txt"
cargo --version > "$work/cargo-version.txt"
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe-host > "$work/host-probe.json"

git init -q "$work/repo"
git -C "$work/repo" remote add origin https://github.com/aburan28/cryptanalysis.git
git -C "$work/repo" sparse-checkout init --cone
git -C "$work/repo" sparse-checkout set experiments
git -C "$work/repo" fetch -q --depth=16 origin "$expected"
git -C "$work/repo" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/repo" rev-parse HEAD)" = "$expected"
printf 'checked_out_commit=%s\n' "$expected" >> "$work/manifest.txt"

cd "$work/repo"
experiment=experiments/prime-j0-power2-residual-20261010
python3 "$experiment/verify_atlas.py" > "$work/atlas-verification.log"
python3 "$experiment/verify_inputs.py" > "$work/input-verification.log"
python3 "$experiment/verify_group.py" --design > "$work/design-replay.log"
python3 "$experiment/materialize_native.py" "$work/native" > "$work/materialization.json"
sha256sum "$experiment/run_linux_replay.sh" "$experiment/native-delta.patch" \
  "$experiment/fresh-inputs.json" "$experiment/atlas-r1024-full.bin" \
  "$experiment/atlas-r1024-terminal.bin" > "$work/source-files.sha256"

export CARGO_TARGET_DIR="$work/cargo-target"
cargo test --locked --release --manifest-path "$work/native/Cargo.toml" \
  --bin eisenstein_fixed power2_residual -- --nocapture --test-threads=1 \
  > "$work/native-targeted-tests.log" 2>&1
grep -F 'test result: ok. 1 passed; 0 failed;' "$work/native-targeted-tests.log" \
  > "$work/targeted-summary.txt"
cargo test --locked --release --manifest-path "$work/native/Cargo.toml" \
  --bin eisenstein_fixed -- --test-threads=2 \
  > "$work/native-full-tests.log" 2>&1
grep -F 'test result: ok. 136 passed; 0 failed;' "$work/native-full-tests.log" \
  > "$work/full-summary.txt"
cargo build --locked --release --manifest-path "$work/native/Cargo.toml" \
  --bin eisenstein_fixed > "$work/native-build.log" 2>&1
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary" > "$work/linux-binary.sha256"
sha256sum "$work/native/src/bin/eisenstein_fixed.rs" \
  "$work/native/src/bin/eisenstein_fixed/unit_orbit_windows.rs" \
  > "$work/native-source.sha256"

flag=--check-scalar-unit-orbit-u256-tau-power2-residual-gauge-xyzz-tau-fixed-fixture
"$binary" "$flag" experiments/prime-j0-tau-bucket-two-x-20261010/edge-fixture.json \
  > "$work/edge.stdout" 2> "$work/edge.stderr"
python3 - "$work" <<'PY'
from pathlib import Path
import sys

work = Path(sys.argv[1])
sys.path.insert(0, str(Path('experiments/prime-j0-asymmetric-r944-20261010').resolve()))
from verify import check_fixture

assert (work / 'edge.stderr').read_bytes() == b''
result = check_fixture('edge', Path('experiments/prime-j0-tau-bucket-two-x-20261010/edge-fixture.json'),
                       (work / 'edge.stdout').read_bytes(), 10)
print(f'edge: {result["cases"]} verified; stdout_sha256={result["stdout_sha256"]}', flush=True)
PY
printf 'linux_correctness_replay=passed\n' | tee "$work/result.txt"
