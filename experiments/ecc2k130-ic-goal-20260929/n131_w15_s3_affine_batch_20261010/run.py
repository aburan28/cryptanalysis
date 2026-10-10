#!/usr/bin/env sage -python
"""Affine half-trace and batched inversion for an exact N131 S3 join."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_fixedseed_s3_join_20261010"
ROOTS = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010/pair_roots.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value*1024)


def halftrace(value, zero):
    result = zero
    for _ in range(66):
        result += value
        value = value**4
    return result


def batch_inverse(values, one):
    """One inversion and 3m-3 multiplies for m nonzero field values."""
    if not values:
        return []
    prefixes = [one]
    for value in values:
        assert value != 0
        prefixes.append(prefixes[-1]*value)
    remaining = one/prefixes[-1]
    output = [None]*len(values)
    for i in range(len(values)-1, -1, -1):
        output[i] = remaining*prefixes[i]
        remaining *= values[i]
    assert remaining == one
    return output


def field_instance():
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    return GF(2**131, "z", modulus=t**131+t**13+t**2+t+1)


def input_hashes():
    return {"source": digest(Path(__file__)), "roots": digest(ROOTS),
            "reference": digest(PRIOR / "sage_query_result.json"),
            "runtime": digest(HERE / "sage_runtime_info.json")}


def prepare(field, left):
    one, zero = field.one(), field.zero()
    inverse_c = batch_inverse(left, one)
    prepared = []
    for c, inv_c in zip(left, inverse_c):
        argument = (c+inv_c)**2
        h = halftrace(argument, zero)
        trace = h**2+h+argument
        assert trace in (zero, one)
        prepared.append((c, h, int(trace)))
    return prepared


def join(prepared, right, q, field, cap_ns, rss_cap):
    """Query begins with q supplied and reusable source transforms ready."""
    started = time.monotonic_ns()
    one, zero = field.one(), field.zero()
    assert q != 0
    ordinary, denominators, exceptional = [], [], []
    for index, (c, _, _) in enumerate(prepared):
        product = c*q
        denominator = one+product
        if denominator == 0:
            exceptional.append((index, product))
        else:
            ordinary.append((index, product))
            denominators.append(denominator)
    all_inverses = batch_inverse([q, *denominators], one)
    inverse_q, inverse_denominators = all_inverses[0], all_inverses[1:]
    hq_argument = (q+inverse_q)**2
    hq = halftrace(hq_argument, zero)
    trace_q = int(hq**2+hq+hq_argument)
    assert trace_q in (0, 1)
    hits = set()
    roots_by_index = [()] * len(prepared)
    compatible = 0
    for (index, product), inverse in zip(ordinary, inverse_denominators):
        _, hc, trace_c = prepared[index]
        if trace_c != trace_q:
            continue
        compatible += 1
        h = hc+hq
        scale = product*inverse**2
        candidates = (scale*h, scale*(h+one))
        roots_by_index[index] = candidates
        for d in candidates:
            if d in right:
                hits.add((encode(prepared[index][0]), encode(d)))
    for index, product in exceptional:
        assert product == one
        c = prepared[index][0]
        d = (c+q)**2
        roots_by_index[index] = (d,)
        if d in right:
            hits.add((encode(c), encode(d)))
    elapsed = time.monotonic_ns()-started
    status = ("CENSORED_TIME" if elapsed > cap_ns else
              "CENSORED_MEMORY" if peak_rss() > rss_cap else
              "COMPLETE")
    return {"status": status, "query_ns": elapsed,
            "left_outputs_checked": len(prepared),
            "trace_compatible_outputs": compatible,
            "exceptional_linear_outputs": len(exceptional),
            "batch_inversions": 1,
            "algebraic_hit_coordinate_pairs": sorted(hits),
            "peak_process_rss_bytes": peak_rss()}, roots_by_index


def main(mode):
    if mode == "freeze":
        assert not (HERE / "protocol.json").exists()
        assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
        reference = json.loads((PRIOR / "sage_query_result.json").read_text())
        assert reference["status"] == "COMPLETE" and reference["domain_sizes"] == [8176, 8340]
        save(HERE / "protocol.json", {"status": "FROZEN_AFFINE_BATCH_S3_JOIN",
             "curve_id": reference["curve_id"], "candidate_id": None,
             "cases": [row["name"] for row in reference["cases"]],
             "per_query_cap_ns": 120*10**9, "rss_cap_bytes": 4*1024**3,
             "workers": 1, "source_hashes": input_hashes(),
             "timing_boundary": "q supplied to complete S3 inverse and membership lookup; reusable transforms and independent replay excluded"})
        return
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_AFFINE_BATCH_S3_JOIN"
    assert protocol["source_hashes"] == input_hashes()
    assert not (HERE / "result.json").exists()
    setup_started = time.monotonic_ns()
    field = field_instance()
    roots = json.loads(ROOTS.read_text())
    left = sorted({v for row in roots["pair_rows"][0]["pairs"] for v in row[2:]})
    right = {field.from_integer(v) for row in roots["pair_rows"][1]["pairs"] for v in row[2:]}
    assert [len(left), len(right)] == [8176, 8340]
    left = [field.from_integer(v) for v in left]
    prepared = prepare(field, left)
    setup_ns = time.monotonic_ns()-setup_started
    setup_peak_rss = peak_rss()
    reference = json.loads((PRIOR / "sage_query_result.json").read_text())
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("independent_s3_audit", PRIOR / "sage_audit.py")
    audit = module_from_spec(spec)
    spec.loader.exec_module(audit)
    cases = []
    for old in reference["cases"]:
        q = field.from_integer(old["target_reciprocal"])
        actual, all_roots = join(prepared, right, q, field,
                                 protocol["per_query_cap_ns"], protocol["rss_cap_bytes"])
        replay_started = time.monotonic_ns()
        expected = sorted(map(tuple, old["algebraic_hit_coordinate_pairs"]))
        assert actual["status"] == "COMPLETE"
        assert list(map(tuple, actual["algebraic_hit_coordinate_pairs"])) == expected
        for c, candidates in zip(left, all_roots):
            independently = audit.right_roots(c, q, field)
            assert {encode(v) for v in candidates} == {encode(v) for v in independently}
        replay_ns = time.monotonic_ns()-replay_started
        actual.update({"name": old["name"],
                       "target_reciprocal": old["target_reciprocal"],
                       "independent_full_domain_replay_ns": replay_ns,
                       "reference_query_ns": old["query_ns"]})
        cases.append(actual)
        print(json.dumps({"case": old["name"], "query_seconds": actual["query_ns"]/1e9,
                          "replay_seconds": replay_ns/1e9, "hits": len(expected)}), flush=True)
    controls = []
    for name, q in (("exceptional_linear", field.one()/left[0]),
                    ("trace_mismatch", next(field.from_integer(v) for v in range(1, 256)
                        if int(((field.from_integer(v)+field.one()/field.from_integer(v))**2).trace())
                        not in {row[2] for row in prepared}))):
        actual, all_roots = join(prepared, right, q, field,
                                 protocol["per_query_cap_ns"], protocol["rss_cap_bytes"])
        assert actual["status"] == "COMPLETE"
        for c, candidates in zip(left, all_roots):
            assert {encode(v) for v in candidates} == \
                {encode(v) for v in audit.right_roots(c, q, field)}
        if name == "exceptional_linear":
            assert actual["exceptional_linear_outputs"] == 1
        else:
            assert actual["trace_compatible_outputs"] == 0
        controls.append({"name": name, "target_reciprocal": encode(q),
                         "exceptional_linear_outputs": actual["exceptional_linear_outputs"],
                         "trace_compatible_outputs": actual["trace_compatible_outputs"],
                         "full_domain_roots_match": True})
    save(HERE / "result.json", {"status": "PASS_AFFINE_BATCH_S3_JOIN",
         "candidate_id": None, "curve_id": protocol["curve_id"],
         "target_count": 1, "domain_sizes": [len(left), len(right)],
         "reusable_setup_ns": setup_ns, "setup_peak_process_rss_bytes": setup_peak_rss,
         "cases": cases, "edge_controls": controls,
         "source_hashes": input_hashes(), "protocol_sha256": digest(HERE / "protocol.json")})


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] in (["freeze"], ["run"])
    main(sys.argv[1])
