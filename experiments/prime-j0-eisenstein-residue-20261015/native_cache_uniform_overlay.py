#!/usr/bin/env python3
"""Expose the frozen seven-row cache-budget path on the uniform fixture."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b"
WINDOWS_SHA256 = "71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d"


def main(root: Path) -> None:
    front = root / "src/bin/eisenstein_fixed.rs"
    windows = root / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    f, w = front.read_text(), windows.read_text()
    assert sha256(f.encode()).hexdigest() == FRONT_SHA256
    assert sha256(w.encode()).hexdigest() == WINDOWS_SHA256
    begin = f.index("fn benchmark_mixed640_affine_layer_uniform(")
    end = f.index("\nfn main()", begin)
    benchmark = f[begin:end]
    assert benchmark.count("fn benchmark_mixed640_affine_layer_uniform(") == 1
    benchmark = benchmark.replace("affine_layer_uniform", "cache_budget_uniform")
    benchmark = benchmark.replace("warm_split_prime_table", "warm_split_prime_cache_budget_table")
    benchmark = benchmark.replace("multiply_u256_tau_split_prime_affine_layer_batch",
                                  "multiply_u256_tau_split_prime_cache_budget_affine_batch")
    f = f[:end] + "\n" + benchmark + f[end:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-cache-budget-uniform" {
        benchmark_mixed640_cache_budget_uniform(
            args[2].parse().expect("uniform passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert f.count(needle) == 1
    front.write_text(f.replace(needle, needle + dispatch, 1))
    print("front_sha256=" + sha256(front.read_bytes()).hexdigest())
    print("windows_sha256=" + sha256(w.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
