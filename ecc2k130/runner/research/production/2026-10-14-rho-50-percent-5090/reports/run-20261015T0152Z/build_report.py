"""Render the two-attempt RTX 5090 rho benchmark record from frozen runs."""

import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent.parent
FAILED = CAMPAIGN / "runs/20261015T012515Z"
VALID = CAMPAIGN / "runs/20261015T013232Z"
failed = json.loads((FAILED / "result.json").read_text())
data = json.loads((VALID / "result.json").read_text())
assert not failed["valid"] and len(failed["samples"]) == 0
assert data["valid"] and len(data["samples"]) == 39
assert len(data["compatibility"]["checks"]) == 6
assert len(data["population_results"]) == 3


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


rows = []
for population in data["parameters"]["populations"]:
    arms = {
        label: [s["rate_billion_per_second"] for s in data["samples"]
                if s["population"] == population and s["phase"] == "timed" and s["arm"] == label]
        for label in "AB"
    }
    measured = next(r for r in data["population_results"] if r["population"] == population)
    assert len(arms["A"]) == len(arms["B"]) == 5
    assert all(s["dropped"] == 0 for s in data["samples"] if s["population"] == population)
    assert len({s["dp_sorted_sha256"] for s in data["samples"]
                if s["population"] == population}) == 1
    rows.append({
        "population": population,
        "A": {"minimum": min(arms["A"]), "median": statistics.median(arms["A"]),
              "maximum": max(arms["A"])},
        "B": {"minimum": min(arms["B"]), "median": statistics.median(arms["B"]),
              "maximum": max(arms["B"])},
        "paired_ratios": measured["pairs"],
        "paired_ratio": {"minimum": measured["minimum_ratio"],
                         "median": measured["median_ratio"],
                         "maximum": measured["maximum_ratio"]},
        "dp_records_per_sample": next(s["dp_records"] for s in data["samples"]
                                      if s["population"] == population),
        "dp_sorted_sha256": measured["corpus_sha256"],
        "return_rate_billion_per_second": measured["return_rate_billion_per_second"],
    })
