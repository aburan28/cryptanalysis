#!/usr/bin/env python3
"""Add the ordinary affine-layer arm for the distinct-scalar stream."""

from hashlib import sha256
from pathlib import Path
import sys

FRONT_SHA256 = "34857ca6813b767b6341440367da5fb475c845cc615215859a16d2f4c789a08b"


def main(root):
    front = root / "src/bin/eisenstein_fixed.rs"
    source = front.read_text()
    assert sha256(source.encode()).hexdigest() == FRONT_SHA256
    start = source.index("fn benchmark_mixed640_two_x_stream(")
    end = source.index("fn benchmark_mixed640_cache_budget_stream(", start)
    function = source[start:end]
    function = function.replace("two_x_stream", "affine_layer_stream")
    function = function.replace("warm_split_prime_two_x_table",
                                "warm_split_prime_table")
    function = function.replace("multiply_u256_tau_split_prime_two_x_affine_batch",
                                "multiply_u256_tau_split_prime_affine_layer_batch")
    insertion = source.index("\nfn main()", end)
    updated = source[:insertion] + "\n" + function + source[insertion:]
    dispatch = '''    if args.len() == 3 && args[0] == "--benchmark-split-prime-affine-layer-stream" {
        benchmark_mixed640_affine_layer_stream(
            args[2].parse().expect("stream passes"),
            args[1].parse().expect("batch size"));
        return;
    }
'''
    needle = "    let args: Vec<String> = std::env::args().skip(1).collect();\n"
    assert updated.count(needle) == 1
    updated = updated.replace(needle, needle + dispatch, 1)
    front.write_text(updated)
    print("front_sha256=" + sha256(updated.encode()).hexdigest())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
