# PR #33478 - Fuse the AGL KF velocity as a velD observation (EKF3)

Analysis archive for [ArduPilot/ardupilot#33478](https://github.com/ArduPilot/ardupilot/pull/33478).
Branch `pr-ekf3-aglkf-veld` (andyp1per fork), base `master`. No real-flight
logs are committed here; the flight numbers below are from three indoor
flights on one 5-inch baro-only quad and Replay on a MatekH743 flow quad.
Option bits are the upstream ones (`EK3_OPTIONS=24` = AglKfForOptflow bit 3
plus AglKfVelForVelD bit 4; the flights were on the SmallFastDrone branch,
where the same options are bits 4 and 5, `EK3_OPTIONS=48`, and the AGL KF
logs as `XKF6` rather than `XKFA`).

## Status (one line)

Design validated by Replay, an autotest and three flights; with the AGL KF
bias process noise raised to 0.3 (#33507) it gave 36 s of hands-off VALT at
0.13 m true altitude std on a baro-only indoor quad with no velZ source. Two
defects found in flight were not in the PR when this was written: a
rangefinder-freshness gate on the fusion, and a corrected comment on the
zero-velocity fusion gate in master. The first has since landed
(`aglKfRngCurrent`, 500 ms, `PosVelFusion.cpp:769`); the second has not - the
comment at `PosVelFusion.cpp:723` still says "and takeoff_expected for
armed-on-ground" while the gate is `onGroundNotMoving` alone. Open: the fusion
collapses P[posD] 11x and starves the barometer - now confirmed at 10.3x by an
independent SITL A/B, see below.

## The problem

With `EK3_SRC1_VELZ=0`, the rangefinder excluded from height
(`EK3_RNG_USE_HGT=-1`) and the baro rejected near the ground, the EKF
vertical channel is open loop: velocity is the integral of `AccZ - bias`.
Three things then drive it away, measured on two flow-quad logs (not
committed):

- Vibration rectification fills the vacuum. IMU AccZ motors-off vs hover:
  -9.783 vs -9.90 m/s^2 (~0.12 m/s^2, upward). Over 20 s that is 2.4 m/s,
  matching the observed VD of -2.4 to -3.5.
- The Z accel bias state loses a race. It has to learn the full 0.12 from
  the baro before ground effect gates the baro; in the healthy segment it
  reached -0.10 and nothing ran away, in every failing segment it reached
  -0.05 to -0.07 and froze the moment the baro was rejected.
- Ground-contact accel clips kick the channel (-1.1 m/s in one sample) and
  nothing corrects it.

Result: EKF altitude to 55 m (log t5_034) and 36 m (second flight) while the
rangefinder read a clean ~2 m, baro innovations of -51 m, height fusion
timed out. In VALT that either refuses entry or sinks the vehicle
(see `../32270/`). The one sensor that is good precisely when the baro is
bad was fused for nothing.

## The conclusion and why

Fuse `-aglKfV` (the IMU-aided AGL KF's vertical velocity, rangefinder
anchored) as a velocity-down observation through the existing
`FuseVelPosNED` path, continuously. No divergence detector (the fragile
part), self-weighting (small innovation when the main filter is right,
large when it diverges), and it makes the Z accel bias observable, which
attacks the rectification root rather than mopping up after it.

Velocity only, not `EK3_RNG_USE_HGT`: baro keeps absolute height (mission,
RTL, fence untouched); a terrain step is a brief velocity transient rather
than a persistent height offset; no baro-vs-rangefinder arbitration on one
state; the runaway is a double integral of the accel offset, so pinning
velocity collapses it to a bounded linear drift; each sensor is used where
it is strong. The cost: with baro gated and only velocity fused, absolute
height dead-reckons and can sit 1-2 m off until the baro recovers.

Gated on no active velZ source (a real source always wins), the AGL KF
valid, low horizontal speed (reuses `EK3_RNG_USE_SPD`), and not fusing
stationary zero velocity.

## Key findings

### The main filter is over-confident in velD without a velZ source (SITL)

`P[6][6]` sat near 0.004, 100x tighter than the horizontal velocity
variances, even with the baro deweighted. A measurement-noise floor of
`sq(0.3)` was ~20x larger and collapsed the Kalman gain to ~0.04, making
the fusion inert. The AGL KF reports a tight self-managed uncertainty
(`VAglStd` ~0.06), so the floor is `sq(0.05)`. Replay had masked this
because there the baro was gated, P had grown and the gain was fine.

### Replay and autotest

`Tools/Replay --force-ekf3 --parm EK3_OPTIONS=24` on the two divergence
logs, replayed cores against as-flown:

| log     | as flown                 | with the fusion            |
|---------|--------------------------|----------------------------|
| t5_034  | alt -> 55 m, VD -> -3.8  | alt 2-5 m, VD +/- 0.5      |
| 2 of 2  | alt -> 36 m, VD -> -4    | alt 2-4 m                  |

The healthy segment of t5_034 is untouched (fusion inert when VD already
agrees). Autotest `EK3_AglKfVelForVelD`: injected accel-Z bias, EKF velD
error against the AGL KF velocity 2.49 m/s without the fusion, 0.38 with.

### Flight: it works, and three things had to change (log35/38/41)

5-inch baro-only indoor quad, `EK3_SRC1_VELZ=0`, rangefinder excluded from
height and used as truth, mean flight height 1.10 m. `XKF1.VD` tracks
`-XKFA.VAgl` with small live innovations from the first flight; stick-centred
velocity error normalised by truth RMS 1.27 -> 0.86, sign correct 66% -> 75%.
True altitude lost with the stick centred, holds >= 3 s:

| flight                         | centred time | lost    | rate       |
|--------------------------------|--------------|---------|------------|
| before (`EK3_OPTIONS=0`)       | 118.6 s      | 5.97 m  | 0.050 m/s  |
| log35, fusion on               | 41.4 s       | 3.02 m  | 0.073 m/s  |
| log38 phase 1                  | 15.4 s       | 0.43 m  | 0.028 m/s  |
| log41, `AGL_ABIAS_P=0.3`, seg2 | 36.0 s       | 0.00 m  | -0.01 m/s  |
| log41, seg3                    | 68.8 s       | 0.00 m  | 0.00 m/s   |

log41's holds are 0.129 m and 0.130 m true std for 36 s each, the best
result on the airframe by a wide margin.

1. The AGL KF under-tracked real height change by 25-40% at the 0.05
   default of the bias process noise (slope of AGL-KF height change against
   rangefinder change 0.59-0.71 at correlation 0.89-0.94: a gain error, not
   noise). At 0.3 the slope is 0.83-0.94 at 0.96-0.98. This is #33507's
   parameter; the velD fusion faithfully anchored VD to a velocity the AGL
   KF computed short, which is why log35 made height tracking worse (slope
   0.51 -> 0.28) while making velocity better.
2. On the SmallFastDrone build, synthetic zero-velocity fusion displaced
   the velD fusion whenever `takeoff_expected` was set, i.e. the whole
   post-liftoff ground-effect window and every descent below the threshold.
   The logged innovation gives it away: above ground effect `IVD` equals
   `VD + VAgl`, in ground effect it equals `VD` (observation zero). The
   upstream gate is `onGroundNotMoving` only and never had the term; the
   SmallFastDrone branch had picked it up and never took the removal. The
   master comment at `AP_NavEKF3_PosVelFusion.cpp:709` still says "and
   takeoff_expected for armed-on-ground"; it should not.
3. A rangefinder dropout fabricates a climb. With no measurement the AGL
   KF velocity does not decay to zero: the prediction keeps adding
   `-velDotNED.z*dt` and the 2 s decay leaves a steady state of residual
   times tau. The master comment in `UpdateAglKf()` ("at the 5 s validity
   timeout |v| is at most exp(-5/2) ~ 8% of its value") is wrong whenever
   `velDotNED.z` has a residual, which on the deck it always does. Log38, a
   mid-flight touchdown, rangefinder `OutOfRangeLow` for 3.45 s: `VAgl`
   +0.40 to +0.51 m/s, `HAgl` ramping 0.42 m/s while the vehicle sat on the
   deck, `Valid` still 1 (5 s timeout), the fusion consumed it, `VD`
   snapped +0.01 -> -0.63 in 0.5 s, peak altitude error +3.60 m, and ground
   effect then floored the baro innovation at -0.5 m so it could not
   correct. Upstream only synthesises an on-ground reading while disarmed
   (`onGround` is `!motorsArmed` for a copter), so every armed-on-deck
   period before liftoff is exposed; log41 shows `VAgl` drifting to -0.106
   with `Valid=1` in the 2.5 s before liftoff. Fixed on the SmallFastDrone
   branch (`1ca41a1687`) by requiring a rangefinder reading within 500 ms
   (normal age on the vehicle is 0-50 ms). Not in this PR yet.

### Open: the fusion starves the barometer of authority over position

| fusion   | P[posD] median | P[velD] median | baro gain K = P/(P+4) |
|----------|----------------|----------------|-----------------------|
| off      | 0.187 m^2      | 0.0154         | 0.0447                |
| on       | 0.0165 m^2     | 0.0009         | 0.0041                |

(Medians from the per-fusion diagnostic logging on the SmallFastDrone
branch, log35.)

Reproduced in SITL on the upstream branch, 2026-09-05, and it needs no
diagnostic build: `XKV1.V06` and `XKV1.V09` are `P[6][6]` and `P[9][9]` at
2 Hz already. Four legs, 40 s indoor flow hover each, `EK3_OPTIONS` bit 3
alone against bits 3+4, at two accel process noises. Note the leg's own
`EK3_OPTIONS` cannot be read from the boot `PARM` record - `set_parameters`
lands in the previous leg's log - so identify legs by `XKFA.VFuse`.

| leg | EK3_ACC_P_NSE | P[6][6] | P[9][9] | baro gain P/(P+4) |
|---|---|---|---|---|
| fusion off | 0.35 | 1.200e-2 | 1.641e-1 | 0.0394 |
| fusion on  | 0.35 | 8.571e-4 | 1.599e-2 | 0.0040 |
| fusion off | 0.05 | 4.536e-3 | 1.248e-1 | 0.0303 |
| fusion on  | 0.05 | 1.943e-4 | 1.205e-2 | 0.0030 |

velD variance collapses 14x at the default process noise and 23x at 0.05;
posD collapses 10.3x and 10.4x. That confirms the flight-derived 17x/11x
above from an independent path, so the trade is real and is the size it was
recorded as.

The review of #33585 additionally predicted that at `EK3_ACC_P_NSE=0.05`
`P[6][6]` would fall below `VEL_STATE_MIN_VARIANCE` (1e-4) and enter the
`zeroStatesVarCov(6,6)` reset cycle, wiping the `P[6][15]` cross-covariance
every 5 s. **Not reproduced**: the closest approach is 1.943e-4, 1.9x above
the clip, and no sample in any leg reached it. The prediction was
directionally right and about 3x out. A 1.9x margin on a quiet SITL airframe
is not much, so a lower process noise or a quieter real airframe could still
cross it; it is not a demonstrated failure and it is not a demonstrated
safety margin either.

A confident velocity observation (`VAglStd` ~0.068 against
the `sq(0.05)` floor) shrinks P[velD] 17x and, through the cross-covariance,
P[posD] 11x, so the barometer moves the position state 11x more weakly and
absolute height is dead-reckoned from the fused velocity. Accepted in the
design; it only bit because the velocity was short. Two levers: the PR's own
open item (inflate `P[6][6]` when no velZ source is active), and
`EK3_ALT_M_NSE` 2.0 -> 1.0 (with P << R the baro gain is linear in 1/R, a
clean 4x back, safer with the fusion on than without because the velocity
anchor bounds the ground-sucking runaway).

## Changes made 2026-09-05 (self-review of the stacked #33585)

Branch head is now `2f1cc48977`. Nothing above is revised; these are additions
found by reviewing the stack rather than the feature.

- **`EK3_AGL_VD_SPD` moved from parameter index 12 to 15.** Index 12 has never
  been used in EKF3's `var_info2` upstream, but #32471's branch carries
  `// index 12 was ABIAS_HVR_Z, moved to INS_ACC_VRFB_Z` and retires it, and
  anyone who flew that branch has a stored `EK3_ABIAS_HVR_Z` that would load
  into the new parameter. 13 is #33484's `FLOW_QMIN`, 14 is #33507's
  `AGL_ABIAS_P`, so 15.
- **The bad IMU aliasing check no longer consumes the AGL KF observation.**
  `fuse_gps_vz` at `PosVelFusion.cpp` is `useVelZSource(GPS) &&
  gpsDataDelayed.have_vz`, and `gpsDataDelayed` keeps its last recalled value,
  so it can still be set after the >1 s GPS silence that let the AGL KF claim
  `velPosObs[2]`. `R_OBS[2]` has by then been replaced by the AGL KF variance
  (~0.004), so the `sq(velDErr) > 9*R_OBS[2]` arm trips around 0.2 m/s instead
  of ~1.5, and on a trip the remedy writes `stateStruct.velocity.z =
  gpsDataDelayed.vel.z` - a pre-outage GPS velocity - for 10 s. Three
  independent reviewers found this; it is a reachable code path, the trigger
  being met in flight is unconfirmed.

  The obvious one-line fix is wrong. `fuse_gps_vz` also drives `imax` in the
  velocity consistency test, so narrowing it there drops velD out of that test
  entirely, and `fusingAglKfVel` lives inside `#if EK3_FEATURE_OPTFLOW_AGL_KF`
  so an unguarded use breaks the feature-off build. The exclusion is on the
  aliasing `if` only, via a local that is false when the feature is compiled
  out.
- **Commit message corrected.** It claimed the gate uses "velTimeout, not a
  bare source check"; the code comment says velTimeout is unsuitable and the
  implementation uses a 1 s window on `lastTimeGpsReceived_ms`.

### Open, from the same review, not acted on

All unmeasured. Recorded so they are not rediscovered, not so they are believed.

- `haveGpsVelZ` tests source configuration plus message arrival, not whether GPS
  velZ is being fused. In `AID_RELATIVE` (flow nav, no GPS fusion) a merely
  connected GPS blocks the fallback for the whole flight, which is the failure
  this PR exists to fix. `readGpsData()` already computes `useGpsVertVel` for
  exactly this question. Changing it alters the validated gate, so it wants a
  re-run of the three flights or Replay first.
- Both sides of the AGL KF innovation are floored at `rngOnGnd`, so at the floor
  `hgtInnov` is identically zero: the fusion is a numerical no-op that still
  refreshes `lastAglRngFuseTime_ms` and still takes the covariance update. Armed
  on the deck after touchdown is the case (`inFlight` stays latched until
  disarm).
- The AGL KF hard reset sets `aglKfV = 0` with `aglKfValid` true and the range
  timestamp refreshed, so the next step fuses "velD = 0" during a descent back
  into range.
- `aglKfRngGapMax_ms` (500 ms) is a validity window, but `R_OBS[2]` grows only by
  `sq(accNoise*imuDt)` across it, so a 2-3 Hz rangefinder is presented with an R
  several times too small.
- Terrain slope: `_terrGradMax * |v_xy|` with defaults admits ~0.6 m/s of
  apparent climb at the 2 m/s speed gate over a 30% ramp, inside the innovation
  gate, absorbed by the Z accel bias state.

## What is here

```
33478/
  README.md          <- this file
```

No logs committed. The `EK3_AglKfVelForVelD` autotest BIN is SITL and could
be added under `data/`.

## Reproduce

```
git checkout pr-ekf3-aglkf-veld
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.EK3_AglKfVelForVelD
# Replay on an indoor log with no velZ source:
./waf --targets tool/Replay
./build/sitl/tool/Replay --force-ekf3 --parm EK3_OPTIONS=24 <log>.bin
# compare XKF1.VD / XKF1.PD core 100 vs core 0 against RFND.Dist
```

The dropout defect can be shown in SITL without a flight: arm with
`RNGFND1_MIN` above the ground clearance and an injected accel-Z bias, and
watch `XKFA.VAgl` settle at bias x 2 s with `XKFA.Valid=1`. Not yet built.

## Branches and people

- `pr-ekf3-aglkf-veld` - the PR branch (bit 4, `XKFA`). The PR body still
  says "not tested on hardware"; the three flights above were of the
  SmallFastDrone copy (`valt-aglkf-veld-fusion`, bit 5, `XKF6`), which
  still carries the `takeoff_expected` guard, so anything rebased from it
  reintroduces finding 2. The two fixes are `b00359b2f3` and `1ca41a1687`
  on `SmallFastDrone-4.7-beta`.
- Depends in practice on #33507 (`../33507/`): the flights ran the 3-state
  AGL KF at `EK3_AGL_ABIAS_P=0.3`. Not yet re-validated with this branch's
  2-state KF; a Replay of the same logs with this branch would settle it.
- No maintainer review yet.
