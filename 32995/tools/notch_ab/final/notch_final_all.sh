#!/bin/bash
# Rename the helper on a fresh PR branch, then A/B three firmwares on the bench:
#   A  alpha2 031f2549, unchanged
#   R  A with only __ieee754_rem_pio2f moved to SRAM
#   F  A with calculate_sinf_cosf()
S=${NOTCH_AB_SCRATCH:?}
REPO=${NOTCH_AB_REPO:?}
PR_WT=$S/wt-sinf
AL_WT=$S/wt-alpha3
OUT=$S/notch-ab-final
WIN=${NOTCH_AB_DATA:?}-final
L=$OUT/logs
REG=libraries/AP_HAL_ChibiOS/rp2350/rp2350_ramfunc2_registry.txt
F=libraries/Filter/NotchFilter.cpp
mkdir -p "$OUT/A" "$OUT/R" "$OUT/F" "$L" "$WIN"
cd "$REPO" || exit 1

subs() {
    for p in $(git config -f .gitmodules --get-regexp 'submodule\..*\.path' | awk '{print $2}'); do
        if [ -e "$REPO/$p/.git" ] && [ "$p" != "modules/ChibiOS" ]; then
            git submodule update --init --reference "$REPO/$p" -- "$p" > /dev/null 2>&1 || git submodule update --init -- "$p" > /dev/null 2>&1
        fi
    done
    local pin
    pin=$(git ls-tree HEAD modules/ChibiOS | awk '{print $3}')
    git submodule update --init --reference "$REPO/modules/ChibiOS" -- modules/ChibiOS > /dev/null 2>&1
    if [ "$(git -C modules/ChibiOS rev-parse HEAD 2>/dev/null)" != "$pin" ]; then
        git -C modules/ChibiOS fetch -q https://github.com/ArduPilot/ChibiOS.git "$pin" \
            && git -C modules/ChibiOS checkout -q --detach "$pin" || { echo "ChibiOS pin failed"; exit 1; }
    fi
}

echo "=== rename on pr-notch-sinf-cosf"
git worktree add -q -b pr-notch-sinf-cosf "$PR_WT" 0d9b8c0005 || exit 1
cd "$PR_WT" || exit 1
git cherry-pick -n 13221e013c > /dev/null || exit 1
sed -i 's/calculate_sin_cos/calculate_sinf_cosf/g' "$F"
git add "$F"
[ "$(git diff --cached --name-only)" = "$F" ] || { echo "unexpected files"; exit 1; }
git commit -q -C 13221e013c || exit 1
FIX=$(git rev-parse HEAD)
git log -2 --format='  %h %an %s'
echo "  lines differing from the verified commit: $(git diff 13221e013c HEAD -- "$F" | grep -cE '^[-+][^-+]')  (old name left: $(grep -c calculate_sin_cos "$F"), new name: $(grep -c calculate_sinf_cosf "$F"))"
subs
if ./waf configure --board sitl > "$L/unit.log" 2>&1 && ./waf --targets tests/test_notchfilter >> "$L/unit.log" 2>&1 \
    && ./build/sitl/tests/test_notchfilter >> "$L/unit.log" 2>&1; then
    echo "  test_notchfilter: $(grep -E '\[  PASSED  \]' "$L/unit.log" | sed -n '$p'), failed $(grep -c '\[  FAILED  \]' "$L/unit.log")"
else
    echo "  unit test FAILED"; exit 1
fi
rm -f harmonicnotch_test.csv harmonicnotch_test2.csv
for b in MatekF405 MatekH743; do
    if ./waf configure --board "$b" > "$L/pr_$b.log" 2>&1 && ./waf copter >> "$L/pr_$b.log" 2>&1; then
        echo "  $b flash $(grep -E 'bin/arducopter +[0-9]+' "$L/pr_$b.log" | awk '{print $5}' | sed -n '$p'), warnings $(grep -c 'warning:' "$L/pr_$b.log")"
    else
        echo "  $b FAILED"; exit 1
    fi
done

echo "=== bench firmwares on alpha2"
cd "$REPO" || exit 1
git worktree add -q --detach "$AL_WT" 031f2549fb || exit 1
cd "$AL_WT" || exit 1
subs
cp "$S/notch-ab/A/arducopter.elf" "$S/notch-ab/A/arducopter.apj" "$OUT/A/"
build() {
    local tag=$1
    if ./waf configure --board RPI_UAVFC > "$L/$tag.log" 2>&1 && ./waf copter >> "$L/$tag.log" 2>&1; then
        cp build/RPI_UAVFC/bin/arducopter "$OUT/$tag/arducopter.elf"
        cp build/RPI_UAVFC/bin/arducopter.apj "$OUT/$tag/arducopter.apj"
        echo "  $tag $(git rev-parse --short=8 HEAD), warnings $(grep -c 'warning:' "$L/$tag.log"), $(grep -E 'bin/arducopter +[0-9]+' "$L/$tag.log" | tr -s ' ' | cut -d' ' -f2-5)"
    else
        echo "  $tag build FAILED, see $L/$tag.log"; exit 1
    fi
}
sed -i 's#^(archive)|lib_a-sf_cos.o.*#&\n(archive)|lib_a-ef_rem_pio2.o   \# __ieee754_rem_pio2f, bench test#' "$REG"
git diff --stat -- "$REG" | sed -n '$p'
git add "$REG"
git -c user.name=bench -c user.email=bench@localhost commit -q -m "bench only: __ieee754_rem_pio2f in SRAM" || exit 1
build R
git checkout -q --detach 031f2549fb || exit 1
git cherry-pick "$FIX" > /dev/null || exit 1
build F
for t in A R F; do
    E="$OUT/$t/arducopter.elf"
    echo "  $t: $(strings -a "$E" | grep -m1 -oE 'V4\.8\.0-dev \([0-9a-f]{8}\)'), rem_pio2f at $(arm-none-eabi-nm "$E" | awk '$3=="__ieee754_rem_pio2f" {print $1}'), trig calls in the Vector3f init: $(arm-none-eabi-objdump -dC --disassemble='NotchFilter<Vector3<float> >::init_with_A_and_Q(float, float, float, float)' "$E" 2>/dev/null | grep -cE 'bl.*<(_*sinf|_*cosf)')"
