'''Apply #34942's EKF3 changes to an ArduPilot tree by text edit, one stage per commit.

usage: python3 stages.py <tree> <1|2|3|4>

The stages are the EKF content of the PR's first four commits at a1fbfbcdc7.
They apply unchanged to upstream master 278a68a57a and to the SFD beta
refresh12 2e2936166d, which is how the Replay build for this record was
made: git am -3 of the PR's patches does not apply to refresh12 at stage 3.
'''
import sys

root = sys.argv[1] + "/libraries/AP_NavEKF3/"
stage = sys.argv[2]


def sub(name, old, new):
    p = root + name
    s = open(p).read()
    assert s.count(old) == 1, (name, old)
    open(p, "w").write(s.replace(old, new))


if stage == "1":
    # the filter keeps its own update time
    sub("AP_NavEKF3_core.h",
        "    ftype hgtInnovFiltState;        // state used for fitering of the height innovations used for pre-flight checks\n",
        "    ftype hgtInnovFiltState;        // state used for fitering of the height innovations used for pre-flight checks\n"
        "    uint32_t hgtInnovFiltTime_ms;   // time stamp when the height innovation filter last ran (msec)\n")
    sub("AP_NavEKF3_core.cpp",
        "    hgtInnovFiltState = 0.0f;\n",
        "    hgtInnovFiltState = 0.0f;\n    hgtInnovFiltTime_ms = 0;\n")
    sub("AP_NavEKF3_PosVelFusion.cpp",
        "    hgtTimeout = false;\n    lastHgtPassTime_ms = imuSampleTime_ms;\n",
        "    hgtTimeout = false;\n    lastHgtPassTime_ms = imuSampleTime_ms;\n    hgtInnovFiltTime_ms = imuSampleTime_ms;\n")
    sub("AP_NavEKF3_PosVelFusion.cpp",
        """                if (onGround) {
                    ftype dtBaro = (imuSampleTime_ms - lastHgtPassTime_ms) * 1.0e-3;
                    const ftype hgtInnovFiltTC = 2.0;
                    ftype alpha = constrain_ftype(dtBaro/(dtBaro+hgtInnovFiltTC), 0.0, 1.0);
                    hgtInnovFiltState += (innovVelPos[5] - hgtInnovFiltState)*alpha;
                } else {
                    hgtInnovFiltState = 0.0f;
                }
""",
        """                if (onGround) {
                    ftype dtBaro = (imuSampleTime_ms - hgtInnovFiltTime_ms) * 1.0e-3;
                    const ftype hgtInnovFiltTC = 2.0;
                    ftype alpha = constrain_ftype(dtBaro/(dtBaro+hgtInnovFiltTC), 0.0, 1.0);
                    hgtInnovFiltState += (innovVelPos[5] - hgtInnovFiltState)*alpha;
                } else {
                    hgtInnovFiltState = 0.0f;
                }
                hgtInnovFiltTime_ms = imuSampleTime_ms;
""")

elif stage == "2":
    # one helper for the height test, shared by healthy() and the pre-arm reason
    sub("AP_NavEKF3_core.h",
        """    // should we assume zero sideslip?
    bool assume_zero_sideslip(void) const;
""",
        """    // should we assume zero sideslip?
    bool assume_zero_sideslip(void) const;

    // true when on the ground with a height error that healthy() fails on
    bool onGroundHgtError(void) const;
""")
    sub("AP_NavEKF3_Outputs.cpp",
        """    // position and height innovations must be within limits when on-ground and in a static mode of operation
    float horizErrSq = sq(innovVelPos[3]) + sq(innovVelPos[4]);
    if (onGround && (PV_AidingMode == AID_NONE) && ((horizErrSq > 1.0f) || (fabsF(hgtInnovFiltState) > 1.0f))) {
        return false;
    }
""",
        """    // position and height innovations must be within limits when on-ground and in a static mode of operation
    float horizErrSq = sq(innovVelPos[3]) + sq(innovVelPos[4]);
    if (onGround && (PV_AidingMode == AID_NONE) && (horizErrSq > 1.0f)) {
        return false;
    }
    if (onGroundHgtError()) {
        return false;
    }
""")
    sub("AP_NavEKF3_Outputs.cpp",
        """/*
  per-core pre-arm checks.""",
        """/*
  return true when on the ground and not navigating with more than 1 m of
  filtered height innovation
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    return onGround && (PV_AidingMode == AID_NONE) && (fabsF(hgtInnovFiltState) > 1.0f);
}

/*
  per-core pre-arm checks.""")
    sub("AP_NavEKF3_Outputs.cpp",
        """                         "EKF3[%u] vel error %.1f", unsigned(core_index)+1, hvel_innovation);
            return false;
        }
    }

    // all OK""",
        """                         "EKF3[%u] vel error %.1f", unsigned(core_index)+1, hvel_innovation);
            return false;
        }
    }

    if (onGroundHgtError()) {
        dal.snprintf(failure_msg, failure_msg_len,
                     "EKF3[%u] height error %.1fm", unsigned(core_index)+1, fabsF(hgtInnovFiltState));
        return false;
    }

    // all OK""")
    sub("AP_NavEKF3.cpp",
        """    for (uint8_t i = 0; i < num_cores; i++) {
        if (!core[i].healthy()) {
            const char *failure = core[i].prearm_failure_reason();
            if (failure != nullptr) {
                dal.snprintf(failure_msg, failure_msg_len, failure);
            } else {
                dal.snprintf(failure_msg, failure_msg_len, "EKF3 core %d unhealthy", (int)i);
            }
            return false;
        }
        // run per-core pre-arm checks
        if (!core[i].pre_arm_check(requires_position, failure_msg, failure_msg_len)) {
            return false;
        }
    }""",
        """    for (uint8_t i = 0; i < num_cores; i++) {
        // run per-core pre-arm checks first, as their reasons are more specific than an unhealthy core's
        if (!core[i].pre_arm_check(requires_position, failure_msg, failure_msg_len)) {
            return false;
        }
        if (!core[i].healthy()) {
            const char *failure = core[i].prearm_failure_reason();
            if (failure != nullptr) {
                dal.snprintf(failure_msg, failure_msg_len, failure);
            } else {
                dal.snprintf(failure_msg, failure_msg_len, "EKF3 core %d unhealthy", (int)i);
            }
            return false;
        }
    }""")

