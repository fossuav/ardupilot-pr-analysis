// Accuracy of a notch sine/cosine helper taken directly from source, against
// exact values and against libm's sinf()/cosf(): every float angle from 1e-4 to
// pi, the steps where the reduction changes branch, and the notch response.
//
// g++ -std=gnu++17 -O2 -ffp-contract=off -DCANDIDATE_H='"candidate.h"' accuracy_source.cpp
// where candidate.h defines: void candidate(float angle, float &sin_out, float &cos_out)
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdio>

#include CANDIDATE_H

struct Worst {
    double abs_err = 0, rel_err = 0, ulp_err = 0, at = 0;
    void add(float value, double exact, float angle)
    {
        const double e = fabs(double(value) - exact);
        if (e > abs_err) {
            abs_err = e;
            at = angle;
        }
        if (exact != 0 && e / fabs(exact) > rel_err) {
            rel_err = e / fabs(exact);
        }
        const float ef = fabsf(float(exact));
        const double ulp = double(nextafterf(ef, INFINITY)) - double(ef);
        if (e / ulp > ulp_err) {
            ulp_err = e / ulp;
        }
    }
};

struct Coeff {
    double b0, b1, b2, a1, a2;
};

// the same single precision arithmetic as NotchFilter::init_with_A_and_Q()
static Coeff coeffs_f(float s, float c, float A, float Q)
{
    const float alpha = s / (2 * Q);
    float b0 = 1.0f + alpha * (A * A), b1 = -2.0f * c, b2 = 1.0f - alpha * (A * A), a1 = b1, a2 = 1.0f - alpha;
    const float a0_inv = 1.0f / (1.0f + alpha);
    b0 *= a0_inv;
    b1 *= a0_inv;
    b2 *= a0_inv;
    a1 *= a0_inv;
    a2 *= a0_inv;
    return {b0, b1, b2, a1, a2};
}

static Coeff coeffs_d(double w, double A, double Q)
{
    const double alpha = sin(w) / (2 * Q), a0 = 1 + alpha;
    return {(1 + alpha * A * A) / a0, -2 * cos(w) / a0, (1 - alpha * A * A) / a0, -2 * cos(w) / a0, (1 - alpha) / a0};
}

static double gain_db(const Coeff &k, double w)
{
    const std::complex<double> z1 = std::polar(1.0, -w), z2 = z1 * z1;
    return 20 * log10(std::abs((k.b0 + k.b1 * z1 + k.b2 * z2) / (1.0 + k.a1 * z1 + k.a2 * z2)));
}

static void exhaustive()
{
    Worst s, c, ls, lc;
    uint64_t n = 0;
    union {
        float f;
        uint32_t u;
    } v;
    v.f = 1e-4f;
    const float end = float(M_PI);
    while (true) {
        float ps, pc;
        candidate(v.f, ps, pc);
        const double ds = sin(double(v.f)), dc = cos(double(v.f));
        s.add(ps, ds, v.f);
        c.add(pc, dc, v.f);
        ls.add(sinf(v.f), ds, v.f);
        lc.add(cosf(v.f), dc, v.f);
        n++;
        if (v.f >= end) {
            break;
        }
        v.u++;
    }
    printf("%llu angles from 1e-4 to pi\n", (unsigned long long)n);
    printf("  helper sin: abs %.2e (at %.5f), rel %.2e, %.2f ulp\n", s.abs_err, s.at, s.rel_err, s.ulp_err);
    printf("  helper cos: abs %.2e (at %.5f), rel %.2e, %.2f ulp\n", c.abs_err, c.at, c.rel_err, c.ulp_err);
    printf("  libm   sin: abs %.2e, rel %.2e, %.2f ulp\n", ls.abs_err, ls.rel_err, ls.ulp_err);
    printf("  libm   cos: abs %.2e, rel %.2e, %.2f ulp\n", lc.abs_err, lc.rel_err, lc.ulp_err);
}