done

echo "=== harness"
for f in ab_session.py ab_run.py ab_analyse.py; do sed 's/notch-ab/notch-ab-final/g' "$S/notch-ab/$f" > "$OUT/$f"; done
cp "$S/notch-ab/notch_ab_rpm.lua" "$OUT/"
cp "$S/notch-ab/notch_ab_rpm.lua" "$WIN/"
python3 - "$OUT" <<'PY'
import sys
d = sys.argv[1]
p = d + "/ab_run.py"
s = open(p).read()
assert 'for tag in "AB":' in s
open(p, "w").write(s.replace('for tag in "AB":', 'for tag in sorted(set(sequence)):'))
p = d + "/ab_analyse.py"
s = open(p).read()
assert 'for t in "AB"}' in s and 'rt = win("RTDT", 2)' in s
s = s.replace('for t in "AB"}', 'for t in "ARF"}')
s = s.replace('rt = win("RTDT", 2)', 'rt = [m for t, m in r["RTDT"] if 3.5 <= t <= end - 0.2]')
head = s[:s.index('print("\\nby build')]
tail = '''print("\\nby build: mean of boots (min-max) [change from A]")
METRICS = (("core1 busy, PC samples", lambda r: r["c1"]["busy"]), ("core1 notch update", lambda r: r["c1"]["update"]),
           ("core1 trig (libm)", lambda r: r["c1"]["libm"]), ("core1 in flash", lambda r: r["c1"]["flash"]),
           ("core0 busy, PC samples", lambda r: r["c0"]["busy"]), ("RPLD C1", lambda r: r["log"]["C1"]),
           ("RPLD C0", lambda r: r["log"]["C0"]), ("XIP hit %", lambda r: r["log"]["XHit"]),
           ("worst armed rate gap ms", lambda r: r["log"]["dt_worst_ms"]))
for label, get in METRICS:
    parts, base = [], None
    for t in "ARF":
        v = [get(x) for x in rows if x["tag"] == t]
        if not v:
            continue
        m = st.mean(v)
        base = m if t == "A" else base
        parts.append(f"{t} {m:6.2f} ({min(v):.2f}-{max(v):.2f})" + ("" if t == "A" else f" [{m - base:+.2f}]"))
    print(f"  {label:24s} " + "   ".join(parts))
'''
open(p, "w").write(head + tail)
PY
python3 -m py_compile "$OUT/ab_session.py" "$OUT/ab_run.py" "$OUT/ab_analyse.py" || exit 1
rm -rf "$OUT/__pycache__"

echo "=== bench"
timeout 220 python.exe -u "$(wslpath -w "$OUT/ab_session.py")" setup 2>&1 | tr -d '\r' | grep -vE 'WARNING|^original'
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "setup failed"; exit 1; }
python3 "$OUT/ab_run.py" ARFFRAARF 2>&1 | tr -d '\r' | grep -vE 'fetched|text while|session done|disarm result|armed now|arm result'
RUN=${PIPESTATUS[0]}
echo "sequence exit=$RUN"
if [ "$RUN" -eq 0 ]; then
    ~/venv-ardupilot/bin/python "$OUT/ab_analyse.py" "$WIN" "$OUT" 2>&1
fi

echo "=== restore the bench"
timeout 180 python.exe -u "$(wslpath -w "$OUT/ab_session.py")" restore 2>&1 | tr -d '\r' | grep -v WARNING
timeout 240 python.exe "$(wslpath -w "$REPO/Tools/scripts/uploader.py")" --port COM15 "$(wslpath -w "$OUT/A/arducopter.apj")" > "$L/restore_upload.log" 2>&1
echo "restore upload exit=$?"
sleep_until=$((SECONDS + 12)); while [ $SECONDS -lt $sleep_until ]; do :; done
timeout 40 python.exe "$(wslpath -w "$S/board_check.py")" COM15 3 2>&1 | tr -d '\r' | grep -E '^(heartbeat:|firmware)' | cut -c1-120
powershell.exe -NoProfile -Command "'openocd left: ' + @(Get-Process openocd -ErrorAction SilentlyContinue).Count" 2>&1 | tr -d '\r'
echo "notch_final_all done"
