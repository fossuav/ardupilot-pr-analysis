#!/bin/bash
# Exhaustive accuracy of sin_cos_0_to_pi() exactly as it stands in NotchFilter.cpp.
set -e
W=$1
OUT=$2
{
    echo '#include <cmath>'
    echo '#include <cstdint>'
    echo '#include <cstdio>'
    sed -n '/^__attribute__((always_inline)) static inline void sin_cos_0_to_pi/,/^}/p' "$W/libraries/Filter/NotchFilter.cpp"
    cat <<'EOF'
int main()
{
    double max_s = 0, max_c = 0;
    uint64_t n = 0;
    union { float f; uint32_t u; } v;
    v.f = 1e-4f;
    const float end = (float)M_PI;
    for (; v.f < end; v.u++) {
        float s, c;
        sin_cos_0_to_pi(v.f, s, c);
        const double es = fabs(s - sin((double)v.f)), ec = fabs(c - cos((double)v.f));
        if (es > max_s) { max_s = es; }
        if (ec > max_c) { max_c = ec; }
        n++;
    }
    printf("source helper, %llu angles: max |sin err| %.2e, max |cos err| %.2e\n", (unsigned long long)n, max_s, max_c);
    return (max_s < 1e-7 && max_c < 1e-7) ? 0 : 1;
}
EOF
} > "$OUT/source_check.cpp"
g++ -std=gnu++17 -O2 -ffp-contract=off "$OUT/source_check.cpp" -o "$OUT/source_check_nofma"
g++ -std=gnu++17 -O2 -mfma -ffp-contract=fast "$OUT/source_check.cpp" -o "$OUT/source_check_fma"
"$OUT/source_check_nofma"
"$OUT/source_check_fma"
