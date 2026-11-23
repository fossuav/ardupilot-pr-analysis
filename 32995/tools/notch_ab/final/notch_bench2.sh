#!/bin/bash
# Bench the review-fixed notch helper on alpha2, three firmwares over nine boots:
#   A  alpha2 031f2549, unchanged
#   F  the forced-inline helper, as measured before the review
#   G  the review-fixed helper, out of line with a RAM registry entry
S=${NOTCH_AB_SCRATCH:?}
REPO=${NOTCH_AB_REPO:?}
W=$S/wt-notch-review
AL=$S/wt-alpha3
OLD=$S/notch-ab-final
OUT=$S/notch-ab-final2
WIN=${NOTCH_AB_DATA:?}-final2
L=$OUT/logs
REG=libraries/AP_HAL_ChibiOS/rp2350/rp2350_ramfunc2_registry.txt
F=libraries/Filter/NotchFilter.cpp
NM=arm-none-eabi-nm
mkdir -p "$OUT/A" "$OUT/F" "$OUT/G" "$L" "$WIN"

cd "$REPO" || exit 1
[ -d "$AL" ] || git worktree add -q --detach "$AL" 031f2549fb || exit 1
cd "$AL" || exit 1
for p in $(git config -f .gitmodules --get-regexp 'submodule\..*\.path' | awk '{print $2}'); do
    if [ -e "$REPO/$p/.git" ] && [ "$p" != "modules/ChibiOS" ]; then
        git submodule update --init --reference "$REPO/$p" -- "$p" > /dev/null 2>&1 || git submodule update --init -- "$p" > /dev/null 2>&1
    fi
done
pin=$(git ls-tree HEAD modules/ChibiOS | awk '{print $3}')
git submodule update --init --reference "$REPO/modules/ChibiOS" -- modules/ChibiOS > /dev/null 2>&1
if [ "$(git -C modules/ChibiOS rev-parse HEAD 2>/dev/null)" != "$pin" ]; then
    git -C modules/ChibiOS fetch -q https://github.com/ArduPilot/ChibiOS.git "$pin" \
        && git -C modules/ChibiOS checkout -q --detach "$pin" || { echo "ChibiOS pin failed"; exit 1; }
fi

echo "=== firmware G"
git -C "$W" diff 5ec9286ba1 -- "$F" | git apply || { echo "patch failed"; exit 1; }
sed -i "s#^libraries/Filter/NotchFilter.cpp|NotchFilter<Vector3<float>>::init_with_A_and_Q.*#&\nlibraries/Filter/NotchFilter.cpp|calculate_sinf_cosf  \# review fix, bench only#" "$REG"
[ "$(grep -c 'calculate_sinf_cosf' "$REG")" = 1 ] || { echo "registry edit failed"; exit 1; }
if ! { ./waf configure --board RPI_UAVFC > "$L/G.log" 2>&1 && ./waf copter >> "$L/G.log" 2>&1; }; then
    echo "G build failed"; grep -E 'error|no symbol' "$L/G.log" | cut -c1-160 | sed -n 1,6p; exit 1
fi
cp build/RPI_UAVFC/bin/arducopter "$OUT/G/arducopter.elf"
cp build/RPI_UAVFC/bin/arducopter.apj "$OUT/G/arducopter.apj"
cp "$OLD/A/arducopter.elf" "$OLD/A/arducopter.apj" "$OUT/A/"
cp "$OLD/F/arducopter.elf" "$OLD/F/arducopter.apj" "$OUT/F/"
echo "  changed from alpha2: $(git status --short | grep -v '^??' | awk '{print $2}' | tr '\n' ' ')"
echo "  helper: $($NM -S -C "$OUT/G/arducopter.elf" | grep calculate_sinf_cosf)"
echo "  size: $(grep -E 'bin/arducopter +[0-9]+' "$L/G.log" | sed -n '$p' | awk '{print $2, $3, $4, $5}'), warnings $(grep -c 'warning:' "$L/G.log")"
for t in A F G; do
    echo "  $t: $(strings -a "$OUT/$t/arducopter.elf" | grep -m1 -oE 'V4\.8\.0-dev \([0-9a-f]{8}\)'), libm calls in the Vector3f init: $(arm-none-eabi-objdump -d -C "$OUT/$t/arducopter.elf" | awk '/^[0-9a-f]+ <NotchFilter<Vector3<float> >::init_with_A_and_Q/{f=1} f&&/^$/{exit} f' | grep -cE '<(sinf|cosf)')"
done

echo "=== harness"
for f in ab_session.py ab_run.py ab_analyse.py; do sed 's/notch-ab-final/notch-ab-final2/g' "$OLD/$f" > "$OUT/$f"; done
cp "$OLD/notch_ab_rpm.lua" "$OUT/"
cp "$OLD/notch_ab_rpm.lua" "$WIN/"
python3 - "$OUT/ab_analyse.py" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
assert 'UPDATE = re.compile(r"(NotchFilter<' in s and '"ARF"' in s
s = s.replace('UPDATE = re.compile(r"(NotchFilter<', 'UPDATE = re.compile(r"(calculate_sinf_cosf|NotchFilter<')
s = s.replace('"ARF"', '"AFG"')
open(p, "w").write(s)
PY
python3 -m py_compile "$OUT/ab_session.py" "$OUT/ab_run.py" "$OUT/ab_analyse.py" || exit 1
rm -rf "$OUT/__pycache__"

echo "=== bench"
timeout 220 python.exe -u "$(wslpath -w "$OUT/ab_session.py")" setup 2>&1 | tr -d '\r' | grep -vE 'WARNING|^original'
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "setup failed"; exit 1; }
python3 "$OUT/ab_run.py" AFGGFAAGF 2>&1 | tr -d '\r' | grep -vE 'fetched|text while|session done|disarm result|armed now|arm result'
RUN=${PIPESTATUS[0]}
echo "sequence exit=$RUN"
if [ "$RUN" -eq 0 ]; then
    ~/venv-ardupilot/bin/python "$OUT/ab_analyse.py" "$WIN" "$OUT" 2>&1
fi

echo "=== restore the bench"
timeout 180 python.exe -u "$(wslpath -w "$OUT/ab_session.py")" restore 2>&1 | tr -d '\r' | grep -v WARNING
timeout 240 python.exe "$(wslpath -w "$REPO/Tools/scripts/uploader.py")" --port COM15 "$(wslpath -w "$OUT/A/arducopter.apj")" > "$L/restore_upload.log" 2>&1
echo "restore upload exit=$?"
wait_until=$((SECONDS + 12)); while [ $SECONDS -lt $wait_until ]; do :; done
timeout 40 python.exe "$(wslpath -w "$S/board_check.py")" COM15 3 2>&1 | tr -d '\r' | grep -E '^(heartbeat:|firmware)' | cut -c1-120
powershell.exe -NoProfile -Command "'openocd left: ' + @(Get-Process openocd -ErrorAction SilentlyContinue).Count" 2>&1 | tr -d '\r'
echo "notch_bench2 done"
