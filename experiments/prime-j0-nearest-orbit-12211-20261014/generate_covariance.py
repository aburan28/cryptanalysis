#!/usr/bin/env python3
"""Generate bounded, kernel-checked finite covariance certificates."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNT = 12211
CHUNK = 128


def generate():
    chunks = [(start, min(CHUNK, COUNT-start))
              for start in range(0, COUNT, CHUNK)]
    out = [
        'import NearestOrbit12211',
        '',
        'namespace NearestOrbitCovariance',
        'open SplitPrime12211NearestStep',
        'open SplitPrimeRadix',
        '',
        'noncomputable def covarianceCheck (r : Nat) : Bool :=',
        '  decide (nearestDigit ((12100*r) % 12211) =',
        '    omegaMul (nearestDigit r))',
        '',
    ]
    for index, (start, length) in enumerate(chunks):
        out += [
            'set_option maxRecDepth 100000 in',
            'set_option maxHeartbeats 0 in',
            f'theorem covariance_chunk_{index} :',
            f'    (List.range {length}).all (fun k => covarianceCheck ({start}+k)) = true := by decide',
            '',
        ]
    out += [
        'private theorem from_chunk (start len : Nat)',
        '    (hc : (List.range len).all (fun k => covarianceCheck (start+k)) = true)',
        '    (r : Nat) (hlo : start ≤ r) (hhi : r < start+len) :',
        '    covarianceCheck r = true := by',
        '  have h := (List.all_eq_true.mp hc) (r-start)',
        '    (List.mem_range.mpr (by omega))',
        '  have heq : start+(r-start)=r := by omega',
        '  simpa [heq] using h',
        '',
        'theorem all_runtime_digits_covariant (r : Nat) (hr : r < 12211) :',
        '    covarianceCheck r = true := by',
    ]
    for index, (start, length) in enumerate(chunks[:-1]):
        out += [
            f'  by_cases h{index} : r < {start+length}',
            f'  · exact from_chunk {start} {length} covariance_chunk_{index} r (by omega) (by omega)',
        ]
    index = len(chunks)-1
    start, length = chunks[-1]
    out += [
        f'  exact from_chunk {start} {length} covariance_chunk_{index} r (by omega) (by omega)',
        '',
        'theorem runtime_digit_covariant (r : Nat) (hr : r < 12211) :',
        '    nearestDigit ((12100*r) % 12211) =',
        '      omegaMul (nearestDigit r) := by',
        '  exact of_decide_eq_true (by simpa [covarianceCheck] using',
        '    all_runtime_digits_covariant r hr)',
        '',
        '#print axioms runtime_digit_covariant',
        'end NearestOrbitCovariance',
    ]
    return '\n'.join(out)+'\n'


if __name__ == '__main__':
    (HERE/'NearestOrbitCovariance.lean').write_text(generate())
