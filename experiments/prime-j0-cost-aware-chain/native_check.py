#!/usr/bin/env python3
"""Differential correctness check for the standalone native selector."""

import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import tempfile

from run import ORDERS, omega_eigenvalues, select, toy_instance


class Choice(ctypes.Structure):
    _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64),
                ("triples", ctypes.c_uint32), ("mixed_adds", ctypes.c_uint32),
                ("unit_rotations", ctypes.c_uint32),
                ("weighted_cost", ctypes.c_uint32)]


def check():
    source = Path(__file__).with_name("native.c")
    compiler = os.environ.get("CC", "cc")
    rng = random.Random(20261004)
    groups = []
    for b, order in ((2, 13), (10, 103)):
        _, _, _, _, eigenvalue, _ = toy_instance(b, order)
        groups.append((order, (eigenvalue,)))
    groups.extend((order, omega_eigenvalues(order)) for order in
                  (*ORDERS, 18446744073709551427))
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        library = Path(directory) / "libtau_select.so"
        subprocess.run([compiler, "-std=c11", "-O2",
                        "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                        str(source), "-o", str(library)], check=True)
        native = ctypes.CDLL(str(library)).tau_select
        native.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
                           ctypes.POINTER(Choice), ctypes.POINTER(Choice)]
        native.restype = ctypes.c_int
        for order, roots in groups:
            scalars = [0, 1, 2, 3, order - 2, order - 1]
            if order < 1000:
                scalars.extend(range(order))
            else:
                scalars.extend(rng.randrange(order) for _ in range(200))
            scalars = sorted(set(scalars))
            for lam in roots:
                for k in scalars:
                    baseline, candidate = Choice(), Choice()
                    if native(order, lam, k, ctypes.byref(baseline),
                              ctypes.byref(candidate)) != 1:
                        raise AssertionError((order, lam, k, "native rejection"))
                    for actual, expected in zip((baseline, candidate),
                                                select(order, lam, k)):
                        metrics = expected[4]
                        want = (expected[1], expected[2], metrics["triples"],
                                metrics["mixed_adds"], metrics["unit_rotations"],
                                metrics["weighted_cost"])
                        got = tuple(getattr(actual, name) for name, _ in Choice._fields_)
                        if got != want:
                            raise AssertionError((order, lam, k, got, want))
                rows.append({"order": order, "omega_eigenvalue": lam,
                             "scalars_checked": len(scalars)})
    result = {"status": "pass", "checks": sum(row["scalars_checked"]
                                               for row in rows),
              "rows": rows, "architecture": platform.machine(),
              "os": platform.platform(),
              "compiler": subprocess.check_output([compiler, "--version"],
                                                  text=True).splitlines()[0],
              "source_sha256": {
                  path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in (source, Path(__file__), source.with_name("run.py"))}}
    Path(__file__).with_name("native-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    check()
