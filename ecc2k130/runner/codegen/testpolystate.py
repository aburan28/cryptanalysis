"""Cross-binary GPU checks for optional polynomial coordinate storage.

Run: python3 codegen/testpolystate.py NORMAL_BINARY POLYNOMIAL_BINARY
Both binaries must use the same batch size. Tests use fixed worker counts,
normal-basis checkpoint v2 payloads, and bounded deterministic walks. This is
a correctness gate; the small launches do not measure throughput.
"""
import argparse
from collections import Counter
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from benchreport import reportsVerified


HEADER = struct.Struct('<8s6IQ')
BACKEND = re.compile(r'backend cuda-packed131: (\d+) threads x (\d+) slots x 1 lanes = (\d+) walks')
FINISHED = re.compile(r'finished:.*?, (\d+) distinguished points \((\d+) verified against the reference, (\d+) dropped\)')


def require(condition, message):
    # Retain correctness gates even when Python is invoked with -O.
    if not condition:
        raise AssertionError(message)


def run(binary, mode, args, expected=0, timeout=240):
    command = [str(binary), '--packed', '--curve', '131', '--run-id', '1'] + args
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    output = result.stdout + result.stderr
    require(result.returncode == expected,
            f'Exit {result.returncode}, expected {expected}: {command}\n{output}')
    require('MISMATCH' not in output and 'stopping:' not in output, output)
    require(re.findall(r'^packed polynomial state: ([01])$', output, re.MULTILINE) == [str(mode)],
            f'Missing or incorrect polynomial storage identity for {binary}\n{output}')
    if expected == 0:
        require(len(FINISHED.findall(output)) == 1, f'No unique completion summary\n{output}')
        require('warning: could not write checkpoint' not in output, output)
    return output


def checkpoint(path, threads, iteration):
    data = path.read_bytes()
    require(len(data) >= HEADER.size, f'Incomplete checkpoint header: {path}')
    magic, version, degree, workers, batch, lanes, run_id, base = HEADER.unpack_from(data)
    require((magic, version, degree, workers, lanes, run_id, base) ==
            (b'ECC2K130', 2, 131, threads, 1, 1, iteration),
            f'Unexpected external checkpoint header: {HEADER.unpack_from(data)}')
    require(batch > 0, 'Empty batch')
    count = workers * batch
    require(len(data) == HEADER.size + count * 60,
            f'Incorrect packed checkpoint payload length: {len(data)}')
    # Every external coordinate occupies five 32-bit words, with only three
    # valid bits in the final word. This also catches leaked denominator tags.
    for coordinate in range(2):
        offset = HEADER.size + coordinate * count * 20
        for slot in range(batch):
            for tid in range(workers):
                index = (slot * 5 + 4) * workers + tid
                top = struct.unpack_from('<I', data, offset + 4 * index)[0]
                require(top & ~7 == 0, f'Non-field bits in checkpoint coordinate: {path}')
    return data, batch


def counters(output, threads, batch, steps, launches):
    backend = BACKEND.findall(output)
    require(backend == [(str(threads), str(batch), str(threads * batch))],
            f'Incorrect scalar walk identity\n{output}')
    iterations = re.findall(r'M it/s\s+(\d+) iterations', output)
    require(bool(iterations) and int(iterations[-1]) == threads * batch * steps * launches,
            f'Incorrect newly executed scalar iteration count\n{output}')


def records(path):
    data = path.read_bytes()
    require(len(data) % 32 == 0, f'Partial corpus record: {path}')
    # GPU atomic insertion order is unspecified; compare full record multisets
    # so order changes are accepted while missing and duplicate records fail.
    return Counter(data[offset:offset + 32] for offset in range(0, len(data), 32))


def check_resume(root, binaries, timeout):
    common = ['--bench', '--threads', '8', '--steps', '16', '--verify', '0']
    half, whole = {}, {}
    batch = None
    for mode, binary in enumerate(binaries):
        for launches, label, destination in ((2, 'half', half), (4, 'whole', whole)):
            path = root / f'{mode}-{label}.ck'
            output = run(binary, mode, common + ['--launches', str(launches), '--checkpoint', str(path)], timeout=timeout)
            data, current_batch = checkpoint(path, 8, launches * 16)
            if batch is None:
                batch = current_batch
            require(current_batch == batch, 'Binaries use different batch sizes')
            counters(output, 8, batch, 16, launches)
            destination[mode] = data
    require(half[0] == half[1], 'Normal and polynomial half-run checkpoints differ')
    require(whole[0] == whole[1], 'Normal and polynomial whole-run checkpoints differ')
    for source, target in ((0, 1), (1, 0)):
        path = root / f'resume-{source}-to-{target}.ck'
        path.write_bytes(half[source])
        output = run(binaries[target], target, common + ['--launches', '2', '--checkpoint', str(path)], timeout=timeout)
        require(re.search(r'resumed from .* at iteration 32\n', output), output)
        data, current_batch = checkpoint(path, 8, 64)
        require(current_batch == batch and data == whole[target],
                f'Cross-mode {source}->{target} resume differs from uninterrupted execution')
        counters(output, 8, batch, 16, 2)
    print('PASS: byte-identical external v2 normal-basis checkpoints, both cross-mode resume directions and scalar counts', flush=True)
    return whole[0], batch


