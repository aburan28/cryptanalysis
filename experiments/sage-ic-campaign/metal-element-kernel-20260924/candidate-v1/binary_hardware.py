# SPDX-License-Identifier: GPL-2.0-or-later
r"""
Optional hardware backends for exact binary Frobenius batches.

One fixed Frobenius power is a GF(2)-linear map. This module represents it
using byte lookup tables and identical uint32 XOR arithmetic on CPU, Metal,
CUDA, and OpenCL. GPU adapters are opt-in; source portability is not a claim
of measured acceleration on a device. No dispatch threshold is inferred
from a different machine. ``backend='auto'`` conservatively uses Sage.

GPU buffers use polynomial-basis coordinates of the actual Sage field,
not normal-basis coordinates or an assumed reduction polynomial. The
supported accelerated degrees are 1 through 256. The Sage fallback has
no such additional degree limit. All arithmetic is variable-time.
"""
import ctypes
from operator import index as integer_index
import os
from pathlib import Path
import sys
import threading
import time

import numpy as np
from sage.schemes.elliptic_curves.binary_batch import (
    _curve_coefficient, _point_data, frobenius_points,
)
try:
    from sage.schemes.elliptic_curves import binary_hardware_codec as _codec
except ImportError:
    _codec = None


def kernel_source(backend):
    """Generate the same linear map for three GPU programming interfaces."""
    body = r"""
    if (i >= count * words) return;
    uint e = i / words, w = i % words;
    uint value = 0;
    for (uint b = 0; b < bytes; ++b) {
        uint digit = (input[e*words + b/4] >> (8*(b%4))) & 255u;
        value ^= table[(b*256u + digit)*words + w];
    }
    output[i] = value;
"""
    if backend == 'metal':
        return r"""#include <metal_stdlib>
using namespace metal;
struct Params { uint bytes; uint words; uint count; };
kernel void bh_map(device const uint *table [[buffer(0)]],
                   device const uint *input [[buffer(1)]],
                   device uint *output [[buffer(2)]],
                   constant Params &p [[buffer(3)]],
                   uint i [[thread_position_in_grid]]) {
    if (i >= p.count) return;
    uint acc[8] = {};
    for (uint b = 0; b < p.bytes; ++b) {
        uint digit = (input[i*p.words + b/4] >> (8*(b%4))) & 255u;
        uint row = (b*256u + digit)*p.words;
        for (uint w = 0; w < p.words; ++w) acc[w] ^= table[row + w];
    }
    for (uint w = 0; w < p.words; ++w) output[i*p.words + w] = acc[w];
}
"""
    if backend == 'cuda':
        return r"""
typedef unsigned int uint;
extern "C" __global__ void bh_map(const uint *table, const uint *input,
                                uint *output, uint bytes, uint words, uint count) {
    uint i = blockIdx.x * blockDim.x + threadIdx.x;
""" + body + '\n}\n'
    if backend == 'opencl':
        return r"""
__kernel void bh_map(__global const uint *table, __global const uint *input,
                     __global uint *output, uint bytes, uint words, uint count) {
    uint i = (uint)get_global_id(0);
""" + body + '\n}\n'
    raise ValueError('unknown GPU source language')


def _library(path=None):
    if path is None:
        path = os.environ.get('SAGE_BINARY_NATIVE')
    if path is None:
        paths = [p for p in Path(__file__).parent.glob('_binary_hardware_native.*')
                 if p.suffix in ('.so', '.dylib', '.dll')]
        if len(paths) != 1:
            raise RuntimeError('native binary hardware module is not built; use backend="sage"')
        path = paths[0]
    lib = ctypes.CDLL(str(Path(path).resolve()))
    ptr = ctypes.POINTER(ctypes.c_uint32)
    lib.bh_last_error.restype = ctypes.c_char_p
    lib.bh_cpu_apply.argtypes = [ptr, ptr, ptr, ctypes.c_uint64,
                                ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    lib.bh_cpu_apply.restype = ctypes.c_int
    lib.bh_metal_create.argtypes = [ctypes.c_char_p, ptr, ctypes.c_uint32,
                                   ctypes.c_uint32, ctypes.c_uint32]
    lib.bh_metal_create.restype = ctypes.c_void_p
    lib.bh_metal_destroy.argtypes = [ctypes.c_void_p]
    lib.bh_metal_destroy.restype = None
    lib.bh_metal_name.argtypes = [ctypes.c_void_p]
    lib.bh_metal_name.restype = ctypes.c_char_p
    lib.bh_metal_apply.argtypes = [ctypes.c_void_p, ptr, ptr, ctypes.c_uint64,
                                  ctypes.POINTER(ctypes.c_double)]
    lib.bh_metal_apply.restype = ctypes.c_int
    return lib


def _ptr(array):
    return array.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32))


