"""Validate and measure the packed multiplier on one Modal GPU allocation.

ECC_GPU=RTX-PRO-6000 ECC_PACKED_SINGLE_PRODUCT=1 modal run packed_audit.py \
    --output packed-audit.json
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

import modal
# Modal re-imports this entry point as /root/packed_audit.py; dependencies live
# in the source tree copied into client.image.
if not modal.is_local():
    sys.path.insert(0, "/root/ecc2k130")
import modal_app as client

app = modal.App("ecc2k130-packed-audit")


def checkScalarCounts(sample, workers, dpWeight, batch=32):
    """Require the requested packed geometry and its exact completed work."""
    client.checkPackedReduction(sample)
    raw = sample.get("raw", "")
    completed = client.benchResult(sample.get("command"), sample.get("returncode"), raw)
    backend = re.findall(
        r"^backend cuda-packed131: (\d+) threads x (\d+) slots x 1 lanes = (\d+) walks, "
        r"dp weight (\d+), (\d+) steps per launch$", raw, re.MULTILINE)
    progress = re.findall(r"M it/s\s+(\d+) iterations\s+\d+ dp\s+\d+ stored\s+(\d+) dropped", raw)
    actual = walks = expected = None
    shapeOk = len(backend) == 1
    if shapeOk:
        actual, actualBatch, walks, weight, steps = map(int, backend[0])
        expected = walks * 1024 * 32
        shapeOk = (actual > 0 and batch > 0 and actualBatch == batch and walks == actual * batch
                   and steps == 1024 and weight == dpWeight
                   and (workers == 0 or actual == workers))
    counts = [int(row[0]) for row in progress]
    countsOk = (shapeOk and bool(counts) and counts[-1] == expected
                and counts == sorted(counts) and all(0 < count <= expected for count in counts)
                and all(int(row[1]) == 0 for row in progress))
    sample.update(requestedWorkers=workers, actualWorkers=actual, requestedBatch=batch,
                  actualBatch=int(backend[0][1]) if len(backend) == 1 else None, scalarWalks=walks,
                  expectedIterations=expected, reportedIterations=counts[-1] if counts else None)
    sample["valid"] = bool(sample.get("valid") and completed["valid"] and countsOk)
    sample["rate"] = completed["rate"] if sample["valid"] else 0.0
    if not sample["valid"]:
        sample.setdefault("error", "run failed, requested workers were not honored, or completed scalar counts disagree")
    return sample["valid"]


@app.function(image=client.image, gpu=client.DEFAULT_GPU, timeout=1800,
              volumes={"/data": client.volume})
def runAudit(minBlocks=4, repeats=3, blockThreads=128, workers=0, batch=32):
    result = dict(valid=False, minBlocks=minBlocks, repeats=repeats,
                  batch=batch, blockThreads=blockThreads, requestedWorkers=workers, steps=1024, launches=32,
                  packedDirectReduction=client.PACKED_DIRECT_REDUCE == "1",
                  expectedPackedGeneratedProduct=client.PACKED_GENERATED_PRODUCT == "1",
                  packedGeneratedProduct=None,
                  expectedPackedClmad=client.PACKED_CLMAD == "1", packedClmad=None,
                  expectedPackedClmadSquare=client.PACKED_CLMAD_SQUARE == "1", packedClmadSquare=None,
                  expectedPackedKarat3=client.PACKED_KARAT3 == "1", packedKarat3=None,
                  expectedPackedCompactState=client.PACKED_COMPACT_STATE == "1", packedCompactState=None,
                  expectedPackedSharedSigma=client.PACKED_SHARED_SIGMA == "1", packedSharedSigma=None,
                  expectedPackedWeightedPrefix=int(client.PACKED_WEIGHTED_PREFIX), packedWeightedPrefix=None,
                  expectedPackedStateTile=int(client.PACKED_STATE_TILE), packedStateTile=None)
    try:
        if minBlocks <= 0 or repeats <= 0 or blockThreads <= 0 or batch <= 0:
            raise ValueError("min-blocks, repeats, block-threads and batch must be positive")
        if workers < 0:
            raise ValueError("workers must be nonnegative (0 selects automatic workers)")
        if client.PACKED_STATE_TILE == "256" and batch > 64:
            raise ValueError("tiled storage validation supports batch sizes 1 through 64")
        ok, build = client.buildFor(batch, blockThreads, 0, minBlocks=minBlocks)
        result["build"] = build
        if not ok:
            raise RuntimeError("CUDA build failed")
        result["identity"] = client.benchmarkIdentity(packed=True)

        def run(command, timeout):
            p = subprocess.run(command, cwd=client.REMOTE, capture_output=True,
                               text=True, timeout=timeout)
            row = dict(command=command, returncode=p.returncode,
                       output=p.stdout + p.stderr)
            print(json.dumps(row), flush=True)
            return row

        arch = client.computeCapability()
        result["deviceArithmetic"] = run(
            ["make", "test-packed-cuda", f"ARCH=-gencode arch=compute_{arch},code=sm_{arch}",
             f"BATCH={batch}", f"THREADS={blockThreads}", f"MINBLOCKS={minBlocks}",
             f"PACKED_SINGLE_PRODUCT={client.PACKED_SINGLE_PRODUCT}",
             f"PACKED_CACHE_DENOM={client.PACKED_CACHE_DENOM}", f"PACKED_BY_VALUE={client.PACKED_BY_VALUE}",
             f"PACKED_PERM_SIGMA={client.PACKED_PERM_SIGMA}", f"PACKED_POLY_CHAIN={client.PACKED_POLY_CHAIN}",
             f"PACKED_UNROLL_INV={client.PACKED_UNROLL_INV}", f"PACKED_PAIR_PRODUCTS={client.PACKED_PAIR_PRODUCTS}",
             f"PACKED_POLY_STATE={client.PACKED_POLY_STATE}",
             f"PACKED_DIRECT_REDUCE={client.PACKED_DIRECT_REDUCE}",
             f"PACKED_GENERATED_PRODUCT={client.PACKED_GENERATED_PRODUCT}",
             f"PACKED_CLMAD={client.PACKED_CLMAD}",
             f"PACKED_CLMAD_SQUARE={client.PACKED_CLMAD_SQUARE}",
             f"PACKED_KARAT3={client.PACKED_KARAT3}",
             f"PACKED_COMPACT_STATE={client.PACKED_COMPACT_STATE}",
             f"PACKED_SHARED_SIGMA={client.PACKED_SHARED_SIGMA}",
             f"PACKED_WEIGHTED_PREFIX={client.PACKED_WEIGHTED_PREFIX}",
             f"PACKED_STATE_TILE={client.PACKED_STATE_TILE}"], 120)
        if result["deviceArithmetic"]["returncode"]:
            raise RuntimeError("packed GPU arithmetic failed")
        arithmeticModes = re.findall(r"^packed arithmetic direct reduction: (.*)$",
                                     result["deviceArithmetic"]["output"], re.MULTILINE)
        if arithmeticModes != [client.PACKED_DIRECT_REDUCE]:
            raise RuntimeError("packed GPU arithmetic reducer identity disagrees with the requested build")
        generatedModes = re.findall(r"^packed arithmetic generated product: (.*)$",
                                    result["deviceArithmetic"]["output"], re.MULTILINE)
        actualGenerated = generatedModes[0] if len(generatedModes) == 1 else None
        result["packedGeneratedProduct"] = (actualGenerated == "1") if actualGenerated in ("0", "1") else None
        result["deviceArithmetic"].update(
            expectedPackedGeneratedProduct=client.PACKED_GENERATED_PRODUCT == "1",
            packedGeneratedProduct=result["packedGeneratedProduct"])
        if generatedModes != [client.PACKED_GENERATED_PRODUCT]:
            raise RuntimeError("packed GPU arithmetic generated product identity disagrees with the requested build")
        clmadModes = re.findall(r"^packed arithmetic native carryless multiply: (.*)$",
                                result["deviceArithmetic"]["output"], re.MULTILINE)
        actualClmad = clmadModes[0] if len(clmadModes) == 1 else None
        result["packedClmad"] = (actualClmad == "1") if actualClmad in ("0", "1") else None
        result["deviceArithmetic"].update(expectedPackedClmad=client.PACKED_CLMAD == "1",
                                          packedClmad=result["packedClmad"])
        if clmadModes != [client.PACKED_CLMAD]:
            raise RuntimeError("packed GPU arithmetic CLMAD identity disagrees with the requested build")
        squareModes = re.findall(r"^packed arithmetic native carryless square: (.*)$",
                                result["deviceArithmetic"]["output"], re.MULTILINE)
        actualSquare = squareModes[0] if len(squareModes) == 1 else None
        result["packedClmadSquare"] = (actualSquare == "1") if actualSquare in ("0", "1") else None
        result["deviceArithmetic"].update(expectedPackedClmadSquare=client.PACKED_CLMAD_SQUARE == "1",
                                          packedClmadSquare=result["packedClmadSquare"])
        if squareModes != [client.PACKED_CLMAD_SQUARE]:
            raise RuntimeError("packed GPU arithmetic CLMAD square identity disagrees with the requested build")
        karatModes = re.findall(r"^packed arithmetic three-limb Karatsuba: (.*)$",
                                result["deviceArithmetic"]["output"], re.MULTILINE)
        actualKarat = karatModes[0] if len(karatModes) == 1 else None
        result["packedKarat3"] = (actualKarat == "1") if actualKarat in ("0", "1") else None
        result["deviceArithmetic"].update(expectedPackedKarat3=client.PACKED_KARAT3 == "1",
                                          packedKarat3=result["packedKarat3"])
        if karatModes != [client.PACKED_KARAT3]:
            raise RuntimeError("packed GPU arithmetic Karat3 identity disagrees with the requested build")
        weightedModes = re.findall(r"^packed arithmetic weighted prefix: (.*)$",
                                   result["deviceArithmetic"]["output"], re.MULTILINE)
        actualWeighted = weightedModes[0] if len(weightedModes) == 1 else None
        result["packedWeightedPrefix"] = int(actualWeighted) if actualWeighted in ("0", "1", "2") else None
        result["deviceArithmetic"].update(
            expectedPackedWeightedPrefix=int(client.PACKED_WEIGHTED_PREFIX),
            packedWeightedPrefix=result["packedWeightedPrefix"])
        if weightedModes != [client.PACKED_WEIGHTED_PREFIX]:
            raise RuntimeError("packed GPU arithmetic weighted prefix identity disagrees with the requested build")
        pairedSigmaPass = "PASS: 6240 GPU paired Frobenius vectors, both inputs against independent routing"
        if result["deviceArithmetic"]["output"].splitlines().count(pairedSigmaPass) != 1:
            raise RuntimeError("packed GPU paired Frobenius validation did not complete exactly once")
        if client.PACKED_STATE_TILE == "256":
            # This exercises actual load/store accessors for either tiled layout.
            # It runs before client integration and every timed sample.
            storageCommand = list(result["deviceArithmetic"]["command"])
            storageCommand[1] = "test-packed-storage-cuda"
            storage = result["deviceStorage"] = run(storageCommand, 300)
            if storage["returncode"]:
                raise RuntimeError("packed GPU storage validation failed")
            storageModes = re.findall(r"^packed storage compact state: (.*)$", storage["output"], re.MULTILINE)
            storageBatches = re.findall(r"^packed storage batch: (.*)$", storage["output"], re.MULTILINE)
            actualCompact = storageModes[0] if len(storageModes) == 1 else None
            storage.update(expectedPackedCompactState=client.PACKED_COMPACT_STATE == "1",
                           packedCompactState=(actualCompact == "1") if actualCompact in ("0", "1") else None)
            storagePass = (f"PASS: 128 GPU storage cases, {18584 * batch} records, "
                           "independent physical images and logical reads with canaries")
            if (storageModes != [client.PACKED_COMPACT_STATE] or storageBatches != [str(batch)]
                    or [line for line in storage["output"].splitlines() if line.startswith("PASS:")] != [storagePass]):
                raise RuntimeError("packed GPU storage identity or complete validation counts disagree")
            storage.update(cases=128, records=18584 * batch)
        # The probe's C++ guards require WP2 and the walk permutation network.
        # Exercise both shared/global controls when applicable, including
        # untiled WP2 builds, without changing the WP0/WP1 audit paths.
        result["sharedSigmaProbeApplicable"] = (client.PACKED_WEIGHTED_PREFIX == "2"
                                               and bool(int(client.PACKED_PERM_SIGMA) & 1))
        if result["sharedSigmaProbeApplicable"]:
            probeCommand = list(result["deviceArithmetic"]["command"])
            probeCommand[1] = "test-shared-sigma-cuda"
            probe = result["deviceSharedSigma"] = run(probeCommand, 300)
            if probe["returncode"]:
                raise RuntimeError("packed GPU shared sigma validation failed")
            sharedModes = re.findall(r"^packed shared sigma probe: (.*)$", probe["output"], re.MULTILINE)
            actualShared = sharedModes[0] if len(sharedModes) == 1 else None
            result["packedSharedSigma"] = ((actualShared == "1")
                                           if actualShared in ("0", "1") else None)
            probe.update(expectedPackedSharedSigma=client.PACKED_SHARED_SIGMA == "1",
                         packedSharedSigma=result["packedSharedSigma"])
            probePasses = [
                "PASS: 21 GPU sigma scenarios, 21036 input pairs, global and selected helpers against independent routing",
                "PASS: 114 complete block mask snapshots, 51072 words, output guards and inactive blocks",
            ]
            if (sharedModes != [client.PACKED_SHARED_SIGMA]
                    or [line for line in probe["output"].splitlines() if line.startswith("PASS:")] != probePasses):
                raise RuntimeError("packed GPU shared sigma identity or complete validation counts disagree")
            probe.update(scenarios=21, inputPairs=21036, blockSnapshots=114, maskWords=51072)
        result["integration"] = run(
            ["python3", "codegen/testpackedclient.py", "./ecc2k130"], 600)
        if result["integration"]["returncode"]:
            raise RuntimeError("packed GPU integration failed")

        result["benchmark"] = client.measureBench(1024, 32, workers, False, repeats, packed=True)
        benchmarkSamples = result["benchmark"].get("samples", [])
        for sample in benchmarkSamples:
            checkScalarCounts(sample, workers, 0, batch)
        result["benchmark"] = client.summarizeSamples(benchmarkSamples)
        if len(benchmarkSamples) != repeats:
            result["benchmark"].update(valid=False, rate=0.0, error="benchmark did not complete every requested repetition")
        if not result["benchmark"]["valid"]:
            raise RuntimeError("throughput benchmark failed or completed scalar counts disagree")
        result["packedStateTile"] = benchmarkSamples[0]["packedStateTile"]
        result["packedCompactState"] = benchmarkSamples[0]["packedCompactState"]
        result["packedSharedSigma"] = benchmarkSamples[0]["packedSharedSigma"]

        # Time real collection with CPU trail replay disabled only after the
        # integration test has independently replayed reports. Each sample
        # starts with its own corpus, so no earlier reports enter its count.
        samples = result["collection"] = []
        for repeat in range(repeats):
            with tempfile.TemporaryDirectory() as directory:
                corpus = Path(directory) / "points.bin"
                command = ["./ecc2k130", "--packed", "--curve", "131",
                           "--dp-weight", "34", "--steps", "1024", "--launches", "32",
                           "--verify", "0", "--dp-file", str(corpus)]
                if workers:
                    command += ["--threads", str(workers)]
                row = run(command, 180)
                sample = client.benchResult(row["command"], row["returncode"], row["output"])
                checkScalarCounts(sample, workers, 34, batch)
                records = corpus.stat().st_size if corpus.exists() else 0
                final = re.findall(r"finished:.*?, (\d+) distinguished points "
                                   r"\(0 verified against the reference, (\d+) dropped\)",
                                   row["output"])
                sample["corpusBytes"] = records
                sample["corpusRecords"] = records // 32
                sample["valid"] = (sample["valid"] and len(final) == 1
                                   and int(final[0][0]) > 0 and int(final[0][1]) == 0
                                   and records == int(final[0][0]) * 32)
                if not sample["valid"]:
                    sample["rate"] = 0.0
                samples.append(sample)
                if not sample["valid"]:
                    raise RuntimeError("collection failed or report counts disagree")
        result["collectionSummary"] = client.summarizeSamples(samples)
        result["valid"] = True
    except Exception as exc:
        result["error"] = str(exc)
    artifact = Path("/data/packed-audit") / (str(time.time_ns()) + ".json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    result["remoteArtifact"] = str(artifact)
    artifact.write_text(json.dumps(result, indent=2) + "\n")
    client.volume.commit()
    return result


@app.local_entrypoint()
def main(output: str = "packed-audit.json", min_blocks: int = 4, repeats: int = 3,
         block_threads: int = 128, workers: int = 0, batch: int = 32):
    result = runAudit.remote(minBlocks=min_blocks, repeats=repeats, blockThreads=block_threads, workers=workers,
                             batch=batch)
    Path(output).write_text(json.dumps(result, indent=2) + "\n")
    print(f"Audit saved to {output}")
    if not result["valid"]:
        raise RuntimeError(result.get("error", "packed audit failed"))
    print(f"Benchmark median: {result['benchmark']['rate']:.3f} M iterations/s")
    print(f"Collection median: {result['collectionSummary']['rate']:.3f} M iterations/s")

