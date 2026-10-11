"""Independently check XCNF prefix identity and the known witness extension."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_fixed_seed_eight_pair_circuit_20261010"
FOUR = GOAL / "n131_w18_four_preimage_20261010"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    paths = {"audit": HERE / "audit_overlay.py",
             "baseline": FOUR / "four_unpinned_constructed.xcnf",
             "overlay": HERE / "matched_unpinned_constructed.xcnf",
             "overlay_result": HERE / "overlay_result.json",
             "constructed": BASE / "derive_result.json"}
    protocol = json.loads((HERE / "overlay_audit_protocol.json").read_text())
    assert protocol["source_sha256"] == {key: digest(path) for key, path in paths.items()}
    record = json.loads(paths["overlay_result"].read_text())
    assert record["input_sha256"] == digest(paths["baseline"])
    assert record["output_sha256"] == digest(paths["overlay"])
    with paths["baseline"].open() as b, paths["overlay"].open() as o:
        bhead, ohead = b.readline().split(), o.readline().split()
        assert bhead[:2] == ohead[:2] == ["p", "cnf"]
        bvars, brows = map(int, bhead[2:])
        ovars, orows = map(int, ohead[2:])
        assert ovars-bvars == 476 and orows-brows == 1016
        base_lines = 0
        for line in b:
            assert line == o.readline()
            base_lines += 1
        assert base_lines == brows
        added = [line.strip() for line in o]
    assert len(added) == 1016
    raw_codes = [item["masks"][0] for item in
                 json.loads(paths["constructed"].read_text())["selected"]]
    source_bits = [bit for bit in range(18) if bit != 7]
    codes = [sum(((mask >> bit) & 1) << index for index, bit in
                 enumerate(source_bits)) for mask in raw_codes]
    assert len(codes) == len(set(codes)) == 8
    selected = {2+17*slot+bit: bool(code >> bit & 1)
                for slot, code in enumerate(codes) for bit in range(17)}
    xor_values = {}
    for offset, line in enumerate(added[540:]):
        parts = line.split()
        assert len(parts) == 4 and parts[-1] == "0" and parts[0].startswith("x-")
        a, b, output = int(parts[0][2:]), int(parts[1]), int(parts[2])
        assert output == bvars+offset+1
        xor_values[output] = selected[a] != selected[b]
    values = {**selected, **xor_values}
    for line in added[:540]:
        literals = [int(part) for part in line.split()]
        assert literals[-1] == 0
        assert any(values[abs(lit)] == (lit > 0) for lit in literals[:-1])
    audit = {"status": "PASS_INDEPENDENT_MATCHING_OVERLAY_AUDIT",
             "unchanged_baseline_rows": brows,
             "added_cnf_clauses": 540, "added_native_xor_rows": 476,
             "fixture_codes": codes,
             "fixture_satisfies_all_added_rows": True,
             "source_sha256": protocol["source_sha256"],
             "protocol_sha256": digest(HERE / "overlay_audit_protocol.json")}
    (HERE / "overlay_audit_result.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": audit["status"],
                      "unchanged_baseline_rows": brows}))


if __name__ == "__main__":
    main()
