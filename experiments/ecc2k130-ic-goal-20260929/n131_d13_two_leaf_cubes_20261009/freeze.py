#!/usr/bin/env python3
"""Freeze two public-Q d13 cubes by pinning valid first-link leaf codes."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_d13_public_bridge_projection_20261009"
PROJECTED = SOURCE / "budget1/projected.xcnf"
MAPPING = SOURCE / "budget1/variable_map.json"
RAW = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/d13_m12_probe/"
       "official_q_phi_fiber_d13_m12_v1.xcnf")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "runtime_info.json"
LABEL = "n131_d13_two_leaf_cubes_20261009"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_codes():
    forbidden = set()
    leaf_vars = set(range(2, 15))
    with RAW.open("rt", encoding="ascii") as stream:
        header = stream.readline().split()
        assert header == ["p", "cnf", "232244", "399907"]
        assert stream.readline() == "1 0\n"
        for line in stream:
            if line.startswith(("x", "c")) or not line.strip():
                continue
            terms = [int(part) for part in line.split()]
            if len(terms) == 14 and terms[-1] == 0 and {
                    abs(value) for value in terms[:-1]} == leaf_vars:
                code = sum(1 << (abs(value) - 2) for value in terms[:-1]
                           if value < 0)
                forbidden.add(code)
    if len(forbidden) != 4058:
        raise ValueError("source leaf-selector exclusions changed")
    result = sorted(set(range(8192)) - forbidden)
    assert len(result) == 4134
    return result


def select(codes, source_hash, cube, position):
    seed = f"{LABEL}|{cube}|{position}|{source_hash}".encode("ascii")
    index = int.from_bytes(hashlib.sha256(seed).digest(), "big") % len(codes)
    return codes[index]


def write_cube(index, codes):
    destination = HERE / f"cube{index}.xcnf"
    if destination.exists():
        raise FileExistsError(destination)
    units = []
    for position, code in enumerate(codes):
        for bit in range(13):
            variable = 2 + 13 * position + bit
            units.append(variable if (code >> bit) & 1 else -variable)
    with PROJECTED.open("rt", encoding="ascii") as src, destination.open(
            "x", encoding="ascii") as dst:
        header = src.readline().split()
        if header != ["p", "cnf", "115289", "292555"]:
            raise ValueError("projected XCNF dimensions changed")
        dst.write(f"p cnf {header[2]} {int(header[3]) + len(units)}\n")
        for line in src:
            dst.write(line)
        for literal in units:
            dst.write(f"{literal} 0\n")
    return {"leaf_codes": codes, "unit_literals": units,
            "formula_sha256": sha(destination), "formula_bytes": destination.stat().st_size}


def main():
    protocol = HERE / "protocol.json"
    if protocol.exists() or not RUNTIME.exists():
        raise RuntimeError("protocol exists or checked Sage runtime receipt missing")
    runtime = json.loads(RUNTIME.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("Sage runtime failed verification")
    mapping = json.loads(MAPPING.read_text())
    if mapping["new_to_old"][:28] != list(range(28)) or mapping["free_private"]:
        raise ValueError("primary leaf selectors did not survive projection")
    source_sha = sha(RAW)
    if source_sha != "91ed7b49e8a8e8637f79c94cdb568ece415f32359d82425d4369fd829481622e":
        raise ValueError("raw public-Q source changed")
    projected_sha = sha(PROJECTED)
    if projected_sha != "00c77b01a8728d86d450bf8edf6f5bcedc322044a9680adc10aa4d4a0b0a30af":
        raise ValueError("projected public-Q source changed")
    codes = valid_codes()
    cubes = []
    for cube in range(2):
        selected = [select(codes, source_sha, cube, position)
                    for position in (0, 1)]
        if selected[0] == selected[1]:
            raise ValueError("pinned leaves reuse one Frobenius column")
        cubes.append(write_cube(cube, selected))
    record = {
        "kind": "n131_d13_m12_two_valid_first_link_leaf_cubes",
        "status": "FROZEN_PROPOSAL", "proposal_id": "Q20261009193600",
        "curve_id": "EC1N131Ckb1heb5f1998f20b", "workload_id": "3c1992b7c92f",
        "candidate_id": None, "run_id": None, "target_count": 1, "batch": False,
        "query_role": "one supplied public-Q point-decomposition stage",
        "selection_rule": "SHA-256(label|cube|position|raw XCNF SHA-256), integer modulo sorted valid code count",
        "pinned_positions": [0, 1], "valid_codes_count": len(codes),
        "cubes": cubes,
        "solver_flags": ["--threads=1", "--verb=1", "--verbstat=2",
                         "--printsol=1", "--restartprint=10000000",
                         "--random=2026100613", "--maxmatrixrows=10000",
                         "--maxmatrixcols=15000", "--maxnummatrices=10",
                         "--xor=0", "--maxconfl=1000000000000"],
        "per_cube_wall_cap_seconds": 290, "total_solver_stage_cap_seconds": 580,
        "combined_rss_cap_bytes": 4294967296,
        "model_rule": "projected and original XCNF checks, then independent checked-Sage point and subgroup replay",
        "source_sha256": {"raw": source_sha, "projected": projected_sha,
                          "mapping": sha(MAPPING), "solver": sha(SOLVER),
                          "runtime": sha(RUNTIME), "freeze": sha(Path(__file__))},
        "accounting_boundary": "all cube attempts charged to one public target; earlier formula build, bridge, and projection costs remain separate target-dependent stages",
    }
    protocol.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN_PROPOSAL", "codes": [c["leaf_codes"] for c in cubes]}))


if __name__ == "__main__":
    main()
