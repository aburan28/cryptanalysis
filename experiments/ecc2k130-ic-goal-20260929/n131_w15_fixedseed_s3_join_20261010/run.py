#!/usr/bin/env python3
"""Exact target-coupled S3 inverse join of two complete W15 pair domains."""

import hashlib
import importlib.util
import json
import resource
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
PROTOCOL = HERE / "protocol.json"
ROOTS = BASE / "pair_roots.json"
PUBLIC = BASE / "result.json"

spec = importlib.util.spec_from_file_location("independent_bit_field", BASE / "audit_prefix.py")
field = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if __import__("sys").platform == "darwin" else value*1024)


def inverse(value):
    """Binary polynomial extended Euclid, independent of Sage's field API."""
    if value == 0:
        raise ZeroDivisionError
    modulus = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
    a, b, x, y = value, modulus, 1, 0
    while a != 1:
        assert a != 0
        shift = a.bit_length()-b.bit_length()
        if shift < 0:
            a, b = b, a
            x, y = y, x
            shift = -shift
        a ^= b << shift
        x ^= y << shift
    result = field.reduce_poly(x)
    assert field.multiply(value, result) == 1
    return result


def half_trace(value):
    result = 0
    power = value
    for _ in range(66):
        result ^= power
        power = field.square(field.square(power))
    return result if field.square(result) ^ result == value else None


def reciprocal_s3(left, right, target):
    product = field.multiply(field.multiply(left, right), target)
    return field.square(left ^ right ^ target) ^ product ^ field.square(product)


def roots_for_right(right, q):
    product = field.multiply(q, right)
    leading = 1 ^ field.square(product)
    constant = field.square(right) ^ field.square(q)
    if leading == 0:
        return [field.multiply(constant, inverse(product))] if product else []
    if product == 0:
        root = constant
        for _ in range(130):
            root = field.square(root)
        return [root]
    inv_leading = inverse(leading)
    inv_product = inverse(product)
    rhs = field.multiply(field.multiply(leading, constant), field.square(inv_product))
    h = half_trace(rhs)
    if h is None:
        return []
    scale = field.multiply(product, inv_leading)
    roots = [field.multiply(scale, h), field.multiply(scale, h ^ 1)]
    assert roots[0] != roots[1]
    assert all(reciprocal_s3(root, right, q) == 0 for root in roots)
    return roots


def query(name, q, left, right, cap, rss_cap, control=None):
    started = time.monotonic()
    hits = []
    visited = no_rational = quadratic = linear = 0
    status = "COMPLETE"
    for d, right_pairs in right.items():
        if visited % 128 == 0 and time.monotonic()-started >= cap:
            status = "CENSORED_TIME"
            break
        if visited % 128 == 0 and peak_rss() >= rss_cap:
            status = "OOM"
            break
        visited += 1
        options = roots_for_right(d, q)
        if not options:
            no_rational += 1
        elif len(options) == 1:
            linear += 1
        else:
            quadratic += 1
        for c in options:
            if c in left:
                hits.append({"left_output": c, "right_output": d,
                             "left_pairs": left[c], "right_pairs": right_pairs})
    elapsed = time.monotonic()-started
    if control is not None and status == "COMPLETE":
        assert any(row["left_output"] == control["left_output"] and
                   row["right_output"] == control["right_output"] and
                   control["left_masks"] in row["left_pairs"] and
                   control["right_masks"] in row["right_pairs"] for row in hits)
    return {"name": name, "status": status, "target_reciprocal": q,
            "right_outputs_visited": visited, "right_outputs_total": len(right),
            "no_rational_roots": no_rational, "quadratic_outputs": quadratic,
            "linear_outputs": linear, "algebraic_hits": hits,
            "query_seconds": elapsed, "peak_process_rss_bytes": peak_rss()}


def main():
    protocol = json.loads(PROTOCOL.read_text())
    from freeze import sources
    assert protocol["status"] == "FROZEN_W15_FIXEDSEED_S3_JOIN"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert not (HERE / "result.json").exists()
    setup_start = time.monotonic()
    roots = json.loads(ROOTS.read_text())
    control = json.loads(CONTROL.read_text())
    public = json.loads(PUBLIC.read_text())
    assert roots["status"] == "PASS_COMPLETE_W15_PAIR_OUTPUT_ROOTS"
    assert public["target_q"] == protocol["public_target_q"]
    domains = []
    for pair_case in roots["pair_rows"]:
        domain = {}
        for a, b, c0, c1 in pair_case["pairs"]:
            for output in (c0, c1):
                domain.setdefault(output, []).append([a, b])
        domains.append(domain)
    left, right = domains
    assert [len(left), len(right)] == protocol["domain_sizes"]
    setup_seconds = time.monotonic()-setup_start
    positive_q = control["middle_reciprocals"][6]
    positive = {"left_output": control["middle_reciprocals"][0],
                "right_output": control["middle_reciprocals"][1],
                "left_masks": control["masks"][0:2],
                "right_masks": control["masks"][2:4]}
    assert reciprocal_s3(positive["left_output"], positive["right_output"], positive_q) == 0
    assert positive_q == protocol["positive_reciprocal"]
    cases = [query("constructed_four_atom", positive_q, left, right,
                   protocol["per_query_cap_seconds"], protocol["rss_cap_bytes"], positive)]
    for index, point in enumerate(public["raw_target_preimages"]):
        q = inverse(point[0])
        if half_trace(q) is None:
            continue
        cases.append(query(f"published_point_lift_{index}", q, left, right,
                           protocol["per_query_cap_seconds"], protocol["rss_cap_bytes"]))
    assert len(cases) == 3 and cases[0]["status"] == "COMPLETE"
    overall_status = ("OOM" if any(row["status"] == "OOM" for row in cases)
                      else "COMPLETE" if all(row["status"] == "COMPLETE" for row in cases)
                      else "CENSORED_TIME")
    result = {"status": overall_status, "candidate_id": None,
              "curve_id": protocol["curve_id"],
              "positive_subtarget_is_constructed": True,
              "published_target_q": protocol["public_target_q"],
              "reusable_setup_seconds": setup_seconds,
              "domain_sizes": [len(left), len(right)], "cases": cases,
              "sampled_peak_process_rss_bytes": peak_rss(),
              "sha256": {"protocol": sha(PROTOCOL),
                         "source": sha(Path(__file__)),
                         "pair_roots": sha(ROOTS),
                         "constructed_input": sha(CONTROL),
                         "published_input": sha(PUBLIC)}}
    with (HERE / "result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "setup_seconds": setup_seconds,
                      "cases": [{"name": x["name"], "status": x["status"],
                                 "hits": len(x["algebraic_hits"]),
                                 "seconds": x["query_seconds"]} for x in cases]}), flush=True)


if __name__ == "__main__":
    main()
