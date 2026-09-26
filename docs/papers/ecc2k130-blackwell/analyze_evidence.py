#!/usr/bin/env python3
"""Verify the frozen paper evidence and regenerate its statistics and figures.

This script performs local analysis only. It does not launch a GPU workload.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARCHIVE = ROOT / "ecc2k130/research/candidates/goal22"
EVIDENCE = HERE / "evidence"
FIGURES = HERE / "figures"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    EVIDENCE.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    # Bundle the receipt and manifest; never alter their archived originals.
    for filename in ("measurement.json", "acceptance.json", "source-manifest.json"):
        source = ARCHIVE / filename
        destination = EVIDENCE / filename
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
        assert source.read_bytes() == destination.read_bytes(), filename
    manifest = json.loads((EVIDENCE / "source-manifest.json").read_text())
    assert sha(EVIDENCE / "measurement.json") == manifest["receipt_sha256"]
    bad = [name for name, expected in manifest["source_files"].items()
           if not (ARCHIVE / name).exists() or sha(ARCHIVE / name) != expected]
    assert not bad, bad
    receipt = json.loads((EVIDENCE / "measurement.json").read_text())
    candidate = receipt["certification_candidate"]
    stats = {}
    for name in ("baseline", candidate):
        samples = receipt["samples"][name]
        assert len(samples) == 5
        rates = []
        for s in samples:
            assert s["returncode"] == 0 and s["valid"]
            count = s["threads"] * s["batch"] * 1024 * 256
            assert count == s["expected_iterations"] == s["completed_iterations"]
            assert "0 dropped)" in s["raw"]
            final = re.search(r"finished: ([0-9.]+) M it/s", s["raw"])
            assert final and float(final[1]) == s["rate"]
            rates.append(s["rate"] / 1000)
        stats[name] = {
            "rates_billions_per_second": rates,
            "median": statistics.median(rates), "min": min(rates), "max": max(rates),
            "sample_sd": statistics.stdev(rates),
            "updates_per_sample": count,
            "workers": samples[0]["threads"], "walks": samples[0]["walks"],
            "telemetry": [s["telemetry"]["raw"].splitlines()[-1] for s in samples],
        }
        assert stats[name]["median"] == receipt["summary"][name]["rate"] / 1000
    c = receipt["variants"][candidate]
    b = receipt["variants"]["baseline"]
    assert c["reports_ok"] and b["reports_ok"]
    assert c["corpus"] == b["corpus"]
    assert c["collection_corpus"] == b["collection_corpus"]
    assert receipt["candidate_corpus_matches"]
    assert all(x["ok"] for x in c["resume_checks"])
    assert c["collection"]["valid"] and c["collection"]["returncode"] == 0
    stats["gain_percent"] = 100 * (stats[candidate]["median"] / stats["baseline"]["median"] - 1)
    stats["collection"] = {
        "samples": 1, "billions_per_second": c["collection"]["rate"] / 1000,
        "records": c["collection_corpus"]["records"],
        "bytes": c["collection_corpus"]["records"] * 32,
        "updates": c["collection"]["completed_iterations"],
        "ratio_to_benchmark_median": c["collection"]["rate"] / receipt["summary"][candidate]["rate"],
    }
    sq = load_module(ARCHIVE / "research/gen_square_reduce.py", "square_reduce_proof")
    assert sq.generate() == (ARCHIVE / "include/square_reduce.h").read_text()
    cases = sq.check()
    reduction = load_module(ARCHIVE / "codegen/genpolyreduce.py", "poly_reduce_proof")
    reduction.check()
    assert reduction.polynomial() == sq.MODULUS
    # Prime-degree binary irreducibility criterion, independent long division.
    def mod(a, f):
        while a.bit_length() >= f.bit_length():
            a ^= f << (a.bit_length() - f.bit_length())
        return a
    def gcd(a, b):
        while b:
            a, b = b, mod(a, b)
        return a
    x = 2
    for _ in range(131):
        x = mod(sq.spread(x), sq.MODULUS)
    assert x == 2 and gcd(sq.MODULUS, 2**2 ^ 2) == 1
    stats["local_checks"] = {
        "manifest_files_verified": len(manifest["source_files"]),
        "square_vectors": cases, "generated_header_identical": True,
        "general_reduction_vectors": 1261,
        "degree_131_modulus_irreducible": True,
        "square_basis_vectors": 131,
        "scope": "Receipt replay and exact local arithmetic checks; no new GPU measurement.",
    }
    (EVIDENCE / "analysis.json").write_text(json.dumps(stats, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(6.2, 2.55), layout="constrained")
    for name, label, color, marker in [
        ("baseline", "Baseline (512 threads/block)", "#596675", "s"),
        (candidate, "Candidate (640 threads/block)", "#165d92", "o"),
    ]:
        ax.plot(range(1, 6), stats[name]["rates_billions_per_second"],
                marker=marker, color=color, linewidth=1.4, label=label)
        ax.axhline(stats[name]["median"], color=color, linestyle=":", linewidth=0.9)
    ax.set(xlabel="Confirmation round (alternating run order)",
           ylabel="Billion slot updates / second", xticks=range(1, 6), ylim=(19.5, 22.65))
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    ax.legend(loc="center right", frameon=False, fontsize=8)
    fig.savefig(FIGURES / "confirmation-rates.pdf")
    plt.close(fig)
    print(json.dumps({"gain_percent": stats["gain_percent"],
                      "baseline_median": stats["baseline"]["median"],
                      "candidate_median": stats[candidate]["median"],
                      "collection": stats["collection"],
                      "checks": stats["local_checks"]}, indent=2))


if __name__ == "__main__":
    main()
