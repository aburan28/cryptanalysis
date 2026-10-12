#!/usr/bin/env python3
"""Pair the existing one-bucket U14 and split-terminal U12 schedules."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from math import sqrt
from pathlib import Path
import statistics
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
U14_DIR = ROOT / "prime-j0-secp256k1-native"
U14_SOURCE = U14_DIR / "unit_orbit_windows_screen.py"
U14_VERIFICATION = ROOT / "prime-j0-sector-digit-20261010/verification.json"
U12_DIR = ROOT / "prime-j0-terminal-split-20261011"
U12_REPLAY = U12_DIR / "replay.py"
U12_NATIVE = ROOT / "prime-j0-terminal-split-selector-20261011/full-panel-replay.json"


def digest(raw):
    return sha256(raw).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gauge_rotations(windows, atlases, u14, scalar):
    group_scalars = [0, 0, 0]
    powers = set()
    place = 1
    for width, (orbit, code, active) in zip(u14.WIDTHS, windows):
        if active:
            digit = u14.unit_images(atlases[width].digits[orbit])[code]
            group_scalars[code // 2] = (
                group_scalars[code // 2] +
                place * (digit[0] + digit[1] * u14.LAMBDA_TAU)) % u14.N
            powers.add(code // 2)
        place *= 1 << width
    assert sum(group_scalars) % u14.N == scalar % u14.N
    previous = None
    accumulated = 0
    rotations = 0
    for power in (1, 2, 0):
        if power not in powers:
            continue
        if previous is not None and previous != power and accumulated:
            rotations += 1
        accumulated = (accumulated + group_scalars[power]) % u14.N
        previous = power
    if previous is not None and previous != 0 and accumulated:
        rotations += 1
    return rotations


def main():
    output = HERE / "paired.jsonl"
    receipt_path = HERE / "comparison.json"
    if output.exists() or receipt_path.exists():
        raise SystemExit("refusing to overwrite paired records")
    # The old module imports its neighboring reference modules by bare name.
    sys.path.insert(0, str(U14_DIR.resolve()))
    u14 = load("u14_paired_reference", U14_SOURCE)
    u12 = load("u12_paired_reference", U12_REPLAY)
    input_raw = (U12_DIR / "holdout-inputs.json").read_bytes()
    path_raw = (U12_DIR / "holdout-paths.jsonl").read_bytes()
    prior = json.loads((U12_DIR / "holdout-screen.json").read_bytes())
    native = json.loads(U12_NATIVE.read_bytes())
    verification = json.loads(U14_VERIFICATION.read_bytes())
    inputs = json.loads(input_raw)
    assert digest(input_raw) == prior["input_sha256"] == native["input_sha256"]
    assert digest(path_raw) == prior["certificate_sha256"] == native["certificate_sha256"]
    assert digest(U12_REPLAY.read_bytes()) == inputs["candidate_source_sha256"]["replay.py"]
    assert native["status"] == "passed" and native["cases"] == 4096
    assert verification["status"] == "passed" and not verification["problems"]
    u14_bytes = verification["resources"]["candidate"]["retained_bytes"]
    assert u14_bytes == 64_314_112
    atlases = {width: u14.OrbitAtlas(width) for width in (9, 10)}
    rows = []
    totals = Counter()
    differences = []
    for index, line in enumerate(path_raw.splitlines()):
        recorded = json.loads(line)
        assert recorded["index"] == index
        scalar = int(inputs["scalars_hex"][index], 16)
        u14_rep = tuple(u14.hex_choices(scalar)[0][2:4])
        u12_rep = u12.representatives(scalar)[0]
        assert u14_rep == u12_rep
        windows = u14.recode(u14_rep, atlases)
        unit_codes = [unit for _, unit, active in windows if active]
        u14_terms = len(unit_codes)
        u14_mixed = max(u14_terms - 1, 0)
        u14_rotations = gauge_rotations(windows, atlases, u14, scalar)
        assert u14_rotations <= 2
        u14_proxy = 11 * u14_mixed + u14_rotations
        selected = recorded["options"][recorded["selected_option"]]
        u12_metrics = selected["metrics"]
        u12_proxy = u12_metrics["point_proxy_units"]
        difference = u12_proxy - u14_proxy
        differences.append(difference)
        totals.update(cases=1, same_representative=1, u14_terms=u14_terms,
                      u14_mixed=u14_mixed, u14_rotations=u14_rotations,
                      u14_proxy=u14_proxy, u12_proxy=u12_proxy,
                      u12_terms=u12_metrics["terms"],
                      u12_mixed=u12_metrics["mixed_additions"],
                      u12_merges=u12_metrics["bucket_merges"],
                      u12_rotations=u12_metrics["grouped_rotations"],
                      u12_tau1=u12_metrics["tau1_active"],
                      u12_tau2=u12_metrics["tau2_active"],
                      u14_lower=int(difference > 0),
                      equal=int(difference == 0),
                      u12_lower=int(difference < 0))
        rows.append(json.dumps({"index": index, "u14_terms": u14_terms,
                                "u14_mixed": u14_mixed,
                                "u14_rotations": u14_rotations,
                                "u14_proxy": u14_proxy,
                                "u12_proxy": u12_proxy,
                                "u12_terms": u12_metrics["terms"],
                                "u12_mixed": u12_metrics["mixed_additions"],
                                "u12_merges": u12_metrics["bucket_merges"],
                                "u12_rotations": u12_metrics["grouped_rotations"],
                                "u12_tau1": u12_metrics["tau1_active"],
                                "u12_tau2": u12_metrics["tau2_active"],
                                "u12_minus_u14": difference},
                               sort_keys=True, separators=(",", ":")))
    assert len(rows) == 4096 and totals["u12_proxy"] == 609671
    assert totals["u14_proxy"] == 593895
    raw = ("\n".join(rows) + "\n").encode()
    output.write_bytes(raw)
    mean = statistics.mean(differences)
    error = 1.96 * statistics.stdev(differences) / sqrt(len(differences))
    result = {"schema": 1, "status": "compared",
              "kind": "retrospective-same-scalar-point-work",
              "totals": dict(sorted(totals.items())),
              "mean_difference": mean,
              "normal_95pct_mean_interval": [mean - error, mean + error],
              "median_difference": statistics.median(differences),
              "u14_retained_bytes": u14_bytes,
              "u12_retained_bytes": native["retained_bytes"],
              "input_sha256": digest(input_raw),
              "u12_paths_sha256": digest(path_raw),
              "paired_sha256": digest(raw),
              "u14_screen_source_sha256": digest(U14_SOURCE.read_bytes()),
              "u14_native_verification_sha256": digest(U14_VERIFICATION.read_bytes()),
              "u12_replay_source_sha256": digest(U12_REPLAY.read_bytes()),
              "u12_native_replay_sha256": digest(U12_NATIVE.read_bytes()),
              "source_sha256": digest(Path(__file__).read_bytes())}
    receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"totals": result["totals"],
                      "mean_difference": mean,
                      "normal_95pct_mean_interval": result["normal_95pct_mean_interval"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
