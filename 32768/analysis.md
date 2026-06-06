# Clearing disarmed baro drift on Copter: why the reset belongs at arm

## Thesis

Resetting the EKF height datum at arm is the only safe, coherent, and
meaningful way to clear accumulated barometer temperature drift on Copter. The
periodic disarmed reset (mimicking Plane) clears a number nothing acts on, runs
`resetHeightDatum` in vehicle states it was never written for, and in the
GPS-denied case actively degrades the takeoff altitude estimate. The three SITL
comparisons below back each claim.

Status: this is now the implemented design. The periodic reset and its
convergence-gate machinery were removed; this branch (`pr-baro-drift-minimum`)
resets at arm only. The periodic-reset version analysed here is preserved on
branch `pr-baro-drift-minimum-periodic-reset` so the comparisons below can be
reproduced.

All numbers are from SITL (ArduCopter, EKF3). `XKF1.PD`/`VD` are NED position/
velocity down; `XKF2.AZ` is the learned Z accel bias; `CTUN.BAlt` is barometer
height; `POS.RelOriginAlt` is reported height above the EKF origin. Below,
"arm-only" is this branch and "periodic" is the
`pr-baro-drift-minimum-periodic-reset` branch.

## Background

The barometer drifts with temperature while the vehicle sits disarmed, so the
reported altitude can be several metres off by the time it arms. The goal is a
correct altitude at takeoff. Plane resets the height datum every ~5 s while
disarmed and at arm; this PR resets at arm only. The review suggestion was to add
Plane's periodic reset; this note records why that was tried and then removed.

## Arm-time reset has the three properties we need

### Meaningful - the drift only matters from arm onward

The altitude estimate is only consumed by the controller once the vehicle is
armed. The arm reset makes it correct at exactly that instant. Plot A is an
arm-time reset clearing ~9 m of accumulated drift (SIM_BARO_DRIFT, vehicle
stationary):

![arm-time reset](plots/A_arm_reset.png)

The estimate tracks the drifting baro up to ~9.5 m while the vehicle sits still,
then steps to 0 in one sample at arm. Clearing the same drift continuously while
disarmed corrects a value no controller reads - it is busywork, not a feature.

### Safe - arm is the one state the operation is valid in

`resetHeightDatum` is "relabel the current height as zero, recalibrate the baro,
flush the baro buffer." That is only valid (i) on the ground, (ii) with baro or
GPS as the height reference, and (iii) at a moment you are about to start using
the estimate. The arm event satisfies all three by construction.

The feared "kick" is the opposite of what happens (Plot A, lower panel): before
the reset the EKF reports a phantom -0.29 m/s descent - the baro drift rate read
as motion - and the reset removes it. Post-reset `|VD|` stays under 0.015 m/s.
There is no transient for the controller to chase. (This relies on the buffer
flush and `baroHgtOffset = 0`; a naive reset skipping those would produce a
transient, which is probably where the "kick" worry comes from, but this
implementation does both.)

### Coherent - one reset, one well-defined trigger

Firing once at a known event is simple to reason about and to test. The periodic
version fires in whatever state the vehicle happens to be in every 10 s, and
that is exactly where it goes wrong.

## Why the periodic reset is none of these

Every failure below is the same root cause: `resetHeightDatum` running in a
disarmed state it was not designed for.

### 1. It fires with non-baro height sources and corrupts the estimate

GPSViconSwitching: take off on GPS, switch to ExternalNav (vicon) height,
disable GPS, land. `resetHeightDatum` guards the rangefinder source but not
ExternalNav, so the periodic reset zeroes `position.z` and recalibrates the baro
while height is referenced to vicon, and the reported height jumps to the
takeoff altitude (~9.5 m) with the vehicle on the ground:

![gpsvicon corruption](plots/B_gpsvicon.png)

