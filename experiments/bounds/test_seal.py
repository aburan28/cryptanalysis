"""The seal, proved on real ecbench records; the adapter, on a synthetic sweep.

    python3 -m pytest -q experiments/bounds

The two records under `testdata/` are `docs/bounds/records/prime-rho-neg.json`
and `prime-bsgs-neg.json` of aburan28/crypto at commit
85be1540d1dad415f067b11e79291ff7737d3f7e, byte for byte as `ecbench bound fit`
wrote them.  The writer here must reproduce them from their parsed form and
recover their ids from their blanked form, or nothing this adapter writes can
be trusted to carry the id ecbench would check.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emit_bounds as eb  # noqa: E402

REAL_RECORDS = {
    "prime-rho-neg.json": "ECBND1h7b69b9787056",
    "prime-bsgs-neg.json": "ECBND1hd392c8f42bb0",
}


def real(name: str) -> str:
    return (HERE / "testdata" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name,expected", sorted(REAL_RECORDS.items()))
def test_writer_reproduces_a_real_record_byte_for_byte(name: str, expected: str) -> None:
    text = real(name)
    doc = json.loads(text)
    assert doc["bound_id"] == expected
    assert eb.dumps_pretty(doc) + "\n" == text


@pytest.mark.parametrize("name,expected", sorted(REAL_RECORDS.items()))
def test_seal_recovers_a_real_record_id(name: str, expected: str) -> None:
    text = real(name)
    doc = json.loads(text)
    doc["bound_id"] = ""
    ident, sealed = eb.seal(doc)
    assert ident == expected
    assert sealed == text
    assert eb.check_seal(text) == expected
    forged = text.replace("0.8862269254527579", "0.5862269254527579", 1)
    assert forged != text
    with pytest.raises(ValueError, match="seal mismatch"):
        eb.check_seal(forged)


def test_domain_and_method_ids_match_the_real_records() -> None:
    rho = json.loads(real("prime-rho-neg.json"))
    bsgs = json.loads(real("prime-bsgs-neg.json"))
    assert eb.domain_id(rho["domain"]) == "ECDOM1ha1f283af3a5d" == rho["domain_id"]
    assert eb.method_id("rho.negation", {"cap_multiple": "64"}) == "ECM1hefea4e0ebe79"
    assert rho["method"]["method_id"] == "ECM1hefea4e0ebe79"
    assert eb.method_id("bsgs.negation", {}) == "ECM1h87f6341629c3" == bsgs["method"]["method_id"]
    ours = {
        "problem": eb.PROBLEM,
        "family": "zp",
        "target_kind": "planted",
        "unit": eb.UNIT,
        "tier": "toy",
        "envelope": {"targets": 1, "precomputation": "none", "threads": 1},
    }
    ident = eb.domain_id(ours)
    assert ident.startswith("ECDOM1h") and len(ident) == len("ECDOM1h") + 12
    assert ident != rho["domain_id"]


def test_canonical_json_sorts_compacts_escapes_and_refuses_floats() -> None:
    v = {"b": 1, "a": [True, None, "x"], "c": {"z": 0, "y": "é"}}
    assert eb.canonical(v) == '{"a":[true,null,"x"],"b":1,"c":{"y":"\\u00e9","z":0}}'
    with pytest.raises(ValueError):
        eb.canonical({"x": 1.5})


@pytest.mark.parametrize(
    "value,text",
    [
        (1.0, "1.0"),
        (24.0, "24.0"),
        (100.0, "100.0"),
        (0.1, "0.1"),
        (0.5, "0.5"),
        (123456789.0, "123456789.0"),
        (1e-5, "0.00001"),
        (1.234e-5, "0.00001234"),
        (1e-6, "1e-6"),
        (1.5e-7, "1.5e-7"),
        (1e15, "1000000000000000.0"),
        (1e16, "1e16"),
        (1.2345678901234568e17, "1.2345678901234568e17"),
        (9007199254740993.0, "9007199254740992.0"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e308"),
        (0.0, "0.0"),
        (-0.0, "-0.0"),
        (-0.0020845730197195035, "-0.0020845730197195035"),
        (0.8862269254527579, "0.8862269254527579"),
        (596.4583333333334, "596.4583333333334"),
    ],
)
def test_floats_take_ryu_layout(value: float, text: str) -> None:
    assert eb.ryu_f64(value) == text
    assert float(text) == value


def test_non_finite_floats_are_refused() -> None:
    with pytest.raises(ValueError):
        eb.ryu_f64(math.inf)
    with pytest.raises(ValueError):
        eb.ryu_f64(math.nan)


def test_pretty_printer_layout() -> None:
    doc = {"z": [], "a": {}, "m": [1, {"k": "v"}], "s": 'q"\\\n\té', "n": None, "t": True}
    assert eb.dumps_pretty(doc) == (
        "{\n"
        '  "a": {},\n'
        '  "m": [\n'
        "    1,\n"
        "    {\n"
        '      "k": "v"\n'
        "    }\n"
        "  ],\n"
        '  "n": null,\n'
        '  "s": "q\\"\\\\\\n\\té",\n'
        '  "t": true,\n'
        '  "z": []\n'
        "}"
    )


# Ports of the stats.rs and bounds.rs unit tests, so that the resampler and
# the fit behave as ecbench's do on the cases ecbench itself checks.


def _mean_of(strata: list[list[float]]) -> float | None:
    return eb.mean([x for s in strata for x in s])


def test_bootstrap_is_deterministic_and_brackets_the_mean() -> None:
    strata = [[1.0, 2.0, 3.0, 4.0, 5.0], [10.0, 11.0, 12.0]]
    a = eb.bootstrap_ci(strata, 2000, 7, _mean_of)
    b = eb.bootstrap_ci(strata, 2000, 7, _mean_of)
    assert a is not None and a == b
    m = _mean_of(strata)
    assert m is not None and a[0] < m < a[1]


def test_cluster_bootstrap_sees_between_stratum_spread() -> None:
    strata = [[1.0] * 4, [2.0] * 4, [3.0] * 4]
    one = eb.bootstrap_ci(strata, 2000, 1, _mean_of)
    two = eb.cluster_bootstrap_ci(strata, 2000, 1, _mean_of)
    assert one is not None and one[0] == one[1]
    assert two is not None and two[1] - two[0] > 0.5
    assert eb.cluster_bootstrap_ci(strata[:1], 100, 1, _mean_of) is None


def test_quantiles_interpolate() -> None:
    assert eb.quantile([3.0, 1.0, 2.0], 0.5) == 2.0
    assert eb.quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert eb.quantile([], 0.5) is None


def test_ols_recovers_an_exact_power_law() -> None:
    pts = [(math.log(2.0**b), math.log(3.0 * math.sqrt(2.0**b))) for b in (16.0, 18.0, 20.0, 22.0)]
    fit = eb.ols(pts)
    assert fit is not None
    alpha, b, r2 = fit
    assert abs(alpha - 0.5) < 1e-9
    assert abs(math.exp(b) - 3.0) < 1e-9
    assert abs(r2 - 1.0) < 1e-12
    assert eb.ols(pts[:1]) is None
    assert eb.ols([(1.0, 1.0), (1.0, 2.0)]) is None


def test_power_law_interval_brackets_the_slope_and_needs_two_sizes() -> None:
    strata = []
    for i, b in enumerate((16.0, 18.0, 20.0, 22.0)):
        r = 2.0**b
        strata.append(
            [
                (
                    math.log(r),
                    math.log(
                        1.25 * math.sqrt(r) * (1.0 + 0.3 * (((k * 7 + i * 3) % 5) - 2.0) / 2.0)
                    ),
                )
                for k in range(8)
            ]
        )
    alpha, ci, log2_c, r2, method = eb.power_law(strata, 500, 1)
    assert alpha is not None and abs(alpha - 0.5) < 0.05
    assert ci is not None and ci[0] <= alpha <= ci[1]
    assert method == "cluster"
    assert log2_c is not None and math.isfinite(log2_c)
    assert r2 is not None and r2 > 0.9
    _, ci1, _, _, m1 = eb.power_law(strata[:1], 500, 1)
    assert ci1 is None and m1 == "none"


def test_tiers_follow_the_field_size() -> None:
    assert [eb.tier_of_bits(b) for b in (13, 32, 33, 96, 131)] == [
        "toy",
        "toy",
        "medium",
        "medium",
        "crypto",
    ]


# The adapter end to end, on a sweep shaped like `ca_bench complexity --json`.

ALGS = (("bsgs", 1.5), ("rho", 1.3), ("kangaroo", 1.9), ("grumpy", 1.2))
BITS = (20, 24, 28, 32, 36)


def synthetic_sweep(path: Path, fail_one: bool = False) -> None:
    header = {
        "record": "header",
        "schema": "ca_bench.sweep/v1",
        "mode": "complexity",
        "library_version": "0.1.0",
        "binary_sha256": "ab" * 32,
        "git_commit": "0" * 40,
        "command_line": "build/ca_bench complexity --bits 20,24,28,32,36 --reps 8 --json sweep.jsonl",
        "host": "Linux test 1.0 #1 x86_64",
    }
    lines = [json.dumps(header)]
    for group in ("zp", "ec"):
        for bits in BITS:
            n = (1 << (bits - 1)) + 2 * bits + 1
            for alg, c in ALGS:
                for i in range(8):
                    noise = 1.0 + 0.3 * (((i * 7 + bits) % 5) - 2.0) / 2.0
                    ops = int(c * math.sqrt(n) * noise)
                    row = {
                        "record": "instance",
                        "algorithm": alg,
                        "group": group,
                        "bits": bits,
                        "n": str(n),
                        "p": str(2 * n + 1),
                        "a": "1" if group == "ec" else None,
                        "b": "7" if group == "ec" else None,
                        "instance": i,
                        "x": str(i + 1),
                        "seed": 100 + i if alg in ("rho", "kangaroo") else None,
                        "status": "ok",
                        "ok": True,
                        "group_ops": ops,
                        "iterations": ops,
                        "table_entries": int(math.sqrt(n)) if alg in ("bsgs", "grumpy") else 8,
                        "collisions": 1,
                        "bytes_peak": 0,
                        "seconds": 0.001,
                        "threads": 1,
                    }
                    if fail_one and (alg, group, bits, i) == ("rho", "zp", 36, 0):
                        row["ok"] = False
                        row["status"] = "not found"
                    lines.append(json.dumps(row))
    threaded = json.loads(lines[-1])
    threaded.update(algorithm="rho-T", threads=4)
    lines.append(json.dumps(threaded))
    precomp = json.loads(lines[-2])
    precomp.update(algorithm="precomp-online")
    lines.append(json.dumps(precomp))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_emit_splits_tiers_seals_and_is_deterministic(tmp_path: Path) -> None:
    sweep = tmp_path / "sweep.jsonl"
    synthetic_sweep(sweep, fail_one=True)
    header, rows = eb.read_sweep(sweep)
    bounds, skipped = eb.build_bounds(header, rows, sweep, tmp_path, resamples=200)
    assert len(bounds) == 16
    sha = hashlib.sha256(sweep.read_bytes()).hexdigest()
    by_name = {}
    for b in bounds:
        assert eb.check_seal(b.text) == b.bound_id
        doc = json.loads(b.text)
        assert doc == b.doc
        assert eb.domain_id(doc["domain"]) == doc["domain_id"]
        assert {eb.tier_of_bits(s["field_bits"]) for s in doc["sizes"]} == {doc["domain"]["tier"]}
        if doc["domain"]["tier"] == "toy":
            assert doc["level"] == "exponent"
            assert doc["fit"]["sizes"] == 4 and doc["fit"]["alpha_ci95"] is not None
            assert doc["fit"]["scaling_claim"] is True
        else:
            assert doc["level"] == "constant"
            assert doc["fit"]["alpha"] is None and doc["fit"]["ci_method"] == "none"
            assert doc["constant"]["s"]["ci_method"] == "within"
            assert any("below 4" in r for r in doc["admissibility"]["reasons"])
        sess = doc["provenance"]["sessions"][0]
        assert sess["dir"] == "sweep.jsonl"
        assert sess["records_sha256"] == sha
        assert sess["session_id"] == "CAB1h" + sha[:12]
        assert (
            sess["spec_id"]
            == "CAS1h" + hashlib.sha256(header["command_line"].encode()).hexdigest()[:12]
        )
        assert (
            sess["env_class_id"]
            == "CAENV1h" + hashlib.sha256(header["host"].encode()).hexdigest()[:12]
        )
        assert sess["arm"] in eb.METHODS and sess["binary_sha256"] == "ab" * 32
        assert doc["stages"][0]["share_of_gae"] == 1.0
        assert doc["dimensions"]["memory"]["known"] is True
        assert doc["dimensions"]["uncharged"]["value"] == 0.0
        by_name[b.name] = doc
    assert len({d["domain_id"] for d in by_name.values()}) == 4
    bad = by_name["ca-zp-rho-medium.json"]
    assert bad["admissibility"]["status"] == "inadmissible"
    assert bad["provenance"]["verified"] == 7 and bad["provenance"]["statuses"] == {
        "verified": 7,
        "unverified": 1,
    }
    assert by_name["ca-zp-rho-toy.json"]["admissibility"]["status"] == "admissible"
    assert by_name["ca-ec-rho-toy.json"]["sizes"][0]["declared_ratio_to_floor"] == pytest.approx(
        1.0
    )
    assert by_name["ca-zp-bsgs-toy.json"]["constant"]["declared_ratio_to_floor"] == pytest.approx(
        1.5 / math.sqrt(math.pi / 2)
    )
    assert any("threads" in why for why in skipped)
    assert any("precomp-online" in why for why in skipped)
    again, _ = eb.build_bounds(header, rows, sweep, tmp_path, resamples=200)
    assert [b.text for b in again] == [b.text for b in bounds]


@pytest.mark.skipif(
    not os.environ.get("ECBENCH"), reason="set ECBENCH to an ecbench binary to run it"
)
def test_ecbench_frontier_build_accepts_the_records(tmp_path: Path) -> None:
    sweep = tmp_path / "sweep.jsonl"
    synthetic_sweep(sweep)
    header, rows = eb.read_sweep(sweep)
    bounds, _ = eb.build_bounds(header, rows, sweep, tmp_path, resamples=200)
    records = tmp_path / "records"
    records.mkdir()
    for b in bounds:
        (records / b.name).write_text(b.text, encoding="utf-8")
    out = tmp_path / "frontier.json"
    page = tmp_path / "FRONTIER.md"
    proc = subprocess.run(
        [
            os.environ["ECBENCH"],
            "frontier",
            "build",
            "--bounds",
            str(records),
            "--out",
            str(out),
            "--markdown",
            str(page),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    frontier = json.loads(out.read_text(encoding="utf-8"))
    assert len(frontier["built_from"]) == 16
    assert len(frontier["domains"]) == 4
    assert frontier["inadmissible"] == []
