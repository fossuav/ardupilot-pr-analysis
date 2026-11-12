# PR #35105 - a landed Copter is on the ground in EKF3 (rmackay9)

Analysis archive for [ArduPilot/ardupilot#35105](https://github.com/ArduPilot/ardupilot/pull/35105).

Opened 2026-11-11 by rmackay9. Head `06f1cf36d2`, two commits on
master: `bfea00cc4a` (AP_NavEKF3) and `06f1cf36d2` (autotest
`EK3YawAlignEachTakeoff`). Not our branch: this record is what our
testing found on it and what was posted.

It is the follow-up rmackay9 named on #35077 (2026-11-11 08:32Z) for
that PR's post-landing EKF failsafe. Read `../35077/README.md` and
`../34292/README.md` first: #34292 wrote the same gate,
`vehicle_class == COPTER && time_flying_ms == 0`, on 2026-09-30 and
withdrew it on 2026-10-03 (its "What 'landed' means took three tries").

### Head superseded 2026-11-12: `3993abc2e6`, a logged flag

The head is now `3993abc2e6`, eight commits on master `546cf152a8`.
The first three are #35128 (rmackay9): the EKF keeps a copy of the
learned body field while it is valid and `getMagOffsets()` hands that
out, so learned compass offsets survive landing until disarm saves
them. The other five replace the build-type gate with a flag the
vehicle sets:

- `AP_AHRS::set_vehicle_landed()`, called from Copter's
  `set_land_complete()` beside `set_likely_flying()`. Only Copter and
  Heli set it.
- AP_DAL logs it as bit 0 of a new `Flags2` byte appended to RFRN;
  EKF3 reads `dal.get_vehicle_landed()`.
- `detectFlight()`, non fly-forward branch: `motorsArmed &&
  !dal.get_vehicle_landed()` sets `onGround = false`, anything else
  `onGround = true`, `inFlight = false`. No class or build-type test.
- `c8de8fefeb` is the EKF commit, `3993abc2e6` the autotest.

On Copter the flag changes exactly when `land_complete` does, as
`time_flying_ms` did, so the windows under "What it changes" stand.
Every number below was taken on `06f1cf36d2` (SITL with its two
commits on #35077 `9c25e44f45`) and has not been re-run at this head.

## What it changes

`detectFlight()`, non fly-forward branch: under
`APM_BUILD_COPTER_OR_HELI || APM_BUILD_TYPE(APM_BUILD_Replay)` a
vehicle with `dal.get_time_flying_ms() == 0` (Copter: `land_complete`)
gets `onGround = true`, `inFlight = false` even while armed. Before,
armed meant `onGround = false` on Copter. So the on-ground paths now
also run:

- after landing, until disarm (the case the PR is for);
- from arming until NOT_LANDED;
- through THROW's whole armed wait, as `land_complete` stays set until
  the throw is detected (`mode_throw.cpp` `set_land_complete(false)`);
- after a mid-air disarm and re-arm, until throttle clears the flag.

Superseded 2026-11-12 by `3993abc2e6`: the gate above is now the logged
`vehicle_landed` flag (see "Head superseded" above). The four windows
are unchanged.

## SITL, 2026-11-11 (tier 2)

Two scratch worktrees of #35077 at `9c25e44f45`, both with our landing
test from `dded8ebc27` ported to the `FLOW_ALT_MIN` rename (the test
kept its name, `OpticalFlowFocusHeightLanding`); one also had #35105's
two commits. Each leg records its failure and the test raises once at
the end, so every leg ran on the base too (local change, not pushed).
Times are from LAND_COMPLETE (EV 18). Base 2 runs, with #35105 3 runs.

| leg | #35077 `9c25e44f45` | #35077 + #35105 |
|---|---|---|
| LOITER, FLOW_ALT_MIN 0.3 | "stopped aiding" +3.45 s, failsafe to LAND +4.43/+4.44 s | no failsafe, aiding kept to DISARM_DELAY (+10.43-10.47 s), walk 0.044-0.052 m |
| LOITER, FLOW_ALT_MIN 0 (control) | no failsafe, walk 0.14/0.26 m | no failsafe, walk 0.10-0.21 m |
| ALT_HOLD, RNGFND1_MIN 0.2, bad flow | "stopped aiding" +2.74/+2.76 s | aiding kept, walk 0.053-0.056 m |
| ALT_HOLD, RNGFND1_MIN 0, bad flow | "stopped aiding" +2.73/+2.77 s | aiding kept, walk 0.050-0.059 m |

- With #35105, `takeoff_detected` (XKF4.SS bit 10) cleared 0.12-0.19 s
  after LAND_COMPLETE.
- The EKF's HAGL on the ground stayed at 0.10-0.31 m in every leg, so
  the `< 0.5 m` condition behind the zero flow held throughout.
- `EK3YawAlignEachTakeoff` passes.

How the walk was measured: it is the largest XKF1 core 0 PN/PE distance
from the touchdown point while aiding was kept. The touchdown point is
LAND_COMPLETE for LOITER, and the moment the bad flow was switched on
for ALT_HOLD. The simulated vehicle did not move in any leg.

When aiding stops on the base, the EKF position resets to (0, 0) and
steps back when aiding restarts at disarm. That is a 0.75-0.78 m step,
left out of the walk above. The test's own end-minus-start number,
which `../35077/` quotes for the ALT_HOLD legs, ends just after disarm
and misses the step: it printed 0.09-0.17 m on the base and 0.04-0.05 m
with #35105.

### A landing #35105 does not cover (one run per build)

A local leg outside the test: LOITER with an origin, `RNGFND1_MIN`
raised to 0.2 after takeoff, so the range finder reads out of range low
on the ground.

- On both builds, with `FLOW_ALT_MIN` 0.3 and 0: "EKF variance: position
  lost", then LAND, at +4.4 to +4.5 s.
- With #35105, aiding stays on, but `horiz_pos_rel` drops at
  +3.55-3.60 s. That is the `gndOffsetValid` timeout, 5 s after the
  last range sample.
- The ALT_HOLD 0.2 legs show the same drop at +3.0 s. The test cannot
  see it there: those legs set no origin, so Copter's `ekf_check`
  returns early.

The PR text says that with no range data for 200 ms the EKF assumes the
on-ground range. On master that branch is never reached for a sensor
that is not reading Good: `readRangeFinder()` takes the `continue`
first, so the branch only runs for a Good sensor with fewer than three
fresh samples (`../32232/README.md`, "What the PR actually does";
derived from the source, not measured here). #32232 makes the branch
reachable. Flight logs show flow copters with `RNGFNDx_MIN` 0.05 and no
ground clearance reading 0.00 m, out of range low, on the ground
(`../34292/`), so this is the usual case for them.

## Flight-log scan, 2026-11-11 (tier 1 for the windows only)

282 Copter logs (516 arms) from the private flight-test records. Windows
are taken from `RFRH.TF == 0` where the log has it (262 logs), and from
LDET bit 0 otherwise. RFRH, LDET and EV 18/28 agree within 0.5 s on
every log that has both. Evidence of being airborne: a Good range more
than 1 m above the on-ground reading, GPS speed, IMU free fall, and baro
only when something else agrees. What the EKF would do in each window
is inference; none of it has been replayed.

- **Powered flight:** no window with `land_complete` set in sustained
  powered flight.
- **THROW, carrier drops:** 15 windows, median 17 s at about 30 m,
  longest 152.8 s at 31 m (log46). Each ends in 0.1-0.8 s of free fall
  before detection clears the flag.
  - On the carrier drop already recorded in `../32475/` (log32), the
    flag was set while armed for 10.1 s, 1.7 s and 2.7 s over its three
    attempts. The carrier was flying at 15-17 m/s.
- **THROW, by hand:** 61 windows, median 7.4 s, up to 22 s and
  11.8 m/s.
- **Re-arm after a mid-air disarm:** two hand-held windows of 1.85 s
  and 2.8 s. These are inferred from a range of about 1.1 m and could be
  a range finder artefact. The drop re-arms behind `../34942/` were on
  the ground (range 0.04-0.07 m), where `onGround = true` is right.
  `../32972/` has the in-air case in SITL only: about 9 s at 17 m/s with
  `tfly = 0`.
- **Arming to NOT_LANDED:** 382 non-throw arms, median 2.3 s, p90 5.7 s,
  max 24.1 s. None left the ground before NOT_LANDED; the three
  apparent cases were range finder steps or an inverted vehicle.
- **LAND_COMPLETE to disarm:** 146 windows, median 2.1 s, p90 9.5 s,
  max 62.2 s. By mode: LOITER 75, VALT 19, ALT_HOLD 17, LAND 17,
  STABILIZE 13.
- **GPS while landed:** above 0.3 m/s in 8 of 111 windows, max 0.8 m/s,
  all stationary noise. No moving-platform logs.

The missing-NOT_LANDED flight cited in `../32514/`, `../34457/` and
`../34292/` could not be checked: that log is not on the analysis
machine. Nine other logs from the same operator (44 arms) were read,
and every arm that flew logged NOT_LANDED. See the 2026-11-11 notes in
those entries.

## Findings by inspection (tier 3 unless marked: derived from the source)

1. **Paths gated on `onGroundNotMoving`.** These are zero-velocity
   fusion, the static yaw hold and yaw bias learning on the ground.
   They need the IMU stillness test to pass, and with the props
   spinning it does not.
   - Tier 1, from `../34292/`: armed after landing, `gyro_diff` read
     15.5-21.6x and `accel_diff` 2.0-3.4x their threshold (log281,
     log66). A steady hover read 3.6-3.8x; disarmed 0.16-0.73x.
   - SITL models no motor vibration by default, so it shows these
     paths working.
   - What does take effect on hardware: the dvel bias axes are
     inhibited (`onGround && !onGroundNotMoving`) and the flow is
     zeroed.
2. **`hgtInnovFiltState` and `healthy()` before takeoff.** The filter
   is zeroed only while `!onGround`, so it now runs from arming to
   NOT_LANDED, through spool-up.
   - Tier 1: flight tests show prop wash taking the baro 4.4-5.7 m
     low at liftoff (private analysis repo).
   - In AID_NONE, `healthy()` fails once the filter passes 1 m.
     `NavEKF3::UpdateFilter()` then allows an armed lane switch on
     `!core[primary].healthy()`, and `AP_AHRS::healthy()` reports
     false. Not tested.
   - **Superseded 2026-11-12 for master (tier 3).** On master the
     filter does not move on an accepted sample: `dtBaro` is taken from
     `lastHgtPassTime_ms`, which the same sample has just set, and a
     rejected sample never reaches the filter. It moves only on a
     height timeout or bad IMU data, as AP-Review said at `3993abc2e6`.
     So point 4 of comment 6799001716 does not hold on master; the
     correction is not posted. It holds on a branch whose filter works:
     #34942's `9d75f6fd6f` times the filter from its own last update and
     counts rejected samples up to the gate, and the SFD beta carries
     it. The text above is left in place because it describes that
     build.
3. **Replay.** AP-Review measured Rover and QuadPlane Replay diverging.
   A logged class test alone would still break Blimp logs: Blimp calls
   `set_vehicle_class(COPTER)` and never calls `set_likely_flying()`, so
   its `time_flying_ms` is always 0. Rover passes
   `is_armed_and_safety_off()`. Once Blimp passes its armed state, as
   the PR text plans, `dal.get_vehicle_class() == COPTER` under
   `APM_BUILD_TYPE(APM_BUILD_Replay)` is correct for every vehicle, as
   #34292 does for its Rover exclusion. A new logged flag needs a new
   byte or message, since RFRN's flag byte has all 8 bits allocated.
   - **Superseded 2026-11-12 by `3993abc2e6`.** The new head logs a
     flag only Copter and Heli set, in the new byte this finding says a
     flag needs, and AP-Review measured the Rover and QuadPlane logs
     replaying with 0 errors. A log recorded before the change has no
     `Flags2`; master replays it as 0 (not landed) since `9610cb59b7`.
4. **THROW.** Not raised on the PR.
   - **Compass.** While armed and waiting, `inFlight` is forced false,
     and `fuseEulerYaw()` rejects a failed sample only `if (inFlight)`.
     So the compass is fused past its gate for the whole carry, where
     flight tests show it reading 10-30x the earth field (private
     analysis repo). Before, the armed wait set `inFlight` once the
     vehicle had climbed 1.5 m above its arming height, or once the
     range had risen 0.5 m.
   - **In-flight yaw reset.** `posDownAtTakeoff` follows the vehicle
     until release, so the final reset needs a climb of
     `EKF3_MAG_FINAL_RESET_ALT` (2.5 m) above the detection point. A
     drop that holds height below its release point may never make
     that climb.
   - **GPS.** The 0.3 m/s horizontal speed check now runs through the
     carry, so `gpsGoodToAlign` drops 5 s in and needs 10 s clean after
     release. That stops GPS aiding starting in that window, but does
     not stop fusion that is already running.
   - **Scan observation, not explained:** on log34 the in-flight yaw
     alignment message came 30 ms after arming on the carrier. Replay
     owed.
   - **2026-11-12:** AP-Review raised it at `3993abc2e6`, with SITL:
     ThrowDoubleDrop logs no in-flight yaw or field alignment, against
     two per flight on master. See "Reviews and posts".
5. **Our open PRs that read these flags.**
   - #34942: `onGroundHgtError()` rests on "onGround only means
     disarmed". Under #35105 it acts while armed and landed, in aided
     modes too.
   - #32232: `movedSinceArming` is cleared while `onGround`. Its
     substitution therefore restarts at each landing, which is right,
     but stays live for a whole THROW wait. Its open defect 2 covers
     the re-arm case for at least 1 s.
   - Other readers that assume `onGround` means disarmed on Copter:
     #33585's flight scoping, #33359, #32471 `dc53f21285` ("armed, the
     EKF fuses no zero velocity"), and #34941, which chose
     `get_time_flying_ms()` because `!onGround` missed the armed carry.
     The EKF3 playbook's observability idiom also reads `!onGround` as
     "armed".
   - #34851 is not made redundant. Position was lost before
     LAND_COMPLETE: 60 ms before (log54), 0.78 s before (log58 Replay)
     and 0.7 s before (log47). #35105 acts only after LAND_COMPLETE.

## `3993abc2e6` against the SFD stack, 2026-11-12 (tier 3)

Derived from the source at `3993abc2e6` and at SFD beta head
`c42bd1fb40`, not measured. It adds to finding 5.

The design is the one the EKF3 playbook asks for: a generic signal the
vehicle opts into, logged through the DAL, with no vehicle-class test.
#34292 had no such signal and withdrew its class test. The signal
carries no new information, though: on Copter it is `land_complete`,
and it is wrong where that is wrong, in a THROW wait and after a re-arm
in the air. What it adds is a flag separate from `land_complete`, which
Copter can make truer case by case without touching the land detector.

- **#32232 may close the out-of-range-low landing.** Its substitution
  (a sensor reading out of range low, with no other Good, taken as
  `rngOnGnd` while `!movedSinceArming`) comes back at LAND_COMPLETE,
  which should keep `gndOffsetValid` after touchdown, where #35105
  alone loses it at +3.55-3.60 s. Not run.
- **#34942's height check runs armed.** Its working filter is what
  makes finding 2 real on the beta: from arming to NOT_LANDED (median
  2.3 s, max 24.1 s in the scan), after landing, through a THROW wait
  and after an in-air re-arm. In AID_NONE, or in an aided mode without
  an agreeing measured vertical velocity, it fails `healthy()` and
  allows an armed lane switch; with `SRC_PER_CORE` that changes the
  sources flown on. Testing `!motorsArmed` in `onGroundHgtError()`
  keeps the meaning its comment states.
- **#32475:** finding 4, now measured by AP-Review. Its fix, clearing
  the flag when THROW enters `Throw_Detecting`, is one line in Copter.
- **#32471:** on hardware every accel bias axis is inhibited from
  arming to NOT_LANDED (`onGround && !onGroundNotMoving`), which may
  help the Z bias learned on the ground while armed (SFD-O4 log63). In
  SITL, which has no motor vibration, the copter fuses zero velocity
  armed on the ground, so the VRF tests may move.
- **`EK3_MAG_CAL` 7 (#34057):** the in-flight yaw and field reset is
  redone at each takeoff. Ground learning after a landing was already
  on before.
- **#33478:** its AGL KF velD fusion is gated on `inFlight`, so it now
  stops at LAND_COMPLETE instead of at disarm.
- **#34941 and #32972** read `get_time_flying_ms()` directly and do not
  change on Copter.

### A mid-air disarm and re-arm

Disarm forces `land_complete`, and once re-armed only throttle above
the non-takeoff level clears it, so `vehicle_landed` stays set while
the copter falls. Master sets `onGround = false` on the first EKF cycle
after arming. Through that window the compass is fused past its gate,
and the in-flight yaw and field reset is held off with its flags
cleared each cycle. #32972's SITL (`../32972/README.md` and its
2026-09-04 review response) measured how long it lasts: re-arms in
Stabilize at zero throttle and in ALT_HOLD with the stick at 1450, 1500
and 1550 all stayed landed and fell at 15-17 m/s, one of them for about
9 s.

#32768 already covers the case for its arm-time height datum reset:
`ap.disarmed_in_air` is set by a disarm with `land_complete` clear, or
by a watchdog reset while armed, and only the disarmed land detector
clears it, once the airframe has stopped accelerating and descending.
With it, Copter can report landed only while `disarmed_in_air` is
clear. `set_land_complete()` returns early when nothing changes, so the
flag also has to be set where the land detector clears
`disarmed_in_air`. Posted as comment 6828417700.

### Carrying it on the beta

`git merge-tree --merge-base 546cf152a8` of the PR head onto
`c42bd1fb40`: the EKF3 files merge cleanly; `AP_AHRS.h`, `AP_DAL.cpp`,
`AP_DAL.h`, `AP_Arming.cpp` and `arducopter.py` conflict. The beta's
RFRN already uses its spare bit for #32471's `hover_z_bias_enabled`.

`Flags2` grows RFRN by a byte. `9610cb59b7` ("Replay: cope with logged
messages of a different length") is on master but not on 4.7 or the
beta; without it, Replay of an SFD log recorded before the change reads
that byte from past the record (the EKF3 playbook's "Never grow an
existing DAL struct"). Carrying #35105 needs `9610cb59b7`, the THROW
line, the `disarmed_in_air` change and the #34942 gate with it.

## Reviews and posts

- **AP-Review at `285e3a8063`, 2026-11-11 06:04Z: REQUEST CHANGES.**
  The autotest force-disarmed while climbing and ended 3.9 m from
  home. Replay of Rover and QuadPlane logs diverged (139417 and 38469
  errors, against 0 on master).
- **AP-Review at `06f1cf36d2`, 2026-11-11 07:44Z: COMMENT.** The test
  now ends with `do_RTL()` and passes; the Replay point is still open.
- **Posted 2026-11-11 14:49Z,
  [comment 6799001716](https://github.com/ArduPilot/ardupilot/pull/35105#issuecomment-6799001716).**
  The SITL table in brief, then four points: the out-of-range-low
  landing and the unreachable substitution, the stillness-gated paths,
  Replay and Blimp, and spool-up `healthy()`. THROW (finding 4) was left
  out by decision.
- **AP-Review at `3993abc2e6`, 2026-11-12 08:05Z: COMMENT.** Replay now
  uses the logged flag; the Rover and QuadPlane logs replay with 0
  errors. Should fix: THROW, where `land_complete` stays set through
  the carry, so ThrowDoubleDrop logs no in-flight yaw or field
  alignment (two per flight on master). Clearing the flag on entering
  `Throw_Detecting` restored them in its SITL, with ThrowDoubleDrop,
  ThrowMode and EK3YawAlignEachTakeoff passing. Minor: the PR text's
  range finder bullet, and spool-up `healthy()` (finding 2's
  supersession).
- **Posted 2026-11-12 15:49Z,
  [comment 6828417700](https://github.com/ArduPilot/ardupilot/pull/35105#issuecomment-6828417700).**
  The mid-air re-arm case, with #32768's `disarmed_in_air` as the way
  to cover it and the early return in `set_land_complete()`. The
  correction to point 4 of 6799001716 was not included.

## Open

- rmackay9's answer.
- **Replay through `bfea00cc4a` on the THROW windows,** for the yaw
  reset timing, the compass fusion and yaw against the GPS course after
  release. Candidates:
  - log46 at 453.8 s;
  - log34 at 166.6 s;
  - a drop at 199.9 s;
  - a hand spin-drop at 56.9 s.

  All four carry RFRH; fingerprints are in the private index.
- **The out-of-range-low leg:** repeat it, and run it again with
  #32232 stacked.
- **#34942 and the other readers above** need re-checking if #35105
  merges first.
- 2026-11-12:
  - The correction to point 4 of comment 6799001716 (finding 2's
    supersession). Not posted.
  - **Replay at this head shows master on old logs.** The THROW logs
    above carry no `Flags2`, so through `c8de8fefeb` they replay as
    not landed (derived from the source). The THROW Replay needs
    `bfea00cc4a`, which gates on the logged `time_flying_ms`, or a
    temporary Replay change that sets the flag from RFRH on Copter
    logs.
  - **SITL on the beta** with #35105, `9610cb59b7` and the three
    companion changes: the out-of-range-low landing (expected to pass
    with #32232), ThrowDoubleDrop's alignments, an in-air re-arm leg,
    and spool-up `healthy()` in AID_NONE.
