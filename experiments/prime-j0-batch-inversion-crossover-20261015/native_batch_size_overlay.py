#!/usr/bin/env python3
"""Add a frozen 128-input chunk-size selector to the checked batch front door."""

from hashlib import sha256
from pathlib import Path
import sys

PARENT_SHA256 = "65cd774f8916721340ddec872dfa76522f496a5547c088acb3668016f3aa3c36"


def once(source, old, new):
    assert source.count(old) == 1, (old[:80], source.count(old))
    return source.replace(old, new)


def main(root):
    path = root / "src/bin/eisenstein_fixed.rs"
    original = path.read_text()
    assert sha256(original.encode()).hexdigest() == PARENT_SHA256
    start = original.index("fn benchmark_mixed640_batch_inverse(repetitions: usize) {")
    end = original.index("\nfn main() {", start)
    section = original[start:end]
    section = once(section,
        "fn benchmark_mixed640_batch_inverse(repetitions: usize) {",
        "fn benchmark_mixed640_batch_inverse(repetitions: usize, batch_size: usize) {")
    section = once(section,
        "    assert!((1..=100).contains(&repetitions));",
        "    assert!((1..=100).contains(&repetitions));\n"
        "    assert!((1..=128).contains(&batch_size) && 128 % batch_size == 0);")
    section = once(section,
        """    for _ in 0..repetitions {
        answers.extend(std::hint::black_box(
            unit_orbit_windows::multiply_u256_tau_split_prime_batch_inverse(
                std::hint::black_box(&words))));
    }
""",
        """    for _ in 0..repetitions {
        for chunk in words.chunks(batch_size) {
            answers.extend(std::hint::black_box(
                unit_orbit_windows::multiply_u256_tau_split_prime_batch_inverse(
                    std::hint::black_box(chunk))));
        }
    }
""")
    section = once(section,
        " point={last_point}\");",
        " point={last_point} batch_size={batch_size}\");")
    output = original[:start]+section+original[end:]
    output = once(output,
        """    if args.len() == 2 && args[0] == "--benchmark-split-prime-batch-inverse" {
        benchmark_mixed640_batch_inverse(args[1].parse().expect("batch repetitions"));
        return;
    }
""",
        """    if args.len() == 3 && args[0] == "--benchmark-split-prime-batch-inverse-size" {
        benchmark_mixed640_batch_inverse(
            args[2].parse().expect("batch repetitions"),
            args[1].parse().expect("batch size"));
        return;
    }
    if args.len() == 2 && args[0] == "--benchmark-split-prime-batch-inverse" {
        benchmark_mixed640_batch_inverse(args[1].parse().expect("batch repetitions"),128);
        return;
    }
""")
    path.write_text(output)
    print(sha256(output.encode()).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: native_batch_size_overlay.py CARGO_ROOT")
    main(Path(sys.argv[1]))
