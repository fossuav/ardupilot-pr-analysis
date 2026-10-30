#!/bin/bash
# Run EK3HardLandingRearm at the PR head and with each EKF change taken out.
# usage: OUT=<dir> variants.sh <ArduPilot worktree checked out at a1fbfbcdc7>
# Every variant but "full" should FAIL. Results land in $OUT/variants.txt.
S=${OUT:-$PWD/variants-out}; mkdir -p $S
cd "${1:?usage: variants.sh <worktree at the PR head>}" || exit 1
export BUILDLOGS=$S/buildlogs
EKF=libraries/AP_NavEKF3
OUT=$S/variants.txt
: > $OUT

edit() {
    python3 - "$1" "$2" "$3" <<'EOF'
import sys
p, old, new = sys.argv[1:4]
s = open(p).read()
assert s.count(old) == 1, (p, old)
open(p, "w").write(s.replace(old, new))
EOF
}

run_variant() {
    name=$1
    if ! ./waf copter > $S/v_build_$name.log 2>&1; then
        echo "$name: BUILD FAILED" >> $OUT
    else
        rm -f logs/*.BIN
        timeout 1800 python3 Tools/autotest/autotest.py test.Copter.EK3HardLandingRearm > $S/v_test_$name.log 2>&1
        rc=$?
        res=$(grep -h "PASSED:\|FAILED:" $S/v_test_$name.log | head -1 | sed 's/(see .*//' | sed 's/.*EK3HardLandingRearm[^:]*: *//' | cut -c1-160)
        sub=$(grep -h ">>>> Subtest\|Subtest:" $S/v_test_$name.log | tail -1 | cut -c1-100)
        echo "$name: rc=$rc ${res:-PASSED} | $sub" >> $OUT
        mkdir -p $S/v_logs_$name && mv logs/*.BIN $S/v_logs_$name/ 2>/dev/null
    fi
    git checkout -- $EKF
}

O=$EKF/AP_NavEKF3_Outputs.cpp
P=$EKF/AP_NavEKF3_PosVelFusion.cpp

run_variant full

git diff upstream/master HEAD -- $EKF | git apply -R && run_variant master

edit $P "ftype dtBaro = (imuSampleTime_ms - hgtInnovFiltTime_ms) * 1.0e-3;" "ftype dtBaro = (imuSampleTime_ms - lastHgtPassTime_ms) * 1.0e-3;"
run_variant no_filter_fix

edit $O "    if (onGroundHgtError()) {
        dal.snprintf(failure_msg, failure_msg_len," "    if (false) {
        dal.snprintf(failure_msg, failure_msg_len,"
run_variant no_prearm_reason

edit $O "    const bool velDMeasured = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) ||
                              ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000);
    return ((PV_AidingMode == AID_NONE) || !velDMeasured) && (fabsF(hgtInnovFiltState) > 1.0f);" "    return (PV_AidingMode == AID_NONE) && (fabsF(hgtInnovFiltState) > 1.0f);"
run_variant no_aided_mode

edit $O "    const bool velDMeasured = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) ||
                              ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000);
    return ((PV_AidingMode == AID_NONE) || !velDMeasured) && (fabsF(hgtInnovFiltState) > 1.0f);" "    return (fabsF(hgtInnovFiltState) > 1.0f);"
run_variant no_exemption

git show 82abc5737b -- $EKF | git apply -R && run_variant no_rejected

./waf copter > /dev/null 2>&1
cat $OUT
