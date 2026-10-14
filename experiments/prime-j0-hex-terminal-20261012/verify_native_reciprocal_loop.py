#!/usr/bin/env python3
"""Compile the exact native reciprocal word loop and compare its outputs with k*R."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs"
RECEIPT = HERE / "native-reciprocal-loop.json"
MASK = (1 << 64) - 1
SEED = 20261012
RANDOM_CASES = 4096


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def extract_function(source: str) -> str:
    start_tag = "fn reciprocal_cell_limbs_from_words_512("
    end_tag = "\nfn reciprocal_cell_limbs_512("
    if source.count(start_tag) != 1 or source.count(end_tag) != 1:
        raise RuntimeError("native reciprocal function boundary changed")
    start = source.index(start_tag)
    end = source.index(end_tag, start)
    body = source[start:end].strip()
    if not body.endswith("}") or "([product[8], product[9], product[10]], product[7])" not in body:
        raise RuntimeError("native reciprocal function body or output mapping changed")
    return body


def native_reciprocals(source: str) -> list[list[int]]:
    result = []
    for name in ("RECIP_V1", "RECIP_MINUS_W1"):
        match = re.search(rf"const {name}: \[u64; 7\] = \[(.*?)\];", source, re.S)
        if match is None:
            raise RuntimeError(f"missing {name}")
        words = [int(token, 0) for token in re.findall(r"0x[0-9a-f]+|\b\d+\b", match.group(1))]
        if len(words) != 7:
            raise RuntimeError(f"{name} has {len(words)} words")
        result.append(words)
    return result


def cases(source: str) -> list[tuple[list[int], list[int]]]:
    zero4, zero7 = [0] * 4, [0] * 7
    max4, max7 = [MASK] * 4, [MASK] * 7
    result = [
        (zero4, zero7), (max4, max7), (max4, [1] * 7),
        ([1] * 4, max7), ([MASK, 0, MASK, 0], [0, MASK, 0, MASK, 0, MASK, 0]),
    ]
    for i in range(4):
        for value in (1, 1 << 63, MASK):
            k = zero4.copy()
            k[i] = value
            result.extend((k, r) for r in (max7, [1] * 7))
    for j in range(7):
        for value in (1, 1 << 63, MASK):
            r = zero7.copy()
            r[j] = value
            result.extend((k, r) for k in (max4, [1] * 4))
    rng = random.Random(SEED)
    for _ in range(RANDOM_CASES):
        result.append(([rng.getrandbits(64) for _ in range(4)],
                       [rng.getrandbits(64) for _ in range(7)]))
    for reciprocal in native_reciprocals(source):
        for k in (zero4, max4, [1] * 4):
            result.append((k, reciprocal))
        for _ in range(512):
            result.append(([rng.getrandbits(64) for _ in range(4)], reciprocal))
    return result


def integer(words: list[int]) -> int:
    return sum(word << (64 * i) for i, word in enumerate(words))


def wrapper(function: str) -> str:
    return (
        "use std::io::{self, Read, Write};\n"
        + function
        + "\nfn main() {\n"
        " let mut input = String::new();\n"
        " io::stdin().read_to_string(&mut input).unwrap();\n"
        " let stdout = io::stdout();\n"
        " let mut out = io::BufWriter::new(stdout.lock());\n"
        " for line in input.lines() {\n"
        "  let mut words = [0u64; 11];\n"
        "  let mut count = 0usize;\n"
        "  for token in line.split_whitespace() {\n"
        "   assert!(count < 11);\n"
        "   words[count] = u64::from_str_radix(token, 16).unwrap();\n"
        "   count += 1;\n"
        "  }\n"
        "  assert_eq!(count, 11);\n"
        "  let k = [words[0], words[1], words[2], words[3]];\n"
        "  let r = [words[4], words[5], words[6], words[7], words[8], words[9], words[10]];\n"
        "  let (q, h) = reciprocal_cell_limbs_from_words_512(k, &r);\n"
        "  writeln!(out, \"{:016x} {:016x} {:016x} {:016x}\", q[0], q[1], q[2], h).unwrap();\n"
        " }\n"
        "}\n"
    )


def verify() -> dict[str, object]:
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode("utf-8")
    function = extract_function(source)
    panel = cases(source)
    rustc_version = subprocess.run(["rustc", "--version"], check=True,
                                   capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="hex-reciprocal-loop-") as tmp:
        directory = Path(tmp)
        (directory / "main.rs").write_text(wrapper(function))
        subprocess.run(["rustc", "--edition=2021", "-C", "opt-level=2",
                        str(directory / "main.rs"), "-o", str(directory / "loop")],
                       check=True, capture_output=True, text=True)
        input_text = "".join(
            " ".join(f"{word:016x}" for word in k + r) + "\n" for k, r in panel
        )
        process = subprocess.run([str(directory / "loop")], input=input_text,
                                 capture_output=True, text=True, check=True)
    output_lines = process.stdout.splitlines()
    if len(output_lines) != len(panel):
        raise RuntimeError(f"native output count {len(output_lines)} != {len(panel)}")
    for index, ((k, r), line) in enumerate(zip(panel, output_lines, strict=True)):
        got = [int(token, 16) for token in line.split()]
        product = integer(k) * integer(r)
        expected = [(product >> (64 * i)) & MASK for i in (8, 9, 10, 7)]
        if got != expected:
            raise RuntimeError(
                f"case {index} mismatch: k={k} r={r} got={got} expected={expected}"
            )
    return {
        "status": "verified",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": digest(source_bytes),
        "extracted_function_sha256": digest(function.encode()),
        "rustc": rustc_version,
        "architecture": platform.machine(),
        "os": platform.system(),
        "seed": SEED,
        "random_cases": RANDOM_CASES,
        "total_cases": len(panel),
        "case_input_sha256": digest(input_text.encode()),
        "native_output_sha256": digest(process.stdout.encode()),
        "oracle": "Python unbounded integer multiplication; words 8,9,10,7",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    actual = verify()
    if args.write:
        RECEIPT.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
        print(f"wrote {RECEIPT}")
    else:
        expected = json.loads(RECEIPT.read_text())
        if actual != expected:
            raise RuntimeError("native reciprocal loop receipt changed")
        print(f"verified {actual['total_cases']} exact native reciprocal loop cases")


if __name__ == "__main__":
    main()
