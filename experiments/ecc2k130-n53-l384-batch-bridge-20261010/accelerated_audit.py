"""Run the frozen independent group-law audit with a checked C field kernel.

Only multiplication is replaced in memory. The archived audit, its point/group
operations, input checks and expected output stay byte-for-byte unchanged.
"""
from __future__ import annotations

import ctypes
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_panel(experiment: Path, panel: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="gf53-kernel-") as directory:
        library = Path(directory) / "fastfield.so"
        subprocess.run(["cc", "-O3", "-shared", "-fPIC", "-o", str(library),
                        str(HERE / "fastfield_n53.c")], check=True)
        native = ctypes.CDLL(str(library))
        native.gf53_mul.argtypes = (ctypes.c_uint64, ctypes.c_uint64)
        native.gf53_mul.restype = ctypes.c_uint64
        multiply = native.gf53_mul
        audit = load(experiment / "audit.py", "frozen_l384_audit")
        original_load = audit.load
        reference = original_load(
            experiment.parent / "autolab_orbit_extract_20260924"
            / "independent_replay_20260924_codex/replay.py", "reference_field")
        rho_reference = original_load(
            experiment.parent / "autolab_matched_point_rho_n53_20260925/analyze.py",
            "reference_rho_field")
        field = type("Field", (), {"n": 53, "modulus": (1 << 53) | 0x47})()
        rng = random.Random(531384)
        pairs = ((1 << i, 1 << j) for i in range(53) for j in range(53))
        random_pairs = ((rng.randrange(1 << 53), rng.randrange(1 << 53))
                        for _ in range(1000))
        for a, b in (*pairs, *random_pairs):
            expected = reference.Curve.multiply(field, a, b)
            assert multiply(a, b) == expected == rho_reference.mul(a, b)

        def checked_load(path: Path, name: str):
            module = original_load(path, name)
            if path.name == "cold_batch_rank.py":
                original_verifier = module.load_verifier

                def fast_verifier():
                    verifier = original_verifier()
                    verifier.Curve.multiply = lambda self, a, b: multiply(a, b)
                    return verifier

                module.load_verifier = fast_verifier
            elif path.name == "analyze.py":
                module.mul = multiply
            return module

        audit.load = checked_load
        points, labels = audit.inputs()
        _, verifier, curve, by_point, by_x, logs, training = audit.training_replay(panel)
        ic_logs, ic = audit.ic_replay(
            panel, points, labels, verifier, curve, by_point, by_x, logs)
        rho_logs, rho = audit.rho_replay(panel, points, labels)
        assert ic_logs == rho_logs == labels
        report = {
            "classification": "PASS_ALL_384_SAME_Q_LOGS_AND_512_TRAINING_RELATIONS",
            "points_sha256": audit.POINTS_HASH,
            "validator_manifest_sha256": audit.MANIFEST_HASH,
            "training": training, "ic": ic, "rho": rho,
            "all_operational_and_rho_logs_match_withheld_labels": True,
            "input_count": 384, "unique_points": len(set(points)),
        }
        assert report == json.loads((panel / "audit.json").read_text())
        return {
            "verdict": "PASS_COMPLETE_ACCELERATED_INDEPENDENT_REPLAY",
            "field_pairs_differentially_checked": 3809,
            "orbit_labels": training["orbit_labels_replayed"],
            "training_relations": training["training_relations_replayed"],
            "ic_logs": ic["ic_relations_replayed"],
            "rho_logs": rho["rho_scalars_replayed"],
        }
