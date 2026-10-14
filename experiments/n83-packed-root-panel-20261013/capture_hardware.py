#!/usr/bin/env python3
"""Bind a post-run static Mac hardware audit to immutable arm receipts."""

import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    hardware = output('system_profiler', 'SPHardwareDataType', '-detailLevel', 'mini')
    model = re.search(r'Model Identifier: (\S+)', hardware).group(1)
    chip = re.search(r'Chip: (.+)', hardware).group(1)
    assert model == 'Mac16,7' and chip == 'Apple M4 Pro'
    def sysctl(name):
        return int(output('sysctl', '-n', name))
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    receipt = {
        'schema': 'n83_a1_cpu_only_32_point_panel_hardware_audit_v1',
        'collection_phase': 'post_run_static_host_audit',
        'collected_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_commands': ['system_profiler SPHardwareDataType -detailLevel mini',
                            'sysctl -n hw.physicalcpu hw.logicalcpu hw.memsize hw.l1icachesize hw.l1dcachesize hw.l2cachesize',
                            'sw_vers', 'uname -r -m'],
        'hardware': {
            'physical_host_model': model, 'chip': chip, 'cpu_vendor': 'Apple',
            'cpu_generation': 'M4 Pro', 'architecture': 'arm64',
            'physical_cores': sysctl('hw.physicalcpu'),
            'logical_threads': sysctl('hw.logicalcpu'),
            'performance_cores': sysctl('hw.perflevel0.physicalcpu'),
            'efficiency_cores': sysctl('hw.perflevel1.physicalcpu'),
            'sockets': 1,
            'cache_bytes_reported': {
                'l1i': sysctl('hw.l1icachesize'),
                'l1d': sysctl('hw.l1dcachesize'),
                'l2': sysctl('hw.l2cachesize'),
                'mapping_to_core_clusters': None},
            'os': 'macOS', 'os_version': output('sw_vers', '-productVersion'),
            'os_build': output('sw_vers', '-buildVersion'),
            'kernel': output('uname', '-r'),
            'physical_memory_bytes': sysctl('hw.memsize'),
            'memory_technology': 'unknown', 'memory_speed': None,
            'memory_channels': None,
            'virtualization': 'local_physical_mac_reported_by_system_profiler',
            'container': False, 'cpu_cgroup_limit': 'not_applicable_darwin',
            'memory_cgroup_limit': 'not_applicable_darwin',
            'numa_nodes_exposed': None,
        },
        'placement': {
            'allowed_cpus': 'host_scheduler_all_14_logical_cpus',
            'selected_cpu_affinity': None,
            'memory_policy': 'macOS_default',
            'observed_page_placement': None,
            'cpu_throttling_counters': None,
            'co_runners_during_arms': None,
            'process_cpu_time_s': None,
            'limitations': 'No contemporaneous affinity, page-placement, throttling, co-runner, or final process-CPU-time receipt; wall ratios are exploratory.',
        },
        'gpu': {'devices': [], 'cuda_available': False,
                'measurement_class': 'cpu_only_secondary_control',
                'f4_backend': 'not_used_by_compact_orbit_rust_solver'},
        'execution': {
            'rank_threads': protocol['rank_threads'],
            'target_threads': protocol['target_threads'],
            'ic_process_cap_seconds': protocol['ic_process_cap_seconds'],
            'target_count': protocol['target_count'],
            'sampled_rss_cap_bytes': protocol['sampled_rss_cap_bytes'],
            'rss_poll_seconds': protocol['rss_poll_seconds'],
            'protocol_sha256': sha(HERE / 'protocol.json'),
            'binary_manifest_sha256': sha(HERE / 'binary_manifest.json'),
            'arm_execution_sha256': {
                name: sha(HERE / 'runs' / name / 'execution.json')
                for name in protocol['arms']},
        },
    }
    assert receipt['hardware']['physical_cores'] == receipt['hardware']['logical_threads'] == 14
    with (HERE / 'hardware.json').open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': 'PASS', 'host': model, 'chip': chip,
                      'hardware_sha256': sha(HERE / 'hardware.json')}))


if __name__ == '__main__':
    main()
