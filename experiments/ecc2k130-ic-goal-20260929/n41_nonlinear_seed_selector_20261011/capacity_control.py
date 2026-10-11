"""Check that the frozen forest can learn an explicit seed-bit signal."""

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
    with tempfile.TemporaryDirectory(prefix="ecc2k-seed-control-", dir="/private/tmp") as temp:
        input_path = Path(temp) / "input.tsv"
        output_path = Path(temp) / "predictions.tsv"
        with source.open() as old, input_path.open("w") as new:
            new.write(next(old))
            for line in old:
                row = line.rstrip("\n").split("\t")
                assert len(row) == 10
                seed = int(row[6])
                assert 1 <= seed <= 63
                row[0] = str((int(row[0]) & ~63) | seed)
                new.write("\t".join(row) + "\n")
        process = subprocess.run([str(HERE / "forest"), str(input_path), str(output_path)],
                                 capture_output=True, text=True, timeout=120)
        assert process.returncode == 0 and process.stdout.startswith("COMPLETE")
        hits = {name: 0 for name in ("baseline", "public", "one_pair_residual",
                                     "two_pair_residual", "joint")}
        with output_path.open() as output:
            assert output.readline().rstrip("\n") == "row\tseed\t" + "\t".join(hits)
            for line in output:
                row = line.rstrip("\n").split("\t")
                assert len(row) == 7
                seed = int(row[1])
                for name, values in zip(hits, row[2:]):
                    hits[name] += seed in [int(value) for value in values.split(",")]
        result = {"status": "CAPACITY_CONTROL_PASS", "law": "replace public x low six bits with the generating seed in both training and held-out rows; all other fields unchanged",
                  "source_input_sha256": digest(source), "derived_input_sha256": digest(input_path),
                  "binary_sha256": digest(HERE / "forest"),
                  "predictions_sha256": digest(output_path), "holdout_count": 20000,
                  "seven_seed_hits": hits}
        assert hits["baseline"] == 4465 and hits["public"] == 20000
        assert hits["joint"] > 18000
        (HERE / "capacity_control.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "seven_seed_hits": hits}, sort_keys=True))


if __name__ == "__main__":
    main()
