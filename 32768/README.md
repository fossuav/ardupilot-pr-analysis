# PR #32768 - Clear baro temperature drift on arming (ArduCopter / EKF3)

Analysis archive for [ArduPilot/ardupilot#32768](https://github.com/ArduPilot/ardupilot/pull/32768).
Branch `pr-baro-drift-minimum` (andyp1per fork), base `master`, head
`33e4911d63` (2026-09-06). All committed data is SITL; real-flight numbers are
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

Fix prepared on the SmallFastDrone branch on 2026-09-05, not yet pushed to this
PR: allow the reset when the configured primary source is baro or GPS and
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

The test asserted only that `EKF_ALT_RESET` reached the log, so it was green
across all three rows. It now asserts the post-arm height as well.

EKF2 keeps `terrainState = 0`: its `resetHeightDatum()` still refuses a
rangefinder height source outright, so the constraint always runs there.

### Measured and rejected

| Change | Argument for | Measured |
|---|---|---|
| `terrainState = stateStruct.position.z + rngOnGnd` in `resetHeightDatum()` | matches `ResetHeight()`, which is the established convention for the same state; suggested in review at `06860d0425` | 0.529 m post-arm excursion against 0.648 m unchanged and 0.000 m carrying the state across. Rejected 2026-09-06 |
| seed `disarmed_in_air = true` on every boot, rather than only a watchdog-armed one | closes the booted-in-air hole without depending on the watchdog flag | not measured; rejected on inspection because a vehicle arming on a moving platform never satisfies the accel-stationary test, so the drift reset this PR exists for would never run there |

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
