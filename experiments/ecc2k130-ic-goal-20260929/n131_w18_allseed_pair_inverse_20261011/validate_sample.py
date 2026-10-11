#!/usr/bin/env sage -python
"""Independent Sage field-map samples and exact group replay of native hits."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
PRIOR = HERE / "validate.py"
COUNT = 262143


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    paths = {"sampler": HERE / "validate_sample.py", "sage_methods": PRIOR,
             "support": SUPPORT, "run_protocol": HERE / "protocol.json",
             "lowpivot_audit": HERE / "lowpivot_audit.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for index in range(4):
        paths[f"query_{index}"] = HERE / f"query_{index:03d}.json"
    return paths


def sample_seeds():
    values = {13686, 12004, 12005, 262143}
    for ordinal in range(256):
        digest = hashlib.sha256(f"W18:allseed:sample:20261011:{ordinal}".encode()).digest()
        values.add(1 + int.from_bytes(digest[:8], "big") % COUNT)
    return sorted(values)


def freeze():
    assert not (HERE / "sample_protocol.json").exists()
    assert json.loads((HERE / "lowpivot_audit.json").read_text())["status"] == "PASS"
    protocol = {"status": "FROZEN_BEFORE_SAMPLE",
                "method": "Sage GF(2^131) direct half-trace per seed, 256 SHA-256 selected seeds plus four boundary/positive seeds, and all accepted group hits",
                "sample_seed_masks": sample_seeds(),
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save_new(HERE / "sample_protocol.json", protocol)
    print("sample frozen", len(protocol["sample_seed_masks"]), "seeds")


def main():
    protocol = json.loads((HERE / "sample_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SAMPLE"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    spec = importlib.util.spec_from_file_location("w18_sage_map", PRIOR)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "z", modulus=t**131 + t**13 + t**2 + t + 1)
    basis = [field.from_integer(1 << i) for i in range(1, 19)]
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(columns) == 131307 and len(set(columns.values())) == 131068
    cases = json.loads((HERE / "protocol.json").read_text())["cases"]
    raw = [json.loads((HERE / f"query_{i:03d}.json").read_text()) for i in range(4)]
    prepared = []
    for case, result in zip(cases, raw):
        c = field.from_integer(case["coordinate"])
        for _ in range((131 - case["rotation"]) % 131):
            c *= c
        assert prior.enc(c**(2**case["rotation"])) == case["coordinate"]
        c2 = c*c
        hc = prior.halftrace(c2, field)
        trace = hc*hc + hc + c2
        assert int(trace) == result["trace_bit"]
        prepared.append((c, hc, 1/c, int(trace)))
    sample_hits = []
    for ordinal, seed_mask in enumerate(protocol["sample_seed_masks"]):
        seed = field.from_integer(seed_mask << 1)
        hs = prior.halftrace(seed*seed, field)
        assert hs*hs + hs == seed*seed
        inverse = prior.linear_inverse(field, seed, basis, seed_mask)
        for index, (c, hc, inverse_c, trace) in enumerate(prepared):
            if trace:
                continue
            for branch in (0, 1):
                product = (hc + hs + field.from_integer(branch)) * inverse_c
                mask = prior.invert(inverse, prior.enc(product))
                if mask is None:
                    continue
                a, b = sorted((mask, mask ^ seed_mask))
                if a not in columns or b not in columns or columns[a] == columns[b]:
                    continue
                assert field.from_integer(a << 1) * field.from_integer(b << 1) == product
                native = {(hit["seed"], *hit["masks"],
                           hit["product"][0] | hit["product"][1] << 64 |
                           hit["product"][2] << 128) for hit in raw[index]["hits"]}
                record = (seed_mask, a, b, prior.enc(product))
                assert record in native
                sample_hits.append([index, *record])
        if (ordinal + 1) % 64 == 0:
            print("Sage sampled seeds", ordinal + 1, flush=True)
    sign_matches = []
    for case, result in zip(cases, raw):
        sign_matches.append(sum(prior.group_replay(hit, case["coordinate"],
                                                   case["rotation"], columns)
                                for hit in result["hits"]))
    assert len(sample_hits) >= 2
    assert sign_matches[:2] == [2, 2] or all(value > 0 for value in sign_matches[:2])
    assert sign_matches[2:] == [0, 0]
    receipt = {"status": "PASS_SAMPLED_SAGE_AND_GROUP_REPLAY",
               "sample_seeds": len(protocol["sample_seed_masks"]),
               "sample_hits": sample_hits,
               "group_sign_matches": sign_matches,
               "source_sha256": protocol["source_sha256"],
               "sample_protocol_sha256": sha(HERE / "sample_protocol.json")}
    save_new(HERE / "sample_validation.json", receipt)
    print(receipt["status"])


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else main()
