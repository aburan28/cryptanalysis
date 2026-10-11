"""Freeze Sage-verified raw preimages and native input before rerun."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
paths = {
    "source": HERE / "exact_join.cpp",
    "binary": HERE / "exact_join_native",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "input": HERE / "input_v2.txt",
    "input_manifest": HERE / "input_v2_manifest.json",
    "producer": HERE / "make_input_sage.py",
    "sage_runtime": HERE / "sage_runtime_info.json",
    "screen": HERE.parent / "n131_w18_four_pairs/screen.json",
    "fixture": HERE.parent / "n41_two_pair_relaxation_20261011/targets.json",
    "relaxed_receipt": HERE.parent / "n41_direct_relaxed_pair_join_20261011/receipt.json",
    "v1_protocol": HERE / "protocol.json",
    "v1_failure": HERE / "run.stderr",
}
assert json.loads((HERE / "input_v2_manifest.json").read_text())["status"] == \
       "PASS_SAGE_RAW_SOURCE_PREIMAGES"
out = {"status": "FROZEN_EXACT_TRANSPORT_N41_PAIR_JOIN_V2",
       "candidate_id": None,
       "utc": datetime.now(timezone.utc).isoformat(),
       "platform": platform.platform(),
       "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                         for name, path in paths.items()},
       "limits": {"workers": 1, "setup_seconds": 120,
                  "online_seconds_per_query": 120, "rss_bytes": 4*1024**3},
       "input_law": "Sage-verified raw P preimages of each frozen 4P screen row; D=P+F(P) in native join"}
path = HERE / "protocol_v2.json"
if path.exists():
    raise SystemExit("protocol_v2 exists")
path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], hashlib.sha256(path.read_bytes()).hexdigest())
