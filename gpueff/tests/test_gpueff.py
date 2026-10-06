"""Tests for gpueff.  Run from gpueff/: python3 -m unittest discover -s tests -v"""
import copy
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from gpueff import cli, export, metrics, observe, probe, profiles, score  # noqa: E402

PROBE_RESULT = REPO / 'ecc2k130/runner/benchmarks/hardware-limits/result.json'
PROBE_SOURCE = 'ecc2k130/runner/benchmarks/hardware-limits/result.json'
RTX = profiles.load(ROOT / 'profiles/rtx-pro-6000-blackwell-server.json')
WALK = profiles.load(ROOT / 'profiles/ecc2k130-packed-walk.json')
SCRAPES = [(HERE / 'data/scrape-t0.prom', 1000.0), (HERE / 'data/scrape-t60.prom', 1060.0)]


def scraped_samples():
    samples = []
    for path, when in SCRAPES:
        samples.extend(metrics.parse_text(path.read_text(), when))
    return samples


def gpus(**fields):
    return {'0': dict(fields)}


class Parsing(unittest.TestCase):
    def test_text_format_labels_escapes_and_timestamps(self):
        text = ('# HELP x y\n'
                'a{b="c",d="e \\"q\\" \\\\ f"} 1.5\n'
                'plain 2 1700000000000\n'
                'inf_value +Inf\n')
        samples = metrics.parse_text(text, scrape_time=7.0)
        self.assertEqual(samples[0], metrics.Sample('a', {'b': 'c', 'd': 'e "q" \\ f'}, 7.0, 1.5))
        self.assertEqual(samples[1].time, 1700000000.0)
        self.assertTrue(math.isinf(samples[2].value))

    def test_malformed_line_is_an_error(self):
        with self.assertRaises(ValueError):
            metrics.parse_text('not a sample at all{\n')

    def test_range_json(self):
        reply = {'status': 'success', 'data': {'resultType': 'matrix', 'result': [
            {'metric': {'__name__': 'DCGM_FI_PROF_SM_ACTIVE', 'gpu': '0'},
             'values': [[10, '0.5'], [25, '0.7']]}]}}
        samples = metrics.parse_range_json(json.dumps(reply))
        self.assertEqual([s.value for s in samples], [0.5, 0.7])
        self.assertEqual(samples[1].time, 25.0)

    def test_counter_rate_survives_a_reset(self):
        # 0 -> 100 in 10 s, reset, then 0 -> 50 in the next 10 s: 150 over 20 s.
        self.assertAlmostEqual(metrics.counter_rate([(0, 0), (10, 100), (15, 0), (20, 50)]), 7.5)

    def test_one_point_has_no_rate(self):
        self.assertIsNone(metrics.counter_rate([(0, 5)]))


class Roofline(unittest.TestCase):
    def test_ecc2k130_roofs_match_the_throughput_ceiling_note(self):
        roofs = profiles.roofline(RTX, WALK)
        self.assertEqual(roofs[0]['demand'], 'issue')
        # THROUGHPUT-CEILING.md: 742.5 wide multiplies per update at 53 lanes per
        # SM-clock is "31 B/s if the walk did nothing else".
        wide = next(r for r in roofs if r['demand'] == 'wide_multiply')
        self.assertAlmostEqual(wide['units_per_second'] / 1e9, 31.1, delta=0.1)
        # The audited 6.905 B/s is below the issue roof, and above what the
        # LOP3+IMAD probe would allow: that roof is not a ceiling for it.
        self.assertLess(6.905e9, roofs[0]['units_per_second'])
        lop3_imad = copy.deepcopy(WALK)
        lop3_imad['demand_per_unit']['issue']['resource'] = 'alu:lop3+imad'
        report = score.score({'throughput': 6.905e9 * 1.05, 'devices': 1}, RTX, lop3_imad)
        self.assertIn('CEILING_EXCEEDED', [f['code'] for f in report['findings']])

    def test_clock_scaled_and_absolute_ceilings(self):
        self.assertAlmostEqual(profiles.ceiling(RTX, 'alu:lop3', 1000),
                               RTX['resources']['alu:lop3']['per_sm_per_clock'] * 188 * 1e9)
        self.assertEqual(profiles.ceiling(RTX, 'dram:read', 1000), profiles.ceiling(RTX, 'dram:read', 2000))

    def test_llm_decode_example_is_memory_bound(self):
        machine = profiles.load(ROOT / 'profiles/h100-sxm-datasheet.json')
        workload = profiles.load(ROOT / 'profiles/llm-decode-8b-bf16.json')
        roofs = profiles.roofline(machine, workload)
        self.assertEqual(roofs[0]['resource'], 'hbm_bytes')
        self.assertAlmostEqual(roofs[0]['units_per_second'], 3.35e12 / 7.70e8)
        report = score.score({'throughput': 3000.0, 'devices': 1,
                              'gpus': gpus(DCGM_FI_PROF_SM_ACTIVE=0.99, DCGM_FI_PROF_DRAM_ACTIVE=0.72,
                                           DCGM_FI_DEV_SM_CLOCK=1500)}, machine, workload)
        # A memory roof does not scale with the SM clock, so a low clock is no loss.
        self.assertEqual(report['components']['clock']['status'], 'not_applicable')
        self.assertEqual(report['decomposition']['factors']['clock_factor'], 1.0)


