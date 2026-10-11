"""Validate the exact deployment image against the pinned legacy binary."""
import json
import os
from pathlib import Path
import modal

LOCAL = Path(__file__).resolve().parent
if modal.is_local():
    import modal_worker as production
    validation_image = production.image
else:
    validation_image = None
app = modal.App("ecc2k130-deployment-validation")


@app.function(image=validation_image, gpu="RTX-PRO-6000", cpu=4, memory=4096,
              timeout=900, max_containers=1,
              secrets=[modal.Secret.from_name(os.environ.get("ECC_MODAL_SECRET", "ecc2k130-cloud"))])
def validate():
    import datetime
    import hashlib
    import subprocess
    import sys
    import tempfile
    import boto3
    root = Path("/opt/ecc2k130")
    sys.path.insert(0, str(root / "codegen"))
    from testwalkcompat import compare, corpus
    binary = root / "ecc2k130"
    manifest = json.loads((root / "build.json").read_text())
    result = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "manifest": manifest}
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        s3 = boto3.client("s3")
        bucket = os.environ["ECC_BUCKET"]
        config = json.loads(s3.get_object(Bucket=bucket, Key="campaign.json")["Body"].read())
        assert config["dpWeight"] == 32
        assert config["binarySha256"] == manifest["legacyBinarySha256"]
        legacy = temporary / "legacy"
        s3.download_file(bucket, config["binaryKey"], str(legacy))
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == manifest["legacyBinarySha256"]
        legacy.chmod(0o700)
        result["compatibility"] = compare(legacy, binary, workers=(640, 641, 256))
        reports = temporary / "screen.bin"
        command = [str(binary), "--packed", "--curve", "131", "--threads", "120320",
                   "--steps", "1024", "--launches", "64", "--run-id", "11000",
                   "--dp-weight", "32", "--verify", "0", "--dp-cap", "65536",
                   "--dp-file", str(reports)]
        run = subprocess.run(command, capture_output=True, text=True, timeout=180)
        output = run.stdout + run.stderr
        assert run.returncode == 0 and "MISMATCH" not in output and "stopping:" not in output, output
        records = corpus(reports)
        digest = hashlib.sha256(b"".join(records)).hexdigest()
        assert len(records) == 355 and digest == "c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90"
        assert "355 distinguished points (0 verified against the reference, 0 dropped)" in output, output
        result["screen_corpus"] = {"command": command, "output": output,
                                    "records": len(records), "sorted_sha256": digest}
    result["ok"] = True
    result["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result


@app.local_entrypoint()
def main(output: str = "research/production/2026-09-21-120k-deployment-validation.json"):
    path = LOCAL / output
    path.parent.mkdir(parents=True, exist_ok=True)
    result = validate.remote()
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"ok": result["ok"], "binary_sha256": result["binary_sha256"],
                      "receipt": str(path)}))
