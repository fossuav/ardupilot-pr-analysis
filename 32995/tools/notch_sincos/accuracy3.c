// The notch response from the polynomial and from sinf()/cosf(), over the centre
// frequencies a vehicle actually uses, including this quad's own A and Q.
#define main accuracy2_main
#include "accuracy2.c"
#undef main
#include <stdlib.h>

static void quad_a_q(float centre, float bw, float atten, float *A, float *Q)
{
    *A = powf(10, -atten / 40.0f);
    const float octaves = log2f(centre / (centre - bw / 2.0f)) * 2.0f;
    *Q = sqrtf(powf(2, octaves)) / (powf(2, octaves) - 1.0f);
}

static void run(const char *name, const float *rates, unsigned nr, float fmin, const float *as, const float *qs, unsigned ncfg)
{
    double lc = 0, pc = 0, lb = 0, pb = 0, diff_c = 0, diff_b = 0;
    uint64_t cases = 0, same = 0;
    for (unsigned r = 0; r < nr; r++) {
        for (float f = fmin; f < 0.45f * rates[r]; f *= 1.001f) {
            const float w = 2.0f * (float)M_PI * f / rates[r];
            float ps, pcs;
            poly_sin_cos(w, &ps, &pcs);
            for (unsigned i = 0; i < ncfg; i++) {
                const struct coeff e = coeffs_d(w, as[i], qs[i]);
                const struct coeff p = coeffs_f(ps, pcs, as[i], qs[i]);
                const struct coeff l = coeffs_f(sinf(w), cosf(w), as[i], qs[i]);
                if (p.b0 == l.b0 && p.b1 == l.b1 && p.b2 == l.b2 && p.a2 == l.a2) { same++; }
                const double ge = gain_db(e, w), gl = gain_db(l, w), gp = gain_db(p, w);
                if (fabs(gl - ge) > lc) { lc = fabs(gl - ge); }
                if (fabs(gp - ge) > pc) { pc = fabs(gp - ge); }
                if (fabs(gp - gl) > diff_c) { diff_c = fabs(gp - gl); }
                for (int k = -4; k <= 4; k++) {
                    if (k == 0) { continue; }
                    const double wk = w * (1 + k * 0.02);
                    if (wk >= M_PI) { continue; }
                    const double gk = gain_db(e, wk), glk = gain_db(l, wk), gpk = gain_db(p, wk);
                    if (fabs(glk - gk) > lb) { lb = fabs(glk - gk); }
                    if (fabs(gpk - gk) > pb) { pb = fabs(gpk - gk); }
                    if (fabs(gpk - glk) > diff_b) { diff_b = fabs(gpk - glk); }
                }
                cases++;
            }
        }
    }
    printf("%s: %llu cases, %.0f%% identical coefficients\n", name, (unsigned long long)cases, 100.0 * same / cases);
    printf("  worst error against exact, dB: centre libm %.3f poly %.3f; +-8%% libm %.4f poly %.4f\n", lc, pc, lb, pb);
    printf("  worst poly-libm difference, dB: centre %.3f; +-8%% %.4f\n", diff_c, diff_b);
}

int main(int argc, char **argv)
{
    const float atten = atof(argv[1]), bw = atof(argv[2]), base = atof(argv[3]);
    float A, Q;
    quad_a_q(base, bw / 3.0f, atten, &A, &Q);
    printf("quad: INS_HNTCH_ATT %.0f, BW %.0f, FREQ %.0f, triple notch: A %.4f Q %.3f\n", atten, bw, base, A, Q);
    const float quad_rate[] = { 3201 };
    run("this quad's notch at 3201 Hz, 30 Hz up", quad_rate, 1, 30, &A, &Q, 1);

    const float rates[] = { 1000, 1600, 2000, 3200, 4000, 8000 };
    float as[12], qs[12];
    const float at[] = { 15, 25, 40 }, qv[] = { 1, 2, 4, 8 };
    for (unsigned i = 0; i < 12; i++) {
        as[i] = powf(10, -at[i % 3] / 40.0f);
        qs[i] = qv[i / 3];
    }
    run("general, 1-8 kHz, 15-40 dB, Q 1-8, 30 Hz up", rates, 6, 30, as, qs, 12);
    return 0;
}
