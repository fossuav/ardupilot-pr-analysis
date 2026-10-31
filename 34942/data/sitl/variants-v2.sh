#!/bin/bash
# Run EK3HardLandingRearm at the PR head 3da7a8cf2e and with each EKF change taken out.
# usage: OUT=<dir> variants-v2.sh <ArduPilot worktree checked out at 3da7a8cf2e>
# Every variant but "full" and "no_test_ratio" (which SITL cannot reach) should FAIL.
S=${OUT:-$PWD/variants-out}; mkdir -p $S
cd "${1:?usage: variants-v2.sh <worktree at the PR head>}" || exit 1
export BUILDLOGS=$S/buildlogs
EKF=libraries/AP_NavEKF3
O=$EKF/AP_NavEKF3_Outputs.cpp
P=$EKF/AP_NavEKF3_PosVelFusion.cpp
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
        rm -rf logs
        timeout 2400 python3 Tools/autotest/autotest.py test.Copter.EK3HardLandingRearm > $S/v_test_$name.log 2>&1
        rc=$?
        res=$(grep -h "PASSED:\|FAILED:" $S/v_test_$name.log | head -1 | sed 's/(see .*//' | sed 's/.*vertical state wrong)"//' | cut -c1-150)
        sub=$(grep -o "Subtest [0-9]*: [^(]*\|#### [A-Za-z:]*.*####" $S/v_test_$name.log | tail -1 | cut -c1-110)
        echo "$name: rc=$rc ${res:-PASSED} | $sub" >> $OUT
    fi
    git checkout -- $EKF
}

run_variant full
# no_cap: SITL cannot produce the shock the cap is for
edit $O "    return navVelAgrees || bodyVelAgrees;" "    return false && (navVelAgrees || bodyVelAgrees);"
run_variant no_exemption
git diff 278a68a57a HEAD -- $EKF | git apply -R && run_variant master
edit $P "ftype dtBaro = (imuSampleTime_ms - hgtInnovFiltTime_ms) * 1.0e-3;" "ftype dtBaro = (imuSampleTime_ms - lastHgtPassTime_ms) * 1.0e-3;"
run_variant no_filter_fix
edit $O "    if (onGroundHgtError()) {
        dal.snprintf(failure_msg, failure_msg_len," "    if (false) {
        dal.snprintf(failure_msg, failure_msg_len,"
run_variant no_prearm_reason
edit $O "    return ((PV_AidingMode == AID_NONE) || !measuredVertVelAgrees()) && (fabsF(hgtInnovFiltState) > 1.0f);" "    return (PV_AidingMode == AID_NONE) && (fabsF(hgtInnovFiltState) > 1.0f);"
run_variant no_aided_mode
edit $O "    const bool navVelAgrees = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) && (fabsF(innovVelPos[2]) < 0.5f) &&
                              (velTestRatio < 1.0f);
    const bool bodyVelAgrees = ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000) &&
                               (norm(innovBodyVel[0], innovBodyVel[1], innovBodyVel[2]) < 0.5f);" "    const bool navVelAgrees = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000);
    const bool bodyVelAgrees = ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000);"
run_variant exempt_if_fused
edit $O "(fabsF(innovVelPos[2]) < 0.5f) &&
                              (velTestRatio < 1.0f);" "(fabsF(innovVelPos[2]) < 0.5f);"
run_variant no_test_ratio
git show c7fc88ce75 -- $EKF | git apply -R && run_variant no_rejected
edit $P "    } else if (fuseHgtData && !velDCheckedAtRest) {" "    } else if (false) {"
run_variant no_still_reset
edit $O "    if (!onGround || (velDotNEDfilt.z > 0.5f * GRAVITY_MSS)) {" "    if (!onGround) {"
run_variant no_fall_skip
./waf copter > /dev/null 2>&1
cat $OUT