class FrobeniusPlan:
    r"""
    Reusable map for valid Sage points on one Koblitz curve.

    ``backend`` is ``'sage'``, ``'cpu'``, ``'metal'``, ``'cuda'``, or
    ``'opencl'``. ``'auto'`` selects the existing Sage implementation until
    device-specific end-to-end calibration has been established. CUDA
    requires CuPy; OpenCL requires PyOpenCL and a GPU driver. CPU/Metal
    require the optional native module. Missing backends raise explicitly.

    Construction computes the map and initializes the selected backend.
    Charge it when comparing a cold call. Reusing a plan amortizes this cost.
    ``apply`` includes packing, transfers, computation, and point creation.
    ``apply_words`` operates on canonical packed field coordinates and is a
    separate, lower-level metric, not a complete Sage-point API benchmark.
    """
    def __init__(self, curve, power=1, backend='auto', device=0,
                 cpu_threads=1, native_library=None):
        started = time.perf_counter()
        a = _curve_coefficient(curve)
        if (a != 0 and a != 1) or curve.a6() != 1:
            raise ValueError('a Koblitz curve is required')
        if backend == 'auto':
            backend = 'sage'
        if backend not in ('sage', 'cpu', 'metal', 'cuda', 'opencl'):
            raise ValueError('unknown backend')
        self.curve, self.field = curve, curve.base_ring()
        self.degree = int(self.field.degree())
        self.power = integer_index(power) % self.degree
        self.backend = backend
        self.words = (self.degree + 31)//32
        self.bytes = (self.degree + 7)//8
        self.cpu_threads = integer_index(cpu_threads)
        self.device = integer_index(device)
        if self.device < 0 or not 1 <= self.cpu_threads <= 32:
            raise ValueError('invalid device index or CPU thread count')
        self._lock = threading.Lock()
        self._context = None
        self._closed = False
        self.last_gpu_seconds = None
        self.device_name = 'Sage CPU'
        self.table_seconds = 0.0
        self.codec = 'native-ntl' if _codec is not None and _codec.supports(self.field) else 'python'
        if backend == 'sage':
            self.setup_seconds = time.perf_counter()-started
            return
        if self.degree > 256 or sys.byteorder != 'little':
            raise ValueError('accelerated path requires degree <= 256 and a little-endian host')
        table_start = time.perf_counter()
        self._table = self._make_table()
        self.table_seconds = time.perf_counter()-table_start
        if backend in ('cpu', 'metal'):
            self._lib = _library(native_library)
            if backend == 'metal':
                self._context = self._lib.bh_metal_create(
                    kernel_source('metal').encode(), _ptr(self._table),
                    self.words, self.bytes, self.device)
                if not self._context:
                    raise RuntimeError(self._lib.bh_last_error().decode())
                self.device_name = self._lib.bh_metal_name(self._context).decode()
            else:
                self.device_name = 'portable C++ CPU'
        elif backend == 'cuda':
            self._init_cuda()
        else:
            self._init_opencl()
        self.setup_seconds = time.perf_counter()-started

    def _make_table(self):
        # from_integer/to_integer are inverse polynomial-basis encodings.
        basis = np.zeros((self.bytes*8, self.words), dtype=np.uint32)
        for bit in range(self.degree):
            value = self.field(1 << bit) if self.degree == 1 else self.field.from_integer(1 << bit)
            image = value if not self.power else value.frobenius(self.power)
            integer = int(image) if self.degree == 1 else int(image.to_integer())
            basis[bit] = [(integer >> (32*word)) & 0xffffffff
                          for word in range(self.words)]
        table = np.zeros((self.bytes, 256, self.words), dtype=np.uint32)
        for byte in range(self.bytes):
            row = table[byte]
            for bit in range(8):
                span = 1 << bit
                row[span:2*span] = row[:span] ^ basis[byte*8 + bit]
        result = table.reshape(-1)
        result.setflags(write=False)
        return result

    def _init_cuda(self):
        try:
            import cupy as cp
        except ImportError as error:
            raise RuntimeError('CUDA backend requires CuPy and an NVIDIA driver') from error
        self._cp = cp
        with cp.cuda.Device(self.device):
            props = cp.cuda.runtime.getDeviceProperties(self.device)
            name = props['name']
            self.device_name = name.decode() if isinstance(name, bytes) else str(name)
            self._gpu_table = cp.asarray(self._table)
            self._kernel = cp.RawKernel(kernel_source('cuda'), 'bh_map')
            self._kernel.compile()

    def _init_opencl(self):
        try:
            import pyopencl as cl
        except ImportError as error:
            raise RuntimeError('OpenCL backend requires PyOpenCL and a GPU driver') from error
        devices = [d for p in cl.get_platforms() for d in p.get_devices()
                   if d.type & cl.device_type.GPU]
        if self.device >= len(devices):
            raise RuntimeError('requested OpenCL GPU is unavailable')
        device = devices[self.device]
        if not device.endian_little:
            raise RuntimeError('OpenCL device must use little-endian words')
        self._cl = cl
        self.device_name = f'{device.vendor} {device.name}'
        self._cl_context = cl.Context([device])
        self._queue = cl.CommandQueue(self._cl_context,
                                     properties=cl.command_queue_properties.PROFILING_ENABLE)
        self._program = cl.Program(self._cl_context, kernel_source('opencl')).build(options=['-cl-std=CL1.2'])
        self._kernel = cl.Kernel(self._program, 'bh_map')
        self._gpu_table = cl.Buffer(self._cl_context,
                                    cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                    hostbuf=self._table)

    def apply_words(self, data):
        """Map an (n, words) uint32 array; return a new array, including copies."""
        if self.backend == 'sage':
            raise ValueError('packed mapping requires an accelerated backend')
        if not isinstance(data, np.ndarray) or data.dtype != np.dtype('uint32'):
            raise ValueError('expected a uint32 NumPy array')
        if data.ndim != 2 or data.shape[1] != self.words or not data.flags.c_contiguous:
            raise ValueError('expected a contiguous (n, words) array')
        if 2*data.nbytes+self._table.nbytes > 512*1024*1024:
            raise ValueError('packed working-set cap exceeded')
        if self.degree % 32 and np.any(data[:, -1] >> (self.degree % 32)):
            raise ValueError('noncanonical high coordinate bits')
        with self._lock:
            if self._closed:
                raise RuntimeError('plan is closed')
            self.last_gpu_seconds = None
            if not len(data):
                return np.empty_like(data)
            if self.backend in ('cpu', 'metal'):
                output = np.empty_like(data)
                if self.backend == 'cpu':
                    status = self._lib.bh_cpu_apply(_ptr(self._table), _ptr(data), _ptr(output),
                                                   len(data), self.words, self.bytes, self.cpu_threads)
                else:
                    gpu_time = ctypes.c_double()
                    status = self._lib.bh_metal_apply(self._context, _ptr(data), _ptr(output),
                                                     len(data), ctypes.byref(gpu_time))
                    self.last_gpu_seconds = gpu_time.value
                if status:
                    raise RuntimeError(self._lib.bh_last_error().decode())
                return output
            if self.backend == 'cuda':
                cp = self._cp
                with cp.cuda.Device(self.device):
                    device_input = cp.asarray(data)
                    device_output = cp.empty_like(device_input)
                    start, end = cp.cuda.Event(), cp.cuda.Event()
                    start.record()
                    self._kernel(((data.size+255)//256,), (256,),
                                 (self._gpu_table, device_input, device_output,
                                  np.uint32(self.bytes), np.uint32(self.words), np.uint32(len(data))))
                    end.record(); end.synchronize()
                    self.last_gpu_seconds = cp.cuda.get_elapsed_time(start, end)/1000
                    return cp.asnumpy(device_output)
            cl = self._cl
            device_input = cl.Buffer(self._cl_context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                                     hostbuf=data)
            device_output = cl.Buffer(self._cl_context, cl.mem_flags.WRITE_ONLY, size=data.nbytes)
            event = self._kernel(self._queue, (data.size,), None,
                                 self._gpu_table, device_input, device_output,
                                 np.uint32(self.bytes), np.uint32(self.words), np.uint32(len(data)))
            output = np.empty_like(data)
            cl.enqueue_copy(self._queue, output, device_output, wait_for=[event]).wait()
            self.last_gpu_seconds = (event.profile.end-event.profile.start)*1e-9
            return output

    def pack_points(self, points):
        """Validate and pack Sage points; return coordinates and infinity flags."""
        if self.codec == 'native-ntl':
            return _codec.pack_points(self.curve, points, self.words)
        rows, infinity = [], []
        width = self.words*4
        for P in points:
            P, x, y = _point_data(self.curve, P)
            infinity.append(x is None)
            for value in (x, y):
                integer = 0 if value is None else (int(value) if self.degree == 1 else int(value.to_integer()))
                rows.append(integer.to_bytes(width, 'little'))
        data = np.frombuffer(b''.join(rows), dtype=np.uint32).reshape((-1, self.words))
        return data, np.array(infinity, dtype=np.bool_)

    def _unpack_points(self, data, infinity):
        if self.codec == 'native-ntl':
            return _codec.unpack_points(self.curve, data, infinity, self.words)
        one = self.field.one()
        constructor = self.curve._point
        output = []
        for i, is_zero in enumerate(infinity):
            if is_zero:
                output.append(self.curve(0))
            else:
                convert = self.field if self.degree == 1 else self.field.from_integer
                x = convert(int.from_bytes(data[2*i].tobytes(), 'little'))
                y = convert(int.from_bytes(data[2*i+1].tobytes(), 'little'))
                output.append(constructor(self.curve, [x, y, one], check=False))
        return output

    def apply(self, points):
        """Return ordinary Sage points, with all conversion work included."""
        if self._closed:
            raise RuntimeError('plan is closed')
        if self.backend == 'sage':
            return frobenius_points(self.curve, points, self.power)
        data, infinity = self.pack_points(points)
        return self._unpack_points(self.apply_words(data), infinity)

    def apply_batches(self, batches):
        r"""Map independent point batches with one backend dispatch.

        The outer and inner inputs may be iterators. Batch boundaries and
        point order are preserved, including empty batches. This operation
        shares the plan's existing 512 MiB packed working-set limit.
        """
        if self._closed:
            raise RuntimeError('plan is closed')
        points = []
        lengths = []
        for batch in batches:
            before = len(points)
            points.extend(batch)
            lengths.append(len(points) - before)
        mapped = self.apply(points)
        output = []
        offset = 0
        for length in lengths:
            output.append(mapped[offset:offset + length])
            offset += length
        return output

    def close(self):
        """Release native resources. The plan cannot be used after closing."""
        with self._lock:
            if not self._closed and self._context:
                self._lib.bh_metal_destroy(self._context)
                self._context = None
            for name in ('_gpu_table', '_kernel', '_program', '_queue', '_cl_context'):
                if hasattr(self, name):
                    setattr(self, name, None)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        if getattr(self, '_context', None):
            self._lib.bh_metal_destroy(self._context)
            self._context = None
