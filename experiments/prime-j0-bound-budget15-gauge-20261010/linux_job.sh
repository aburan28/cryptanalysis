#!/usr/bin/env bash
set -euo pipefail

expected=${1:?expected commit SHA required}
freeze=ab16299685c62d590f909babee40dd9766604b72
work=$(mktemp -d /workspace/experiment-runs/prime-j0-bound-budget15-gauge-linux-XXXXXX)
printf 'artifact_dir=%s\nexpected_commit=%s\nsource_freeze_commit=%s\ntiming_class=correctness_only\n' "$work" "$expected" "$freeze" | tee "$work/manifest.txt"
uname -a > "$work/uname.txt"
lscpu > "$work/lscpu.txt"
rustc --version > "$work/rustc-version.txt"
cargo --version > "$work/cargo-version.txt"
python3 /workspace/cryptanalysis/scripts/isolated_bench.py probe-host > "$work/host-probe.json"

git init -q "$work/repo"
git -C "$work/repo" remote add origin https://github.com/aburan28/cryptanalysis.git
git -C "$work/repo" sparse-checkout init --cone
git -C "$work/repo" sparse-checkout set experiments suite/src
git -C "$work/repo" fetch -q --depth=3 origin "$expected"
git -C "$work/repo" checkout -q --detach FETCH_HEAD
actual=$(git -C "$work/repo" rev-parse HEAD)
test "$actual" = "$expected"
git -C "$work/repo" cat-file -e "$freeze^{commit}"
printf 'checked_out_commit=%s\n' "$actual" >> "$work/manifest.txt"

cd "$work/repo"
python3 experiments/prime-j0-bound-budget15-gauge-20261010/verify.py > "$work/receipt-verification.log"
python3 experiments/prime-j0-bound-budget15-gauge-20261010/verify_ops.py >> "$work/receipt-verification.log"
export CARGO_TARGET_DIR="$work/cargo-target"
cargo test --locked --release --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml --bin eisenstein_fixed -- --test-threads=2 > "$work/native-tests.log" 2>&1
grep -F 'test result: ok. 131 passed; 0 failed;' "$work/native-tests.log" > "$work/test-summary.txt"
cargo build --locked --release --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml --bin eisenstein_fixed > "$work/native-build.log" 2>&1
binary="$CARGO_TARGET_DIR/release/eisenstein_fixed"
sha256sum "$binary" > "$work/linux-binary.sha256"
sha256sum experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs > "$work/source-files.sha256"

python3 - "$binary" "$work" <<'PY'
import gzip
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

binary = Path(sys.argv[1])
work = Path(sys.argv[2])
sys.path.insert(0, str(Path('experiments/prime-j0-bound-budget15-gauge-20261010').resolve()))
from run_replay import HERE, MODES, PANELS

for panel, fixture, count in PANELS:
    for label, (flag, _) in MODES.items():
        result = subprocess.run([str(binary), flag, str(fixture)], capture_output=True, timeout=600)
        (work / f'{panel}-{label}.stdout').write_bytes(result.stdout)
        (work / f'{panel}-{label}.stderr').write_bytes(result.stderr)
        assert result.returncode == 0 and not result.stderr, (panel, label, result.returncode)
        frozen = gzip.decompress((HERE / f'{panel}-{label}.out.gz').read_bytes())
        assert result.stdout == frozen, (panel, label)
        assert len(result.stdout.splitlines()) == count, (panel, label)
        print(f'{panel}-{label}: {count} verified; sha256={sha256(result.stdout).hexdigest()}', flush=True)
PY
printf 'linux_correctness_replay=passed\n' | tee "$work/result.txt"
