// Exhaustive accuracy of the octant-reduced sine and cosine, and the notch
// response from float coefficients made with it and with sinf()/cosf(), each
// measured against coefficients computed exactly in double precision.
#include <complex.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>

static inline void poly_sin_cos(float w, float *s, float *c)
{
    static const float PI_4 = 0.785398163f, PI_3_4 = 2.35619449f;
    static const float PI_2_HI = 1.57079637f, PI_2_LO = -4.37113900e-08f;
    static const float PI_HI = 3.14159274f, PI_LO = -8.74227801e-08f;
    float y;
    int octant;
    if (w <= PI_4) {
        y = w;
        octant = 0;
    } else if (w < PI_3_4) {
        y = (w - PI_2_HI) - PI_2_LO;
        octant = 1;
    } else {
        y = (PI_HI - w) + PI_LO;
        octant = 2;
    }
    const float y2 = y * y;
    const float sy = y + y * y2 * (-1.666665077e-01f + y2 * (8.331978694e-03f + y2 * -1.949563593e-04f));
    const float cy = 1.0f + y2 * (-5.000000000e-01f + y2 * (4.166662320e-02f +
                     y2 * (-1.388676348e-03f + y2 * 2.439045056e-05f)));
    if (octant == 0) { *s = sy; *c = cy; }
    else if (octant == 1) { *s = cy; *c = -sy; }
    else { *s = sy; *c = -cy; }
}

struct coeff { double b0, b1, b2, a1, a2; };

static struct coeff coeffs_f(float s, float c, float A, float Q)
{
    const float alpha = s / (2 * Q);
    float b0 = 1.0f + alpha * (A * A), b1 = -2.0f * c, b2 = 1.0f - alpha * (A * A), a1 = b1, a2 = 1.0f - alpha;
    const float a0_inv = 1.0f / (1.0f + alpha);
    b0 *= a0_inv; b1 *= a0_inv; b2 *= a0_inv; a1 *= a0_inv; a2 *= a0_inv;
    return (struct coeff){ b0, b1, b2, a1, a2 };
}

static struct coeff coeffs_d(double w, double A, double Q)
{
    const double alpha = sin(w) / (2 * Q), a0 = 1 + alpha;
    return (struct coeff){ (1 + alpha * A * A) / a0, -2 * cos(w) / a0, (1 - alpha * A * A) / a0,
                           -2 * cos(w) / a0, (1 - alpha) / a0 };
}

static double gain_db(struct coeff k, double w)
{
    const double complex z1 = cexp(-I * w), z2 = z1 * z1;
    const double complex h = (k.b0 + k.b1 * z1 + k.b2 * z2) / (1.0 + k.a1 * z1 + k.a2 * z2);
    return 20 * log10(cabs(h));
}

int main(void)
{
    double max_s = 0, max_c = 0, max_rel = 0, lib_s = 0, lib_c = 0, lib_rel = 0;
    uint64_t n = 0;
    union { float f; uint32_t u; } v = { .f = 1e-4f };
    const float end = (float)M_PI;
    for (; v.f < end; v.u++) {
        float s, c;
        poly_sin_cos(v.f, &s, &c);
        const double ds = sin((double)v.f), dc = cos((double)v.f);
        const double es = fabs(s - ds), ec = fabs(c - dc), ls = fabs(sinf(v.f) - ds), lc = fabs(cosf(v.f) - dc);
        if (es > max_s) { max_s = es; }
        if (ec > max_c) { max_c = ec; }
        if (ls > lib_s) { lib_s = ls; }
        if (lc > lib_c) { lib_c = lc; }
        if (v.f < 3.0f) {
            if (es / ds > max_rel) { max_rel = es / ds; }
            if (ls / ds > lib_rel) { lib_rel = ls / ds; }
        }
        n++;
    }
    printf("angles %llu: poly max |sin err| %.2e, |cos err| %.2e, rel sin %.2e\n", (unsigned long long)n, max_s, max_c, max_rel);
    printf("               libm max |sin err| %.2e, |cos err| %.2e, rel sin %.2e\n", lib_s, lib_c, lib_rel);

    static const float rates[] = { 400, 1000, 1600, 2000, 3200, 4000, 8000 };
    static const float atten[] = { 10, 15, 25, 40, 60 };
    static const float qs[] = { 0.7f, 1.0f, 2.0f, 3.7f, 8.0f, 20.0f };
    printf("gain error against exact coefficients, dB (centre, then +-8%% of centre), worst case\n");
    printf("atten   cases   libm centre  poly centre   libm band   poly band\n");
    uint64_t unstable = 0;
    for (unsigned a = 0; a < 5; a++) {
        double lc = 0, pc = 0, lb = 0, pb = 0;
        uint64_t cases = 0;
        const float A = powf(10, -atten[a] / 40.0f);
        for (unsigned r = 0; r < 7; r++) {
            for (float f = 5.0f; f < 0.49f * rates[r]; f *= 1.003f) {
                const float w = 2.0f * (float)M_PI * f / rates[r];
                float ps, pcs;
                poly_sin_cos(w, &ps, &pcs);
                for (unsigned q = 0; q < 6; q++) {
                    const struct coeff e = coeffs_d(w, A, qs[q]);
                    const struct coeff p = coeffs_f(ps, pcs, A, qs[q]);
                    const struct coeff l = coeffs_f(sinf(w), cosf(w), A, qs[q]);
                    const double g = gain_db(e, w);
                    if (fabs(gain_db(l, w) - g) > lc) { lc = fabs(gain_db(l, w) - g); }
                    if (fabs(gain_db(p, w) - g) > pc) { pc = fabs(gain_db(p, w) - g); }
                    for (int k = -4; k <= 4; k++) {
                        if (k == 0) { continue; }
                        const double wk = w * (1 + k * 0.02);
                        if (wk <= 0 || wk >= M_PI) { continue; }
                        const double gk = gain_db(e, wk);
                        if (fabs(gain_db(l, wk) - gk) > lb) { lb = fabs(gain_db(l, wk) - gk); }
                        if (fabs(gain_db(p, wk) - gk) > pb) { pb = fabs(gain_db(p, wk) - gk); }
                    }
                    if (!(fabs(p.a2) < 1.0 && fabs(p.a1) < 1.0 + p.a2)) { unstable++; }
                    cases++;
                }
            }
        }
        printf("%3.0f dB %7llu   %10.4f  %10.4f  %10.4f  %10.4f\n", atten[a], (unsigned long long)cases, lc, pc, lb, pb);
    }
    printf("unstable coefficient sets from the polynomial: %llu\n", (unsigned long long)unstable);
    return 0;
}
