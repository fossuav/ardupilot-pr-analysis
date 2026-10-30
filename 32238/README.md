# PR #32238 - Add FAST_BOOT bitmask parameter

Analysis archive for [ArduPilot/ardupilot#32238](https://github.com/ArduPilot/ardupilot/pull/32238).
Branch `fast_takeoff_3` (rishabsingh3003 fork, maintainer edits allowed).
Record started 2026-10-30.

## 2026-10-30: AP-Review round at f4361d8b65

The bot (review 4) still requested changes: the DroneCAN bit can leave a
DroneCAN baro or airspeed without a backend for the whole boot, the ESC
bit latches a pending ESC_CALIBRATION, FAST_BOOT lacks @RebootRequired,
and _fast_boot is signed. All four were checked against the code and
hold. Work is on r1030/32238 in /home/andy/github/r1030-32238, on top of
the PR head; nothing pushed.

ESC latch: confirmed in SITL. ESC_CALIBRATION=1 with BRD_FAST_BOOT=4
stayed 1 across a reboot at the head and was cleared with 0. Fixed the
way rmackay9 and IamPete1 asked: e6d9168288 makes ESC_CALIBRATION=9
return before the 2 s radio wait and drops the FAST_BOOT early return,
and e14da6c069 removes bit 2 and fast_boot_esc(). With no RC
(SIM_RC_FAIL=1) the boot log starts at 4.272 s at the head with 9 and at
2.282 s after the fix; 0 stays at about 4.27 s on both. The wait was the
only effect of 9 at boot: pre_arm_rc_check has no readers, and Copter
raises no radio failsafe while disarmed before it has seen RC.
192d953ccf adds ESCCalibrationStartup, which fails at the head (1 kept)
and passes after.

64d009f417 adds @RebootRequired: the remaining readers are
AP_DroneCAN::init() (once, from AP_CANManager::init(), guarded by
_initialized) and the top of AP_DroneCAN::loop(). b08b51cea3 makes
_fast_boot AP_UInt32; AP_UInt32 is AP_ParamT<uint32_t, AP_PARAM_INT32>,
and PARAM_VALUE reports type 6 (INT32) for BRD_FAST_BOOT before and
after.

DroneCAN bit: not fixed, options left for a decision. Only four DroneCAN
drivers use the probe pattern; GPS (detect_instance) and compass
(_detect_runtime, 1 Hz while disarmed) re-probe, baro (AP_Baro::init)
and airspeed (allocate) do not. SITL models it with
--enable-dronecan-tests, which needed a local three-line build fix in the
test-only block of AP_Compass_DroneCAN::probe() (bit-rot, not committed).
With the simulated DroneCAN baro as the only baro, BRD_FAST_BOOT=0 found
it (BARO1_DEVID 32003) and BRD_FAST_BOOT=2 left BARO1_DEVID 0 and the
boot looping on "Config Error: Baro: unable to calibrate". On hardware
without HAL_BARO_ALLOW_INIT_NO_BARO it would stop at "unable to
initialise driver" instead. Airspeed (ARSPD_TYPE=8, no baro) was found
either way in SITL, as its probe runs at the end of setup, but SITL nodes
publish from time zero, with no node boot or DNA delay.

Keeping discovery ahead of the probes means waiting before
barometer.init(), which comes straight after can_mgr.init() on Copter
and Plane, so the bit would save almost nothing. Runtime detection is a
redesign in both libraries: a late baro is never calibrated (healthy()
needs calibrated, and calibrate() runs once), a DroneCAN-only board
still hits the boot-time config errors, and a late airspeed misses its
offset calibration. Recommended: drop the DroneCAN bit from this PR
(then FAST_BOOT has no readers and the PR reduces to the
ESC_CALIBRATION=9 early return), and do baro/airspeed runtime
detection separately if fast CAN boot is still wanted.

Andy's decisions: keep the DroneCAN bit and document its limit (added to
the BRD_FAST_BOOT description in 47714568af); the removal of the
Copter-only ESC calibration bit in favour of ESC_CALIBRATION=9 returning
early is accepted.

Pushed to rishabsingh3003 f4361d8b65 -> 47714568af (fast-forward from
r1030/32238).