static void branch_steps()
{
    double worst = 0;
    for (const double edge : {M_PI / 4, 3 * M_PI / 4}) {
        float a = float(edge);
        for (int i = 0; i < 2000; i++) {
            a = nextafterf(a, 0.0f);
        }
        for (int i = 0; i < 4000; i++) {
            const float b = nextafterf(a, 10.0f);
            float sa, ca, sb, cb;
            candidate(a, sa, ca);
            candidate(b, sb, cb);
            const double ds = (double(sb) - double(sa)) - (sin(double(b)) - sin(double(a)));
            const double dc = (double(cb) - double(ca)) - (cos(double(b)) - cos(double(a)));
            worst = fmax(worst, fmax(fabs(ds), fabs(dc)));
            a = b;
        }
    }
    printf("largest unwanted step between adjacent angles at a branch change: %.2e\n", worst);
}

template <size_t NR, size_t NA, size_t NQ>
static void response(const char *name, const float (&rates)[NR], float fmin, float fmax_of_rate,
                     const float (&atten)[NA], const float (&qs)[NQ])
{
    double centre = 0, band = 0, lib_centre = 0, lib_band = 0, diff_centre = 0, diff_band = 0;
    uint64_t cases = 0, same = 0, unstable = 0;
    for (const float rate : rates) {
        for (float f = fmin; f < fmax_of_rate * rate; f *= 1.003f) {
            const float w = 2.0f * float(M_PI) * f / rate;
            float ps, pc;
            candidate(w, ps, pc);
            const float ls = sinf(w), lc = cosf(w);
            for (const float at : atten) {
                const float A = powf(10, -at / 40.0f);
                for (const float Q : qs) {
                    const Coeff e = coeffs_d(w, A, Q), p = coeffs_f(ps, pc, A, Q), l = coeffs_f(ls, lc, A, Q);
                    same += (p.b0 == l.b0 && p.b1 == l.b1 && p.b2 == l.b2 && p.a2 == l.a2);
                    unstable += !(fabs(p.a2) < 1.0 && fabs(p.a1) < 1.0 + p.a2);
                    const double g = gain_db(e, w), gp = gain_db(p, w), gl = gain_db(l, w);
                    centre = fmax(centre, fabs(gp - g));
                    lib_centre = fmax(lib_centre, fabs(gl - g));
                    diff_centre = fmax(diff_centre, fabs(gp - gl));
                    for (int k = -4; k <= 4; k++) {
                        const double wk = w * (1 + k * 0.02);
                        if (k == 0 || wk >= M_PI) {
                            continue;
                        }
                        const double gk = gain_db(e, wk), gpk = gain_db(p, wk), glk = gain_db(l, wk);
                        band = fmax(band, fabs(gpk - gk));
                        lib_band = fmax(lib_band, fabs(glk - gk));
                        diff_band = fmax(diff_band, fabs(gpk - glk));
                    }
                    cases++;
                }
            }
        }
    }
    printf("%s: %llu cases, %.1f%% of coefficient sets identical to libm's, %llu unstable\n", name,
           (unsigned long long)cases, 100.0 * same / cases, (unsigned long long)unstable);
    printf("  at the centre:  error against exact, helper %.4f dB, libm %.4f dB; helper against libm %.4f dB\n",
           centre, lib_centre, diff_centre);
    printf("  within +-8%%:    error against exact, helper %.4f dB, libm %.4f dB; helper against libm %.4f dB\n",
           band, lib_band, diff_band);
}

int main()
{
    exhaustive();
    branch_steps();
    const float flight_rates[] = {1000, 1600, 2000, 3200, 3201, 4000, 8000};
    const float flight_atten[] = {15, 25, 40};
    const float flight_q[] = {1.0f, 2.0f, 4.0f, 8.0f, 11.7f};
    response("typical notches, 1-8 kHz, 30 Hz to 0.45 of the rate, 15-40 dB, Q 1-11.7", flight_rates, 30.0f, 0.45f,
             flight_atten, flight_q);
    const float all_rates[] = {400, 1000, 1600, 2000, 3200, 3201, 4000, 8000};
    const float all_atten[] = {10, 15, 25, 40, 60};
    const float all_q[] = {0.7f, 1.0f, 2.0f, 3.7f, 8.0f, 11.7f, 20.0f};
    response("extreme notches, 400 Hz-8 kHz, 5 Hz to 0.49 of the rate, 10-60 dB, Q 0.7-20", all_rates, 5.0f, 0.49f,
             all_atten, all_q);
    return 0;
}
