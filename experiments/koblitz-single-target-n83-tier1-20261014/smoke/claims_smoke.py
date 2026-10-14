"""Usage: python3 claims_smoke.py <experiment dir> <smoke dir with rho_q0.jsonl> <crypto run dir R1>.
Schema smoke for verify_tier1_receipt.build_claims: real n=83 strong-rho record on Q0 from the local
smoke, IC record carrying the archived 2026-10-06 R1 relation (real witness) with R1's timers mapped onto
the online producer's field names. NOT a measurement."""
import json, sys
from pathlib import Path
E, SM, R1 = map(Path, sys.argv[1:4])
sys.path.insert(0, str(E))
import verify_tier1_receipt as v
lab, panel = v.harness()
protocol = json.loads((E / "tier1_protocol.json").read_text())
ic = json.loads((R1 / "ic.jsonl").read_text()); s = json.loads((R1 / "ic_summary.jsonl").read_text())
ic_rec = dict(ic, online_ms=ic["target_ms"], target_pdp_ms=ic["target_pdp_ms"], online_start_ns=66_000_000_000,
              online_stop_ns=66_000_000_000 + int(ic["target_ms"] * 1e6), relation_checks=1)
ic_rec["target_query_ms"] = ic["target_ms"] - sum(ic[k] for k in ("target_pdp_ms", "target_relation_check_ms", "target_descent_ms", "target_recovery_check_ms"))
ic_sum = {"base_hash": s["base_hash"], "setup_complete_ns": 65_797_000_000}
rows = [json.loads(l) for l in (SM / "rho_q0.jsonl").read_text().splitlines()]
pair = {"case": "A-q0", "repeat": 0, "order": "rho_then_ic", "ratio": rows[0]["online_ms"] / ic_rec["online_ms"],
        "ic": {"_raw": {"records": [ic_rec, ic_sum], "point": ic["target"], "seed": 0}, "binary_sha256": "0" * 64},
        "rho": {"_raw": {"records": rows, "point": rows[0]["published_q"], "seed": 202610141}, "binary_sha256": "1" * 64}}
receipt = SM / "claims_receipt"; receipt.mkdir(exist_ok=True)
(receipt / "allocation.json").write_text(json.dumps({"provider": "local_container_smoke", "instance_id": "claude-container-smoke-20261014"}))
pre = {"timing_ms": {"rank_stage": s["timing_ms"]["rank_stage"], "linear_algebra": s["timing_ms"]["linear_algebra"]}, "table_sha256": "2" * 64}
claims = v.build_claims("A", [pair], protocol, receipt, pre, lab, panel, 3)
c = claims[0]
print(json.dumps({"check": c["check"], "errors": c["errors"], "independent_validation": c["claim"]["independent_validation"],
                  "replay": json.loads((receipt / "claims/A/A_A-q0_r0.replay.json").read_text())["ic"]["checks"],
                  "candidate_id": c["claim"]["candidate_id"], "run_id": c["claim"]["run_id"]}, indent=1))
