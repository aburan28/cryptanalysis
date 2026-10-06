"""The profiling screen must reject unequal/incomplete work and bogus rates."""
import unittest
import profile_goal28 as profile
from testnativebench import sample
import native_candidate_bench as bench

class ProfileScreen(unittest.TestCase):
    def test_equal_work_across_grids(self):
        for workers,launches in [(385024,32),(192512,64),(96256,128)]:
            raw=sample(mode='control')['raw'].replace('385024 threads',f'{workers} threads').replace('6160384 walks',f'{workers*16} walks')
            row=profile.timing(raw,workers,1024,launches,0)
            self.assertEqual(row['iterations'],201863462912)
    def test_column_padding_and_final_timer_rounding(self):
        raw=sample(mode='control')['raw'].replace(' iterations 0 dp 0 stored 0 dropped',' iterations         0 dp         0 stored         0 dropped').replace('M it/s 201863462912','M it/s  201863462912').replace('finished: 14500.000','finished: 14499.999')
        self.assertEqual(profile.timing(raw,385024,1024,32,0)['rateMPerSecond'],14499.999)

    def test_bad_completions_rejected(self):
        raw=sample(mode='control')['raw']
        for bad in [raw.replace('201863462912','201863462911'),raw.replace('385024 threads','96256 threads'),raw.replace('0 dropped','1 dropped'),raw.replace('finished: 14500.000','finished: 15500.000'),raw.replace('finished:','interrupted:')]:
            with self.subTest(bad=bad),self.assertRaises(RuntimeError):profile.timing(bad,385024,1024,32,0)

    def test_range_instrumented_timing_rejected(self):
        row=sample(mode='control');row['raw']='packed profile ranges: 1\n'+row['raw']
        with self.assertRaises(RuntimeError):bench.validate_sample(row,'control',0)
        with self.assertRaises(RuntimeError):profile.timing(row['raw'],385024,1024,32,0)

if __name__=='__main__':unittest.main()
