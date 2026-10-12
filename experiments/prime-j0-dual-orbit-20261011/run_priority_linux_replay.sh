#!/usr/bin/env bash
set -euo pipefail

expected=${1:?expected commit SHA required}
[[ $expected =~ ^[0-9a-f]{40}$ ]]
work=$(mktemp -d /workspace/experiment-runs/prime-j0-dual-priority-linux-XXXXXX)
printf 'artifact_dir=%s\nexpected_commit=%s\ntiming_class=correctness_only\n' \
  "$work" "$expected" | tee "$work/manifest.txt"
uname -a > "$work/uname.txt"
lscpu > "$work/lscpu.txt"
rustc --version > "$work/rustc-version.txt"
cargo --version > "$work/cargo-version.txt"
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe-host \
  > "$work/host-probe.json"

git init -q "$work/repo"
git -C "$work/repo" remote add origin https://github.com/aburan28/cryptanalysis.git
git -C "$work/repo" sparse-checkout init --cone
git -C "$work/repo" sparse-checkout set experiments suite
git -C "$work/repo" fetch -q --depth=16 origin "$expected"
git -C "$work/repo" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/repo" rev-parse HEAD)" = "$expected"
printf 'checked_out_commit=%s\n' "$expected" >> "$work/manifest.txt"

cd "$work/repo"
experiment=experiments/prime-j0-dual-orbit-20261011
python3 "$experiment/verify_priority.py" > "$work/cover-verification.log"
python3 "$experiment/verify_priority_group.py" > "$work/group-verification.log"
python3 "$experiment/verify_priority_inputs.py" > "$work/input-verification.log"
python3 "$experiment/verify_priority_native_atlas.py" > "$work/atlas-verification.log"
python3 "$experiment/materialize_priority_native.py" "$work/native-priority" \
  > "$work/priority-materialization.log"
python3 "$experiment/materialize_priority_control.py" "$work/native-control" \
  > "$work/control-materialization.log"
python3 - "$work" <<'PY'
from pathlib import Path
import json
import sys

work = Path(sys.argv[1])
a = json.loads((work / 'native-priority/materialization.json').read_bytes())
b = json.loads((work / 'native-control/materialization.json').read_bytes())
assert a['generated_sha256'] == b['generated_sha256']
assert a['assets_sha256']['dual-rho0-fresh-inputs.json'] == \
    b['assets_sha256']['dual-rho0-fresh-inputs.json']
assert a['assets_sha256']['atlas-r1024-full-dual-rho0.bin'] != \
    b['assets_sha256']['atlas-r1024-full-dual-rho0.bin']
PY
sha256sum "$experiment/run_priority_linux_replay.sh" \
  "$experiment/priority-fresh-inputs.json" \
  "$experiment/cover-priority-rho0.bin" \
  "$experiment/atlas-r1024-full-dual-priority.bin" \
  > "$work/source-files.sha256"

export CARGO_TARGET_DIR="$work/cargo-target"
cargo test --locked --release --manifest-path "$work/native-priority/Cargo.toml" \
  --bin eisenstein_fixed dual_rho0_folded_matches_fresh_panel_and_controls \
  -- --nocapture --test-threads=1 > "$work/priority-targeted.log" 2>&1
grep -F 'test result: ok. 1 passed; 0 failed;' \
  "$work/priority-targeted.log" > "$work/priority-summary.txt"
cargo test --locked --release --manifest-path "$work/native-control/Cargo.toml" \
  --bin eisenstein_fixed dual_rho0_folded_matches_fresh_panel_and_controls \
  -- --nocapture --test-threads=1 > "$work/control-targeted.log" 2>&1
grep -F 'test result: ok. 1 passed; 0 failed;' \
  "$work/control-targeted.log" > "$work/control-summary.txt"
cargo test --locked --release --manifest-path "$work/native-priority/Cargo.toml" \
  --bin eisenstein_fixed -- --test-threads=2 \
  > "$work/priority-full-tests.log" 2>&1
grep -F 'test result: ok. 141 passed; 0 failed;' \
  "$work/priority-full-tests.log" > "$work/full-summary.txt"
cargo build --locked --release --manifest-path "$work/native-priority/Cargo.toml" \
  --bin eisenstein_fixed > "$work/priority-build.log" 2>&1
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary" > "$work/linux-binary.sha256"
sha256sum "$work/native-priority/src/bin/eisenstein_fixed.rs" \
  "$work/native-priority/src/bin/eisenstein_fixed/unit_orbit_windows.rs" \
  > "$work/native-source.sha256"

flag=--check-scalar-unit-orbit-u256-tau-dual-rho0-folded-gauge-xyzz-tau-fixed-fixture
"$binary" "$flag" experiments/prime-j0-tau-bucket-two-x-20261010/edge-fixture.json \
  > "$work/edge.stdout" 2> "$work/edge.stderr"
python3 - "$work" <<'PY'
from pathlib import Path
import sys

work = Path(sys.argv[1])
sys.path.insert(0, str(Path('experiments/prime-j0-power2-residual-20261010').resolve()))
from verify_fixture import check_fixture

assert (work / 'edge.stderr').read_bytes() == b''
result = check_fixture('unit_orbit_u256_tau_dual_rho0_folded_gauge_xyzz_tau_fixed',
                       'edge', Path('experiments/prime-j0-tau-bucket-two-x-20261010/edge-fixture.json'),
                       (work / 'edge.stdout').read_bytes(), 10)
print(f'edge: {result["cases"]} verified; stdout_sha256={result["stdout_sha256"]}', flush=True)
PY
printf 'linux_correctness_replay=passed\n' | tee "$work/result.txt"
