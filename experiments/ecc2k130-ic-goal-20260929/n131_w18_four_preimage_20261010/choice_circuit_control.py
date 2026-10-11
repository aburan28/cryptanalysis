"""Check the four exact raw targets against one fixed eight-pair witness."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESULTANT = HERE.parent / "n131_w18_two_link_resultant_20261010"
sys.path.insert(0, str(RESULTANT))
from resultant_circuit import build_program, constructed_values  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "choice_circuit_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__),
             "resultant": RESULTANT / "resultant_circuit.py",
             "preimages": HERE / "planted_preimages_result.json",
             "constructed_build": HERE / "four_constructed_build.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    preimages = json.loads(paths["preimages"].read_text())
    build = json.loads(paths["constructed_build"].read_text())
    z_values = [item["reciprocal_x_z"] for item in preimages["preimages"]]
    assert z_values == build["target_z_values"]
    prog, roots, deltas, _ = build_program()
    values, chain = constructed_values()
    counts = []
    for index, z in enumerate(z_values):
        values.update({("target", bit): (z >> bit) & 1 for bit in range(131)})
        bad = sum(prog.evaluate(values, roots))
        counts.append(bad)
        if index == 0:
            assert z == chain["raw_target_z"] and bad == 0
        else:
            assert bad > 0
    assert all(any(prog.evaluate(values, delta)) for delta in deltas)
    result = {"status": "PASS_FOUR_CHOICE_CIRCUIT_CONTROL",
              "failed_root_bits_by_preimage": counts,
              "target_z_values": z_values,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "choice_circuit_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "failed_root_bits_by_preimage": counts}))


if __name__ == "__main__":
    main()
