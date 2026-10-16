"""Isogeny-structure diagram for the study (editable source; renders outputs/structure.{svg,png})."""
import json
import twist
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

iso = json.loads((twist.OUT / 's00-small-isogenies.json').read_text())
fig, ax = plt.subplots(figsize=(10, 5.4)); ax.set_xlim(0, 10); ax.set_ylim(0, 6.4); ax.axis('off')
ax.add_patch(Circle((5, 5.0), 0.62, color='#3b6fb6'))
ax.text(5, 5.0, 'crater E0\nj = 1 (b = 1)', ha='center', va='center', color='w', fontsize=8.5)
ax.text(5, 6.05, 'a2 = 0: volcano-m83 E0, y²+xy=x³+1, n = ELL (81-bit), h = 4\n'
        'a2 = 1: EC1N83Ckb1a1haacb69ee9f37, y²+xy=x³+x²+1, n = 8569786107849059, h = 1128547018',
        ha='center', fontsize=7.5)
k7 = iso['a1_53bit']['7']['n_kernels']; k11 = iso['a1_53bit']['11']['n_kernels']
for side, lab in ((-1, 'ℓ = 7 (ramified): %d kernel\ncodomain a₆′ = 1 → E0' % k7),
                  (1, 'ℓ = 11 (split): %d kernels\ncodomains a₆′ = 1 → E0' % k11)):
    ax.add_patch(FancyArrowPatch((5 + side * 0.55, 5.3), (5 + side * 0.55, 4.7), connectionstyle='arc3,rad=%g' % (-2.2 * side),
                                 arrowstyle='->', mutation_scale=12, color='#333'))
    ax.text(5 + side * 2.5, 4.95, lab, ha='center', fontsize=8)
ax.text(5, 4.05, 'ℓ = 3, 5, 13: no rational kernel (exact factorisation of ψ_ℓ over GF(2^83), both twists)',
        ha='center', fontsize=8, color='#9e2a2b')
for i in range(15):
    x = 0.55 + i * 0.635
    ax.add_patch(FancyArrowPatch((5, 4.38), (x, 1.62), arrowstyle='-', color='#c8c8c8', lw=0.6))
    ax.add_patch(Circle((x, 1.5), 0.13, color='#e09f3e'))
ax.text(5, 2.9, 'descending ℓ = 6473 (inert, ℓ | conductor): 6474 kernel lines, verified Vélu maps in ../volcano-m83 Run-04',
        ha='center', fontsize=8, bbox=dict(fc='w', ec='none'))
ax.text(5, 0.75, 'floor: 6474 curves O00-00 … O77-82 (78 Frobenius orbits × 83), b = 1/j, j a root of the ring class polynomial mod 2\n'
        'the same j-set for both twists; floor curves are not defined over F₂, so Frobenius maps E_b → E_{b²}\n'
        'next level (ℓ = 53676929): no feasible construction (../volcano-m83 §18)', ha='center', fontsize=7.5)
ax.set_title('GF(2^83) Koblitz isogeny class: every small-degree rational isogeny is an endomorphism of E0', fontsize=10)
fig.tight_layout()
for ext in ('svg', 'png'):
    fig.savefig(twist.OUT / ('structure.%s' % ext), dpi=150)
