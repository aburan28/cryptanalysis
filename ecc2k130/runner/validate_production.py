"""Bounded GPU validation against the binary serving the legacy campaign."""
import json
from pathlib import Path
import modal
import os

if modal.is_local():
    import modal_worker as production
    validation_image = production.image
else:
    validation_image = None

app = modal.App("ecc2k130-legacy-compatibility-check")


@app.function(image=validation_image, gpu=os.environ.get("ECC_MODAL_GPU", "RTX-PRO-6000"),
              cpu=4, memory=8192, timeout=1800,
              secrets=[modal.Secret.from_name(os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud"))])
def validate():
    import hashlib
    import os
    import subprocess
    import tempfile
    import time
    import boto3

    root = Path("/opt/ecc2k130")
    results = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": []}

    def run(command, timeout=600):
        p = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
        row = {"command": command, "returncode": p.returncode, "output": p.stdout + p.stderr}
        results["checks"].append(row)
        print(json.dumps(row), flush=True)
        if p.returncode or "MISMATCH" in row["output"]:
            raise RuntimeError("validation command failed")
        return row

    run(["make", "check-production-gpu"], 900)
    s3 = boto3.client("s3")
    config = json.loads(s3.get_object(Bucket=os.environ["ECC_BUCKET"], Key="campaign.json")["Body"].read())
    assert config["dpWeight"] == 32 and config["batch"] == 16
    assert config["binarySha256"] == "0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        legacy = tmp / "legacy"
        s3.download_file(os.environ["ECC_BUCKET"], config["binaryKey"], str(legacy))
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == config["binarySha256"]
        legacy.chmod(0o700)
        results["legacy_binary_sha256"] = config["binarySha256"]
        for weight in (0, 50):
            corpora, checkpoints = [], []
            for name, binary in (("legacy", legacy), ("candidate", root / "ecc2k130")):
                ckpt, dp = tmp / f"{name}-{weight}.ck", tmp / f"{name}-{weight}.bin"
                run([str(binary), "--packed", "--curve", "131", "--threads", "256",
                     "--steps", "32", "--launches", "2", "--run-id", "11000",
                     "--dp-weight", str(weight), "--verify", "4096" if weight else "0",
                     "--checkpoint", str(ckpt), "--dp-file", str(dp)])
                checkpoints.append(ckpt.read_bytes())
                blob = dp.read_bytes() if dp.exists() else b""
                corpora.append(sorted(blob[n:n+32] for n in range(0, len(blob), 32)))
            assert checkpoints[0] == checkpoints[1], f"checkpoint differs at DP{weight}"
            assert corpora[0] == corpora[1], f"reports differ at DP{weight}"
            results[f"dp{weight}_compatibility"] = {"checkpoint_identical": True,
                "records_identical": True, "records": len(corpora[0])}
        run([str(root / "ecc2k130"), "--packed", "--curve", "131", "--threads", "385024",
             "--steps", "1024", "--launches", "32", "--run-id", "11000",
             "--dp-weight", "32", "--verify", "0", "--dp-file", str(tmp / "dp32.bin")])
        results["dp32_records"] = (tmp / "dp32.bin").stat().st_size // 32
        assert results["dp32_records"] > 0
    results["candidate_binary_sha256"] = hashlib.sha256((root / "ecc2k130").read_bytes()).hexdigest()
    results["ok"] = True
    return results


@app.local_entrypoint()
def main():
    result = validate.remote()
    path = Path(__file__).resolve().parent / "research/production/2026-09-21-frobenius32-validation.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"ok": result["ok"], "receipt": str(path)}))
