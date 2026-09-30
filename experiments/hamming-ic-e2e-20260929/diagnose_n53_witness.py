#!/usr/bin/env python3
"""Check a frozen N53 planted XCNF against its known point witness."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from n53_group import Field, N, normal_basis

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_scale_v1"
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_model(stdout):
    if "s SATISFIABLE" not in stdout:
        return None
    model = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for word in line[2:].split():
                literal = int(word)
                if literal:
                    model[abs(literal)] = literal > 0
    return model


def witness_units(receipt, conjugates, pin_middle):
    fixture = receipt["fixture"]
    pair_masks = {}
    for i in range(N):
        for j in range(i + 1, N):
            x = conjugates[i] ^ conjugates[j]
            assert x not in pair_masks
            pair_masks[x] = (i, j)
    assert len(pair_masks) == N * (N - 1) // 2
    units = []
    for row, x in zip(receipt["x_rows"], fixture["x"], strict=True):
        selected = set(pair_masks[x])
        assert len(row) == N and len(selected) == 2
        units.extend(var if i in selected else -var for i, var in enumerate(row))
    if pin_middle:
        for row, value in zip(receipt["middle_rows"], fixture["intermediate_x"], strict=True):
            assert len(row) == N
            units.extend(var if value >> i & 1 else -var for i, var in enumerate(row))
    assert len({abs(unit) for unit in units}) == len(units)
    return units


def write_pinned(archive, path, units):
    digest = hashlib.sha256()
    with gzip.open(archive, "rb") as source, path.open("wb") as out:
        header = source.readline()
        digest.update(header)
        words = header.split()
        assert words[:2] == [b"p", b"cnf"] and len(words) == 4
        out.write(f"p cnf {int(words[2])} {int(words[3]) + len(units)}\n".encode())
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
            out.write(block)
        out.write("".join(f"{unit} 0\n" for unit in units).encode())
    return digest.hexdigest()


def verify_xcnf(path, model):
    checked = {"clauses": 0, "xor_rows": 0, "model_variables": len(model)}
    with path.open() as source:
        for line in source:
            if line.startswith("p "):
                nvars = int(line.split()[2])
                if len(model) != nvars or set(model) != set(range(1, nvars + 1)):
                    return False, checked
                continue
            words = line.split()
            if not words:
                continue
            xor = words[0] == "x"
            literals = [int(word) for word in words[1 if xor else 0:-1]]
            assert words[-1] == "0"
            values = [model.get(abs(lit)) == (lit > 0) for lit in literals]
            if xor:
                checked["xor_rows"] += 1
                if sum(values) % 2 != 1:
                    return False, checked
            else:
                checked["clauses"] += 1
                if not any(values):
                    return False, checked
    return True, checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", choices=("fc", "unary"), required=True)
    parser.add_argument("--pin", choices=("all", "x"), default="all")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wall-seconds", type=int, default=20)
    args = parser.parse_args()
    if args.wall_seconds < 1:
        raise ValueError("wall limit must be positive")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("diagnostic output is immutable")
    out.mkdir(parents=True)
    receipt_path = RUN / f"{args.encoding}_planted" / "receipt.json"
    archive = receipt_path.parent / "system.xcnf.gz"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "EXTERNAL_WATCHDOG"
    assert receipt["encoding"] == args.encoding
    _, conjugates = normal_basis(Field())
    units = witness_units(receipt, conjugates, args.pin == "all")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="n53-witness-") as temp:
        pinned = Path(temp) / "pinned.xcnf"
        original_hash = write_pinned(archive, pinned, units)
        assert original_hash == receipt["xcnf_sha256"]
        cmd = [str(CMS), "--verb=0", "--threads=1", str(pinned)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=args.wall_seconds, check=False)
            stdout, stderr, code, timed_out = result.stdout, result.stderr, result.returncode, False
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode(errors="replace") if error.stdout else ""
            stderr = error.stderr.decode(errors="replace") if error.stderr else ""
            code, timed_out = None, True
        (out / "solver.stdout.txt.gz").write_bytes(gzip.compress(stdout.encode(), mtime=0))
        (out / "solver.stderr.txt.gz").write_bytes(gzip.compress(stderr.encode(), mtime=0))
        model = parse_model(stdout)
        valid, checked = verify_xcnf(pinned, model) if model is not None else (None, None)
        pinned_hash = sha256(pinned)
    report = {"kind": "n53_planted_witness_formula_diagnostic",
              "encoding": args.encoding, "pin": args.pin,
              "source_receipt_sha256": sha256(receipt_path),
              "source_xcnf_sha256": original_hash,
              "source_sha256": {"diagnose_n53_witness.py": sha256(Path(__file__)),
                                "n53_group.py": sha256(HERE / "n53_group.py")},
              "pinned_xcnf_sha256": pinned_hash,
              "pinned_unit_count": len(units),
              "solver_binary_sha256": sha256(CMS),
              "solver_command": cmd[:-1] + ["<temporary pinned XCNF>"],
              "external_wall_limit_seconds": args.wall_seconds,
              "wall_seconds": time.perf_counter() - started,
              "exit_code": code, "external_timeout": timed_out,
              "solver_status": [line for line in stdout.splitlines() if line.startswith("s ")],
              "model_xcnf_verified": valid, "checked_rows": checked,
              "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
              "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
              "stdout_archive_sha256": sha256(out / "solver.stdout.txt.gz"),
              "stderr_archive_sha256": sha256(out / "solver.stderr.txt.gz"),
              "diagnostic_only": True,
              "claim_boundary": "Known-witness formula check; not a natural relation, IC run, or solver speedup."}
    (out / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("encoding", "pin", "pinned_unit_count",
                                             "wall_seconds", "solver_status", "external_timeout",
                                             "model_xcnf_verified")}, sort_keys=True))


if __name__ == "__main__":
    main()
