#!/usr/bin/env bash
set -euo pipefail

expected=${1:?expected commit SHA required}
[[ $expected =~ ^[0-9a-f]{40}$ ]]
work=$(mktemp -d /workspace/experiment-runs/prime-j0-radix640-linux-XXXXXX)
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
git -C "$work/repo" fetch -q --depth=3 origin "$expected"
git -C "$work/repo" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/repo" rev-parse HEAD)" = "$expected"
printf 'checked_out_commit=%s\n' "$expected" >> "$work/manifest.txt"

cd "$work/repo"
experiment=experiments/prime-j0-mixed-radix640-20261010
python3 "$experiment/verify.py" > "$work/source-verification.log"
python3 "$experiment/materialize_native.py" "$work/native" > "$work/materialization.json"
sha256sum "$experiment/run_linux_replay.sh" "$experiment/native-candidate.patch" \
  "$experiment/fresh-inputs.json" \
  experiments/prime-j0-bound-budget15-gauge-20261010/fresh-fixture.json \
  > "$work/source-files.sha256"

export CARGO_TARGET_DIR="$work/cargo-target"
cargo test --locked --release --manifest-path "$work/native/Cargo.toml" \
  --bin eisenstein_fixed radix640 -- --nocapture --test-threads=1 \
  > "$work/native-tests.log" 2>&1
grep -F 'test result: ok. 2 passed; 0 failed;' "$work/native-tests.log" > "$work/test-summary.txt"
cargo build --locked --release --manifest-path "$work/native/Cargo.toml" \
  --bin eisenstein_fixed > "$work/native-build.log" 2>&1
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary" > "$work/linux-binary.sha256"

python3 - "$binary" "$work" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

binary = Path(sys.argv[1])
work = Path(sys.argv[2])
fixture = Path('experiments/prime-j0-bound-budget15-gauge-20261010/fresh-fixture.json')
expected = len(json.loads(fixture.read_text())['cases'])
flag = '--check-scalar-unit-orbit-u256-tau-mixed-radix640-gauge-xyzz-tau-fixed-fixture'
result = subprocess.run([str(binary), flag, str(fixture)], capture_output=True, timeout=1800)
(work / 'prior4096.stdout').write_bytes(result.stdout)
(work / 'prior4096.stderr').write_bytes(result.stderr)
assert result.returncode == 0 and not result.stderr, result.returncode
assert len(result.stdout.splitlines()) == expected, (expected, len(result.stdout.splitlines()))
print(f'prior_fixture_cases={expected}')
print(f'prior_fixture_stdout_sha256={sha256(result.stdout).hexdigest()}')
PY
printf 'linux_correctness_replay=passed\n' | tee "$work/result.txt"
