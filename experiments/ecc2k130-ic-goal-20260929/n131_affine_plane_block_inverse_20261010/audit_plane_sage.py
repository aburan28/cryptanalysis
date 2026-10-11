#!/usr/bin/env sage -python
"""Independent N41 source, query-count, relation, and scalar replay."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "n41_coupled_sixpair_full_ic_20261010"
R = 549756390943
OFFSET = 57


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "plane_audit_protocol.json").read_text())
    paths = {"script": Path(__file__), "query_protocol": HERE / "query_protocol.json",
             "control_protocol": HERE / "control_protocol.json",
             "fresh_native": HERE / "plane_native.json",
             "control_native": HERE / "control_native.json",
             "control_hit": HERE / "control_hit.json",
             "fresh_fixture": HERE / "target_fixture.json",
             "control_fixture": HERE / "control_fixture.json",
             "workload": ROOT / "workload.json", "factor_logs": ROOT / "factor_logs.json",
             "prior_factor_audit": ROOT / "sage_audit.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    fresh = json.loads(paths["fresh_native"].read_text())
    control = json.loads(paths["control_native"].read_text())
    hit = json.loads(paths["control_hit"].read_text())
    fresh_fixture = json.loads(paths["fresh_fixture"].read_text())
    control_fixture = json.loads(paths["control_fixture"].read_text())
    workload = json.loads(paths["workload"].read_text())
    logs = json.loads(paths["factor_logs"].read_text())["logs_mod_r"]
    factor_audit = json.loads(paths["prior_factor_audit"].read_text())
    assert factor_audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    assert len(logs) == 26

    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(41)]))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    generator = point(workload["generator"])
    assert R * generator == curve(0)
    fresh_target = point(fresh_fixture["target"])
    assert fresh_fixture["scalar_kept_out_of_worker_input"] * generator == fresh_target
    assert json.loads(paths["query_protocol"].read_text())["target"] == fresh_fixture["target"]
    assert fresh["status"] == "EXHAUSTED_NO_RELATION"
    assert sum(fresh["exclusive_phase_ns"].values()) == fresh["online_ns"]
    assert fresh["right_quad_a"] == fresh["right_quad_b"] == 3328
    assert fresh["attempts"] == 3328**2

    atom_map = {(item["block"], item["mask"], item["sign"]): item
                for item in workload["atoms"]}
    source_blocks = [0, 1, 2, 2, 4, 4]
    chosen = []
    scalar = 0
    for slot in range(12):
        atom = atom_map[(source_blocks[slot // 2], hit["masks"][slot], hit["signs"][slot])]
        assert atom["column"] == hit["columns"][slot]
        representative = point(workload["representatives"][atom["column"]])
        p = point(atom["point"])
        assert atom["coefficient_mod_r"] * representative == p
        chosen.append(p)
        scalar = (scalar + atom["coefficient_mod_r"] * logs[atom["column"]]) % R
    assert len(set(hit["columns"])) == 12
    for first in (4, 8):
        first_pair = {hit["masks"][first], hit["masks"][first+1]}
        second_pair = {hit["masks"][first+2], hit["masks"][first+3]}
        assert {mask ^ OFFSET for mask in first_pair} == second_pair
        assert hit["masks"][first] ^ hit["masks"][first+1] == hit["masks"][first+2] ^ hit["masks"][first+3]
    control_target = point(control_fixture["target"])
    assert sum(chosen, curve(0)) == control_target
    assert hit["raw_sum"] == control_fixture["target"]
    assert scalar == hit["recovered_scalar"] == control["recovered_scalar"]
    assert scalar == control_fixture["scalar"]
    assert scalar * generator == control_target
    assert sum(control["exclusive_phase_ns"].values()) == control["online_ns"]

    columns = {item["mask"]: item["column"] for item in workload["atoms"]
               if item["block"] == 2 and item["sign"] == 0}
    configs = []
    for a in columns:
        for b in columns:
            if a >= b or columns[a] == columns[b]:
                continue
            shifted = sorted((a ^ OFFSET, b ^ OFFSET))
            if shifted[0] not in columns or shifted[1] not in columns:
                continue
            four = (a, b, *shifted)
            if len({columns[mask] for mask in four}) == 4:
                configs.append(sum(1 << columns[mask] for mask in four))
    assert len(configs) == 208
    admissible_configs = sum((left & right) == 0 for left in configs for right in configs)
    assert admissible_configs == 21600
    assert fresh["accepted_probes"] == admissible_configs * 16**2 == 5529600
    assert control["accepted_probes"] <= fresh["accepted_probes"]
    assert fresh["peak_rss_bytes"] < 4294967296
    assert control["peak_rss_bytes"] < 4294967296

    receipt = {"status": "PASS_INDEPENDENT_N41_PLANE_CONTROL_AND_EXHAUSTIVE_COUNT",
               "fresh_target": fresh_fixture["target"],
               "fresh_status": fresh["status"],
               "fresh_accepted_probes": fresh["accepted_probes"],
               "constructed_control_target": control_fixture["target"],
               "control_recovered_scalar": int(scalar),
               "control_verified_relation_points": len(chosen),
               "admissible_mask_configurations_per_block": len(configs),
               "disjoint_block_configuration_pairs": admissible_configs,
               "source_sha256": {name: digest(path) for name, path in paths.items()}}
    with (HERE / "plane_sage_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "fresh_accepted_probes": fresh["accepted_probes"],
                      "control_scalar": int(scalar)}))


if __name__ == "__main__":
    main()