Attribution: arm-only passes 5/5, periodic 3/5 (intermittent, depends on the
10 s tick landing near the disarm; the mechanism is deterministic). Adding an
ExternalNav guard fixes this specific case - but needing a per-source guard is
the tell that the reset is firing where it should not.

### 2. It degrades the GPS-denied takeoff estimate - the serious one

This is the case the feature is meant to help, and the periodic reset makes it
worse. Indoors / GPS-denied, the EKF learns its Z accel bias while disarmed
through zero-velocity fusion. The periodic reset keeps erasing the small
height/velocity error that fusion needs, so at arm the bias estimate is worse.
Once armed (zero-velocity fusion off, ground effect inhibits learning) that
error integrates into a climbing altitude and velocity.

Plot C is the GPS-denied BaroDriftClearedAtArm scenario, with the baro drift
already stopped before arm so the estimate should be flat. The ExternalNav guard
from issue 1 is in place:

![gps-denied post-arm drift](plots/C_gps_denied_postarm.png)

Arm-only stays flat (<0.03 m, VD ~0). The periodic build climbs past the 0.1 m
mark within 2 s and keeps rising (~0.13 m), with VD accelerating - the signature
of integrating an uncompensated bias. The convergence gate does not prevent
this; closing it would need a more complex innovation/rate-based gate, i.e. more
machinery to undo harm the reset inflicts on itself.

### 3. It stresses the disarmed replay-logging path

The periodic reset writes an RHGT replay block every 10 s while disarmed. The
`log_replay && log_while_disarmed` path panics when a disarmed write hits a full
backend buffer; the Replay test core-dumped in CI in the disarmed setup phase,
where the only `resetHeightDatum` that can run is the periodic one. (Not
reproducible in my local environment, which panics Replay even at the
merge-base, so this one is CI-only evidence.)

### 4. It only avoids breaking from-boot bias learning because of added tuning

At Plane's 5 s interval the naive reset slows from-boot Z-bias convergence
~4.5x. Getting back to baseline takes a 10 s interval plus the convergence gate.
That is load-bearing complexity the arm reset does not need, because it never
fires during the disarmed learning window.

## What about Plane?

No change is needed for safety - Plane already follows the pattern this argues
for - but there is a structural cleanup worth doing (last subsection below).

Plane already follows the safe pattern:

- It clears drift at arm. `AP_Arming_Plane::arm()` calls `update_home()`, whose
  `resetHeightDatum` runs unconditionally (the GPS gate inside `update_home` is
  only on the home-position move, not the datum reset). So Plane gets baro-only
  arm-time clearing - exactly what this PR adds to Copter.
- Its periodic reset is gated on a GPS 3D fix at the call site (`Plane.cpp`), so
  it only runs with GPS present. That is the key: the bias-learning harm (Plot C)
  only occurs GPS-denied, where zero-velocity fusion is the sole bias
  observation; with GPS the EKF has independent velocity aiding and the reset is
  harmless. The GPS gate confines Plane's periodic reset to that safe regime - it
  is protective, not a bug (an earlier draft of this note had that backwards).
- The ExternalNav corruption (issue 1) is now fixed for Plane too, via the shared
  `resetHeightDatum` source guard.

The irony: the Copter periodic reset that was tried (preserved on
`pr-baro-drift-minimum-periodic-reset`) was deliberately *un-gated* - made
baro-only to serve indoor copters - so it ran in exactly the GPS-denied regime
Plane's gate excludes, on the vehicle whose vertical-thrust launch is most
sensitive to a bad Z bias. The consistent-with-Plane choice is therefore not
"add Plane's periodic reset to Copter" but "clear at arm, and never run the
periodic reset while GPS-denied." For Copter that is arm-only. (If a periodic
reset on Copter is ever wanted, it must be GPS-gated like Plane's, not the
baro-only version that was removed.)

### Would a GPS-denied Plane need the Copter machinery?

