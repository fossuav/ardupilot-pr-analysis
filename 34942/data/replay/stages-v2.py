'''#34942's EKF3 changes as text edits, one stage per commit: python3 stages-v2.py <tree> <stage>

The PR head 3da7a8cf2e applies stages 1 2 3 4 5 G 6, in that order:
1 filter time step, 2 pre-arm reason and shared helper, 3 aided modes without an agreeing measured
vertical velocity, 4 rejected samples clipped at the gate, 5 stillness check diff cap, G skip the
height test while falling, 6 reset an impossible vertical velocity once on coming to rest.
Stage 7, the pre-arm hold while the vertical velocity is unconfirmed, is kept only to reproduce the
measured-and-rejected row in the README; it is not in the PR. Applies to upstream master 278a68a57a
and to the SFD beta refresh12 2e2936166d.
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
        "    // true when on the ground with a height error, unless aided with a measured vertical velocity agreeing\n")
    sub("AP_NavEKF3_core.h",
        "    bool onGroundHgtError(void) const;\n",
        "    bool onGroundHgtError(void) const;\n\n"
        "    // true when a recently fused measured velocity agrees with the state in the vertical\n"
        "    bool measuredVertVelAgrees(void) const;\n")
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
  innovation. Aided modes are excluded while a measured vertical velocity
  agrees with the state: the vertical velocity is then known good, and baro
  disturbances on the ground against it are a source of false positives.
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    if (!onGround) {
        return false;
    }
    return ((PV_AidingMode == AID_NONE) || !measuredVertVelAgrees()) && (fabsF(hgtInnovFiltState) > 1.0f);
}

/*
  return true when a measured velocity fused in the last 2 s agrees with the
  state in the vertical: GPS or external nav vertical velocity in an aided
  mode, or a body frame velocity, all three of whose axes must agree since a
  tilted vehicle puts the vertical on any of them. Being fused is not enough:
  with a small velocity variance a fused measurement barely moves the state,
  and past the gate it is rejected until the velocity timeout. The navigation
  velocity innovation changes only when a sample is fused, so the combined
  test ratio, which each tested sample sets, catches one rejected since.
*/
bool NavEKF3_core::measuredVertVelAgrees(void) const
{
    const bool navVelAgrees = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) && (fabsF(innovVelPos[2]) < 0.5f) &&
                              (velTestRatio < 1.0f);
    const bool bodyVelAgrees = ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000) &&
                               (norm(innovBodyVel[0], innovBodyVel[1], innovBodyVel[2]) < 0.5f);
    return navVelAgrees || bodyVelAgrees;
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
elif stage == "5":
    sub("AP_NavEKF3_Measurements.cpp",
        "    gyro_diff = 0.99f * gyro_diff + 0.01f * temp.length();\n",
        "    // a shock reads far beyond the limits, so cap what one sample adds, or the metric\n"
        "    // holds the check off for seconds after the vehicle has stopped\n"
        "    const ftype diff_cap = 2.0f * frontend->_ognmTestScaleFactor;\n"
        "    gyro_diff = 0.99f * gyro_diff + 0.01f * MIN(temp.length(), diff_cap * gyro_diff_limit);\n")
    sub("AP_NavEKF3_Measurements.cpp",
        "    accel_diff = 0.99f * accel_diff + 0.01f * temp.length();\n",
        "    accel_diff = 0.99f * accel_diff + 0.01f * MIN(temp.length(), diff_cap * accel_diff_limit);\n")
elif stage == "6":
    sub("AP_NavEKF3_PosVelFusion.cpp",
        """    // If we are operating without any aiding, fuse in constant position of constant
    // velocity measurements to constrain tilt drift. This assumes a non-manoeuvring
    // vehicle. Do this to coincide with the height fusion.
    fusingStationaryZeroVel = false;
""",
        """    // A disarmed vehicle the IMU reads as still is taken to have no vertical velocity, so one
    // the EKF reports with no measured vertical velocity agreeing, as after a drop whose impact
    // the IMU clipped, is reset away with the height when the vehicle comes to rest. Only then:
    // a velocity that builds while it stays still comes from an accel bias, which repeated
    // resets would stop the EKF learning.
    if (!onGroundNotMoving) {
        velDCheckedAtRest = false;
    } else if (fuseHgtData && !velDCheckedAtRest) {
        velDCheckedAtRest = true;
        if (!measuredVertVelAgrees() && (fabsF(stateStruct.velocity.z) > 0.5f)) {
            GCS_SEND_TEXT(MAV_SEVERITY_INFO, "EKF3 IMU%u vertical velocity reset at rest", (unsigned)imu_index);
            ResetHeight();
            fuseHgtData = false;
            // the vertical state now agrees with a still vehicle, so the disagreement filtered
            // before the reset no longer applies
            hgtInnovFiltState = 0.0f;
        }
    }

    // If we are operating without any aiding, fuse in constant position of constant
    // velocity measurements to constrain tilt drift. This assumes a non-manoeuvring
    // vehicle. Do this to coincide with the height fusion.
    fusingStationaryZeroVel = false;
""")
    sub("AP_NavEKF3_core.h",
        "    bool onGroundNotMoving;             // true when on the ground and not moving\n",
        "    bool onGroundNotMoving;             // true when on the ground and not moving\n"
        "    bool velDCheckedAtRest;             // true once the vertical velocity has been checked since the vehicle came to rest\n")
    sub("AP_NavEKF3_core.cpp",
        "    prevOnGround = true;\n",
        "    prevOnGround = true;\n"
        "    velDCheckedAtRest = false;\n")
elif stage == "G":
    # skip the ground height test while the vehicle falls
    sub("AP_NavEKF3_Outputs.cpp",
        """/*
  return true when on the ground with more than 1 m of filtered height
  innovation. Aided modes are excluded while a measured vertical velocity
  agrees with the state: the vertical velocity is then known good, and baro
  disturbances on the ground against it are a source of false positives.
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    if (!onGround) {
        return false;
    }
""",
        """/*
  return true when on the ground with more than 1 m of filtered height
  innovation. onGround only means disarmed, so a vehicle disarmed in the air
  is excluded while it falls freely, with over 0.5 g of filtered kinematic
  acceleration down, and the re-arm that could recover it is not refused.
  Aided modes are excluded while a measured vertical velocity agrees with
  the state: the vertical velocity is then known good, and baro
  disturbances on the ground against it are a source of false positives.
*/
bool NavEKF3_core::onGroundHgtError(void) const
{
    if (!onGround || (velDotNEDfilt.z > 0.5f * GRAVITY_MSS)) {
        return false;
    }
""")
    sub("AP_NavEKF3_core.h",
        "    // true when on the ground with a height error, unless aided with a measured vertical velocity agreeing\n",
        "    // true when on the ground and not falling with a height error, unless aided with a measured vertical velocity agreeing\n")
elif stage == "7":
    # hold arming while the vehicle is not yet still and reports a vertical velocity
    sub("AP_NavEKF3_Outputs.cpp",
        """    if (onGroundHgtError()) {
        dal.snprintf(failure_msg, failure_msg_len,""",
        """    if (onGround && (velDotNEDfilt.z < 0.5f * GRAVITY_MSS) && !measuredVertVelAgrees() &&
        (fabsF(stateStruct.velocity.z) > 0.5f)) {
        // disarmed and not falling, with a vertical velocity no measurement confirms, as after an
        // impact the IMU clipped: wait for the reset at rest or the height sensor to remove it
        dal.snprintf(failure_msg, failure_msg_len,
                     "EKF3[%u] settling, vel down %.1fm/s", unsigned(core_index)+1, stateStruct.velocity.z);
        return false;
    }

    if (onGroundHgtError()) {
        dal.snprintf(failure_msg, failure_msg_len,""")
else:
    raise SystemExit("unknown stage")
