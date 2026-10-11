"""Prove the cutoff-one unpinned formula removes only witness unit clauses."""

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    paths = {"script": HERE / "audit_unpinned.py",
             "pinned": HERE / "four_constructed.xcnf.gz",
             "unpinned": HERE / "four_unpinned_constructed.xcnf.gz",
             "pinned_build": HERE / "four_constructed_build.json",
             "unpinned_build": HERE / "four_unpinned_constructed_build.json",
             "pinned_audit": HERE / "constructed_audit_result.json"}
    protocol = json.loads((HERE / "unpinned_audit_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: digest(path) for name, path in paths.items()}
    pinned = json.loads(paths["pinned_build"].read_text())["xcnf"]
    unpinned = json.loads(paths["unpinned_build"].read_text())["xcnf"]
    prior = json.loads(paths["pinned_audit"].read_text())
    assert prior["status"] == "PASS_INDEPENDENT_FOUR_PREIMAGE_CONSTRUCTED_MODEL"
    assert pinned["vars"] == unpinned["vars"]
    assert pinned["xors"] == unpinned["xors"]
    assert pinned["clauses"]-unpinned["clauses"] == 1579
    with gzip.open(paths["pinned"], "rt") as a, gzip.open(paths["unpinned"], "rt") as b:
        ah, bh = a.readline().split(), b.readline().split()
        assert ah[:2] == bh[:2] == ["p", "cnf"]
        assert int(ah[2]) == int(bh[2]) == pinned["vars"]
        assert int(ah[3])-int(bh[3]) == 1579
        for _ in range(unpinned["clauses"]):
            assert a.readline() == b.readline()
        removed = [a.readline().strip() for _ in range(1579)]
        assert all(len(line.split()) == 2 and line.endswith(" 0")
                   for line in removed)
        for _ in range(pinned["xors"]):
            assert a.readline() == b.readline()
        assert not a.readline() and not b.readline()
    result = {"status": "PASS_EXACT_WITNESS_PIN_REMOVAL",
              "removed_unit_clauses": len(removed),
              "unchanged_cnf_clauses": unpinned["clauses"],
              "unchanged_native_xor_rows": pinned["xors"],
              "pinned_model_proves_unpinned_satisfiable": True,
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": digest(HERE / "unpinned_audit_protocol.json")}
    (HERE / "unpinned_audit_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": result["status"], "removed_unit_clauses": len(removed)}))


if __name__ == "__main__":
    main()
