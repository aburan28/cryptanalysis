# Low-cost norm-seven branch screen

The first dual-orbit construction saved point-table slots, while the
six-map and nine-map schedules may populate several tau buckets in each
norm-seven branch. This follow-up fixes three smaller map sets before
screening them:

| Mode | Allowed endomorphisms beyond `1,tau,tau^2` |
| --- | --- |
| `rho0` | `rho` |
| `rho0_bar0` | `rho,rho_bar` |
| `rho0_bar012` | `rho,rho_bar,tau*rho_bar,tau^2*rho_bar` |

The first mode has one degree-seven bucket with no additional tau
sub-buckets. The second tests both split orientations with the same
constraint. The third probes whether extra conjugate images save enough
slots to offset their additional bucket work. All modes use the same
174,764 class universe, minimum-norm seed candidates, norm bound,
maximum-uncovered-gain greedy selector, and frozen 4,096-scalar design
panel as the preceding screen. Compare seed count against the exact
73,417-seed three-image reference as well as the 78,253-seed greedy
calibration. Charge all added bucket merges and norm-seven maps when
promoting a candidate.
