"""Native execution of ring-only contraction layouts, with owned packed outputs."""
from array import array
import ctypes as ct
import hashlib
import importlib.util
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round4'))
from descent_plan import DescentPlan

U32, U64 = ct.c_uint32, ct.c_uint64
MASK64 = (1 << 64) - 1


class Edge(ct.Structure):
    _fields_ = [('source', U32), ('destination', U32), ('table', U32)]


class PackedANF:
    """One query's owned numeric output; subsequent calls cannot overwrite it."""
    def __init__(self, nvars, equations, masks, coefficients, count):
        if not 1 <= nvars <= 20 or not 1 <= equations <= 128 or not 0 <= count <= len(masks):
            raise ValueError('packed output dimensions')
        self.nvars, self.equations = nvars, equations
        self._owners = masks, coefficients
        self.masks = (U32 * count).from_buffer(masks)
        self.coefficients = (U64 * (count * ((equations+63)//64))).from_buffer(coefficients)
        self._replay_dictionary = None

    def items(self):
        # The unchanged Python equation/curve replay scans this ANF twice.
        # Materialize its Python view once, after native solving/certification;
        # the conversion remains inside the query's replay interval.
        if self._replay_dictionary is None:
            self._replay_dictionary = self.to_dict()
        return self._replay_dictionary.items()

    def to_dict(self):
        limbs = (self.equations+63)//64
        result = {}
        for i, mask in enumerate(self.masks):
            value = self.coefficients[i*limbs]
            if limbs == 2:
                value |= self.coefficients[i*limbs+1] << 64
            result[mask] = value
        return result


class NativeDescent:
    def __init__(self, n, mod, b, m, ell, *, sanitizer=False):
        if not isinstance(n, int) or not 1 <= n <= 128:
            raise ValueError('native contraction field degree: 1..128')
        # The existing builder validates the ring and builds only invariant data.
        layout = DescentPlan(n, mod, b, m, ell)
        self.shape = layout.shape
        self._field, self._terms, self._exponents = layout._field, layout._terms, layout._exponents
        self._initial_size, self._capacity = len(layout._buffers[0]), len(layout._masks)
        self._lock, self._handle = threading.Lock(), None
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        self.path = HERE / 'build' / ('contraction' + suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self._lib = ct.CDLL(str(self.path))
        u32, u64 = ct.POINTER(U32), ct.POINTER(U64)
        self._lib.contraction_create.argtypes = [U32, U32, U32, u32, u32, ct.POINTER(Edge),
                                                 U32, u64, U64, U32, u32]
        self._lib.contraction_create.restype = ct.c_void_p
        self._lib.contraction_destroy.argtypes = [ct.c_void_p]
        self._lib.contraction_destroy.restype = None
        self._lib.contraction_compute.argtypes = [ct.c_void_p, u64, U64, u32, u64, U32, u32]
        self._lib.contraction_compute.restype = ct.c_int
        self._lib.contraction_error.restype = ct.c_char_p
        tables, table_ids, edges, offsets = [], {}, [], [0]
        for stage in layout._stages:
            for source, outgoing in stage:
                for destination, table in outgoing:
                    identity = id(table)
                    if identity not in table_ids:
                        table_ids[identity] = len(tables)
                        tables.append(table)
                    edges.append(Edge(source, destination, table_ids[identity]))
            offsets.append(len(edges))
        limbs = (n+63)//64
        words = array('Q')
        for table in tables:
            for row in table.t:
                for value in row:
                    words.append(value & MASK64)
                    if limbs == 2:
                        words.append(value >> 64)
        assert words.itemsize == ct.sizeof(U64)
        buffers = ((U32 * len(layout._buffers))(*(len(b) for b in layout._buffers)),
                   (U32 * len(offsets))(*offsets), (Edge * len(edges))(*edges),
                   (U64 * len(words)).from_buffer(words), (U32 * self._capacity)(*layout._masks))
        sizes, starts, native_edges, native_tables, masks = buffers
        self._handle = self._lib.contraction_create(n, m*ell, m, sizes, starts, native_edges,
                              len(edges), native_tables, len(words), len(tables), masks)
        if not self._handle:
            raise ValueError(self._lib.contraction_error().decode())
        self.layout_stats = {'tables': len(tables), 'table_bytes': len(words)*8,
                             'edges': len(edges), 'slots': sum(sizes), 'final_slots': self._capacity}

    def close(self):
        with self._lock:
            if self._handle:
                self._lib.contraction_destroy(self._handle)
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def descend_packed(self, target):
        n, _, _, m, ell = self.shape
        if not isinstance(target, int) or not 0 <= target < 1 << n:
            raise ValueError('target coordinate outside the field')
        limbs = (n+63)//64
        initial = [0]*self._initial_size
        powers = {e: self._field.pow(target, e) for e in self._exponents}
        for destination, exponent, fixed in self._terms:
            initial[destination] ^= self._field.mul(powers[exponent], fixed)
        words = (U64 * (len(initial)*limbs))()
        for i, value in enumerate(initial):
            words[i*limbs] = value & MASK64
            if limbs == 2:
                words[i*limbs+1] = value >> 64
        masks, coefficients = (U32 * self._capacity)(), (U64 * (self._capacity*limbs))()
        count = U32()
        with self._lock:
            if not self._handle:
                raise RuntimeError('native descent plan is closed')
            code = self._lib.contraction_compute(self._handle, words, len(words), masks,
                                                  coefficients, self._capacity, ct.byref(count))
            if code:
                raise ValueError(self._lib.contraction_error().decode())
        return PackedANF(m*ell, n, masks, coefficients, count.value)

    def descend(self, target):
        return self.descend_packed(target).to_dict()


def packed_query(nvars, equations):
    """Adapt only the input view; native solving and certification are unchanged."""
    spec = importlib.util.spec_from_file_location('native_descent_query', HERE.parent/'round4/packed_query.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module._views
    def views(n, e, anf):
        if isinstance(anf, PackedANF):
            if (n, e) != (anf.nvars, anf.equations):
                raise ValueError('packed ANF ring mismatch')
            return anf.masks, anf.coefficients
        return original(n, e, anf)
    module._views = views
    return module.PackedQuery(nvars, equations)