class Scoring(unittest.TestCase):
    def test_end_to_end_from_scrapes(self):
        obs = observe.observe(scraped_samples(), WALK)
        self.assertEqual(obs['window_seconds'], 60.0)
        self.assertAlmostEqual(obs['throughput'], 12.8e9)
        self.assertEqual(obs['cpu']['cores'], 2)
        self.assertAlmostEqual(obs['cpu']['busy_cores'], 15.0 / 60)
        self.assertAlmostEqual(obs['gpus']['GPU-0']['energy_watts'], 400.0)
        report = score.score(obs, RTX, WALK)
        self.assertEqual(report['devices'], 2)
        self.assertEqual(report['basis'], 'roofline')
        self.assertAlmostEqual(report['coverage'], 1.0)
        attainable = 2 * profiles.roofline(RTX, WALK)[0]['units_per_second']
        self.assertAlmostEqual(report['roofline_efficiency'], 12.8e9 / attainable)
        self.assertAlmostEqual(report['components']['sm_active']['value'], 0.95)
        self.assertAlmostEqual(report['components']['occupancy']['raw'], 0.305 / 0.95)
        self.assertAlmostEqual(report['components']['clock']['value'], 2250 / 2307.1)
        self.assertAlmostEqual(report['joules_per_unit'], 800.0 / 12.8e9)
        self.assertEqual([f['code'] for f in report['findings']], ['THROTTLED'])

    def test_decomposition_multiplies_back_to_the_roofline(self):
        report = score.score(observe.observe(scraped_samples(), WALK), RTX, WALK)
        factors = report['decomposition']['factors']
        self.assertAlmostEqual(factors['clock_factor'] * factors['sm_active'] * factors['in_kernel'],
                               report['roofline_efficiency'])
        self.assertAlmostEqual(sum(report['decomposition']['loss_share'].values()), 1.0)

    def test_composite_is_the_weighted_geometric_mean(self):
        report = score.score(observe.observe(scraped_samples(), WALK), RTX, WALK)
        used = [c for c in report['components'].values() if c['value'] is not None and c['weight']]
        expected = 100 * math.exp(sum(c['weight'] * math.log(c['value']) for c in used)
                                  / sum(c['weight'] for c in used))
        self.assertAlmostEqual(report['score'], expected)

    def test_without_throughput_the_score_is_a_flagged_proxy(self):
        samples = [s for s in scraped_samples() if s.name != 'ecc2k130_walk_iterations_total']
        obs = observe.observe(samples, WALK)
        self.assertIn('throughput', obs['missing'])
        report = score.score(obs, RTX, WALK)
        self.assertEqual(report['basis'], 'hardware-proxy')
        self.assertIsNone(report['roofline_efficiency'])
        self.assertAlmostEqual(report['coverage'], 0.5)
        self.assertIsNone(report['decomposition'])

    def test_a_single_counter_scrape_has_no_throughput(self):
        obs = observe.observe(metrics.parse_text(SCRAPES[1][0].read_text(), 1060.0), WALK)
        self.assertNotIn('throughput', obs)
        self.assertIn('two timestamped scrapes', obs['missing']['throughput'])

    def test_occupancy_is_scored_only_against_a_target_and_capped(self):
        no_target = dict(WALK)
        no_target.pop('target_occupancy')
        obs = {'throughput': 5e9, 'gpus': gpus(DCGM_FI_PROF_SM_ACTIVE=1.0, DCGM_FI_PROF_SM_OCCUPANCY=0.9)}
        self.assertEqual(score.score(obs, RTX, no_target)['components']['occupancy']['status'],
                         'not_applicable')
        # Three times the target is not three times better.
        self.assertEqual(score.score(obs, RTX, WALK)['components']['occupancy']['value'], 1.0)

    def test_host_bound_and_wasted_work_findings(self):
        obs = {'throughput': 3.0e9, 'cpu': {'cores': 8, 'busy_cores': 1.0, 'max_core_busy': 0.99},
               'gpus': gpus(DCGM_FI_PROF_SM_ACTIVE=0.6, DCGM_FI_PROF_PIPE_INT_ACTIVE=0.95,
                            DCGM_FI_DEV_SM_CLOCK=2307.1)}
        codes = [f['code'] for f in score.score(obs, RTX, WALK)['findings']]
        self.assertIn('HOST_BOUND', codes)
        self.assertIn('WASTED_WORK', codes)

    def test_bound_mismatch_when_another_resource_is_busier(self):
        workload = copy.deepcopy(WALK)
        workload['demand_per_unit']['dram'] = {'amount': 1.0, 'resource': 'dram:read'}
        obs = {'throughput': 6e9, 'gpus': gpus(DCGM_FI_PROF_SM_ACTIVE=1.0, DCGM_FI_PROF_PIPE_INT_ACTIVE=0.5,
                                               DCGM_FI_PROF_DRAM_ACTIVE=0.9)}
        codes = [f['code'] for f in score.score(obs, RTX, workload)['findings']]
        self.assertIn('BOUND_MISMATCH', codes)

    def test_cpu_workload(self):
        machine = {'schema': profiles.MACHINE_SCHEMA, 'name': 'cpu box', 'device': 'cpu', 'cores': 16,
                   'clock_mhz': {'max': 3000},
                   'resources': {'int_ops': {'per_core_per_clock': 4, 'unit': 'ops'}}}
        workload = {'schema': profiles.WORKLOAD_SCHEMA, 'name': 'cpu rho', 'work_unit': 'step',
                    'demand_per_unit': {'int_ops': 1000}, 'cpu': {'role': 'compute'}}
        report = score.score({'throughput': 96e6, 'cpu': {'cores': 16, 'busy_cores': 12.0}}, machine, workload)
        self.assertAlmostEqual(report['roofline_efficiency'], 96e6 / (4 * 16 * 3e9 / 1000))
        self.assertAlmostEqual(report['components']['cpu']['value'], 0.75)
        self.assertEqual(report['components']['sm_active']['status'], 'not_applicable')

    def test_profiles_are_rejected_when_inconsistent(self):
        bad = copy.deepcopy(WALK)
        bad['demand_per_unit']['issue']['resource'] = 'alu:nonexistent'
        with self.assertRaises(profiles.ProfileError):
            profiles.check_workload(bad, RTX)
        with self.assertRaises(profiles.ProfileError):
            profiles.check_machine(dict(RTX, sms=0))

    def test_every_shipped_profile_is_valid(self):
        for path in sorted((ROOT / 'profiles').glob('*.json')):
            profile = profiles.load(path)
            with self.subTest(path.name):
                if profile['schema'] == profiles.MACHINE_SCHEMA:
                    profiles.check_machine(profile)
                else:
                    profiles.check_workload(profile)


