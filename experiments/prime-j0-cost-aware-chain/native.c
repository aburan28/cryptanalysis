/* Standalone cost-aware tau representative selector.  Operation counts only;
 * curve evaluation and timing are deliberately outside this module. */
#include <limits.h>
#include <stdint.h>

typedef __int128 i128;

typedef struct {
    int64_t a, b;
    uint32_t triples, mixed_adds, unit_rotations, weighted_cost;
} tau_choice;

typedef struct {
    int8_t a, b, power;
} digit;
typedef struct {
    i128 x, y;
} vec;

static i128 absi(i128 x) { return x < 0 ? -x : x; }

static i128 nearest(i128 a, i128 b)
{
    if (b < 0) {
        a = -a;
        b = -b;
    }
    return a < 0 ? -((-a + b / 2) / b) : (a + b / 2) / b;
}

static uint64_t root(uint64_t n)
{
    uint64_t lo = 0, hi = UINT64_C(1) << 32;
    while (lo + 1 < hi) {
        uint64_t mid = lo + (hi - lo) / 2;
        if (mid <= n / mid)
            lo = mid;
        else
            hi = mid;
    }
    return lo;
}

static int basis(uint64_t n, uint64_t lam, vec *v1, vec *v2, i128 *det)
{
    if (n < 5 || lam <= 1 || lam >= n) return 0;
    i128 r0 = n, r1 = lam, t0 = 0, t1 = 1;
    uint64_t limit = root(n);
    while (r1 > limit) {
        i128 q = r0 / r1;
        i128 r2 = r0 - q * r1, t2 = t0 - q * t1;
        r0 = r1;
        r1 = r2;
        t0 = t1;
        t1 = t2;
        if (!r1) return 0;
    }
    *v1 = (vec){r1, -t1};
    *v2 = (vec){r0, -t0};
    *det = v1->x * v2->y - v2->x * v1->y;
    return absi(*det) == (i128)n;
}

static unsigned mod9(int64_t x)
{
    int64_t r = x % 9;
    return (unsigned)(r < 0 ? r + 9 : r);
}

static int make_table(digit table[81])
{
    static const int8_t seeds[9][2] = {{1, 0}, {2, 0}, {4, 0}, {1, 1}, {2, 2},
                                       {1, 2}, {2, 4}, {2, 1}, {1, -2}};
    for (int i = 0; i < 81; i++) table[i] = (digit){0, 0, -1};
    int count = 0;
    for (int s = 0; s < 9; s++) {
        int a = seeds[s][0], b = seeds[s][1];
        for (int power = 0; power < 3; power++) {
            for (int sign = -1; sign <= 1; sign += 2) {
                int x = sign * a, y = sign * b;
                int slot = (int)(mod9(x) * 9 + mod9(y));
                if (mod9(x) % 3 == 0 || table[slot].power >= 0) return 0;
                table[slot] = (digit){(int8_t)x, (int8_t)y, (int8_t)power};
                count++;
            }
            int next_a = a + 3 * b, next_b = -a - 2 * b;
            a = next_a;
            b = next_b;
        }
    }
    return count == 54;
}

static int schedule(int64_t a, int64_t b, const digit table[81], tau_choice *out)
{
    uint32_t triples = 0, adds = 0, rotations = 0;
    for (unsigned i = 0; a || b; i++) {
        if (i >= 256) return 0;
        if (a % 3) {
            digit d = table[mod9(a) * 9 + mod9(b)];
            if (d.power < 0) return 0;
            a -= d.a;
            b -= d.b;
            triples = i / 2;
            adds++;
            rotations += (unsigned)((d.power + (i / 2) % 3) % 3 != 0);
        }
        if (a % 3) return 0;
        int64_t next_a = a + b, next_b = -a / 3;
        a = next_a;
        b = next_b;
    }
    out->triples = triples;
    out->mixed_adds = adds;
    out->unit_rotations = rotations;
    out->weighted_cost = 10 * triples + 16 * adds + rotations;
    return 1;
}

static uint64_t positive_mod(i128 x, uint64_t n)
{
    i128 r = x % n;
    return (uint64_t)(r < 0 ? r + n : r);
}

/* omega_lambda is the eigenvalue of omega, not tau.  Both outputs are exact
 * representatives of k modulo n; candidate cost never exceeds baseline. */
int tau_select(uint64_t n, uint64_t omega_lambda, uint64_t k, tau_choice *baseline,
               tau_choice *candidate)
{
    if (!baseline || !candidate || k >= n) return 0;
    vec v1, v2;
    i128 det;
    if (!basis(n, omega_lambda, &v1, &v2, &det)) return 0;
    digit table[81];
    if (!make_table(table)) return 0;
    i128 u0 = nearest((i128)k * v2.y, det);
    i128 v0 = nearest(-(i128)k * v1.y, det);
    i128 best_l1 = -1, selected_l1 = -1;
    uint64_t lam_tau = (uint64_t)(((i128)1 + n - omega_lambda) % n);
    for (int du = -2; du <= 2; du++) {
        for (int dv = -2; dv <= 2; dv++) {
            i128 u = u0 + du, v = v0 + dv;
            i128 x = (i128)k - u * v1.x - v * v2.x;
            i128 y = -u * v1.y - v * v2.y;
            i128 a = x + y, b = -y, l1 = absi(x) + absi(y);
            if (a < INT64_MIN || a > INT64_MAX || b < INT64_MIN || b > INT64_MAX) return 0;
            if (positive_mod(a + b * lam_tau - k, n)) return 0;
            tau_choice choice = {.a = (int64_t)a, .b = (int64_t)b};
            if (!schedule(choice.a, choice.b, table, &choice)) return 0;
            if (best_l1 < 0 || l1 < best_l1) {
                *baseline = choice;
                best_l1 = l1;
            }
            if (selected_l1 < 0 || choice.weighted_cost < candidate->weighted_cost ||
                (choice.weighted_cost == candidate->weighted_cost && l1 < selected_l1)) {
                *candidate = choice;
                selected_l1 = l1;
            }
        }
    }
    return candidate->weighted_cost <= baseline->weighted_cost;
}