elif stage == "3":
    # aided modes, while no vertical velocity measurement is being fused
    sub("AP_NavEKF3_core.h",
        "    uint32_t lastVelPassTime_ms;    // time stamp when GPS velocity measurement last passed innovation consistency check (msec)\n",
        "    uint32_t lastVelPassTime_ms;    // time stamp when GPS velocity measurement last passed innovation consistency check (msec)\n"
        "    uint32_t lastVelDFuseTime_ms;   // time stamp when a measured vertical velocity was last fused (msec)\n")
    sub("AP_NavEKF3_core.h",
        "    // true when on the ground with a height error that healthy() fails on\n",
        "    // true when on the ground with a height error and no measured vertical velocity to correct it\n")
    sub("AP_NavEKF3_core.cpp",
        "    lastVelPassTime_ms = 0;\n",
        "    lastVelPassTime_ms = 0;\n    lastVelDFuseTime_ms = 0;\n")
    sub("AP_NavEKF3_PosVelFusion.cpp",
        """            if (fuseVelVertData || fusingStationaryZeroVel) {
                fuseData[2] = true;
            }
        }
""",
        """            if (fuseVelVertData || fusingStationaryZeroVel) {
                fuseData[2] = true;
            }
            if (fuseVelVertData && !fusingStationaryZeroVel && (PV_AidingMode != AID_NONE)) {
                lastVelDFuseTime_ms = imuSampleTime_ms;
            }
        }
""")
    sub("AP_NavEKF3_Outputs.cpp",
        """/*
  return true when on the ground and not navigating with more than 1 m of
  filtered height innovation
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    return onGround && (PV_AidingMode == AID_NONE) && (fabsF(hgtInnovFiltState) > 1.0f);
}
""",
        """/*
  return true when on the ground with more than 1 m of filtered height
  innovation and no measured vertical velocity. Aided modes are included
  only while no vertical velocity is being measured: a GPS or external nav
  vertical velocity, or a body frame velocity, corrects the error itself,
  and baro disturbances on the ground against it are a source of false
  positives.
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    if (!onGround) {
        return false;
    }
    const bool velDMeasured = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) ||
                              ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000);
    return ((PV_AidingMode == AID_NONE) || !velDMeasured) && (fabsF(hgtInnovFiltState) > 1.0f);
}
""")

elif stage == "4":
    # every height sample on the ground, rejected ones counted up to the gate
    sub("AP_NavEKF3_PosVelFusion.cpp",
        """            // Use height data if innovation check passed or timed out or if bad IMU data
            // Always fuse data if bad IMU to prevent aliasing and clipping pulling the state estimate away
            // from the measurement un-opposed if test threshold is exceeded.
            if (hgtCheckPassed || hgtTimeout || badIMUdata) {
                // Calculate a filtered value to be used by pre-flight health checks
                // We need to filter because wind gusts can generate significant baro noise and we want to be able to detect bias errors in the inertial solution
                if (onGround) {
                    ftype dtBaro = (imuSampleTime_ms - hgtInnovFiltTime_ms) * 1.0e-3;
                    const ftype hgtInnovFiltTC = 2.0;
                    ftype alpha = constrain_ftype(dtBaro/(dtBaro+hgtInnovFiltTC), 0.0, 1.0);
                    hgtInnovFiltState += (innovVelPos[5] - hgtInnovFiltState)*alpha;
                } else {
                    hgtInnovFiltState = 0.0f;
                }
                hgtInnovFiltTime_ms = imuSampleTime_ms;

                if (hgtTimeout) {""",
        """            // Calculate a filtered value to be used by pre-flight health checks
            // We need to filter because wind gusts can generate significant baro noise and we want to be able to detect bias errors in the inertial solution
            // Samples the gate rejects count up to the gate, so a sustained disagreement fails the checks and a single outlier does not
            if (onGround) {
                const ftype innovLimit = sqrtF(maxTestRatio * varInnovVelPos[5]) * MAX(0.01 * (ftype)frontend->_hgtInnovGate, 1.0);
                ftype dtBaro = (imuSampleTime_ms - hgtInnovFiltTime_ms) * 1.0e-3;
                const ftype hgtInnovFiltTC = 2.0;
                ftype alpha = constrain_ftype(dtBaro/(dtBaro+hgtInnovFiltTC), 0.0, 1.0);
                hgtInnovFiltState += (constrain_ftype(innovVelPos[5], -innovLimit, innovLimit) - hgtInnovFiltState)*alpha;
            } else {
                hgtInnovFiltState = 0.0f;
            }
            hgtInnovFiltTime_ms = imuSampleTime_ms;

            // Use height data if innovation check passed or timed out or if bad IMU data
            // Always fuse data if bad IMU to prevent aliasing and clipping pulling the state estimate away
            // from the measurement un-opposed if test threshold is exceeded.
            if (hgtCheckPassed || hgtTimeout || badIMUdata) {
                if (hgtTimeout) {""")
else:
    raise SystemExit("unknown stage")
