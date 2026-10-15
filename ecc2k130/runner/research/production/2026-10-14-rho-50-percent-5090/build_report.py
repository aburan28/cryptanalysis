"""Render the immutable, pre-trial RunPod allocation observations."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
REPORT = ROOT / "reports" / "access-20261015T010714Z"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(name):
    path = RUNS / name / "runpod-create.json"
    return path, json.loads(path.read_text())


def main():
    REPORT.mkdir(parents=True, exist_ok=False)
    rows = []
    for stamp, cloud, expected in (
        ("20261015T010714Z", "COMMUNITY", 400),
        ("20261015T010929Z", "COMMUNITY", 500),
        ("20261015T011009Z", "SECURE", 500),
    ):
        path, data = receipt(stamp)
        assert data["create_http"] == expected
        assert data["inventory_after_http"] == 200
        assert data["matching_after"] == []
        assert data["request"]["cloudType"] == cloud
        assert data["request"]["gpuCount"] == 1
        rows.append({"stamp": stamp, "cloud": cloud, "http": expected,
                     "started_at_utc": data["started_at_utc"],
                     "completed_at_utc": data["completed_at_utc"],
                     "provider_response": data["create_response"],
                     "matching_pods_after": 0, "receipt_sha256": sha(path),
                     "receipt_path": str(path.relative_to(ROOT))})
    assert "no instances currently available" in rows[1]["provider_response"]["error"]
    assert "balance is too low" in rows[2]["provider_response"]["error"]
    source = RUNS / "20261015T010714Z" / "inputs" / "source.tar.gz"
    pinned = RUNS / "20261015T010714Z" / "inputs" / "pinned"
    assert sha(pinned) == "0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4"
    summary = {"record_type": "ecc2k130_rho_5090_allocation_observation_v1",
               "claim_scope": "RunPod allocation only; no GPU benchmark sample or campaign collection",
               "source_commit": "fb5ae4b9b9ef5c24780d5a82d04102ecffda2dd5",
               "source_tar_sha256": sha(source), "pinned_binary_sha256": sha(pinned),
               "remote_driver_sha256": sha(ROOT / "remote_pair.py"),
               "runpod_controller_sha256": sha(ROOT / "runpod_control.py"),
               "plan_sha256": sha(ROOT / "PLAN.md"),
               "prelaunch_quote_usd_per_gpu_hour": {"community": 0.69, "secure": 1.19},
               "attempts": rows, "allocated_pods": 0, "gpu_trials_started": 0,
               "gpu_samples": 0, "allocated_gpu_duration_seconds": 0,
               "unblock": "Fund the RunPod account and confirm a CUDA 13 capable RTX 5090 offer; then launch a new sealed run directory."}
    (REPORT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="990" height="280" viewBox="0 0 990 280">
<rect width="990" height="280" fill="#f8fafc"/>
<style>text{font-family:Arial,sans-serif;fill:#17324d}.title{font-size:19px;font-weight:bold}.small{font-size:14px}.box{fill:white;stroke:#5481a4;stroke-width:2}.bad{fill:#fff3e6;stroke:#c86e29;stroke-width:2}</style>
<text class="title" x="22" y="32">RTX 5090 allocation path — 0 pods created, 0 GPU samples</text>
<rect class="bad" x="20" y="66" width="295" height="150" rx="12"/>
<text class="title" x="37" y="99">Community attempt 1</text><text class="small" x="37" y="132">HTTP 400; body not retained</text><text class="small" x="37" y="157">Follow-up inventory: no pod</text><text class="small" x="37" y="182">No benchmark process</text>
<path d="M315 141 H347" stroke="#5481a4" stroke-width="3" marker-end="url(#arrow)"/>
<rect class="bad" x="350" y="66" width="295" height="150" rx="12"/>
<text class="title" x="367" y="99">Community attempt 2</text><text class="small" x="367" y="132">HTTP 500: no instance available</text><text class="small" x="367" y="157">Follow-up inventory: no pod</text><text class="small" x="367" y="182">Quoted $0.69 per GPU-hour</text>
<path d="M645 141 H677" stroke="#5481a4" stroke-width="3" marker-end="url(#arrow)"/>
<rect class="bad" x="680" y="66" width="290" height="150" rx="12"/>
<text class="title" x="697" y="99">Secure attempt 3</text><text class="small" x="697" y="132">HTTP 500: account balance low</text><text class="small" x="697" y="157">Follow-up inventory: no pod</text><text class="small" x="697" y="182">Quoted $1.19 per GPU-hour</text>
<text class="small" x="22" y="252">Source: three immutable RunPod create receipts in runs/; provider stock and quotes read immediately before requests.</text>
<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0 0 L10 4 L0 8 Z" fill="#5481a4"/></marker></defs>
</svg>'''
    (REPORT / "allocation.svg").write_text(svg + "\n")


if __name__ == "__main__":
    main()
