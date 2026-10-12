"""Document layout only: plot the counts already recorded by native Rust."""
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

report_dir = Path(__file__).parent
run = json.loads((report_dir / "../../runs/run-20261012T0331Z/n83.json").resolve().read_text())
fig, ax = plt.subplots(figsize=(7.2, 2.5))
categories = ["Orbit-point entries", "Addition pairs", "Surface-only rejection"]
for case, offset, color in zip(run["cases"], [-0.17, 0.17], ["#315b9c", "#309374"]):
    values = [case["transfer"]["projective_roundtrip_points_checked"],
              case["transfer"]["transported_addition_pairs_checked"],
              int(case["negative_control"]["curve_image_decode_rejected"])]
    positions = [index + offset for index in range(len(categories))]
    bars = ax.barh(positions, values, height=0.3, color=color, label=f'a={case["source"]["a"]}')
    ax.bar_label(bars, padding=4, fontsize=9)
ax.set_yticks(range(len(categories)), categories)
ax.invert_yaxis()
ax.set_xlim(0, 190)
ax.set_xlabel("Recorded checks per fixture (counts; no timing)")
ax.legend(loc="lower right", frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.set_title("run-20261012T0331Z — one deterministic run per variant", fontsize=10)
fig.tight_layout()
for extension in ["svg", "pdf", "png"]:
    fig.savefig(report_dir / f"checks.{extension}", dpi=160)
    if extension == "svg":
        svg = report_dir / "checks.svg"
        svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
plt.close(fig)
