"""Small hash-pinned substitutions into the producer and its tested Metal kernels."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = {
    'round51/producer.cpp': '52abda5985b33b8de784c14964f0cf9acc20fda918723b910169812d4fea4be9',
    'round51/metal_backend.mm': '1a1134063c02e6a333832ac749209203073c05bedc3421204932d6661e673fbc',
    'round67/metal.mm': 'a4e6d099bcf6243713942be6732542e57b46fb909230afb5bdbbeba1dc299843',
    'round49/normalized.py': '4e4c60279066095bd9dde73ba9d7857d6bdc4f355949656bbdfd87ccd002d499',
}


class Edit:
    def __init__(self, path):
        data = (HERE.parent / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == PINS[path], path
        self.text = data.decode()

    def replace(self, old, new, count=1):
        assert self.text.count(old) == count, (old, self.text.count(old), count)
        self.text = self.text.replace(old, new)


def producer():
    e = Edit('round51/producer.cpp')
    e.replace('#include "../round49/abi.h"', '#include "../round49/abi.h"\n#include "transform_api.h"')
    e.replace('struct Producer {', 'struct Producer {\n  uint32_t transform_mode = 0;')
    e.replace('struct Produced {', 'struct Produced {\n  ProducerTransformStats transform{};')
    e.replace('static thread_local GPUProjectionStats failed_gpu_projection_stats{};',
              'static thread_local GPUProjectionStats failed_gpu_projection_stats{};\nstatic thread_local ProducerTransformStats failed_transform_stats{};')
    begin = e.text.index('  for (uint32_t bit = 1; bit < w.branches; bit <<= 1)')
    end = e.text.index('  out.stats.transform_xors =', begin)
    original = e.text[begin:end]
    e.replace(original, '''#ifdef QUADRATIC_METAL
  if (w.transform_mode) {
    if (!w.metal || sizeof(Word) != 4)
      throw std::logic_error("configured transform has no compatible producer");
    compact_metal_transform(w.metal, values.data(), values.size() * sizeof(Word),
                            out.transform.generation, out.transform.kernel);
    out.transform.executed_mode = w.transform_mode;
  } else
#endif
  {
''' + original + '  }\n')
    e.replace('''    gpu_rows = compact_metal_solve(
        w.metal, values.data(), values.size() * sizeof(Word),
        out.symmetry.enabled != 0, w.gpu_projection_enabled,
        out.stats.gpu_device);''', '''    const size_t input_bytes = values.size() * sizeof(Word);
    if (w.transform_mode) {
      gpu_rows = compact_metal_solve_prepared(
          w.metal, values.data(), input_bytes, out.symmetry.enabled != 0,
          w.gpu_projection_enabled, out.transform.generation, out.stats.gpu_device);
      out.transform.projection_reused_bytes = input_bytes;
    } else {
      gpu_rows = compact_metal_solve(
          w.metal, values.data(), input_bytes, out.symmetry.enabled != 0,
          w.gpu_projection_enabled, out.stats.gpu_device);
      out.transform.projection_uploaded_bytes = input_bytes;
    }''')
    e.replace('''    std::lock_guard<std::mutex> guard(w.mutex);
    std::visit(''', '''    std::lock_guard<std::mutex> guard(w.mutex);
    result.transform.requested_mode = w.transform_mode;
#ifdef QUADRATIC_METAL
    ProducerTransformCall invocation(w.metal);
    result.transform.generation = invocation.generation;
#endif
    std::visit(''')
    e.replace('  failed_gpu_projection_stats = result.gpu_projection;',
              '  failed_gpu_projection_stats = result.gpu_projection;\n  failed_transform_stats = result.transform;')
    # Revoke readiness under each old configuration function's existing lock.
    for statement in ('    w.normalization = {};', '    w.partial_enabled = enabled != 0;',
                      '  w.gpu_projection_enabled = enabled != 0;'):
        e.replace(statement, '#ifdef QUADRATIC_METAL\n    compact_metal_invalidate(w.metal);\n#endif\n' + statement)
    return e.text + '\n' + (HERE / 'producer_extensions.inc').read_text()


def backend():
    e = Edit('round51/metal_backend.mm')
    e.replace('#include "../round49/metal_backend.h"', '#include "../round49/metal_backend.h"\n#include "transform_api.h"')
    e.replace('struct CompactMetalBranches {', '''struct CompactMetalBranches {
  void *transform = nullptr;
  uint32_t transform_mode = 0, phase = 0;
  uint64_t generation = 0;
  const void *prepared_host = nullptr;
  ~CompactMetalBranches() { producer_transform::destroy(transform); }''')
    e.replace('''options:MTLResourceStorageModeShared];
    c->output''', '''options:MTLResourceStorageModeShared | MTLResourceHazardTrackingModeTracked];
    c->output''')
    e.replace('''const uint64_t *compact_metal_solve(void *context, const void *input,
                                    size_t bytes, bool symmetric,
                                    bool projection, double &device_seconds) {''', '''static const uint64_t *compact_metal_solve_impl(void *context, const void *input,
                                    size_t bytes, bool symmetric,
                                    bool projection, uint64_t generation,
                                    double &device_seconds) {''')
    e.replace('''    auto &c = *static_cast<CompactMetalBranches *>(context);
    if (!input || bytes != c.input.length)''', '''    device_seconds = 0;
    if (!context) throw std::invalid_argument("null producer Metal context");
    auto &c = *static_cast<CompactMetalBranches *>(context);
    const uint32_t prior_phase = c.phase;
    const void *prepared_host = c.prepared_host;
    compact_metal_invalidate(context);
    if (generation && (generation != c.generation || prior_phase != 2 || prepared_host != input))
      throw std::invalid_argument("stale or mismatched producer device table");
    if (!input || bytes != c.input.length)''')
    e.replace('    std::memcpy(c.input.contents, input, bytes);',
              '    if (!generation) std::memcpy(c.input.contents, input, bytes);\n    c.phase = 3; // Consumed even if command creation or execution fails.')
    return e.text + '\n' + (HERE / 'metal_extensions.inc').read_text()


def transform():
    e = Edit('round67/metal.mm')
    e.replace('#include "build/kernel.inc"', '#include "build/transform_kernel.inc"\n#include "transform_api.h"')
    e.replace('void *create(uint32_t variables, uint32_t stride, Mode mode)',
              'static void *make(uint32_t variables, uint32_t stride, Mode mode,\n                  id<MTLDevice> gpu, id<MTLCommandQueue> queue, id<MTLBuffer> buffer)')
    e.replace('        c->gpu = MTLCreateSystemDefaultDevice();',
              '        c->gpu = gpu ? gpu : MTLCreateSystemDefaultDevice();')
    e.replace('''        c->queue = [c->gpu newCommandQueue];
        c->buffer = [c->gpu newBufferWithLength:bytes''', '''        if (buffer && (buffer.length != bytes || buffer.device != c->gpu ||
                       buffer.storageMode != MTLStorageModeShared ||
                       buffer.hazardTrackingMode != MTLHazardTrackingModeTracked ||
                       !queue || queue.device != c->gpu))
            throw std::invalid_argument("borrowed producer transform resources");
        c->queue = queue ? queue : [c->gpu newCommandQueue];
        c->buffer = buffer ? buffer : [c->gpu newBufferWithLength:bytes''')
    e.replace('void destroy(void *p)', '''void *create(uint32_t variables, uint32_t stride, Mode mode) {
    return make(variables, stride, mode, nil, nil, nil);
}
void *create_borrowed(uint32_t variables, uint32_t stride, Mode mode,
                      void *gpu, void *queue, void *buffer) {
    if (!gpu || !queue || !buffer) throw std::invalid_argument("null borrowed producer resources");
    return make(variables, stride, mode, (__bridge id<MTLDevice>)gpu,
                (__bridge id<MTLCommandQueue>)queue, (__bridge id<MTLBuffer>)buffer);
}
void destroy(void *p)''')
    return e.text


def wrapper():
    e = Edit('round49/normalized.py')
    e.replace('HERE = Path(__file__).resolve().parent', 'HERE = Path(__file__).resolve().parents[1]')
    e.replace('class Producer(Native):', (HERE / 'python_stats.inc').read_text() + '\n\nclass Producer(Native):')
    e.replace(''' or (
                backend == 'metal' and (sanitizer or budget_test or multiplier_budget_test or copy_budget_test or reconstruction_budget_test or enumeration_budget_test or partial_commit_budget_test))''', '')
    e.replace("tag = '-metal' if backend == 'metal' else ", "tag = ('-metal' if backend == 'metal' else '') + (")
    e.replace("else '-ubsan' if sanitizer else ''\n", "else '-ubsan' if sanitizer else '')\n")
    e.replace("        self.normalization_configuration = {'requested': False, 'enabled': False}", '''        lib.branch_producer_transform_stats_size.restype = U64
        if lib.branch_producer_transform_stats_size() != ct.sizeof(ProducerTransformStats):
            raise RuntimeError('producer transform metadata ABI mismatch')
        self.producer_transform = 'cpu'
        self.normalization_configuration = {'requested': False, 'enabled': False}''')
    e.replace("            ('branch_gpu_projection_stats',", '''            ('branch_producer_transform_configure', ct.c_int, [ct.c_void_p, U32]),
            ('branch_producer_transform_stats', ct.POINTER(ProducerTransformStats), [ct.c_void_p]),
            ('branch_last_producer_transform_stats', ct.POINTER(ProducerTransformStats), []),
            ('branch_gpu_projection_stats',''')
    e.replace('    def configure_gpu_projection(self, enabled):', '''    def configure_producer_transform(self, mode):
        if type(mode) is not str or mode not in ('cpu', 'metal', 'metal_tiled'):
            raise ValueError('producer transform must be cpu, metal, or metal_tiled')
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer is closed')
            code = self.lib.branch_producer_transform_configure(self._handle, ('cpu', 'metal', 'metal_tiled').index(mode))
            if code == -2:
                raise RuntimeError('producer transform requires a compatible Metal producer')
            if code:
                raise RuntimeError('producer transform configuration failed: ' + self.lib.branch_error().decode())
            self.producer_transform = mode

    def configure_gpu_projection(self, enabled):''')
    e.replace('                error.metrics = stats.record()',
              '                error.producer_transform_stats = self.lib.branch_last_producer_transform_stats().contents.record()\n                error.metrics = stats.record()')
    e.replace("                return {'roots': roots, 'basis': basis, 'stats': stats.record(),", '''                return {'roots': roots, 'basis': basis, 'stats': stats.record(),
                        'producer_transform_stats': self.lib.branch_producer_transform_stats(result).contents.record(),''')
    e.replace("                        'metrics': getattr(error, 'metrics', {}),", "                        'producer_transform_stats': getattr(error, 'producer_transform_stats', {}),\n                        'metrics': getattr(error, 'metrics', {}),")
    e.replace("                    'metrics': result['stats'], 'multiplier_stats':", "                    'producer_transform_stats': result['producer_transform_stats'],\n                    'metrics': result['stats'], 'multiplier_stats':")
    return e.text


def generate(out):
    out.mkdir(exist_ok=True)
    for name, content in {'producer.cpp': producer(), 'backend.mm': backend(),
                          'transform.mm': transform(), 'normalized.py': wrapper()}.items():
        (out / name).write_text(content)


if __name__ == '__main__':
    generate(HERE / 'build')