No. Because the periodic reset is gated on a fix, a Plane that loses GPS
automatically degrades to "arm-time clearing only, no periodic reset" - which is
the Copter arm-only design. The convergence gate, the interval choice and the
inject-from-boot test changes all exist solely to make an *un-gated* periodic
reset survivable; a GPS-denied Plane never runs that, so it needs none of them.
What it does need - arm-time clearing and the ExternalNav source guard - it
already has (the arm path runs `resetHeightDatum` baro-only, and the guard is in
shared core). A vertical-takeoff QuadPlane is as Z-bias-sensitive as a copter,
which is exactly why it must keep *not* running the periodic reset without GPS.

### The convolution worth fixing: home move vs datum reset

`update_home()` does two unrelated jobs: it moves the home position (a
horizontal, GPS-required, genuinely-periodic concern) and it resets the height
datum (a vertical, baro-driven concern that only needs to be right from arm
onward). Tying them together is what makes "should the periodic reset run?" hard
to answer - the periodic call inherits the home move's GPS requirement, and the
datum reset rides along whether or not that is the right moment for it.

Splitting them makes each governed by its own correct rule and makes the
height-datum story uniform across both vehicles:

- periodic, GPS-gated: update home position only (required - tracks the GPS fix
  as it refines while disarmed, for RTL/relative-alt accuracy)
- at arm: reset the height datum (clears baro drift, works baro-only, on-ground,
  baro/GPS source) - the same single call Copter makes

The only thing lost is the periodic datum reset that currently runs while
disarmed *with* GPS. That is harmless but also near-pointless: it clears pre-arm
baro drift that is cosmetic on the ground and that the arm reset clears anyway.
Worth a careful look during the refactor: `update_home`'s home-altitude move and
the datum reset both feed AMSL reporting (`ekfGpsRefHgt`), so the split needs to
keep moving home-alt and re-anchoring the datum consistent - today they happen in
one call. This is a Plane cleanup, separable from the Copter arm-only change, but
it is the structural end-state both vehicles should land on: home updates are
periodic, datum resets happen at arm.

## What the arm reset does NOT do (checked)

- No kick (Plot A).
- Does not dump learned bias - the largest downward step in `XKF2.AZ` across
  resets during learning was 0.01 m/s/s (noise); the reset touches height/
  velocity/baro, not the accel-bias state.
- Cannot fire in flight (`resetHeightDatum` returns early unless `onGround`, and
  the call is gated on `!motors->armed()`).

## Conclusion

Reset at arm. It clears the drift at the only moment it matters, in the only
state the operation is valid, with no kick and no collateral damage. The
periodic reset clears a number nothing reads while introducing a height-source
corruption, a GPS-denied takeoff regression, a replay-logging hazard, and tuning
complexity - every one of them a consequence of running `resetHeightDatum` in a
disarmed state it was not designed for.

The ExternalNav guard is a good standalone hardening of `resetHeightDatum` and
worth keeping regardless; it does not make the periodic reset safe (Plot C
stands with the guard in place).

## Reproduction

On this branch (arm-only) the relevant tests pass:

```
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedAtArm
Tools/autotest/autotest.py --no-configure test.Copter.GPSViconSwitching
```

To reproduce the periodic-reset problems, check out the preserved branch and run
the same tests (the periodic version also carries the ExternalNav guard, so its
GPSViconSwitching failure is the height corruption of issue 1 and its
BaroDriftClearedAtArm climb is the GPS-denied drift of issue 2):

```
git checkout pr-baro-drift-minimum-periodic-reset
./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.GPSViconSwitching   # 3/5 pass (was 5/5 arm-only)
Tools/autotest/autotest.py --no-configure test.Copter.BaroDriftClearedAtArm
```

Plots are regenerated from the captured BINs with `python3 plots/make_plots.py`
(BINs under `armonly/`, `head/`, and `guard_barodrift.BIN`). Plot C is the
periodic build with the ExternalNav guard applied.
