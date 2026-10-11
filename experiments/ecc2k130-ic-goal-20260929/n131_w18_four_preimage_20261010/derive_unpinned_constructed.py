"""Remove only the frozen witness and choice pins from constructed XCNF."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
SOURCE_BITS = [bit for bit in range(18) if bit != 7]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selector_code(mask):
    assert mask >> 7 & 1 == 0
    return sum(((mask >> bit) & 1) << index
               for index, bit in enumerate(SOURCE_BITS))


def expected_pins(derive, planted, built):
    first_selector = 2
    first_output = first_selector + 8*17
    first_middle = first_output + 8*131
    assert built["target_choice_variables"] == [first_middle+3*131,
                                                  first_middle+3*131+1]
    pins = [-var for var in built["target_choice_variables"]]
    for slot, item in enumerate(derive["selected"]):
        code = selector_code(item["masks"][0])
        z = item["unrotated_pair_output_z"]
        for bit in range(17):
            var = first_selector + slot*17 + bit
            pins.append(var if code >> bit & 1 else -var)
        for bit in range(131):
            var = first_output + slot*131 + bit
            pins.append(var if z >> bit & 1 else -var)
    for slot, index in enumerate((1, 3, 5)):
        z = planted["intermediate_z"][index]
        for bit in range(131):
            var = first_middle + slot*131 + bit
            pins.append(var if z >> bit & 1 else -var)
    assert len(pins) == 1579
    return pins


def main():
    protocol_path = HERE / "unpinned_build_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__),
             "formula": HERE / "four_constructed.xcnf",
             "build": HERE / "four_constructed_build.json",
             "derive": BASE / "derive_result.json",
             "planted": BASE / "planted_chain_result.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    built = json.loads(paths["build"].read_text())
    expected = expected_pins(json.loads(paths["derive"].read_text()),
                             json.loads(paths["planted"].read_text()), built)
    old_clauses = built["xcnf"]["clauses"]
    xors = built["xcnf"]["xors"]
    new_clauses = old_clauses - len(expected)
    output = HERE / "four_unpinned_constructed.xcnf"
    with paths["formula"].open() as source, output.open("x") as target:
        header = source.readline().split()
        assert header == ["p", "cnf", str(built["xcnf"]["vars"]),
                          str(old_clauses+xors)]
        target.write("p cnf %d %d\n" %
                     (built["xcnf"]["vars"], new_clauses+xors))
        for index in range(old_clauses):
            line = source.readline()
            assert line.endswith(" 0\n")
            if index < new_clauses:
                target.write(line)
            else:
                assert line == "%d 0\n" % expected[index-new_clauses]
        for _ in range(xors):
            line = source.readline()
            assert line.startswith("x") and line.endswith(" 0\n")
            target.write(line)
        assert source.read() == ""
    result = {"status": "PASS_EXACT_CONSTRUCTED_PIN_REMOVAL",
              "removed_unit_clauses": len(expected),
              "xcnf": {"vars": built["xcnf"]["vars"],
                       "clauses": new_clauses, "xors": xors,
                       "bytes": output.stat().st_size,
                       "sha256": digest(output)},
              "target_z_values": built["target_z_values"],
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "unpinned_build_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "removed_unit_clauses": len(expected),
                      "xcnf": result["xcnf"]}))


if __name__ == "__main__":
    main()
