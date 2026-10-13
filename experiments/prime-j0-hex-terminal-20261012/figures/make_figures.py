#!/usr/bin/env python3
"""Render the source-linked scalar pipeline and exact storage comparison."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hex-terminal-mpl"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def exact_inputs() -> tuple[dict, dict, dict, dict]:
    census = load(EXP / "search.json")
    mac = load(EXP / "storage-macos.json")
    linux = load(EXP / "storage-linux.json")
    direct = load(ROOT / "experiments/prime-j0-power2-direct-terminal-20261012/replay.json")
    assert census["table_point_entries"] == 174_883
    assert census["direct_terminal_point_entries"] == 177_174
    assert mac["runs"]["candidate"]["retained_bytes_exact_accounting"] == 11_505_936
    assert mac["runs"]["reference"]["retained_bytes_exact_accounting"] == 14_309_128
    assert linux["runs"]["candidate"]["retained_bytes_exact_accounting"] == 11_505_936
    assert direct["panels"][0]["candidate_retained_bytes"] == 11_652_560
    return census, mac, linux, direct


def save(fig, stem: str) -> None:
    svg = HERE / f"{stem}.svg"
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fig.savefig(HERE / f"{stem}.png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def pipeline(census: dict) -> None:
    fig, ax = plt.subplots(figsize=(12.8, 3.8))
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 3.8)
    ax.axis("off")
    boxes = [
        (0.1, "Reduced scalar", "0 <= k < r"),
        (2.7, "Lattice cell", "two exact quotients"),
        (5.3, "Nearest corner", "four-score minimum"),
        (7.9, "Radix-256 recode", "15 ordinary digits"),
        (10.5, "Direct terminal", "11,023 orbit slots"),
    ]
    for x, title, detail in boxes:
        patch = FancyBboxPatch((x, 2.1), 2.2, 0.9,
                               boxstyle="round,pad=0.09,rounding_size=0.12",
                               linewidth=1.4, edgecolor="#254b74", facecolor="#eaf3fc")
        ax.add_patch(patch)
        ax.text(x+1.1, 2.67, title, ha="center", va="center", fontsize=10.4,
                weight="bold", color="#173451")
        ax.text(x+1.1, 2.36, detail, ha="center", va="center", fontsize=8.8,
                color="#365978")
    for x in (2.34, 4.94, 7.54, 10.14):
        ax.add_patch(FancyArrowPatch((x, 2.55), (x+0.34, 2.55),
                                    arrowstyle="-|>", mutation_scale=16,
                                    color="#4c6d8d", linewidth=1.4))
    ax.text(6.4, 3.48, "Voronoi-clipped fixed-base scalar multiplication",
            ha="center", fontsize=15, weight="bold", color="#173451")
    ax.add_patch(FancyBboxPatch((0.23, 0.31), 12.35, 1.15,
                               boxstyle="round,pad=0.08,rounding_size=0.1",
                               linewidth=1.1, edgecolor="#1b746c", facecolor="#e7f5f1"))
    ax.text(0.5, 1.2, "Terminal certificate", fontsize=10.5,
            weight="bold", color="#14544f")
    ax.text(0.5, 0.9,
            "3 N(t) <= 66,051   and   |2 <t,w>| <= C for w in {W, V, W+V}",
            fontsize=10.1, color="#14544f")
    ax.text(0.5, 0.58,
            f"C = {census['hex_limit']}   |   15 x 10,924 + 11,023 = 174,883 entries",
            fontsize=9.5, color="#14544f")
    save(fig, "pipeline")


def storage(census: dict, mac: dict, direct: dict) -> None:
    labels = ["Radix-286\nreference", "Radix-256\ndirect disk", "Radix-256\nVoronoi clipped"]
    entries = [mac["runs"]["reference"]["point_entries"],
               census["direct_terminal_point_entries"], census["table_point_entries"]]
    bytes_retained = [mac["runs"]["reference"]["retained_bytes_exact_accounting"],
                      direct["panels"][0]["candidate_retained_bytes"],
                      mac["runs"]["candidate"]["retained_bytes_exact_accounting"]]
    colors = ["#71879d", "#5f94ba", "#168478"]
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.7), gridspec_kw={"wspace": 0.27})
    for ax, values, title, unit, scale in (
        (axes[0], entries, "Stored point entries", "entries", 1),
        (axes[1], bytes_retained, "Retained table allocation", "MiB", 1024**2),
    ):
        bars = ax.bar(range(3), [v/scale for v in values], color=colors, width=0.62)
        ax.set_xticks(range(3), labels, fontsize=9)
        ax.set_ylabel(unit)
        ax.set_title(title, fontsize=12, weight="bold")
        ax.set_ylim(0, max(v/scale for v in values) * 1.22)
        ax.grid(axis="y", alpha=0.22)
        ax.set_axisbelow(True)
        for bar, value in zip(bars, values, strict=True):
            label = f"{value:,}" if scale == 1 else f"{value/scale:.3f} MiB"
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(v/scale for v in values)*0.025,
                    label, ha="center", va="bottom", fontsize=8.5, weight="bold")
    fig.subplots_adjust(bottom=0.27, top=0.83)
    fig.suptitle("Exact secp256k1 fixed-base table accounting", fontsize=15, weight="bold")
    fig.text(0.5, 0.055,
             "One audited build per format; exact table counts and allocator accounting, sampling uncertainty not applicable.",
             ha="center", fontsize=8.8, color="#374b5e")
    save(fig, "storage")


def main() -> None:
    census, mac, linux, direct = exact_inputs()
    pipeline(census)
    storage(census, mac, direct)
    sources = {
        str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
        for path in (EXP / "search.json", EXP / "storage-macos.json",
                     EXP / "storage-linux.json",
                     ROOT / "experiments/prime-j0-power2-direct-terminal-20261012/replay.json")
    }
    (HERE / "sources.json").write_text(json.dumps({"schema": 1, "sources": sources},
                                                 indent=2, sort_keys=True) + "\n")
    print("rendered pipeline.svg and storage.svg from exact receipts")


if __name__ == "__main__":
    main()
