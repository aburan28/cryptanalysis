#!/usr/bin/env python3
"""Check every four-corner path omitted by the midpoint terminal rule."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-terminal-split-20261011"


def digest(raw):
    return sha256(raw).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite omitted-corner receipt")
    prior = load("omitted_prior", PRIOR / "replay.py")
    bound = load("omitted_bound", HERE / "screen.py")
    input_raw = (PRIOR / "holdout-inputs.json").read_bytes()
    path_raw = (PRIOR / "holdout-paths.jsonl").read_bytes()
    table_raw = bound.TABLE.read_bytes()
    cover_raw = prior.COVER.read_bytes()
    inputs = json.loads(input_raw)
    prior_screen = json.loads((PRIOR / "holdout-screen.json").read_bytes())
    bound_screen = json.loads((HERE / "screen.json").read_bytes())
    assert digest(input_raw) == prior_screen["input_sha256"] == bound_screen["input_sha256"]
    assert digest(path_raw) == prior_screen["certificate_sha256"] == bound_screen["path_sha256"]
    assert digest(table_raw) == inputs["terminal_sha256"] == bound_screen["terminal_table_sha256"]
    assert digest(cover_raw) == inputs["cover_sha256"]
    assert digest((PRIOR / "replay.py").read_bytes()) == inputs["candidate_source_sha256"]["replay.py"]
    assert digest((HERE / "screen.py").read_bytes()) == bound_screen["source_sha256"]
    _, assignments, seeds = prior.prior.load_cover(prior.COVER, 83_878, 7)
    canonical, nodes, _, _ = prior.dual.parent.full_classes()
    node_index = {node: index for index, node in enumerate(nodes)}
    points, labels, a_min, b_min = bound.read_table(table_raw)
    counts = {"cases": 0, "missing_corners": 0, "beyond_two_disk": 0,
              "within_two_disk_bound": 0, "viable_missing_corners": 0,
              "missing_corners_below_recorded_proxy": 0}
    within = []
    reconstruction_hash = sha256()
    prior_proxy_total = 0
    for index, line in enumerate(path_raw.splitlines()):
        row = json.loads(line)
        assert row["index"] == index
        scalar = int(inputs["scalars_hex"][index], 16)
        existing = {tuple(option["path"]["representative"])
                    for option in row["options"]}
        recorded_proxy = row["options"][row["selected_option"]]["metrics"]["point_proxy_units"]
        prior_proxy_total += recorded_proxy
        assert existing <= set(prior.representatives(scalar))
        for representative in prior.representatives(scalar):
            if representative in existing:
                continue
            counts["missing_corners"] += 1
            path = prior.recode_pair(representative, assignments, seeds,
                                     canonical, node_index)
            terminal = tuple(path["terminal"])
            terminal_norm = prior.screen.norm(terminal)
            reconstruction_hash.update(json.dumps(
                (index, representative, terminal, terminal_norm),
                separators=(",", ":")).encode())
            if terminal_norm >= 4 * 149 * 149:
                counts["beyond_two_disk"] += 1
                continue
            counts["within_two_disk_bound"] += 1
            candidate, label_count, pair_count = bound.all_pair_best(
                path, points, labels, a_min, b_min)
            record = {"index": index, "terminal": terminal,
                      "terminal_norm": terminal_norm,
                      "recorded_proxy": recorded_proxy,
                      "feasible_pairs": pair_count,
                      "feasible_label_pairs": label_count,
                      "best_pair_proxy": None if candidate is None else candidate[0],
                      "best_pair": None if candidate is None else [candidate[1], candidate[2]]}
            within.append(record)
            if candidate is not None:
                counts["viable_missing_corners"] += 1
                if candidate[0] < recorded_proxy:
                    counts["missing_corners_below_recorded_proxy"] += 1
        counts["cases"] += 1
    assert counts["cases"] == 4096
    assert prior_proxy_total == bound_screen["prior_point_proxy_units"] == 609671
    assert counts["missing_corners"] == bound_screen["omitted_original_corners"]
    assert counts["beyond_two_disk"] + counts["within_two_disk_bound"] == counts["missing_corners"]
    result = {"schema": 1, "status": "checked", "counts": counts,
              "within_two_disk_bound": within,
              "complete_four_corner_pair_oracle_proxy": (
                  bound_screen["all_pair_point_proxy_units"] if
                  counts["missing_corners_below_recorded_proxy"] == 0 else None),
              "missing_reconstruction_sha256": reconstruction_hash.hexdigest(),
              "input_sha256": digest(input_raw), "path_sha256": digest(path_raw),
              "terminal_table_sha256": digest(table_raw),
              "cover_sha256": digest(cover_raw),
              "source_sha256": digest(Path(__file__).read_bytes())}
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"counts": counts,
                      "complete_four_corner_pair_oracle_proxy":
                          result["complete_four_corner_pair_oracle_proxy"]}, sort_keys=True))


if __name__ == "__main__":
    main()
