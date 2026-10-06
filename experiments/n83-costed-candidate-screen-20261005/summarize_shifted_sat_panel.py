#!/usr/bin/env python3
"""Audit and summarize the immutable N83 shifted SAT branch receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROTOCOL = HERE / "shifted_sat_protocol.json"
LABELS = ("shifted_m7_d12", "shifted_m8_d11")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text()) if path.is_file() else None


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def xcnf_header(path: Path):
    if not path.is_file():
        return None
    with path.open() as source:
        parts = source.readline().split()
    if len(parts) != 4 or parts[:2] != ["p", "cnf"]:
        return {"status": "INCOMPLETE_OR_INVALID_HEADER", "bytes": path.stat().st_size}
    return {"status": "HEADER_PRESENT", "variables": int(parts[2]),
            "constraints": int(parts[3]), "bytes": path.stat().st_size,
            "sha256": sha(path)}


def main() -> None:
    protocol = read(PROTOCOL)
    rows = []
    for label in LABELS:
        fixture = read(RUNS / f"{label}_sat_fixture_v1" / "public_input.json")
        geometry = read(RUNS / f"{label}_v1" / "geometry.json")
        assert fixture["curve_id"] == geometry["curve_id"] == protocol["curve_id"]
        pinned_folders = list(RUNS.glob(f"{label}_sat_planted_pinned_f*_v1"))
        assert len(pinned_folders) == 1
        pinned_index = int(pinned_folders[0].name.split("_f")[-1].split("_")[0])
        for kind, index, pinned in [
            ("planted", pinned_index, True),
            *(("planted", i, False) for i in range(4)),
            *(("ordinary", i, False) for i in range(4)),
        ]:
            name = f"{label}_sat_{kind}_{'pinned' if pinned else 'unpinned'}_f{index}_v1"
            folder = RUNS / name
            outer = read(folder / "outer_receipt.json")
            inner = read(folder / "receipt.json")
            started = read(folder / "started.json")
            replay = read(folder / "sage_replay.json")
            if outer is None:
                raise FileNotFoundError(f"missing frozen branch: {name}")
            assert outer["protocol_sha256"] == sha(PROTOCOL)
            assert outer["label"] == label and outer["target_kind"] == kind
            assert outer["fiber_index"] == index and outer["mode"] == \
                ("pinned_all" if pinned else "unpinned")
            assert outer["max_total_wall_seconds"] == protocol["external_wall_seconds_per_branch"]
            assert outer["max_process_tree_rss_bytes"] == protocol["max_process_tree_rss_bytes_per_branch"]
            if inner is not None:
                assert outer["inner_receipt_sha256"] == sha(folder / "receipt.json")
                assert inner["target_Q"] == fixture[kind]["target_Q"]
            if replay is not None:
                assert inner is not None and replay["branch_receipt_sha256"] == sha(folder / "receipt.json")
            solver_stdout = folder / "solver.stdout.txt"
            status_lines = ([line for line in solver_stdout.read_text(errors="replace").splitlines()
                             if line.startswith("s ")] if solver_stdout.is_file() else [])
            if outer["guard"] is not None:
                status = "BOUNDED_" + outer["guard"].upper()
            elif inner is None:
                status = "EXECUTION_INCOMPLETE"
            else:
                status = inner["status"]
            row = {
                "name": name, "label": label, "candidate_id": None,
                "curve_id": protocol["curve_id"],
                "target_kind": kind, "fiber_index": index,
                "mode": "pinned_all" if pinned else "unpinned",
                "target_Q": fixture[kind]["target_Q"],
                "raw_fiber": fixture[kind]["raw_target_fiber"][index],
                "status": status, "sage_replay_status": replay["status"] if replay else None,
                "solver_status_lines": status_lines,
                "xcnf": xcnf_header(folder / "branch.xcnf"),
                "circuit": inner.get("circuit") if inner else None,
                "circuit_build_ns": inner.get("circuit_build_ns") if inner else None,
                "xcnf_write_ns": inner.get("xcnf_write_ns") if inner else None,
                "solver_wall_ns": inner.get("solver", {}).get("wall_ns") if inner else None,
                "solver_search_totals": inner.get("solver", {}).get("search_totals") if inner else None,
                "outer_envelope_wall_ns": outer["external_wall_ns"],
                "sampled_process_tree_peak_rss_bytes": outer["peak_process_tree_rss_bytes_sampled"],
                "guard": outer["guard"], "exit_code": outer["exit_code"],
                "verified_relation": bool(replay and replay["status"] == "PASS"),
                "model_clause_xor_verified": inner.get("model", {}).get("cnf_xor_verified") if inner else None,
                "public_fixture_sha256": sha(RUNS / f"{label}_sat_fixture_v1" / "public_input.json"),
                "started_receipt_sha256": sha(folder / "started.json") if started else None,
                "outer_receipt_sha256": sha(folder / "outer_receipt.json"),
                "inner_receipt_sha256": sha(folder / "receipt.json") if inner else None,
                "sage_replay_sha256": sha(folder / "sage_replay.json") if replay else None,
                "online_target_wall_ns": None,
                "rho_online_wall_ns": None,
                "online_speedup": None,
            }
            rows.append(row)
    assert len(rows) == 18
    ordinary = [row for row in rows if row["target_kind"] == "ordinary"]
    assert len(ordinary) == 8
    assert len({tuple(row["target_Q"]) for row in ordinary}) == 1
    for label in LABELS:
        assert len([row for row in ordinary if row["label"] == label]) == 4
    report = {
        "schema_version": 1, "kind": "n83_shifted_s3_sat_panel",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "single_frozen_ordinary_target_Q": ordinary[0]["target_Q"],
        "branch_count": len(rows), "ordinary_branch_count": len(ordinary),
        "rows": rows,
        "claim_boundary": "Four raw fibers of one fixed ordinary target per geometry, not four independent targets. Bounded PDP diagnostic only. Timing host lacks an auditable isolation receipt. No target DLP, paired rho or speedup.",
    }
    save(HERE / "sat_panel.json", report)
    lines = ["# Frozen N83 shifted S3 SAT panel", "",
             "All times below are exploratory process envelopes; they include checked-Sage process startup.",
             "They are not single-target online IC times. One ordinary target has four raw fibers.", "",
             "| Geometry | Input | Fiber | Mode | Status | Sage replay | Envelope (s) | Peak RSS (MiB) |",
             "| --- | --- | ---: | --- | --- | --- | ---: | ---: |"]
    for row in rows:
        lines.append("| {} | {} | {} | {} | {} | {} | {:.2f} | {:.1f} |".format(
            row["label"], row["target_kind"], row["fiber_index"], row["mode"],
            row["status"], row["sage_replay_status"] or "—",
            row["outer_envelope_wall_ns"] / 1e9,
            row["sampled_process_tree_peak_rss_bytes"] / 2**20))
    lines += ["", "Every attempt is retained in `sat_panel.json`. The complete pipeline costs,",
              "single-target DLP recovery, same-point rho comparison, and speedup are unknown.", ""]
    (HERE / "SAT_PANEL.md").write_text("\n".join(lines))
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "ordinary_verified_relations": sum(row["verified_relation"] for row in ordinary)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
