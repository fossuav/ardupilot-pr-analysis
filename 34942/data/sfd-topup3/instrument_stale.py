#!/usr/bin/env python3
"""Instrument #34942's rest reset on refresh12 for Replay (scratch only).

Writes an XKFM-layout record per core, core + 50, at the EKF log rate:
  ongroundnotmoving (flags): 1 measuredVertVelAgrees, 2 nav part, 4 body part,
      8 onGround, 16 onGroundNotMoving, 32 velDCheckedAtRest, 64 inFlight,
      128 onGroundHgtError
  gyro_length_ratio:  seconds since lastVelDFuseTime_ms
  accel_length_ratio: innovVelPos[2]
  gyro_diff_ratio:    stateStruct.velocity.z
  accel_diff_ratio:   rest resets so far + 1000 * rest checks so far
and counts each rest check (velDCheckedAtRest set) and each reset.
usage: instrument_stale.py <tree>
"""
import sys

root = sys.argv[1] + "/libraries/AP_NavEKF3/"


def sub(name, old, new):
    p = root + name
    s = open(p).read()
    assert s.count(old) == 1, (name, old)
    open(p, "w").write(s.replace(old, new))


sub("AP_NavEKF3_core.h",
    "    bool velDCheckedAtRest;",
    "    uint16_t abtestRestResets;\n    uint16_t abtestRestChecks;\n    bool velDCheckedAtRest;")
sub("AP_NavEKF3_PosVelFusion.cpp",
    "        velDCheckedAtRest = true;\n",
    "        velDCheckedAtRest = true;\n        abtestRestChecks++;\n")
sub("AP_NavEKF3_PosVelFusion.cpp",
    "            ResetHeight();\n            fuseHgtData = false;\n            // the vertical state now agrees",
    "            abtestRestResets++;\n            ResetHeight();\n            fuseHgtData = false;\n            // the vertical state now agrees")
sub("AP_NavEKF3_Logging.cpp",
    "    Log_Write_XKF7(time_us);\n#endif\n",
    """    Log_Write_XKF7(time_us);
#endif

    {
        // ABTEST: #34942 rest reset and its agreement test, XKFM layout, core + 50
        const bool navAgrees = ((imuSampleTime_ms - lastVelDFuseTime_ms) < 2000) && (fabsF(innovVelPos[2]) < 0.5f) &&
                               (velTestRatio < 1.0f);
        const bool bodyAgrees = ((imuSampleTime_ms - prevBodyVelFuseTime_ms) < 2000) &&
                                (norm(innovBodyVel[0], innovBodyVel[1], innovBodyVel[2]) < 0.5f);
        const uint8_t flags = uint8_t(measuredVertVelAgrees()) | (uint8_t(navAgrees) << 1) | (uint8_t(bodyAgrees) << 2) |
                              (uint8_t(onGround) << 3) | (uint8_t(onGroundNotMoving) << 4) |
                              (uint8_t(velDCheckedAtRest) << 5) | (uint8_t(inFlight) << 6) |
                              (uint8_t(onGroundHgtError()) << 7);
        const struct log_XKFM pkth{
            LOG_PACKET_HEADER_INIT(LOG_XKFM_MSG),
            time_us : time_us,
            core    : uint8_t(DAL_CORE(core_index) + 50),
            ongroundnotmoving : flags,
            gyro_length_ratio : (float)((imuSampleTime_ms - lastVelDFuseTime_ms) * 0.001f),
            accel_length_ratio : (float)innovVelPos[2],
            gyro_diff_ratio : (float)stateStruct.velocity.z,
            accel_diff_ratio : (float)(abtestRestResets + 1000U * abtestRestChecks),
        };
        AP::logger().WriteBlock(&pkth, sizeof(pkth));
    }
""")
print("instrumented", root)
