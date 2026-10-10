#!/usr/bin/env python3
"""Independently bind all native inverses to frozen controls and W14 support."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
legacy = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
old_audit = json.loads((legacy / "sage_audit.json").read_text())

for protocol_name, run_name in [("protocol.json", "result.json"),
                                ("protocol_filtered.json", "result_filtered.json")]:
    protocol = json.loads((here / protocol_name).read_text())
    result = json.loads((here / run_name).read_text())
    assert result["protocol_sha256"] == hashlib.sha256((here / protocol_name).read_bytes()).hexdigest()
    for row in result["rows"]:
        assert row["status"] == "PROCESS_OK" and row["returncode"] == 0
        native = row["native"]
        assert native["status"] == "COMPLETE_ALGEBRAIC_SCAN"
        assert native["setup_ns"] > 0 and native["query_ns"] > 0
        n = row.get("field_degree", 131)
        expected = old_audit["panels"][str(n)]["cases"][
            "positive" if row["case"] == "positive" else "trace_zero_control"]["hit_q_roots"]
        if row["variant"] == "legacy":
            assert sorted(int(x["p"][0]) for x in native["hits"]) == sorted(map(int, expected))
        else:
            got = sorted((int(x["p"][0]),int(x["q"][0])) for x in native["hits"])
            want = sorted((int(p),int(q)) for p, qs in expected.items() for q in qs)
            assert got == want
            assert native["output_states_checked"] == native["distinct_pair_outputs"]
            assert native["pair_output_entries"] == native["distinct_pair_outputs"]
        if row["variant"] == "filtered_pair_join":
            assert native["allowed_source_pairs"] == 2062
            assert native["pair_output_entries"] == 4124
            assert native["rational_masks"] == 8220
            assert native["peak_rss_bytes"] < 4294967296

columns = {}
for line in support.read_text().splitlines():
    mask, column = map(int, line.split())
    assert mask not in columns
    columns[mask] = column
assert len(columns) == 8220
pairs = [(a,a^1) for a in columns
         if a < (a^1) and (a^1) in columns and columns[a] != columns[a^1]]
assert len(pairs) == 2062
for a,b in [(18,19),(24,25)]:
    assert (a,b) in pairs
    product = 0
    for i in range(14):
        if (a>>i)&1:
            product ^= b<<i
    assert product<<2 in (1112,1376)

audit = {
    "status": "PASS_MATCHED_NATIVE_AND_SOURCE_AUDIT",
    "v1_rows": 8,
    "v2_rows": 6,
    "source_pairs": len(pairs),
    "support_sha256": hashlib.sha256(support.read_bytes()).hexdigest(),
    "legacy_sage_audit_sha256": hashlib.sha256((legacy / "sage_audit.json").read_bytes()).hexdigest(),
    "result_sha256": hashlib.sha256((here / "result.json").read_bytes()).hexdigest(),
    "result_filtered_sha256": hashlib.sha256((here / "result_filtered.json").read_bytes()).hexdigest(),
}
(here / "audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True)+"\n")
print(json.dumps(audit, sort_keys=True))
