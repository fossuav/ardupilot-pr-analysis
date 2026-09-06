# PR #32768 - Clear baro temperature drift on arming (ArduCopter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32768](https://github.com/ArduPilot/ardupilot/pull/32768).
Branch `pr-baro-drift-minimum` (andyp1per fork), base `master`, head
`3457a96e91` (2026-09-06). All committed data is SITL; real-flight numbers are
cited inline and their logs are not committed.

## Status (one line)

Shipped design is **reset the EKF height datum once, at arm**. The reviewer
suggestion to *also* reset periodically while disarmed (like Plane) was
implemented, tested, found to cause regressions, and removed. A height-only
variant of the periodic idea is preserved as a separate experiment, PR
[#33338](https://github.com/ArduPilot/ardupilot/pull/33338) (see `../33338/`).

**2026-08-29:** self-reviewed and cut back to 11 commits. The origin-vs-GPS
tolerance gate (`HGT_RESET_ALT`, the Plane `HOME_RESET_ALT` changes, the
`RHGT`/`RHG2` replay messages) turned out to be redundant and was removed;
Plane vehicle code is back at master; an EKF3 frontend inconsistency in the
reported origin height was found and fixed; the heli test relaxation got its
real mechanism. See `self-review-2026-08-29.md`.

## The rangefinder height switch silently disabled the reset (2026-09-05)

Found by cross-checking the whole SmallFastDrone stack against the flight
analyses rather than by a failing test, because no test covered the
combination. Each PR involved is correct alone.

`EK3_RNG_USE_HGT > 0` hands the active height source to the rangefinder
*while the vehicle is parked*, and `NavEKF3_core::resetHeightDatum()` refused
any source but baro or GPS. The arm-time reset this PR exists for then never
ran.

The switch fires on the ground because `selectHeightForFusion()` treats the
terrain as stable whenever the AGL KF is valid (#33359, `../33359/`),
overriding Copter's own `terrainHgtStable`, which is otherwise false unless
taking off or landing. With the AGL KF also supplying `heightAboveGnd` and a
fresh `lastAglRngFuseTime_ms`, every term of the switch-on branch
(`belowLowerSwHgt && trustTerrain && prevTnb.c.z >= 0.7f`) holds at rest.

Measured, not inferred. `EKF_ALT_RESET` (EV id 60) is written only when
`resetHeightDatum()` returns true, so it traces the reset directly. Analog
rangefinder, `EK3_OPTIONS = 8`, arm from rest, same binary:

| `EK3_RNG_USE_HGT` | EKF_ALT_RESET at arm |
|---|---|
| -1 (default) | 1 |
| 70 | 0 |

The consequence is latent rather than immediate. While the rangefinder holds
the source the drift does not show: 30 s of accumulated drift left
`relative_alt` at -0.01 m, against 8.65 m in the same probe at the default.
It surfaces when the vehicle climbs past the switch ceiling and falls back to
baro carrying drift that was never cleared, and the GPS re-anchor in
`resetHeightDatum()` is skipped too, so the reported AMSL keeps it.

`../../analysis/topics/ekf3_althold_baro_ge.md` records the accommodation that
used to cover this - allow the reset when `onGroundNotMoving` even if
`activeHgtSource` is RANGEFINDER through `EK3_RNG_USE_HGT` blending, provided
the *configured* primary source is not the rangefinder. It did not survive into
the submitted branch.

Fix prepared on the SmallFastDrone branch on 2026-09-05, pushed to this PR on
2026-09-06 as `3e4ab4715f`: allow the reset when the configured primary source is baro or GPS and
`onGroundNotMoving`, keeping the refusal when the rangefinder is the configured
primary (there the estimate really is rangefinder referenced and there is no
baro drift to clear). At rest the zero the reset moves to is what the
rangefinder reads anyway. With it, `EKF_ALT_RESET` is 1 in both rows above.

Two commits, plus `autotest: cover the datum reset under the rangefinder height
switch`, which fails without the EKF3 change with "No EKF_ALT_RESET at arm" and
passes with it. The existing `BaroDriftClearedAtArm` runs at the
`EK3_RNG_USE_HGT` default of -1, and the one Copter test that sets the switch
(`EK3_AglKfVelForVelD`) sets it to -1 for an unrelated reason, which is why the
gap went unseen.

### Superseded 2026-09-06 by measurement at `33e4911d63`: the AGL KF is not what engages the switch

The finding above is right that the rangefinder holds the height source at
arm and that the reset was refused. The *mechanism* named for it is wrong on
this branch, and the numbers in the table above were taken on the
SmallFastDrone stack, which carries #33359.

`aglKf` appears nowhere in `AP_NavEKF3_PosVelFusion.cpp` on `master`, so the
"terrain stable whenever the AGL KF is valid" override is not present here.
The switch engages anyway, for a different and older reason:

- `NavEKF3_core::InitialiseVariables()` sets `terrainHgtStable = true`
  (`AP_NavEKF3_core.cpp:360`).
- Copter computes it as `is_taking_off() || is_landing()`, so false while
  parked (`ArduCopter/baro_ground_effect.cpp:38`), at 50 Hz from
  `throttle_loop()`.
- `AP_AHRS::set_terrain_hgt_stable()` forwards only on a change of its own
  cached `terrainHgtStableState` (`AP_AHRS.cpp:1976-1991`), and
  `NavEKF3::setTerrainHgtStable()` drops the call entirely while `core` is
  still null (`AP_NavEKF3.cpp:1806`). The first `false` lands before the
  cores exist; after that AHRS believes it has already sent it.

So each core keeps `terrainHgtStable == true` for the whole flight and
`trustTerrain` is satisfied on the ground. Measured at `06860d0425` with a
throwaway `GCS_SEND_TEXT` in `resetHeightDatum()` and in
`NavEKF3_core::setTerrainHgtStable()`, running
`BaroDriftClearedWithRangefinderHeightSwitch`:

```
DIAG0 act=2 trnStab=1 hvel=1 terr=0.25 pz=-0.29
```

`act=2` is `SourceZ::RANGEFINDER`; `trnStab=1` with Copter asking for false.
`setTerrainHgtStable()` was never called once in the whole run.

The conclusion does not move: the clause is needed on this branch, and the
test discriminates. Re-measured at `06860d0425` with `EK3_OPTIONS` removed
(it was there for the AGL KF and is irrelevant): without the EKF3 clause the
test fails with "No EKF_ALT_RESET at arm", with it the reset is logged.

The real-flight caveat further down this file - "Copter asserts
terrain_hgt_stable only during takeoff and landing, so on the ground it is
often still baro" - is the belief this measurement overturns. It is left in
place because it is what the flight was read against.

### The reset left the terrain state behind (2026-09-06)

Found by tridge's automated review at `06860d0425` and confirmed by
measurement. Letting the reset run with `activeHgtSource == RANGEFINDER`
exposed a pre-existing shortcut at the end of `resetHeightDatum()`:
`terrainState = 0`, with the floor in `ConstrainStates()` expected to put it
back. That floor is inside `if (!inhibitGndState)`
(`AP_NavEKF3_core.cpp:2093`) and `EstimateTerrainOffset()` sets
`inhibitGndState = true` whenever the rangefinder is the height source
(`AP_NavEKF3_OptFlowFusion.cpp:96`), so nothing restored it and rangefinder
fusion saw the whole standing range as innovation.

Peak reported height excursion over the 2 s after arming,
`BaroDriftClearedWithRangefinderHeightSwitch`, `EK3_RNG_USE_HGT=70`, one run
each at `06860d0425` plus the noted change:

| `terrainState` after the reset | post-arm excursion |
|---|---|
| `0` (as submitted, and as master) | 0.648 m |
| `stateStruct.position.z + rngOnGnd` (the `ResetHeight()` convention, suggested in review) | 0.529 m |
| `+= oldHgt` (carry it across the datum move) | 0.000 m |

The review's suggested convention only removes `EK3_RNG_ON_GND`; it does not
close the gap, because the vehicle sits about 0.54 m above its terrain state
by the rangefinder's reckoning at that moment. Shipped as `89caba96a1`.

Corrected the same day at `f2425eff3c`, from the self-review's own EKF3 pass:
carrying the state is right only where it is tracking. With no rangefinder and
no usable flow `EstimateTerrainOffset()` inhibits the ground state, so
`terrainState` is only the floor a previous reset left, and carrying it puts
the ground the cleared drift below a vehicle sitting on it - wrong in the
direction master got right. `getHAGL()` refuses there (`gndOffsetValid` false)
so no controller sees it, but `XKF5.HAGL`/`terrOffset` and
`getHeightControlLimit()` do. The carry is now conditioned on
`gndOffsetValid`, which is exactly "fused within 5 s, or the rangefinder is
the source"; otherwise the `ResetHeight()` floor is applied. Rangefinder-case
excursion unchanged at 0.000 m, `BaroDriftClearedAtArm` 0.004-0.024 m.

The test asserted only that `EKF_ALT_RESET` reached the log, so it was green
across all three rows. It now asserts the post-arm height as well.

EKF2 keeps `terrainState = 0`: its `resetHeightDatum()` still refuses a
rangefinder height source outright, so the constraint always runs there.

### Measured and rejected

| Change | Argument for | Measured |
|---|---|---|
| `terrainState = stateStruct.position.z + rngOnGnd` in `resetHeightDatum()` | matches `ResetHeight()`, which is the established convention for the same state; suggested in review at `06860d0425` | 0.529 m post-arm excursion against 0.648 m unchanged and 0.000 m carrying the state across. Rejected 2026-09-06 |
| seed `disarmed_in_air = true` on every boot, rather than only a watchdog-armed one | closes the booted-in-air hole without depending on the watchdog flag | not measured; rejected on inspection because a vehicle arming on a moving platform never satisfies the accel-stationary test, so the drift reset this PR exists for would never run there |

### Resetting only the configured backend was half a fix (2026-09-06)

Raised by tridge's automated review at `ab41a91714`, and it is a defect this
review process introduced: the same review suggested the change on 2026-09-02
and approved it on 2026-09-03.

`71493fda94` replaced the loop over every compiled backend with
`configured_backend->resetHeightDatum()`. That fixed a real problem - with
`EK2_ENABLE=1` and `EK3_OGN_HGT_MASK` bit 2, EKF3 could refuse while EKF2
recalibrated the shared barometer underneath it - but it removed the wrong
half. Deciding *whether* to reset belongs to the configured backend; *following*
the barometer once it has moved applies to every running backend.

Reproduced before fixing, with `EK2_ENABLE=1` and `AHRS_EKF_TYPE=3`, by running
`AmslAltPreservedOnRearmAtDifferentElevation` and then setting
`AHRS_EKF_TYPE=2`. Sampled every 2 s after the parameter write:

```
t=0   amsl=76.28  gps=76.28     <- still EKF3
t=5   amsl=76.28  gps=76.28
t=7   amsl=165.34 gps=76.28     <- EKF2 selected, holding the pre-reset datum
t=38  amsl=165.34 gps=76.28     <- does not converge
```

89.06 m, which is exactly the cliff-to-sea drop, and it does not self-heal:
EKF2 has no way to notice its datum moved. With the fix at `30e560d59e` the
same probe reports 76.3 m. The refusal semantics are unchanged - nothing else
is reset unless the configured backend performed the reset - so the 2026-09-02
issue stays closed.

Two things worth keeping from the reproduction. The backend switch takes about
six seconds to take effect, so a five-second settle reads the old backend and
the test passes for the wrong reason; the test now waits on the
`AHRS: EKF2 active` statustext instead. And baro drift alone does not
discriminate: EKF2 re-converges to within 1.4 m in five seconds because its
own origin never moved. Only an elevation change leaves the two disagreeing.

### The cross-backend test passed with the regression put back (2026-09-06)

Caught by tridge's review at `0f03c2631e`, by mutation rather than by reading,
and it is the second test in this PR to certify nothing. Worth recording as a
pattern, not just an incident.

`AmslAltPreservedOnRearmAtDifferentElevation` asserted the reported AMSL
immediately after selecting EKF2. A backend that was never re-datumed passes
there: its height observation jumps by the 89 m the barometer moved, the
innovation gate **rejects** it, and the filter coasts on the correct height
until height fusion times out after `hgtRetryTimeMode0_ms` (10 s,
`AP_NavEKF2.h:393`) and `ResetHeight()` adopts the displaced datum. So the
assertion reads a correct number either way, and whether it lands inside that
window depends on how long the preceding disarm and backend switch happened to
take. My own probe at the time did catch it - sampling out to t=38 s - which is
exactly why a single passing observation is not evidence that a test
discriminates.

**The general shape: an assertion placed inside a window where an estimator is
rejecting a bad measurement reads the right answer for the wrong reason.** The
sibling trap already recorded here is `relative_alt` falling back to the raw
baro when the EKF vertical position is unhealthy. Both are cases where the test
measures something other than what it names.

Fixed at `2d43b4c09c` by settling 15 s past the timeout. Verified by mutation
in both directions, on the same binary except for the one line:

| build | result |
|---|---|
| `if (ret && ...)` mutated to `if (false && ...)` | FAIL, AMSL 165.3 m against GPS 76.3 m |
| unmodified | PASS, 76.3 m against 76.3 m |

**The review's additional suggestion was measured and dropped.** It asked for
`assert_origin_frame_consistent()` at the same point. That fails on EKF2 -
origin alt 165.3, local z 0.0, AMSL 76.3, an 89.07 m mismatch - whether the
backend followed the datum or not, because `NavEKF2_core::resetHeightDatum()`
moves the core's `EKF_origin.alt` while `NavEKF2::getOriginLLH()` publishes the
frontend's `common_EKF_origin`. That is EKF2 bookkeeping and predates this PR;
the same review comment says so in its own NOTE section. Asserting it here
would have made the test fail on correct code.

### The other half of the narrowing: a backend with no datum was reading as a refusal (2026-09-06)

Found by the self-review, independently by a Claude pass and a Codex cold pass.
The same shape as the 89 m bug, on the opposite side.

`AP_AHRS::resetHeightDatum()` gates the follow loop on the configured backend's
return. DCM, SIM and external AHRS do not override
`AP_AHRS_Backend::resetHeightDatum()` and inherit its `return false`, which the
loop could not tell from a refusal - so with `AHRS_EKF_TYPE` 0, 10 or 11 a
running EKF3 was never told the barometer had moved. Before this series the
unconditional loop reset it. Plane reaches this every 5 s while disarmed through
`update_home()`, and recalibrates the barometer itself either way.

Measured before fixing, `AHRS_EKF_TYPE=10` with 7 m of drift accumulated while
disarmed, then selecting EKF3 after the arm:

| build | EKF3 reported AMSL | GPS |
|---|---|---|
| gated on `ret` alone | 591.5 m | 584.1 m |
| with `has_height_datum()` | 584.0 m | 584.1 m |

Fixed at `49d857c5f3` by asking the configured backend whether it owns a datum
at all: one that does not has no refusal to honour, so it no longer holds the
others off. The 2026-09-02 case is unchanged - a backend that owns a datum and
refuses still suppresses the rest.

### Reviewer conflict resolved: AP_Baro water barometers (2026-09-06)

One pass called `sensors[i].altitude = _alt_offset_active` in
`update_calibration()` wrong for `BARO_TYPE_WATER`, because `update()` computes
water altitude with a different formula and ArduSub calls `update_calibration()`
whenever the primary reads above the water. An earlier round had checked the
same line and called it right for both types.

The earlier round is correct. `update_calibration()` sets
`ground_pressure = get_sealevel_pressure(get_pressure(i) + p_correction, _field_elevation_active)`,
and `get_sealevel_pressure(P, 0)` returns `P` by construction
(`AP_Baro_atmosphere.cpp:335` solves for the p0 whose altitude difference is the
given altitude). `AP_Baro::init()` force-zeroes `_field_elevation` on every boot
(`AP_Baro.cpp:615-617`), so on a Sub the water formula evaluates
`(ground_pressure - corrected_pressure)/9800/sg = 0` and
`sensors[i].altitude = _alt_offset_active` - exactly what the next `update()`
computes. The two only diverge with a water barometer and a deliberately
non-zero `BARO_FIELD_ELV`, which is not a configuration that makes sense.

### Autotest assertions that could not fail (2026-09-06)

Third instance in this PR, so the pattern is worth the entry rather than the
incident. Found by the self-review's autotest pass, which was asked to state per
assertion what would have to be reverted for it to fail.

- The recorded-origin subtest of `BaroDriftClearedAtArm` asserted that
  `GPS_GLOBAL_ORIGIN.altitude` had not moved. Nothing in this series moves
  `common_EKF_origin.alt`, which is what that message reports, so it held with
  the whole change reverted. Its other assertion read the raw barometer through
  `get_relative_position_D_home()`'s no-home fallback rather than the estimate -
  the trap already recorded here. Replaced at `64dd291b3f` with the reported
  AMSL not moving across the arm, which is what the no-GPS carry path exists to
  guarantee.
- The height bound in `HeightDatumKeptOnMidairRearm` cannot catch a datum reset
  at all: `getPosD()` moves `ekfGpsRefHgt` by exactly the height the reset
  zeroes, so the reported down position is invariant by construction. The
  velocity assertion is the one with teeth. Comment corrected rather than the
  bound removed.

Two test-hygiene defects went with them: `peak_relative_alt_excursion()` polled
a 5 Hz stream on the default one second of wallclock, which is the host-stall
failure the autotest playbook describes; and `BaroDriftClearedAfterMidairDisarm`
left `SIM_BARO_DRIFT`'s accumulated offset behind, since setting the rate back
to zero does not undo it.

### BARO_ALT_OFFSET, second attempt: the deferred fix works (2026-09-06)

Superseding the earlier entry that recorded this as out of scope. The one-line
fix there was wrong for the reason given, but the conclusion drawn from it -
that a correct fix needs a new DAL message - was too strong, and the comment
left in the code said so. It does not: the value is unavailable *in that
frame*, not unavailable.

`baroHgtOffset` is what `hgtMea` subtracts from the baro reading. Zeroing it
assumes the recalibrated baro reads zero; it reads `_alt_offset_active`. The
correct value is the steady state `calcFiltBaroOffset()` converges to,
`baroDataDelayed.hgt + position.z`, and that is readable one frame later -
`storedBaro` has just been flushed, so nothing fuses baro height in between.
So set a flag in the reset and take the offset from the first sample after it.

Measured, `BARO_ALT_OFFSET=5`, peak reported height excursion over the 15 s
after a second arm with the vehicle stationary:

| build | peak |
|---|---|
| `baroHgtOffset = 0` | 5.126 m |
| deferred to the first post-reset sample | 0.050 m |

The 5.126 m matches the review's independently measured 5.116 m by a different
route. Covered by `BaroDriftClearedWithAltOffset`, which fails at 5.126 m with
the deferral removed. The drift tests stay green, which is what killed the
first attempt.

### The EKF3 meaHgtAtTakeOff line was dead (2026-09-06)

Added for symmetry with the EKF2 fix and justified in its commit message with
"it reappears through setAidingMode(), which assigns position.z =
-meaHgtAtTakeOff when aiding is lost". Wrong: `setAidingMode()` assigns
`meaHgtAtTakeOff = baroDataDelayed.hgt` at `AP_NavEKF3_Control.cpp:430` and
reads it at `:432`, so the value the reset wrote is overwritten before its only
use. Every other EKF3 reference is the declaration and the self-referential
refilter at `PosVelFusion.cpp:1384`. The line is removed.

EKF2 is different and the fix there is real: two genuine floors,
`MAX(..., meaHgtAtTakeOff)` at `AP_NavEKF2_Measurements.cpp:699` and
`AP_NavEKF2_PosVelFusion.cpp:1126`, measured at 3.634 m against 0.149 m.

Worth naming the error: a fix was applied to a second backend for symmetry, and
its justification was written from the shape of the EKF2 mechanism rather than
from reading the EKF3 call sites.

### Refuted: EKF2 does not need the OGN_HGT_MASK bit-2 refusal (2026-09-06)

The review asked why `EK2_OGN_HGT_MASK` bit 2 got no guard when
`EK3_OGN_HGT_MASK` bit 2 did, both commits being titled "restrict when the
height datum reset is performed". Because the two filters reference height
differently, and this archive already recorded the reason.

EKF3 refuses because `d644b92f9b` stopped it moving `EKF_origin.alt`, and in
bit-2 mode that is exactly what the height observation is referenced to
(`AP_NavEKF3_Measurements.cpp:726`), so state and observation would diverge.
EKF2 still moves `EKF_origin.alt`, sets `ekfGpsRefHgt = 0.01*EKF_origin.alt`
with it, and references its bit-2 observation to `EKF_origin.alt` as well
(`AP_NavEKF2_Measurements.cpp:648`), so the observation shifts by exactly the
amount `position.z` was zeroed by. Reported AMSL is `ekfGpsRefHgt - position.z`
either side and is preserved; `getPosD()` goes from `-oldHgt` to 0, which is
what a datum reset is for.

Guarding EKF2 there would refuse a reset that is self-consistent.

### assert_origin_frame_consistent() was an algebraic identity (2026-09-06)

The sixth assertion in this PR to certify nothing, and the cleanest example:
it could not fail on any build, for any values, because all three published
quantities it compares are built from the same two variables and the helper
subtracts them so they cancel.

With `EK3_OGN_HGT_MASK` bit 2 clear, writing `R` for `ekfGpsRefHgt`, `C` for
`common_EKF_origin.alt` and `d` for `getPosD_local()`:

- `GPS_GLOBAL_ORIGIN.altitude` = `C` (`AP_NavEKF3.cpp:1455`)
- `LOCAL_POSITION_NED.z` = `getPosD()` = `d + (C - R)` (`AP_NavEKF3_Outputs.cpp:277-288`, core `getOriginLLH` at `:388-397` substituting `100*R`)
- `GLOBAL_POSITION_INT.alt` = `R - d` (`getLLH`, `:305-316`)

`err = C - (d + C - R) - (R - d) = 0` identically. So the helper, whose stated
job was to catch the reset relabelling the origin frame, could not have caught
that or anything else. The derived check built on its return values - origin
altitude and local z unchanged across the re-arm - is inert for the same
reason: nothing in either code path writes `common_EKF_origin`, and `getPosD()`
is invariant across the reset by construction, which is precisely what
`d644b92f9b` was written to achieve.

Removed rather than repaired. What the cliff test actually rests on is the
`EKF_ALT_RESET` count and the EKF2 follower check, both of which have been
shown to fail by mutation.

The pattern across all six: an assertion is worth what a revert makes it do,
and nothing else. Reading the assertion tells you almost nothing - three of the
six read as strong checks and two were tautologies.

### A review correction that was itself wrong (2026-09-06)

Worth recording because it is the failure mode the root playbook warns about -
a claim marked checked being inherited rather than re-derived.

The 2026-09-06 review said the previous comment on `land_detector_count = 0`
was wrong: "not what master did: the disarmed branch never touched
`land_detector_count`, so `LDET` logged whatever the armed detector left - the
trigger value after a landing." That was accepted and the comment rewritten to
say the armed detector shares the counter and reads it as a landing countdown.

Both the review's claim and the rewrite are wrong. `Copter::set_land_complete()`
zeroes `land_detector_count` on every change of `land_complete`
(`land_detector.cpp:231-237`), and the armed landing transition reaches
`set_land_complete(true)` (`:174`), so the counter is zeroed at the landing, not
left at the trigger. Every transition to `land_complete == false` also goes
through that function, so the armed detector always starts from zero and can
never observe what the disarmed branch left. On the base branch a disarmed
vehicle logged `Count == 0`.

So the original wording - "as a disarmed vehicle has always logged it, at zero"
- was correct, and the round that "fixed" it replaced a right reason with a
wrong one. Restored, with the mechanism named, at the head below.

The line itself was never in question; only why it is there.

### BARO_ALT_OFFSET: the one-line fix is wrong, and the drift tests caught it (2026-09-06)

Raised by review at `56ccb5405e` and reproduced there: with `BARO_ALT_OFFSET=5`
the arm-time reset leaves the estimate settling at 5.1 m. The mechanism is
sound - `update_calibration()` leaves the barometer reading
`_alt_offset_active`, not zero, so `hgtMea = baroDataDelayed.hgt -
baroHgtOffset` equals the offset once `baroHgtOffset` is zeroed. The faulty
assumption predates the PR; what the PR changes is that the reset now runs on
essentially every arm rather than only the no-GPS branch.

The obvious fix is one line: set `baroHgtOffset` to what the barometer reads
after recalibration instead of to zero. It looks right, and a probe agreed -
arm, disarm, set `BARO_ALT_OFFSET=5`, settle, re-arm without moving:

| build | peak post-arm excursion |
|---|---|
| `baroHgtOffset = 0` | 3.534 m |
| `baroHgtOffset = dal.baro().get_altitude(selected_baro)` | 0.011 m |

**It is wrong anyway.** `AP_DAL_Baro::get_altitude()` returns
`_RBRI[sensor_id].altitude`, the value cached at the last `start_frame()`
(`AP_DAL_Baro.cpp:14-29`), and `resetHeightDatum()` runs outside the EKF frame,
so the read returns the *pre*-calibration altitude - which still contains the
drift the reset exists to remove. The probe passed only because the vehicle was
already at its datum there, making the two readings equal.

The drift cases said so immediately, on the same build the probe passed:
`AmslAltPreservedOnRearmAtDifferentElevation` failed at 165.3 m against a GPS
altitude of 76.3 m, and `BaroDriftClearedAfterMidairDisarm` at a 1.454 m
excursion against its 0.1 m bound. A clean code argument, a passing probe, and
still wrong in the direction the PR is about.

Correcting it properly needs `_alt_offset_active` through the DAL, and the DAL
rule here is that a struct is never grown - it takes a new message. That is not
a minimal change, so it is out of scope: the comment at
`AP_NavEKF3_PosVelFusion.cpp` now states the assumption and its limit instead of
claiming the post-reset baro reads zero, and the PR says so.

### Not adding a rangefinder gate to the latch clearing (2026-09-06)

Raised now by three independent passes: the disarmed clearing branch tests
only filtered accel under 1 m/s/s and vertical speed under 1 m/s, so a descent
slower than 1 m/s with the transient settled - a parachute, an autorotation,
a vehicle caught on a tether - clears `disarmed_in_air` while still airborne,
and a re-arm before touchdown then resets the datum in flight. That is the
dangerous direction, unlike the other latch residual.

The close is available and cheap. The armed detector already carries exactly
the guard, permissive when there is no rangefinder, at `land_detector.cpp:153`:

```cpp
bool rangefinder_check = (!rangefinder_alt_ok() || rangefinder_state.alt_m_filt.get() < LAND_RANGEFINDER_MIN_ALT_M);
```

`read_rangefinder` is a 20 Hz SCHED_TASK, so the value is live while disarmed,
and a vehicle without a rangefinder is unaffected. `WoW_check` is the same
shape.

Not done, deliberately. The maintainer-facing review has seen this twice and
both times recorded it as an accepted residual rather than an open issue - the
2026-09-06 round lists only the `land_detector_count` coupling under smaller
things, not the clearing criteria. Adding a behavioural change the reviewer has
not asked for, at this stage, needs its own rangefinder-configured test to be
honest about, and the case needs a mid-air disarm followed by a sub-1 m/s
descent and a deliberate re-arm before touchdown. Recorded here so the option
and its cost are on file rather than rediscovered.

### A follower that refuses keeps the old datum (2026-09-06)

Recorded, not fixed. `AP_AHRS.cpp` discards the follower's return, so a backend
with its own reason to refuse is left running against a barometer that moved.
Reproduced by the review with EKF2 configured and EKF3 running at
`EK3_OGN_HGT_MASK=4`: 165.3 m against GPS 76.2 m. It needs two backends with
divergent height-source configuration to reach, and the refusal it rests on is
the right behaviour for that backend - at the merge base EKF3 would have reset
and corrupted its origin-referenced height instead. A comment in
`AP_AHRS::resetHeightDatum()` records the limitation.

### Second squash pass: 25 commits to 20 (2026-09-06)

The review asked for commit granularity, on the grounds that a later commit
repairing an earlier one leaves a knowingly broken range for bisect. Grouped on
that rule rather than flattening every subsystem to one commit:

- `AP_AHRS: reset and report only the configured backend` absorbed the fix for
  the 89 m defect it introduced, and moved ahead of the Copter block. It had to:
  it is what changes the return type to `bool`, and the Copter logging change
  folded below uses that return.
- The Copter arm-block commits (log-on-result, `arming_altitude_m`, the terrain
  recapture, the helper) folded into `Copter: clear baro drift at arm time`.
  `Copter: treat a watchdog-armed boot as a mid-air disarm` stays separate: it is
  a distinct mechanism, not a repair.
- `AP_NavEKF3: move the terrain state with the height datum` folded into the
  rangefinder clause that made it reachable, which is what the review asked for.
- The two test-hardening commits were split four ways by hunk and folded into
  the tests they harden, so no test lands in a knowingly weaker state first.

Not done, and said so in the reply: flattening all seven `autotest:` commits
into one. That produces a single commit carrying five tests and two bound
relaxations, which is worse against the "atomic commits" rule, not better.

Two conflicts came up in the replay, both from folding a later test change into
an earlier commit whose file does not yet contain the surrounding tests; both
resolved by keeping only the hunk that belongs to that commit. Tree verified
byte-identical to the pre-rebase head, the test list resolves at all 20 commits,
and the three reordered or squashed intermediates build copter and blimp.

### Correction: KalaupapaCliffs is 165.25 m, not 200 m (2026-09-06)

Derived from the source, not measured, and wrong. A review pass decoded the
SRTM tile (`N21W157.hgt.zip`) and read 202 m at the home coordinates, and that
number was used to "correct" a test comment that already said 165 m.
`Tools/autotest/locations.txt:93` sets the SITL home altitude to **165.25 m**,
and the test logs `Cliff-top AMSL: 165.3 m`. The terrain tile's height at a
coordinate is not the SITL home altitude; locations.txt is. Fixed at
`8960850d97`.

### Review findings answered without a code change (2026-09-06)

From tridge's automated reviews at `1c88a3bf62`, `9525e7d9ee` and
`06860d0425`. Recorded so the next pass does not re-raise them unanswered.

- **"`BaroDriftClearedWithRangefinderHeightSwitch` is green by construction
  and covers none of the new clause."** Wrong, and measured: without the
  EKF3 clause the test fails with "No EKF_ALT_RESET at arm". The reasoning
  behind the finding was right - the AGL KF override it cites is not on this
  branch - but `terrainHgtStable` is stuck true for the older reason above,
  so the switch engages anyway. The finding did lead to the terrain-state
  bug, which is real.
- **`storedGPS` is not flushed alongside `storedBaro`.** Left alone.
  `storedGPS` carries NE position and velocity as well as height, so
  flushing it to correct a height reference would discard horizontal
  observations. Master shifts the same reference by the same amount
  (`EKF_origin.alt` there, `ekfGpsRefHgt` here), so this is unchanged from
  master rather than something the PR introduces. A shift of the queued
  heights, rather than a flush, would be the scoped fix; separate PR.
- **An EKF3 core that refuses still has the baro moved under it by a core
  that accepts.** Left alone. `baroHgtOffset` re-tracks over about 1 s and
  the exposure is a lane switch inside that window.
- **`getOriginLLH()` now also requires the primary core to have an origin.**
  Intended. The reported origin should belong to the frame `getPosD()` is
  expressed in; the change only delays a "not ready yet".
- **Plane's `update_home()` calls `barometer.update_calibration()`
  unconditionally, ahead of the new refusals.** Real, and not fixed here.
  `ArduPlane/commands.cpp:151-152`. Copter reaches the calibration only
  through `resetHeightDatum()`, so a refusal there also holds the baro
  still; Plane does not. Reachable only with `EK3_OGN_HGT_MASK` bit 2 or a
  beacon/extnav height source, both non-default. Not touched because
  @tridge asked this PR to leave Plane alone, and the fix belongs with the
  `HOME_RESET_ALT` follow-up. Noted in the PR description.

### Self-review findings answered without a code change (2026-09-06)

From the `/pr-review` pass at `33e4911d63` (four Claude reviewers plus four
independent Codex cold reads).

- **"Only the primary core's answer is reported, but every core that accepts
  recalibrates the shared baro, so a refusing primary gets a baro step of the
  whole drift."** Refuted on the reachable configurations. Cores can only
  disagree through a per-core `POSZ` (`EK3_SRC_OPTIONS`) or a per-core
  `activeHgtSource` plus `onGroundNotMoving`; in both, the refusing core is by
  construction not using baro as its height observation, so `calcFiltBaroOffset`
  absorbs the shift rather than the state taking a step. A core with
  `activeHgtSource == BARO` always passes the guard's first leg. Residual is a
  lane switch inside the ~1 s convergence, which is what the previous round
  recorded.
- **"`resetHeightDatum()` is a no-op when the configured backend is
  DCM/SIM/ExternalAHRS, and `AP_Baro`'s field-elevation path rezeroes the baro
  anyway."** True, and deliberate. It is the same property the previous round
  accepted when the loop was replaced by `configured_backend->resetHeightDatum()`:
  a parallel non-configured estimator is no longer re-datumed when the shared
  baro moves, and its `baroHgtOffset` re-tracks. The cost, stated plainly: under
  `AHRS_EKF_TYPE` 0/10/11 the arm-time drift clearing does not run at all,
  where on master EKF3 performed it. Not reverted, because reverting reopens
  the EKF2-recalibrates-under-EKF3 issue that change fixed.
- **"Refusing on `EK3_OGN_HGT_MASK` bit 2 is over-broad, because only the
  `bit0 && bit2` and `bit1 && bit2` sites use it."** Refuted: two more sites use
  bit 2 alone - `AP_NavEKF3_Measurements.cpp:721` references the GPS height
  observation to `EKF_origin.alt` instead of `ekfGpsRefHgt`, and
  `AP_NavEKF3_Outputs.cpp:394` stops reporting `ekfGpsRefHgt` as the origin
  height. Both are exactly the references the reset moves, so the refusal is
  right with bits 0/1 clear as well. It does mean `EK3_OGN_HGT_MASK=4` alone
  has no drift handling at all; that is a consequence, not a defect.
- **"The `||` in the sticky latch guards a case that cannot happen."** Refuted:
  the reachable case is not a second call inside one disarm (that recursion is
  stopped) but a second disarm after a mid-air re-arm, where `land_complete` is
  still true from the first. `HeightDatumKeptOnMidairRearm` exercises exactly
  that sequence.
- **The latch is not set when the land detector itself triggers the disarm**
  (`set_land_complete(true)` assigns before calling `arming.disarm()`), so a
  false landing detection at altitude with `THR_BEHAVE_DISARM_ON_LAND_DETECT`
  defeats it. True, and left. It is the land detector's opinion at the moment of
  disarm, which is what every other consumer of `land_complete` in Copter uses,
  including the GCS and rudder disarm gates immediately above. Not a regression:
  master reset unconditionally.
- **The latch can be set on a grounded vehicle** - arm in a manual-throttle
  mode, raise the throttle without lifting off (`set_land_complete(false)`),
  then disarm on an aux switch, which is not gated on landed state. True, and
  left: the consequence is that the next arm skips the drift reset, which is
  master's behaviour, and the land detector clears it after 1 s of stillness.
  It does not self-heal on a platform that never goes still.
- **`meaHgtAtTakeOff` and the stale `baroDataDelayed` are not refreshed**, so an
  AID_NONE transition inside the buffer-refill window re-injects the cleared
  drift through `stateStruct.position.z = -meaHgtAtTakeOff`. Pre-existing and
  unmeasured; the window is a few hundred ms. Recorded, not fixed.
- **`posResetD`/`posDResetCount` are not set by the datum move.** Pre-existing.
  Every caller runs disarmed or on the ground, so no controller is mid-flight
  when it happens; the residual is an unreported step across a later lane
  switch between cores that disagreed.
- **The heli `StabilizeTakeOff` bound at 1.0 m is a 10x loosening.** Left at the
  `PosHoldTakeOff` precedent the previous review round accepted. Tightening it
  towards the measured 0.08-0.12 m trades a review point for CI flakiness,
  which is what produced the blockers this round had to clear.

### What each new test actually discriminates (2026-09-06)

From the self-review's autotest pass, traced against `c9286e3096`. Three of
the assertions only guard behaviour introduced earlier in the same PR, and one
produces identical output on master. Say so in the PR body rather than letting
a reviewer discover it.

| test | fails against master? |
|---|---|
| `BaroDriftClearedAtArm` subtest 1 (GPS healthy) | yes - AMSL sits ~9 m off GPS |
| subtest 2 (dead receiver) | no - guards the 3D-fix clause added in this PR |
| subtest 3 (recorded origin, no GPS) | no - and its `peak` check reads the raw baro through `get_relative_position_D_home()`'s fallback, not the estimate |
| `BaroDriftClearedWithRangefinderHeightSwitch` | yes - no `EKF_ALT_RESET`, or 0.648 m of post-arm movement |
| `AmslAltPreservedOnRearmAtDifferentElevation` | no - guards the origin-frame handling added in this PR |
| `HeightDatumKeptOnMidairRearm` | yes, against the PR without its own guard: EKF3's `onGround` is the armed flag inverted, so the reset would fire mid-air |
| `BaroDriftClearedAfterMidairDisarm` | yes, against the PR without the land detector clearing the latch |
| QuadPlane `AmslAltPreservedAfterUpdateHome...` | no - master produces the identical AMSL, `getPosD` and `getOriginLLH`; a regression guard, as its own commit message says |

Hardened at `4a79aab29c` rather than left: the rangefinder test now asserts its
own precondition (the drift must be invisible in the reported height, which is
true only while the rangefinder holds the source), the return-leg descent wait
went 60 s -> 150 s because `fly_guided_move_to()` waits on horizontal distance
only, the QuadPlane disarm wait 600 s -> 900 s against a measured 434 s, and the
20 Hz `LOCAL_POSITION_NED` stream is raised with the context form so it does not
leak into the rest of the run. `Tools/autotest/CLAUDE.md` recommended the
leaking form; corrected there too.

One of those hardening changes was itself wrong and the re-run caught it.
`context_set_message_rate_hz()` measures the existing rate for ten seconds
before setting the new one; called where `set_message_rate_hz()` had been, just
after the mid-air disarm, that is 170 m of fall. The vehicle reached the ground
inside the second measurement window and the bounce read as a velocity step,
17.2 -> -5.8 m/s, with a pre-rearm height of 66 m where 240 m was intended.
Raising the rate before the takeoff instead restores it: 241.8 m pre-rearm,
17.0 -> 17.0 m/s, arrest at 148.9 m. Fixed at `d8a80b042e`.

The branch was then squashed to 25 commits at `ab41a91714`: the self-review
fixes folded into the commits that introduced them, the truncated
`give HeightDatumKeptOnMidairRearm room to recover` message replaced, and the
rangefinder commit reworded off the AGL KF claim. `autotest: correct the Copter
baro drift registration and coverage` had to be split first, because its
`max_err` half belongs to `autotest: add Copter mid-air disarm height datum
tests` and its registration half to `autotest: cover the datum reset under the
rangefinder height switch`; folding it whole would have left the earlier commit
carrying the TypeError. `reset` is gated separately from `rebase` here, so the
split used the branch-and-patch recipe rather than `edit` + `reset HEAD^`. Tree
verified byte-identical to the pre-rebase head, and every commit in the range
now builds its test list and is free of the `max_err` call.

Left: the `assert_EV_count()` and peak-excursion helpers are open-coded in the
rangefinder test (the event count is `>= 1` rather than exact because the
field-elevation path can also fire the reset, and that was not measured); the
30 s `accumulate_baro_drift()` delay stays a fixed delay because the drift it
builds is the point.

## PR description (edited 2026-09-06 at `ab41a91714`)

The body now carries the rangefinder clause and its real mechanism, the terrain
state A/B, the watchdog seed and its lack of a test, the Plane
`update_home()`/`update_calibration()` note @tridge's follow-up should pick up,
and a "tried and rejected" list with the number that rejected each: the
periodic reset, the `HOME_RESET_ALT`-style tolerance gate, the
`position.z + rngOnGnd` terrain convention, and seeding the mid-air record on
every boot.

It also states which of the new tests actually fail on master - two of the six -
and says plainly that the rest guard behaviour introduced elsewhere in this PR.
That was previously only implied for the QuadPlane test.

## The problem

The barometer drifts with temperature while a copter sits disarmed, so the
reported height wanders off - metres by takeoff. The PR re-zeroes the height
reference at arm, just before flight, so the altitude is correct when it starts
being used.

## The conclusion and why

Arm-only is the right scope for Copter. `resetHeightDatum` is only valid on the
ground, with baro/GPS height, at a moment you are about to use the estimate -
arm satisfies all three. Running it repeatedly while disarmed fires it in states
it was never designed for, and that is where every problem came from.

The periodic reset, in the forms tried, caused:

1. **Height corruption with a non-baro height source** (GPSViconSwitching). The
   reset had no guard for ExternalNav/vicon; firing it there snapped reported
   height to the takeoff altitude on the ground. Plot B.
2. **Degraded GPS-denied takeoff estimate** (BaroDriftClearedAtArm, GPS-denied).
   The reset zeroes `velocity.z`, which on the ground is how the EKF learns its
   Z accel bias (zero-velocity fusion); repeatedly erasing it leaves a worse
   bias at arm that integrates into a post-arm altitude climb. Plots C and D.
3. **Disarmed replay-logging stress** (Replay) - CI-only evidence.
4. It only avoided slowing from-boot bias learning via a convergence gate +
   non-Plane interval, i.e. load-bearing complexity arm-only does not need.

Plane needs no change: it clears drift at arm (works baro-only) and gates its
periodic reset on a GPS fix, which confines it to the regime where it is
harmless. Details in `analysis.md`.

## Key finding: it is the velocity reset, not the datum

Paul Riseborough's review point - a datum reset should redefine the zero-point
without touching vertical velocity - is the crux. A one-variable A/B (Plot D)
confirms it: with the periodic reset firing during GPS-denied bias learning,
zeroing `velocity.z` plateaus the learned bias at ~0.56, while re-datuming
height only reaches the true 0.70. The height/baro re-datum is innocent;
`resetHeightDatum` does not touch the covariance.

That motivated #33338 (a `reset_velocity` flag: periodic = height-only, arm =
full). It fixes findings 1 and 2 and drops the gate - but `RudderDisarmMidair`
still fails on the periodic reset regardless of velocity handling (arm-only
3/3 pass; both periodic variants 3/3 fail), so arm-only remains the
recommendation. See `../33338/`.

## Second key finding (2026-08-29): the reset needs no tolerance gate

`getPosD()` reports `position.z + (public_origin.alt - ekfGpsRefHgt)`. The
full reset zeroes `position.z` and re-anchors `ekfGpsRefHgt` to GPS, so with
GPS the reported height already drops the drift and keeps a real elevation
change; the Kalaupapa re-arm test gives identical numbers with and without
the gate (AMSL 76.3 m, XKF1.PD 89.07 m). Removing it exposed that
`NavEKF3::getOriginLLH()` reported the core's corrected reference height
whenever `common_origin_valid` had been cleared by a filter re-init (an
origin set before the filter starts), which left the reported origin, posD
and AMSL inconsistent by the reference shift: FarOrigin climbed without
bound. The frontend now always reports the public origin height. The heli
`StabilizeTakeOff` offset (0.08-0.12 m) is `AP_Baro::update_calibration()`
re-zeroing from a single noisy sample, not rotor wash (Plot E).

## Real-flight context (2026-08-29)

Numbers from the private flight notes; none of these logs are committed.
They size the problem on hardware, show the vehicle-side trigger working,
and record one trap.

Disarmed drift on real vehicles:

| vehicle, log | window | drift | baro temperature |
|---|---|---|---|
| MatekH743 flow quad, log12 (ground session, never armed) | 206 s | -1.17 m | 41.8 -> 61.8 C, corr -0.978, ~6 cm/C |
| 5-inch baro-only quad, log A (motors off on the floor) | 80 s | -0.88 m | 31.6 -> 43.1 C |
| ducted quad, log21 (SET_HOME to 3rd arm) | 112 s | 0.36 m | indoor, not recorded |

A metre or so over a few minutes, so the 9 m the SITL test injects is a
stress case, not a typical one. On the 5-inch quad, 60% of the 80 s drift
(+6.25 of +10.46 Pa) was the TCAL_BARO_EXP correction rather than the
sensor: the model is powf(MAX(T-25,0),exp), non-negative and increasing,
so on a barometer that reads high when hot it adds drift. At arm that is
just an offset and the reset clears it with the rest; in flight it is
not (below).

The arm-time reset seen working: flown on the ducted quad, log21 (not
committed), SmallFastDrone 4.7-beta4, which carries the same vehicle-side
change (reset on every arm rather than only when home is unset). At the
third arm CTUN.BAlt stepped -0.21 -> 0.00 and the EKF altitude 0.03 -> 0.00
in one sample; the rangefinder read 0.16 m before and after. Two caveats.
That build's resetHeightDatum has a rangefinder special case; this PR's
guard returns false whenever the rangefinder is the active height source,
and whether it is at arm on an EK3_RNG_USE_HGT > 0 vehicle depends on the
hysteretic switch state (Copter asserts terrain_hgt_stable only during
takeoff and landing, so on the ground it is often still baro). Skipping is
benign for the estimate, since calcFiltBaroOffset runs whenever baro is not
the active source and baroHgtOffset absorbs the drift, but CTUN.BAlt keeps
it. So the flight is evidence for the trigger, not for this guard on a
rangefinder-height vehicle. Worth one sentence in the PR body.

The trap: the same flight ends with the EKF 0.85 m below the rangefinder
40 s after a reset that demonstrably fired. It was first blamed on the
idle-period drift; it is not. The estimate was 0.00 at the reset and
reached -0.52 m over the next 5 s of spool-up on the ground while the
compensated barometer read within 0.1 m of zero: IMU drift against a baro
deweighted for ground effect, not the reset. A wrong altitude after a
confirmed arm reset has another cause; check the spool-up window (#32972,
#32472) and the terrain offset (#32553) before this reset.

What the reset cannot touch is in-flight drift, which on the outdoor
vehicles is the larger number: MatekH743 flow quad 1.53 m over 3 min at
20 m with the board cooling 22 C (logtd5); 1.2 m of CTUN.BAlt drift over
100 s warming 9.4 C (log3; the EKF rejected most of it, BAlt minus EKF mean
+0.21 m); the 5-inch quad +0.41 to +0.66 m per flight from the TCAL term
alone as the board prop-cools. Those need the calibration fixed or a second
height reference, not a datum reset.

One tension across the author's own PRs, for reviewers: the periodic-reset
argument above leans partly on disarmed Z-bias learning (finding 2, Plots C
and D), while #32471 ships an option to inhibit disarmed learning because
it learns the motors-off bias. The arm-only conclusion does not depend on
finding 2 (the vicon corruption and RudderDisarmMidair stand on their own),
but the write-up leans on it.

## Plots

| | |
|---|---|
| ![A](plots/A_arm_reset.png) | **A** - arm-time reset clears ~9 m drift in one sample; removes the phantom -0.3 m/s, no kick |
| ![B](plots/B_gpsvicon.png) | **B** - periodic reset corrupts height (jumps to ~9.5 m) with vicon as the height source; arm-only stays at 0 |
| ![C](plots/C_gps_denied_postarm.png) | **C** - GPS-denied: periodic post-arm altitude climbs; arm-only stays flat |
| ![D](plots/D_velocity_vs_bias.png) | **D** - zeroing velocity.z (red) interrupts bias learning; height-only (green) reaches the true bias |
| ![E](plots/E_heli_baro_recal_noise.png) | **E** - heli post-arm height: the reset re-zeroes the baro from one noisy sample (red); with zero baro noise (green) or no reset (blue) it stays at 0 |

## What is here

```
32768/
  README.md          <- this file
  analysis.md        <- full write-up (posted as the PR #32768 analysis comment)
  design-notes.md    <- earlier design notes on the (since removed) periodic reset
  self-review-2026-08-29.md <- review findings, gate removal, origin-height fix, heli mechanism
  plots/             <- A/B/C/D/E PNGs + make_plots.py (regenerates them from data/)
  data/
    arm-only/        <- SITL BINs from the arm-only build (this PR's design)
      barodrift_arm.BIN     (Plots A, C)
      gpsvicon_clean.BIN    (Plot B, clean trace)
    periodic/        <- SITL BINs from the periodic-reset build(s)
      gpsvicon_FAIL.BIN     (Plot B, corrupted trace)
      guard_barodrift.BIN   (Plot C, periodic+guard GPS-denied)
      fullreset_bias.BIN    (Plot D, zero velocity.z)
      heightonly_bias.BIN   (Plot D, leave velocity.z)
    heli/            <- SITL heli BINs from the final series (Plot E)
      reset_baro_rnd_0p2.BIN    (reset at arm, SITL default baro noise)
      reset_baro_rnd_0.BIN      (reset at arm, SIM_BARO_RND 0)
      no_reset_home_locked.BIN  (home locked, so no reset)
```

All BINs are SITL (ArduCopter V4.8.0-dev, CMAC default home; each carries
hundreds of `SIM_*` parameters).

## Reproduce

Plots, from this directory:

```
python3 plots/make_plots.py
```

The SITL behaviours, in an ardupilot checkout:

```
# arm-only branch (this PR, 14 commits at 9525e7d9ee) - these pass:
git checkout pr-baro-drift-minimum
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedAtArm,AmslAltPreservedOnRearmAtDifferentElevation,FarOrigin
Tools/autotest/autotest.py --no-configure test.Copter.GPSViconSwitching
Tools/autotest/autotest.py --no-configure test.Copter.HeightDatumKeptOnMidairRearm,BaroDriftClearedAfterMidairDisarm

# the rangefinder height switch finding above; fails before the 2026-09-05 fix
# with "No EKF_ALT_RESET at arm", and before 89caba96a1 with a 0.648 m post-arm
# height excursion:
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedWithRangefinderHeightSwitch

# periodic-reset branch - reproduces the problems (run GPSViconSwitching a few times):
git checkout pr-baro-drift-minimum-periodic-reset
./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.RudderDisarmMidair   # fails on periodic
```

## Branches and people

- `pr-baro-drift-minimum` - the PR #32768 branch (arm-only). Rewritten to the
  11-commit series on 2026-08-29 and force-pushed; 14 commits at `9525e7d9ee`
  as of 2026-09-05, the last three being the mid-air disarm tests, the
  `EKF_ALT_RESET` logging fix and the test recovery-height fix.
- `pr-baro-drift-minimum-periodic-reset` - PR #33338 (height-only periodic experiment).
- Reviewers: @tridge (suggested mimicking Plane's periodic reset), @rmackay9,
  Paul Riseborough (EKF author; "less is more", datum reset should not touch
  velocity/covariance - which the velocity-reset finding confirms).
