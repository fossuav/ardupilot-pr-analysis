# PR #31274 - Motortest error rate

Analysis archive for [ArduPilot/ardupilot#31274](https://github.com/ArduPilot/ardupilot/pull/31274).
Branch `andyp1per/pr-motortest-error-rate`. Record started 2026-10-30.

## 2026-10-30: AP-Review at 4ef30eefe0, both blockers fixed

The bot's two blockers were both real. RpmData.error_rate means a
percentage for bidirectional DShot, IOMCU and FETtec, the cumulative
DSDL error_count for DroneCAN (Status.error_count "resets when the motor
restarts"), and 0 for BLHeli serial, KDECAN, PiccoloCAN, Torqeedo, QURT,
AP_RPM and SITL. AP_Periph complicates it: it relays its own DShot
percentage in the DroneCAN error_count field, while the HobbyWing and
APD periph drivers send counts. A throwaway gtest against PR head's
AP_ESC_Telem showed a DroneCAN count of 2 blocking are_motors_running()
at 1%, and a BLHeli 0 after a 5% DShot rate passing it with ESC.Err
reading 0. Both were fixed after 5beef05d5c.

Design: drivers pass error_rate_is_pct to update_rpm() (default false),
and an update without a percentage does not overwrite one already
reported for that ESC. The flag fits in RpmData's padding. Other values
are still stored, so ESC.Err and the AP_Periph relay are unchanged.
Converting the DroneCAN count was rejected: it needs a window per ESC
and a rate the DSDL does not define, and would mangle AP_Periph's
relayed percentage. Dropping the count from DroneCAN would change
ESC.Err for every DroneCAN user (peterbarker added it in 1d57ada441).

The motor test indexed ESC telemetry by test order. On "+" a four-motor
test at SIM_ESC_ERR_RATE=5 warned for motors 1, 2, 3 and nothing for the
fourth (head plus the SITL hook, arducopter md5 700dc8c3). After
7477db0924 it warns for 3, 1, 4, 2 (md5 75dd7402). The mapping is
AP_MotorsMatrix's own _test_order, factored into
get_test_seq_motor_mask() and exposed as get_test_seq_output_mask();
non-matrix frames return 0 and get no warning.

Commits on r1030/31274 (on 4ef30eefe0):
- 89beac93b0 SITL: add SIM_ESC_ERR_RATE
- fd0c7ea3cf AP_ESC_Telem: report SIM_ESC_ERR_RATE from the SITL backend
- 5beef05d5c AP_ESC_Telem: only check error rates that are a percentage
- 1f2cfbba08, d930e0e7a7, ce8e7c3956: DShot, IOMCU and FETtec opt in
- 670df11d41 Copter: motor test warns only on a percentage
- ace86c2c92 AP_Motors: add get_test_seq_output_mask()
- 7477db0924 Copter: name the ESC the motor test spins
- 05ddd48130, e1621a406e: TKOFF_RPM_MIN and Q_TKOFF_RPM_MIN docs
- 75ff6bc98c Copter: return after cancel, label the #endif
- 90f7f1d5c4 autotest: error rate takeoff block and motor test warning

Tests at 90f7f1d5c4: Copter MotorTestErrorRate, TakeoffCheck, MotorTest
and QuadPlane TakeoffCheck, MotorTest all pass. MotorTestErrorRate fails
before the fix as above. The new TakeoffCheck subtest fails with the 1%
limit removed from AP_Vehicle, so it measures the gate. In SITL the
warning reports 0 rpm because SITL only simulates motor RPM when
SIM_VIB_MOT_MAX or SIM_ESC_ARM_RPM is set; that explains the bot's
"at 0.0 rpm" note.

Builds: SITL copter after each code change, plane, sub and heli after
the AP_Motors change, and CubeOrange-bdshot copter at 90f7f1d5c4, which
compiles the DShot, IOMCU and FETtec changes. Flash on CubeOrange-bdshot
copter: text 1656892 at 4ef30eefe0 and 1657124 at 90f7f1d5c4, +232 bytes
for these fixes.

Left open: the 5 s bdshot counter reset (one bad frame just after a
reset reads high) needs a minimum frame count in RCOutput, which is new
state, so it was not done. The Copter commit body sentence the bot
flagged needs a history rewrite and was left. 1f2cfbba08's subject is
73 characters; the gate notes it.

## 2026-10-30: quick review of the fixes, fixed in place

Andy chose to fix in place. The quick review closed the five original
findings and raised five more against the new mechanism; all five held
up against the code, except that Q_TKOFF_RPM_MIN already said zero
disables Q_TKOFF_RPM_MAX.

The sticky error_rate_is_pct flag had no freshness of its own: with
DShot silent and BLHeli serial still updating the RPM, the gate kept
using the last percentage. A throwaway gtest against 90f7f1d5c4 showed
a 0.5% rate still passing 400 ms after DShot stopped, and the raw error
rate (ESC.Err, AP_Periph's relay) returning the kept 5% after a BLHeli
update where master returns 0. a0308c713f restores error_rate to
master's latest-driver value and keeps the percentage in error_rate_pct
with its own timestamp, valid for ESC_RPM_CHECK_TIMEOUT_US (210 ms). An
ESC that reported a percentage and went quiet now fails the takeoff
check, since bidirectional DShot only reports on a good frame. The probe
passes 6/6 after it. ESC.Err now logs exactly what master logs. RAM is
8 bytes more per ESC slot.

FETtec: tx_err_count minus its baseline was done in int, so a wrapped
16-bit counter gave a negative rate (baseline 65530, count 5, 1000
commands: -6552.5% before, 1.1% after 04b048c540). A lost reply in the
first _esc_count commands after _fast_throttle_cmd_count wrapped kept
the previous window's baseline; e9c36f8c69 clears a per-ESC flag at the
wrap and baselines from the next reply. The SITL FETtec sim cannot
inject errors, so neither has a SITL test; FETtecESC still passes.

Bidirectional DShot: a missing reply (RECV_FAILED) was counted against
erpm_errors[curr_telem_chan], a group-local slot that the DMA callback
has already advanced, not the output. f7795d2363 uses
group.chan[prev_telem_chan] as the decode path does. Needs a hardware
check; SITL does not run it.

The motor test updated its once-a-second timestamp inside the loop, so
only the first faulty output of a motor was named. With motor 1 on
outputs 5 and 6 (SIM_VIB_MOT_MASK gives them SITL ESC telemetry) the
warnings named [5] before df98b72b3c and both after. Setting up the
test showed that SERVO1 only carries motor 1 as a runtime default, so a
reboot with motor 1 on SERVO5 leaves SERVO1 unassigned; the subtest
uses outputs 5 and 6 and reboots after restoring them.

f2cc80f6bd adds "(which also disables TKOFF_RPM_MAX)" to TKOFF_RPM_MIN.

Commits: a0308c713f, 04b048c540, e9c36f8c69, f7795d2363, f2cc80f6bd,
df98b72b3c, 26b5d5351f. a0308c713f (74) and e9c36f8c69 (75) have
subjects over the gate's 72 characters; reword at squash.

Tests at 26b5d5351f: Copter MotorTestErrorRate, TakeoffCheck, MotorTest
and FETtecESC, and QuadPlane TakeoffCheck and MotorTest all pass.
Builds: SITL copter, plane and heli, and CubeOrange-bdshot copter, which
compiles the DShot, IOMCU and FETtec changes. CubeOrange-bdshot copter
text is 1657268, +376 bytes on 4ef30eefe0 (it was +232 at 90f7f1d5c4).
The gate raises only subject-length notes; branch conventions pass.

Follow-ups, not done: the Lua binding of update_rpm() cannot pass the
percentage flag, so scripted backends are not checked; tri, single,
coax and tailsitter frames give no motor test warning; the bdshot
post-reset small-sample noise.

## 2026-10-30: gate narrowed to bidirectional DShot, r1030/31274b

Andy narrowed the takeoff gate to ChibiOS bidirectional DShot. The
round-2 cold reads found more driver-level problems, so the series was
rebuilt by cherry-pick from 4ef30eefe0 as r1030/31274b, head
d2283c9410; r1030/31274 is left as it was at 26b5d5351f.

Dropped: the IOMCU and FETtec percentage opt-ins and the two FETtec
fixes (d930e0e7a7, ce8e7c3956, 04b048c540, e9c36f8c69). Their rates
stay unflagged and log as on master. The FETtec wrap (a uint16 delta
done in int goes negative when the ESC's error counter wraps) and the
late re-baseline (which under-reports, dividing errors since a late
baseline by all commands since the wrap) are pre-existing logging bugs
for a separate PR. Kept commits were reworded where their subject was
over 72 characters or their body named IOMCU or FETtec.

New on the branch:
- ed0f6a879a AP_HAL_ChibiOS: ESCs do not answer DShot commands, and the
  empty receive window after one counted as an error. Each pulse now
  records whether it sent a command to the channel in the telemetry
  slot. The edit also stripped trailing spaces from the neighbouring
  #endif in RCOutput_serial.cpp; restore at squash if wanted.
- 7dd747e7f5 AP_HAL_ChibiOS: a missing reply now goes through the same
  5 s statistics reset as a failed decode, so a silent ESC's counters
  cannot wrap.
- e8f50bee92, fee4c3a7d6: TKOFF_RPM_MIN and Q_TKOFF_RPM_MIN say only
  bidirectional DShot on flight controller outputs is checked, and that
  an ESC that has never reported a rate is not.
- 2d8fae19b7: TKOFF_RPM_MAX says it needs TKOFF_RPM_MIN.
- 3c07d10af8: the motor test names one faulty output a second, taking a
  motor's outputs in turn, as "Motor Test: motor %u errors %.1f%% at
  %.0f rpm" (47 characters at most, one STATUSTEXT; the queue holds 10
  on HAL_MEM_CLASS_192 boards).
- b04b2dfc95, d2283c9410: autotest regex for the new text, and the
  redundant reboot after context_pop() removed (reboot_sitl() inside a
  context already makes the pop reboot).

Never-received: nothing in AP_HAL says which outputs run bidirectional
DShot (only set_bidir_dshot_mask() exists, and ChibiOS keeps
_bdshot.mask private), and BLHeli's BDMASK includes IOMCU outputs that
no longer report a percentage. So an ESC that has never reported is not
checked; documented in the parameters and the description. A
get_bidir_dshot_mask() on AP_HAL::RCOutput, returning the FMU mask
shifted by chan_offset, would close it.

Results at d2283c9410: Copter MotorTestErrorRate, TakeoffCheck,
MotorTest and FETtecESC, and QuadPlane TakeoffCheck and MotorTest all
pass. Every warning is now one STATUSTEXT, and outputs 5 and 6 are named
one a second. The stale-percentage gtest passes 6/6. Builds: SITL
copter, plane and heli; CubeOrange-bdshot copter (text 1657272, +380
bytes on 4ef30eefe0); iomcu-f103-dshot iofirmware, which compiles the
changed RCOutput files. The gate notes only a9ae4cdc82's subject; branch
conventions pass. The DShot fixes need a hardware check.

Andy's decisions: fix the first cold-review blockers in place, then, when a
second round found more driver-level problems, narrow the takeoff gate to
flight-controller bidirectional DShot only (the FETtec and IOMCU opt-ins
dropped; the FETtec counter wrap left for a separate PR). The pushed head
is r1030/31274c, which is r1030/31274b with an unrelated trailing-
whitespace strip on an #endif in RCOutput_serial.cpp undone. The three
bidirectional DShot statistics fixes need a hardware check.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `4ef30eefe0`
-> `db7371c4d8`.
