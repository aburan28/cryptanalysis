"""Check held-out labels cannot influence any seven-seed proposal."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = run.RESIDUAL / "residuals.tsv"
    old_predictions = HERE / "predictions.tsv"
    with tempfile.TemporaryDirectory(prefix="ecc2k-label-control-", dir="/private/tmp") as temp:
        input_path = Path(temp) / "input.tsv"
        output_path = Path(temp) / "predictions.tsv"
        with source.open() as old, input_path.open("w") as new:
            new.write(next(old))
            for index, line in enumerate(old):
                if index < 80000:
                    new.write(line)
                else:
                    row = line.rstrip("\n").split("\t")
                    assert len(row) == 10
                    row[6] = str(int(row[6]) % 63 + 1)
                    new.write("\t".join(row) + "\n")
        process = subprocess.run([str(HERE / "forest"), str(input_path), str(output_path)],
                                 capture_output=True, text=True, timeout=120)
        assert process.returncode == 0 and process.stdout.startswith("COMPLETE")
        comparisons = 0
        changed_labels = 0
        with old_predictions.open() as old, output_path.open() as new:
            assert old.readline() == new.readline()
            for left, right in zip(old, new):
                l = left.rstrip("\n").split("\t")
                r = right.rstrip("\n").split("\t")
                assert len(l) == len(r) == 7 and l[0] == r[0]
                assert l[2:] == r[2:]
                changed_labels += l[1] != r[1]
                comparisons += 1
            assert old.readline() == new.readline() == ""
        assert comparisons == changed_labels == 20000
        result = {"status": "NO_HOLDOUT_LABEL_LEAKAGE", "law": "cycle only held-out seed_a labels by one modulo 63; preserve every training row and every coordinate",
                  "source_input_sha256": digest(source), "derived_input_sha256": digest(input_path),
                  "binary_sha256": digest(HERE / "forest"), "original_predictions_sha256": digest(old_predictions),
                  "derived_predictions_sha256": digest(output_path),
                  "holdout_rows_checked": comparisons, "changed_labels": changed_labels,
                  "unchanged_proposals": comparisons}
        (HERE / "leakage_control.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "rows": comparisons}))


if __name__ == "__main__":
    main()
