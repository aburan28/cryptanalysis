"""Frozen seven-seed Bernoulli selectors for public and prefix residual points."""

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def features(data, columns):
    shifts = np.arange(41, dtype=np.uint64)
    return np.concatenate([((data[:, col, None] >> shifts) & 1).astype(np.float64)
                           for col in columns], axis=1)


def predict(data, labels, columns):
    x = features(data, columns)
    classes = np.arange(1, 64, dtype=np.int16)
    counts = np.bincount(labels[:80000], minlength=64)[1:]
    bitcounts = np.array([x[:80000][labels[:80000] == seed].sum(axis=0)
                          for seed in classes])
    prob = (bitcounts + 1) / (counts[:, None] + 2)
    logprior = np.log(counts / 80000)
    score = x[80000:] @ np.log(prob / (1 - prob)).T
    score += logprior + np.log(1 - prob).sum(axis=1)
    order = np.argsort(-score, axis=1, kind="stable")
    proposals = classes[order[:, :7]]
    hits = np.any(proposals == labels[80000:, None], axis=1)
    return hits, proposals


def paired(a, b):
    delta = a.astype(np.int8) - b.astype(np.int8)
    mean = float(delta.mean())
    se = float(delta.std(ddof=1) / math.sqrt(len(delta)))
    only_a = int(np.sum(a & ~b))
    only_b = int(np.sum(b & ~a))
    return {"difference": mean,
            "normal95": [mean - 1.959963984540054 * se,
                         mean + 1.959963984540054 * se],
            "discordant_first_only": only_a,
            "discordant_second_only": only_b,
            "mcnemar_exact_two_sided_p": float(binomtest(only_a, only_a + only_b).pvalue)}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"]["fitter"] == digest(HERE / "fit.py")
    assert protocol["residual_sha256"] == digest(HERE / "residuals.tsv")
    assert not (HERE / "fit_result.json").exists()
    data = np.loadtxt(HERE / "residuals.tsv", dtype=np.uint64, delimiter="\t", skiprows=1)
    assert data.shape == (100000, 10)
    labels = data[:, 6].astype(np.int16)
    assert np.all((labels >= 1) & (labels < 64))
    assert np.all((data[:, 6] ^ data[:, 7]) < 8)
    counts = np.bincount(labels[:80000], minlength=64)[1:]
    classes = np.arange(1, 64, dtype=np.int16)
    baseline = classes[np.argsort(-counts, kind="stable")[:7]]
    bhit = np.isin(labels[80000:], baseline)
    arms = {"public": (0, 1), "after_first_pair": (2, 3),
            "after_two_free_pairs": (4, 5)}
    hits = {}
    proposals = {}
    for name, columns in arms.items():
        hits[name], proposals[name] = predict(data, labels, columns)
    assert int(bhit.sum()) == 4465 and int(hits["public"].sum()) == 4208
    with (HERE / "holdout_outcomes.tsv").open("x") as stream:
        stream.write("seed\tbaseline\tpublic\tafter_first_pair\tafter_two_free_pairs\n")
        for seed, base, q, r0, r01 in zip(labels[80000:], bhit, hits["public"],
                                          hits["after_first_pair"], hits["after_two_free_pairs"]):
            stream.write(f"{seed}\t{int(base)}\t{int(q)}\t{int(r0)}\t{int(r01)}\n")
    result = {
        "status": "COMPLETE_HELDOUT_PREFIX_SEED_SELECTOR",
        "protocol_sha256": digest(HERE / "protocol.json"),
        "holdout_outcomes_sha256": digest(HERE / "holdout_outcomes.tsv"),
        "train_count": 80000, "holdout_count": 20000,
        "baseline_seeds": [int(x) for x in baseline],
        "seven_seed_hits": {"baseline": int(bhit.sum()),
                            **{name: int(hit.sum()) for name, hit in hits.items()}},
        "paired_vs_baseline": {name: paired(hit, bhit) for name, hit in hits.items()},
        "paired_residual_vs_public": {name: paired(hits[name], hits["public"])
                                      for name in ("after_first_pair", "after_two_free_pairs")},
        "numpy_version": np.__version__,
    }
    with (HERE / "fit_result.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result["seven_seed_hits"], sort_keys=True))


if __name__ == "__main__":
    main()