class Export(unittest.TestCase):
    def test_report_text_parses_back(self):
        report = score.score(observe.observe(scraped_samples(), WALK), RTX, WALK)
        samples = metrics.parse_text(export.report_to_text(report, {'run': 'fixture'}))
        by_name = {s.name: s for s in samples}
        self.assertAlmostEqual(by_name['gpueff_score'].value, report['score'])
        self.assertEqual(by_name['gpueff_score'].labels['run'], 'fixture')
        factors = [s for s in samples if s.name == 'gpueff_factor']
        self.assertEqual(len(factors), 3)

    def test_worker_metrics_file_is_scoreable(self):
        path = REPO / 'ecc2k130/runner/aws/worker.py'
        spec = importlib.util.spec_from_file_location('ecc_worker', str(path))
        worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(worker)
        with tempfile.TemporaryDirectory() as tmp:
            written = worker.writeMetrics(tmp, 3, {'iters': 123456789012, 'rate': 6.9e9})
            self.assertEqual(os.path.basename(written), 'ecc2k130-gpu3.prom')
            samples = metrics.parse_text(Path(written).read_text(), 0.0)
        names = {s.name: s for s in samples}
        self.assertEqual(names['ecc2k130_walk_iterations_total'].value, 123456789012)
        self.assertEqual(names['ecc2k130_walk_iterations_total'].labels, {'gpu': '3'})
        self.assertEqual(WALK['throughput']['metric'], 'ecc2k130_walk_iterations_total')

    def test_rules_reference_only_their_own_workload(self):
        text = export.to_yaml(export.recording_rules(RTX, WALK))
        self.assertIn('workload=\\"ecc2k130 packed walk\\"', text)
        self.assertNotIn(' gpueff:devices:count *', text)

    @unittest.skipUnless(shutil.which(os.environ.get('PROMTOOL', 'promtool')), 'promtool not installed')
    def test_rules_compute_the_same_score_as_python(self):
        """promtool evaluates the generated rules on constant DCGM series and a
        linear counter; the recorded score must equal score.score() on the
        same values."""
        values = dict(DCGM_FI_PROF_SM_ACTIVE=0.9, DCGM_FI_PROF_SM_OCCUPANCY=0.27,
                      DCGM_FI_PROF_PIPE_INT_ACTIVE=0.8, DCGM_FI_DEV_SM_CLOCK=2250.0)
        rate = 6.5e9
        report = score.score({'throughput': rate, 'gpus': gpus(**values)}, RTX, WALK)
        series = [dict(series='%s{gpu="0"}' % k, values='%r+0x40' % v) for k, v in values.items()]
        series.append(dict(series='ecc2k130_walk_iterations_total{gpu="0"}',
                           values='0+%rx40' % (rate * 15)))
        labels = 'machine="%s",workload="%s"' % (RTX['name'], WALK['name'])
        expected = [('gpueff:score', report['score']),
                    ('gpueff:roofline_efficiency:ratio', report['roofline_efficiency'])]
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'rules.yml').write_text(export.to_yaml(export.recording_rules(RTX, WALK)))
            test = {'rule_files': ['rules.yml'], 'evaluation_interval': '15s', 'tests': [{
                'interval': '15s', 'input_series': series,
                'promql_expr_test': [{'expr': name, 'eval_time': '10m',
                                      'exp_samples': [{'labels': '%s{%s}' % (name, labels), 'value': value}]}
                                     for name, value in expected]}]}
            Path(tmp, 'test.yml').write_text(json.dumps(test))
            result = subprocess.run([shutil.which(os.environ.get('PROMTOOL', 'promtool')), 'test', 'rules',
                                     'test.yml'], cwd=tmp, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class Probe(unittest.TestCase):
    def test_shipped_machine_profile_is_regenerated_from_the_probe(self):
        self.assertEqual(profiles.load(ROOT / 'profiles/rtx-pro-6000-blackwell-server.json'),
                         probe.build(PROBE_RESULT, PROBE_SOURCE))

    def test_probe_ceilings_match_the_ceiling_note(self):
        machine = probe.build(PROBE_RESULT, PROBE_SOURCE)
        self.assertEqual(machine['sms'], 188)
        self.assertEqual(machine['sm_clock_mhz']['max'], 2430)
        self.assertAlmostEqual(machine['resources']['alu:lop3']['per_sm_per_clock'], 62.1, delta=0.1)
        self.assertAlmostEqual(machine['resources']['dram:read']['per_second'] / 1e12, 1.53, delta=0.01)
        self.assertNotIn('dcgm_activity', machine['resources']['alu:iadd3+ffma'])

    def test_cli_round_trip(self):
        rc = cli.main(['machine-from-probe', str(PROBE_RESULT), '--source', PROBE_SOURCE,
                       '--check', str(ROOT / 'profiles/rtx-pro-6000-blackwell-server.json')])
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
