"""Exact bounded XOR preprocessing through the existing CPU/CUDA/RDMA ABI.

Only F2 equations are accepted. Mod-q relation matrices must never use this path.
Auto measures CPU against offload, including packing/copies and reconstruction.
"""
import ctypes as ct
import os
import time
from collections import Counter


def cpuReduce(rows, cols):
    rows = list(rows)
    rank = 0
    for col in range(cols):
        pivot = next((i for i in range(rank, len(rows)) if (rows[i] >> col) & 1), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for i in range(len(rows)):
            if i != rank and (rows[i] >> col) & 1:
                rows[i] ^= rows[rank]
        rank += 1
        if rank == len(rows):
            break
    return rows, rank


class Dispatch:
    def __init__(self, mode='cpu', library=None, modulus=2):
        if modulus != 2:
            raise ValueError('XOR dispatch requires F2; mod-q matrices are unsupported')
        if mode not in ('cpu', 'auto-cuda', 'auto-rdma-cpu', 'auto-rdma-cuda'):
            raise ValueError('unsupported F2 backend')
        self.mode, self.library = mode, library
        self.decisions = {}
        self.stats = Counter()

    def offload(self, rows, cols):
        if not self.library:
            raise RuntimeError('native library unavailable')
        lib = ct.CDLL(self.library)
        words = (cols+63)//64
        array = (ct.c_uint64*(len(rows)*words))(*[(r>>(64*w)) & ((1<<64)-1) for r in rows for w in range(words)])
        rank, ops = ct.c_size_t(), ct.c_uint64()
        args = [ct.POINTER(ct.c_uint64), ct.c_size_t, ct.c_size_t, ct.POINTER(ct.c_size_t), ct.POINTER(ct.c_uint64)]
        if self.mode == 'auto-cuda':
            fn = lib.ic_f2_cuda
            fn.argtypes, fn.restype = args, ct.c_int
            status = fn(array, len(rows), cols, ct.byref(rank), ct.byref(ops))
        else:
            fn = lib.ic_f2_rdma
            fn.argtypes, fn.restype = args + [ct.c_char_p, ct.c_uint, ct.c_uint, ct.c_uint], ct.c_int
            host = os.environ.get('IC_RDMA_IPV4', '').encode()
            port = int(os.environ.get('IC_RDMA_PORT', '0'))
            timeout = int(os.environ.get('IC_RDMA_TIMEOUT_MS', '2000'))
            if not 1 <= port <= 65535 or not 1 <= timeout <= 60000:
                raise ValueError('invalid RDMA endpoint configuration')
            status = fn(array, len(rows), cols, ct.byref(rank), ct.byref(ops), host, port, timeout,
                        int(self.mode == 'auto-rdma-cuda'))
        if status or rank.value > min(len(rows), cols):
            raise RuntimeError('native backend failed')
        output = [sum(int(array[i*words+w])<<(64*w) for w in range(words)) for i in range(len(rows))]
        self.stats['native_word_xors'] += ops.value
        return output, rank.value

    def reduce(self, rows, cols):
        if not 0 <= cols <= 32768 or len(rows) > 4096 or any(r < 0 or r >> cols for r in rows):
            raise ValueError('invalid packed F2 shape')
        if not rows or not cols or self.mode == 'cpu':
            self.stats['cpu_jobs'] += 1
            return cpuReduce(rows, cols)
        shape = (len(rows), cols)
        if shape not in self.decisions:
            start = time.perf_counter_ns()
            reference = cpuReduce(rows, cols)
            cpuNs = time.perf_counter_ns()-start
            self.stats['calibration_cpu_ns'] += cpuNs
            start = time.perf_counter_ns()
            try:
                candidate = self.offload(rows, cols)
                gpuNs = time.perf_counter_ns()-start
                if candidate != reference:
                    raise ValueError('backend disagrees with exact CPU RREF')
                self.decisions[shape] = gpuNs < cpuNs
                self.stats['calibration_offload_ns'] += gpuNs
                self.stats['calibrated_shapes'] += 1
                self.stats['offload_preferred_shapes'] += self.decisions[shape]
            except Exception:
                self.stats['failures'] += 1
                self.stats['calibration_offload_ns'] += time.perf_counter_ns()-start
                self.decisions[shape] = False
            # Calibration has already paid for both; return the verified CPU result.
            self.stats['cpu_jobs'] += 1
            return reference
        if self.decisions[shape]:
            try:
                result = self.offload(rows, cols)
                self.stats['offload_jobs'] += 1
                return result
            except Exception:
                self.stats['failures'] += 1
                self.decisions[shape] = False
        self.stats['cpu_jobs'] += 1
        return cpuReduce(rows, cols)

    def preprocess(self, formula, blockRows=128, maxBlocks=8):
        """Replace only bounded XOR blocks by row-equivalent equations, RHS included."""
        if not 1 <= blockRows <= 4096 or not 1 <= maxBlocks <= 32:
            raise ValueError('invalid preprocessing budget')
        rebuilt = []
        end = min(len(formula.xors), blockRows*maxBlocks)
        start = time.perf_counter_ns()
        for offset in range(0, end, blockRows):
            block = formula.xors[offset:min(end, offset+blockRows)]
            variables = sorted({v for literals, _ in block for v in literals})
            if len(variables)+1 > 32768:
                rebuilt.extend(block)
                self.stats['oversized_blocks'] += 1
                continue
            mapping = {v:i for i,v in enumerate(variables)}
            packed = []
            for literals, rhs in block:
                row = int(rhs) << len(variables)
                for v in literals:
                    row ^= 1 << mapping[v]
                packed.append(row)
            reduced, _ = self.reduce(packed, len(variables)+1)
            for row in reduced:
                if row:
                    rebuilt.append(([v for i,v in enumerate(variables) if row >> i & 1], bool(row >> len(variables) & 1)))
        formula.xors = rebuilt + formula.xors[end:]
        self.stats['preprocess_ns'] += time.perf_counter_ns()-start
