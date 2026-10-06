"""Profiler selection and diagnostics; no Modal or GPU needed to test them."""
import re

# NVIDIA's repository uses versioned names. Ubuntu's unversioned
# nsight-compute package is 2022.4.1 and predates Blackwell.
NCU_VERSION = (2025, 3, 1)
NCU_PACKAGE = 'nsight-compute-2025.3.1=2025.3.1.4-1'
NCU_BINARY = '/opt/nvidia/nsight-compute/2025.3.1/ncu'


def profilerVersionError(output):
    match = re.search(r'\bVersion\s+(\d{4})\.(\d+)\.(\d+)', output, re.IGNORECASE)
    if not match:
        return 'could not identify the Nsight Compute version; refusing to profile with an unknown tool'
    version = tuple(int(x) for x in match.groups())
    if version < NCU_VERSION:
        return ('Nsight Compute %s is older than this app requires (2025.3.1); '
                'rebuild the profiler image using %s' % ('.'.join(match.groups()), NCU_PACKAGE))
    return None


def profileResult(returncode, output):
    result = dict(available=False, returncode=returncode, log=output)
    denied = ('ERR_NVGPU_DEBUG_PERF_COUNTER_ACCESS_DENIED' in output
              or 'The user does not have permission' in output
              or 'insufficient permissions' in output.lower())
    if denied:
        result.update(kind='counter_access_denied',
                      why='the host denied access to GPU performance counters',
                      remedy='ask the GPU provider whether performance-counter access is available')
    elif returncode or '==ERROR==' in output:
        errors = [line.strip() for line in output.splitlines() if '==ERROR==' in line]
        result.update(kind='profiling_failed',
                      why='Nsight Compute failed (exit %d): %s' %
                          (returncode, errors[0] if errors else 'see profiler output'),
                      remedy='run modal run profile_diagnostic.py to compare a tiny CUDA control with profiling; a generic error does not establish a counter-permission failure')
    elif not re.search(r'==PROF==\s+Profiling\s+', output):
        result.update(kind='no_kernel_profiled',
                      why='Nsight Compute exited without reporting a profiled kernel; check the kernel filter')
    else:
        result.pop('log')
        result.update(available=True, kind='profiled', report=output)
    return result
