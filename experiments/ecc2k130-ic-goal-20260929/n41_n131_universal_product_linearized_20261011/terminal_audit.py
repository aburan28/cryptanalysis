"""Check the complete frozen source, panel, run, and replay chain."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def main():
    prepare = load(HERE / "prepare_protocol.json")
    panel = load(HERE / "panel.json")
    protocol = load(HERE / "protocol.json")
    receipt = load(HERE / "run_receipt.json")
    replay = load(HERE / "verification.json")
    n41_protocol = load(HERE / "n41_protocol.json")
    n41 = load(HERE / "n41_result.json")
    bound = load(HERE / "bound.json")
    assert prepare["prepare_sha256"] == digest(HERE / "prepare.py")
    assert prepare["support_sha256"] == digest(run.SUPPORT)
    assert panel["prepare_protocol_sha256"] == digest(HERE / "prepare_protocol.json")
    assert panel["source_support_sha256"] == digest(run.SUPPORT)
    assert protocol["source_sha256"] == {name: digest(path) for name, path in run.source_files().items()}
    assert receipt["status"] == "COMPLETE"
    assert receipt["protocol_sha256"] == replay["protocol_sha256"] == digest(HERE / "protocol.json")
    assert receipt["results_sha256"] == replay["results_sha256"] == digest(HERE / "results.jsonl")
    assert replay["run_receipt_sha256"] == digest(HERE / "run_receipt.json")
    assert replay["verifier_source_sha256"] == digest(HERE / "verify.py")
    assert replay["status"] == "VERIFIED" and replay["positive_cases"] == 130
    assert replay["zero_hit_controls"] == 66 and replay["accepted_hits"] == 130
    assert n41_protocol["source_sha256"] == n41["source_sha256"] == digest(HERE / "n41_control.py")
    assert n41["protocol_sha256"] == digest(HERE / "n41_protocol.json")
    assert n41["status"] == "EXHAUSTIVE_PAIR_SET_MATCH"
    assert n41["distinct_pair_outputs"] == 991 and n41["trace_zero_controls"] == 128
    assert bound["status"] == "EXACT_COUNT_BOUND"
    denominator = bound["denominator"]
    assert bound["rank_loss_union_numerator"] * (1 << 76) < denominator
    assert bound["product_span_pass_union_numerator"] * (1 << 76) < denominator
    audit = {"status": "VERIFIED", "prepare_protocol_sha256": digest(HERE / "prepare_protocol.json"),
             "panel_sha256": digest(HERE / "panel.json"), "protocol_sha256": digest(HERE / "protocol.json"),
             "run_receipt_sha256": digest(HERE / "run_receipt.json"),
             "verification_sha256": digest(HERE / "verification.json"),
             "n41_result_sha256": digest(HERE / "n41_result.json"),
             "bound_sha256": digest(HERE / "bound.json"),
             "source_sha256": {"terminal_audit": digest(HERE / "terminal_audit.py"),
                               "bound": digest(HERE / "bound.py")}}
    (HERE / "terminal_audit.json").write_text(json.dumps(audit, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": audit["status"], "n131_cases": 196,
                      "n41_outputs": 991}))


if __name__ == "__main__":
    main()
