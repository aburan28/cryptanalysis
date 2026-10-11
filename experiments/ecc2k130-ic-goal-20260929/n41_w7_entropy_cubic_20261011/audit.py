"""Bind W7/W8/W9 geometry, controls, and public search logs."""

import collections
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
R=549756390943


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())


def audit_width(path,dimension,mask_count,columns_count,base_count):
    geometry=load(path/"geometry.json")
    geometry_audit=load(HERE/"geometry_audit.json")
    geometry_union=next(row for row in geometry_audit["rows"] if row["dimension"]==dimension)
    scan=load(path/"protocol.json")
    fixture=load(path/"fixture.json")
    query_protocol=load(path/"query/protocol.json")
    control=load(path/"query/control_result.json")
    query=load(path/"query/query_result.json")
    assert geometry["status"]==f"COMPLETE_N41_W{dimension}_RATIONAL_SOURCE_SCAN"
    assert geometry["protocol_sha256"]==sha(path/"protocol.json")
    assert scan["sha256"]["source"]==sha(path/"scan_sage.py")
    assert scan["sha256"]["runtime"]==sha(path/"sage_runtime_info.json")
    assert len(geometry["rows"])==mask_count
    assert geometry["counts"]["signed_frobenius_columns"]==columns_count
    assert geometry["counts"]["usable_points_B"]==base_count
    assert geometry_union["geometry_sha256"]==sha(path/"geometry.json")
    assert geometry_union["distinct_union_B"]==base_count
    assert geometry_union["cross_window_duplicates"]==0
    assert fixture[f"w{dimension}_geometry_sha256"]==sha(path/"geometry.json")
    assert fixture["w6_fixture_sha256"]==sha(ROOT/"n41_transport_cubic_s8_20261011/fixture.json")
    assert query_protocol["source_dimension"]==dimension
    assert query_protocol["source_rational_masks_per_window"]==mask_count
    assert query_protocol["factor_base_B"]==base_count
    assert query_protocol["folded_columns_K"]==columns_count
    for name,digest in query_protocol["source_sha256"].items():
        local={f"w{d}_{kind}":filename for d in (7,8,9) for kind,filename in
               (("runner","run.py"),("circuit","circuit.py"),
                ("geometry","geometry.json"),("scan","scan_sage.py"),
                ("scan_protocol","protocol.json"),("fixture","fixture.json"),
                ("fixture_producer","make_fixture.py"),
                ("runtime","sage_runtime_info.json"))}
        if name in local:
            assert digest==sha(path/local[name]),name
    assert control["status"]=="PASS_FULL_N41_TRANSPORTED_EIGHT_SLOT_ASSIGNMENT"
    assert control["protocol_sha256"]==sha(path/"query/protocol.json")
    assert control["assignment_check"]["clauses"]==control["formula"]["clauses"]
    assert control["assignment_check"]["native_xor_rows"]==control["formula"]["native_xor_rows"]
    assert query["status"]=="BOUNDED_UNKNOWN" and query["solver_started"]
    assert query["solver_timed_out"] and not query["solver_rss_exceeded"]
    assert query["protocol_sha256"]==sha(path/"query/protocol.json")
    assert query["peak_combined_rss_bytes"]<4294967296
    phases=query["phase_seconds"]
    assert phases["total"]>=sum(phases[k] for k in ("construction","write_and_hash","solver"))
    stdout=gzip.open(path/"query/solver.stdout.gz","rb").read()
    stderr=gzip.open(path/"query/solver.stderr.gz","rb").read()
    assert hashlib.sha256(stdout).hexdigest()==query["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest()==query["stderr_sha256"]
    assert b"c rst" in stdout and b"s SATISFIABLE" not in stdout
    assert b"s UNSATISFIABLE" not in stdout
    counts=collections.Counter(row["column"] for row in geometry["rows"])
    signed=2*mask_count
    pair_count=signed*(signed-1)//2-sum((2*v)*(2*v-1)//2 for v in counts.values())
    return {"dimension":dimension,"rational_masks":mask_count,
            "base_points_B":base_count,"folded_columns_K":columns_count,
            "geometry_union_audit_sha256":sha(HERE/"geometry_audit.json"),
            "distinct_column_pair_states":pair_count,
            "raw_four_pair_mean_numerator":pair_count**4,
            "raw_four_pair_mean_denominator":R,
            "query_status":query["status"],
            "query_formula_bytes":query["formula"]["bytes"],
            "query_solver_seconds":phases["solver"],
            "query_peak_rss_bytes":query["peak_combined_rss_bytes"],
            "active_restart_lines":sum(line.startswith(b"c rst") for line in stdout.splitlines()),
            "sha256":{"geometry":sha(path/"geometry.json"),
                      "query_protocol":sha(path/"query/protocol.json"),
                      "query_result":sha(path/"query/query_result.json")}}


w7=audit_width(HERE,7,63,57,504)
w8=audit_width(HERE/"w8",8,125,117,1000)
w9=audit_width(HERE/"w9",9,259,251,2072)
assert w7["distinct_column_pair_states"]==7784
assert w8["distinct_column_pair_states"]==30952
assert w9["distinct_column_pair_states"]==133596
out={"status":"PASS_N41_W7_W8_W9_PUBLIC_CUBIC_AUDIT",
     "candidate_id":None,"rows":[w7,w8,w9]}
(HERE/"audit.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
print(out["status"],[(v["dimension"],v["query_status"]) for v in out["rows"]])