def check_reports(root, binaries, batch, timeout):
    common = ['--threads', '128', '--steps', '32', '--dp-weight', '50', '--verify', '16384']
    reference_state, reference_records = None, None
    for source, target in ((0, 1), (1, 0)):
        path = root / f'reports-{source}-to-{target}.ck'
        corpus = root / f'reports-{source}-to-{target}.bin'
        total_reports = 0
        for mode in (source, target):
            output = run(binaries[mode], mode,
                         common + ['--launches', '2', '--checkpoint', str(path), '--dp-file', str(corpus)],
                         timeout=timeout)
            require(reportsVerified(0, output), f'Cross-mode report replay did not verify reports without drops\n{output}')
            counters(output, 128, batch, 32, 2)
            found, verified, dropped = map(int, FINISHED.findall(output)[0])
            require(found == verified and dropped == 0, f'Not every generated report was replayed\n{output}')
            total_reports += found
        state, current_batch = checkpoint(path, 128, 128)
        collected = records(corpus)
        require(current_batch == batch and sum(collected.values()) == total_reports,
                'Corpus record count disagrees with reported count')
        require(any(struct.unpack_from('<Q', record)[0] & 0xffff for record in collected),
                'No restarted seed was reported')
        if reference_state is None:
            reference_state, reference_records = state, collected
        else:
            require(state == reference_state, 'Cross-mode report/restart final states differ')
            require(collected == reference_records, 'Cross-mode report record multisets differ')
    print('PASS: both cross-mode report replay directions, restarted seeds, complete corpus counts and matching report multisets', flush=True)


def check_guard(root, binaries, batch, timeout):
    reference = None
    for mode, binary in enumerate(binaries):
        path = root / f'guard-{mode}.ck'
        output = run(binary, mode,
                     ['--threads', '1', '--steps', '4096', '--launches', '2', '--dp-weight', '0',
                      '--max-iters', '1', '--verify', '16', '--checkpoint', str(path)], timeout=timeout)
        data, current_batch = checkpoint(path, 1, 8192)
        require(current_batch == batch, 'Guard test batch changed')
        counters(output, 1, batch, 4096, 2)
        require(FINISHED.findall(output) == [('0', '0', '0')], 'Guard emitted false distinguished points')
        offset = HEADER.size + batch * 44
        seeds = struct.unpack_from('<' + 'Q' * batch, data, offset)
        starts = struct.unpack_from('<' + 'Q' * batch, data, offset + 8 * batch)
        require(all(seed & 0xffff == 1 for seed in seeds), 'Guard did not restart each overdue seed exactly once')
        require(all(start == 8192 for start in starts), 'Guard restart iteration is wrong')
        if reference is None:
            reference = data
        else:
            require(data == reference, 'Guard/reseed external state differs between representations')
    print('PASS: identical overdue-walk guard/reseed state with no false reports', flush=True)


def check_rejections(root, binaries, valid, timeout):
    invalid_version = bytearray(valid)
    struct.pack_into('<I', invalid_version, 8, 0)
    variants = {'version': bytes(invalid_version), 'truncated': valid[:-1], 'trailing': valid + b'\0'}
    for mode, binary in enumerate(binaries):
        for label, data in variants.items():
            path = root / f'invalid-{mode}-{label}.ck'
            path.write_bytes(data)
            output = run(binary, mode,
                         ['--bench', '--threads', '8', '--steps', '16', '--launches', '1',
                          '--verify', '0', '--checkpoint', str(path)], expected=6, timeout=timeout)
            require('incompatible or incomplete' in output, output)
            require(path.read_bytes() == data, f'Rejected checkpoint was modified: {path}')
            require(not Path(str(path) + '.tmp').exists(), f'Rejected checkpoint left a staging file: {path}')
            require(not FINISHED.search(output), 'Invalid checkpoint run reached completion')
    print('PASS: incompatible, truncated and trailing-payload checkpoints rejected and preserved in both modes', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('normal_binary', type=Path)
    parser.add_argument('polynomial_binary', type=Path)
    parser.add_argument('--timeout', type=int, default=240, help='Seconds allowed per binary invocation')
    options = parser.parse_args()
    require(options.timeout > 0, '--timeout must be positive')
    binaries = [options.normal_binary.resolve(), options.polynomial_binary.resolve()]
    require(all(binary.is_file() for binary in binaries), 'Both compiled CUDA binaries must exist')
    with tempfile.TemporaryDirectory(prefix='ecc-polystate-') as temporary:
        root = Path(temporary)
        valid, batch = check_resume(root, binaries, options.timeout)
        check_reports(root, binaries, batch, options.timeout)
        check_guard(root, binaries, batch, options.timeout)
        check_rejections(root, binaries, valid, options.timeout)


if __name__ == '__main__':
    main()
