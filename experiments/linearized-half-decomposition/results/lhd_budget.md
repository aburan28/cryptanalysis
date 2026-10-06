| k | max l (linearization) | m | l | log2 columns | log2 relation phase | log2 LA | log2 total | vs rho |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 2 | 44 | 3 | 44 | 44 | 91.0 | 89.6 | 91.5 | +30.6 |
| 3 | 22 | 6 | 22 | 22 | 91.0 | 46.6 | 91.0 | +30.2 |
| 4 | 13 | 10 | 13 | 13 | 96.0 | 29.3 | 96.0 | +35.2 |

Best: k = 3, l = 22, total 2^91.0 against rho 2^60.81.
Asymptotically: relation phase 2^(n - (k-1) l) with l <= 2n/(k(k+1)) gives 2^(n(1 - 2(k-1)/(k(k+1)))) >= 2^(2n/3) for every k; the LA 2^(2l) is below it.