best_a = max(rows, key=lambda row: row["A"]["median"])
best_b = max(rows, key=lambda row: row["B"]["median"])
summary = {
    "record_type": "ecc2k130_rho_5090_pair_report_summary_v1",
    "provenance": "internal",
    "failed_attempt": {
        "result_sha256": digest(FAILED / "result.json"),
        "result_path": str((FAILED / "result.json").relative_to(CAMPAIGN)),
        "valid": False, "samples": 0,
        "error": failed["error"],
        "candidate_binary_sha256": failed["candidate_binary_sha256"],
        "delete_http": json.loads((FAILED / "runpod-delete.json").read_text())["delete_http"],
    },
    "completed_attempt": {
        "result_sha256": digest(VALID / "result.json"),
        "run_log_sha256": digest(VALID / "run.log"),
        "result_path": str((VALID / "result.json").relative_to(CAMPAIGN)),
        "valid": True, "samples": len(data["samples"]),
        "source_commit": data["source_commit"],
        "driver_sha256": data["driver_sha256"],
        "pinned_binary_sha256": data["pinned_binary_sha256"],
        "candidate_binary_sha256": data["candidate_binary_sha256"],
        "candidate_local_hash_matches": digest(VALID / "candidate") == data["candidate_binary_sha256"],
        "gpu": data["gpu"], "compiler": data["compiler"],
        "started_at_utc": data["started_at_utc"],
        "completed_at_utc": data["completed_at_utc"],
        "compatibility_cases": len(data["compatibility"]["checks"]),
        "host_reference_verifications": sum(run["verified"]
            for check in data["compatibility"]["checks"] for run in check["runs"]),
        "delete_http": json.loads((VALID / "runpod-delete.json").read_text())["delete_http"],
    },
    "rows": rows,
    "best_tested_A": {"population": best_a["population"],
                      "billion_updates_per_second": best_a["A"]["median"]},
    "best_tested_B": {"population": best_b["population"],
                      "billion_updates_per_second": best_b["B"]["median"]},
    "derived_best_geometry_rate_ratio": best_b["B"]["median"] / best_a["A"]["median"],
    "derived_1p5x_threshold_billion_updates_per_second": 1.5 * best_a["A"]["median"],
    "measurement_boundary": "one RTX 5090, native GPU client and local DP collection",
    "unmeasured": ["S3 delivery", "ingest", "collision processing", "sustained campaign rate",
                   "expected target-search time"],
}
(HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def line(x1, y1, x2, y2, color="#cbd5e1", width=1, dash=""):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{extra}/>')


def label(x, y, value, size=14, color="#172333", weight=400, anchor="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{value}</text>')


svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="510" '
       'viewBox="0 0 1100 510">',
       '<rect width="1100" height="510" fill="white"/>',
       '<g font-family="Arial, Helvetica, sans-serif">',
       label(32, 34, "ECC2K-130 signed-Frobenius DP32 | one RTX 5090", 22, weight=700),
       label(130, 78, "Native client rate, billion complete updates/s", 15, weight=700),
       label(760, 78, "Paired B/A rate ratio", 15, weight=700)]
rate_x0, rate_x1 = 130, 650
ratio_x0, ratio_x1 = 760, 1040
rate_px = lambda value: rate_x0 + (rate_x1 - rate_x0) * value / 22
ratio_px = lambda value: ratio_x0 + (ratio_x1 - ratio_x0) * (value - 0.7) / 0.85
for value in (0, 5, 10, 15, 20):
    x = rate_px(value)
    svg.extend((line(x, 95, x, 421), label(x, 441, str(value), 12, anchor="middle")))
for value in (0.75, 1.0, 1.25, 1.5):
    x = ratio_px(value)
    svg.extend((line(x, 95, x, 421, "#64748b" if value == 1 else "#cbd5e1"),
                label(x, 441, f"{value:g}", 12, anchor="middle")))
svg.append(line(rate_px(summary["derived_1p5x_threshold_billion_updates_per_second"]),
                95, rate_px(summary["derived_1p5x_threshold_billion_updates_per_second"]),
                421, "#b42318", 2, "6 5"))
svg.append(line(ratio_px(1.5), 95, ratio_px(1.5), 421, "#b42318", 2, "6 5"))
for i, row in enumerate(rows):
    center = 148 + 111 * i
    svg.append(label(30, center + 5, f'{row["population"]:,}', 14, weight=700))
    for offset, arm, color in ((-15, "A", "#415a77"), (15, "B", "#20a39e")):
        item = row[arm]
        y = center + offset
        svg.append(f'<rect x="{rate_x0}" y="{y - 11}" width="{rate_px(item["median"]) - rate_x0:.1f}" '
                   f'height="22" fill="{color}"/>')
        svg.append(line(rate_px(item["minimum"]), y, rate_px(item["maximum"]), y,
                        "#18222d", 2))
        svg.append(line(rate_px(item["minimum"]), y - 5, rate_px(item["minimum"]), y + 5,
                        "#18222d", 2))
        svg.append(line(rate_px(item["maximum"]), y - 5, rate_px(item["maximum"]), y + 5,
                        "#18222d", 2))
        svg.append(label(rate_px(item["median"]) + 8, y + 5,
                         f'{arm} {item["median"]:.3f}', 12))
    ratio = row["paired_ratio"]
    y = center
    svg.append(line(ratio_px(ratio["minimum"]), y, ratio_px(ratio["maximum"]), y,
                    "#186c69", 4))
    svg.append(f'<circle cx="{ratio_px(ratio["median"]):.1f}" cy="{y}" r="6" fill="#186c69"/>')
    svg.append(label(ratio_px(ratio["median"]) + 13, y + 5,
                     f'{ratio["median"]:.3f}', 13, weight=700))
svg.append(label(32, 483, "A = pinned binary; B = four-warp build. Whiskers = observed min/max; dashed red = 1.5x screen.", 12))
svg.append('</g></svg>')
(HERE / "rates.svg").write_text("\n".join(svg) + "\n")
