# PR #33478 - Fuse the AGL KF velocity as a velD observation (EKF3)

Analysis archive for [ArduPilot/ardupilot#33478](https://github.com/ArduPilot/ardupilot/pull/33478).
Branch `pr-ekf3-aglkf-veld` (andyp1per fork), head `2f1cc48977`
(2026-09-05), base `master`. No real-flight
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

## Review 2026-09-10: inert on default parameters, and the covariance trade is undisclosed

Upstream drift is clean and rebasing is free: `merge-tree` against master
(5b6115d65d) produces a zero-conflict tree, only 20 of 1351 commits touch
`AP_NavEKF3/` and none touch `UpdateAglKf()`, the velocity selection, the
`R_OBS`/innovation/`fuseData[]` blocks, or any symbol the PR reads.
`AP_NavEKF3_OptFlowFusion.cpp` has no upstream changes at all. Parameter
index 15 is still free and `EK3_OPTIONS` bit 4 is still free. Two near
misses, both harmless: `getPosVelYawSourceSet()` was removed and XKFS moved
to per-core source sets, but `useVelZSource(source, core_index)` is
unchanged and already core-aware, which is the form the PR uses; and the
reset-timestamp-to-counter changes are in the same file but different hunks.

Of the two defects this record flagged, the rangefinder-freshness gate has
landed (`aglKfRngCurrent`, `aglKfRngGapMax_ms = 500`, keying both the decay
and the velD gate) and the corrected comment has **not** - it still reads
"and takeoff_expected for armed-on-ground" against a gate that is
`onGroundNotMoving` alone. That comment is also still wrong on master.

**M1. The gate blocks the fallback in exactly the configuration the feature
targets.** `EK3_SRC1_VELZ` defaults to 3 (GPS), and GPS velZ is only fused
inside `gpsDataToFuse && PV_AidingMode == AID_ABSOLUTE && posxy_source ==
GPS`. A flow-navigating copter is `AID_RELATIVE`, so GPS velZ is never
fused - yet `haveGpsVelZ` stays true all flight as long as the GPS holds a
3D fix. Flow copter, `SRC1_POSXY/VELXY=5`, `SRC1_POSZ=1`, `SRC1_VELZ` left
at default, GPS with a fix through a window: set `EK3_OPTIONS` bit 4 and
nothing happens for the whole flight, silently, with `XKFA.VFuse` at 0 and
no log field saying why. Correction to the phrasing used here: a merely
*connected* GPS does not block it - `lastTimeGpsReceived_ms` is stamped
after the `FIX_3D` early return, so a fixless GPS stops advancing it and the
fallback engages after 1 s. The blocking case is a GPS with a 3D fix that is
not being fused for velZ, which is the normal indoor and urban flow case.
`useGpsVertVel` (suggested here) is closer but still not the predicate; the
fusion condition is `AID_ABSOLUTE && posxy_source == GPS &&
useVelZSource(GPS) && useGpsVertVel`. Changing it alters the validated gate,
so it needs the Replay re-run before it is believed.

**M2. The observation is not independent of the state it corrects, and this
is the mechanism behind the covariance collapse already measured here.**
`aglKfV -= velDotNED.z * imuDt`, and `velDotNED` derives from
`delVelCorrected` - the main filter's own accel-bias-corrected delta
velocity. So `aglKfV` is the negated integral of the same acceleration the
main filter integrates, plus the rangefinder corrections since; the only new
information in the observation is the `Kv*hgtInnov` term. Fusing `-aglKfV`
with `R = aglKfP[1][1]` hands the filter its own prediction back as an
independent measurement, weighted by a *posterior* covariance rather than a
measurement noise. The numbers in this record are the signature: `P[6][6]`
down 14-23x, `P[9][9]` down 10.3-10.4x, baro gain over posD from
0.039-0.044 to 0.003-0.004, with no commensurate improvement in actual velD
error. This is **not** the rangefinder height counted twice - that is
properly blocked by `activeHgtSource != RANGEFINDER`, and `terrainState`
does not feed velD. What is counted twice is the IMU and accel-bias
information. The "Open" item here proposing to inflate `P[6][6]` when no
velZ source is active is a symptom-level patch on this mechanism. At
minimum the commit message has to say that the change trades baro authority
over absolute height for a velocity anchor, and by how much; right now it
quotes only the velD improvement.

**M3. The autotest's A/B arms are not matched, and the commit message quotes
the mismatched number.** The off leg runs bit 3 alone; all three on legs run
bit 4 alone. Bit 4 enables the AGL KF but does not make it supply the flow
scale height - bit 3 does. So the two arms differ in flow-scaling source as
well as in velD fusion, and the headline "peak velD error 3.47 m/s without,
0.17 m/s with" comes from exactly those two legs. That number cannot be
attributed to the fusion. Fix: off leg = bit 3, on leg = bits 3|4 (the
covariance A/B here already does this, 8 against 24), plus a short separate
leg asserting bit 4 alone brings the KF up.

### Should-fix

- **The load-levelling skip drops IMU samples out of the AGL KF
  integrator.** `SelectFlowFusion()` returns early - and so skips
  `UpdateAglKf()` - whenever `magFusePerformed && dtIMUavg < 0.005f`, armed
  on any 400 or 300 Hz copter. `imuDataDelayed` is popped once per step, so
  a skipped step's `delVelDT` is never integrated by either `aglKfH` or
  `aglKfV`. The new comment states this as benign; it is the same class of
  defect `b04875313b` fixed in the other direction, and it matters more now
  the result is fused into velD. **Hypothesis worth testing:** finding 1
  here ("AGL KF under-tracked real height change by 25-40%", slope
  0.59-0.71) may be partly this - a ~25% dropped-step fraction predicts a
  slope near 0.75 before the rangefinder correction pulls it back. Cheap
  check: re-run the climb/descent A/B at `SCHED_LOOP_RATE=200` (guard
  inactive) against 400. UNCONFIRMED - inferred from source, not measured.
  Note #33507's review reaches the same code from the other side and
  measures the effect as small there.
- **The innovation gate is tight enough to reject the events the feature
  exists to catch, with no recovery path.** With the fusion converged, the
  measured `P[6][6]` ~ 8.6e-4 and `R` ~ 0.0046 give sigma ~ 0.074 m/s, so
  `EK3_VEL_I_GATE=500` rejects past ~0.37 m/s - and the PR's own problem
  statement cites a -1.1 m/s ground-contact clip, 3x outside. Unlike every
  other observation in the function the AGL path has no escape: there is no
  `velTimeout || badIMUdata` branch and no `ResetVelocity()`. Counter-
  evidence, in fairness: the Replay table here shows the fusion recovering
  on two real divergence logs (alt 55 m becoming 2-5 m), so the gate did
  reopen there. Settle it by logging `XKFA.VFuse` alongside `XKF3.IVD`
  through the clip event in one of those replays.
- **The speed-gate hysteresis is thrown away by the else branch.**
  `aglKfVelGateOpen` is reset false on every step the outer condition fails,
  including for reasons unrelated to speed - one GPS message, one step of
  `fuseVelVertData` from another source, a one-step `aglKfRngCurrent`
  dropout. After any blip the vehicle must re-cross the un-hysteresised
  threshold.
- `velTestRatio` can be contaminated: the base test runs with `imax = 2`
  whenever `AID_ABSOLUTE && fuse_gps_vz`, and `fuse_gps_vz` uses
  `gpsDataDelayed.have_vz`, which keeps its last recalled value across an
  outage. Reachable with extNav supplying horizontal velocity and position
  while GPS is configured for velZ and silent - the terrain-relative
  innovation then folds into `velTestRatio` and refreshes
  `lastVelPassTime_ms`, both of which feed lane selection and the EKF
  failsafe.
- Parameter index 15 with 12, 13 and 14 unused and unexplained; upstream
  `var_info2` has never had a 12. Either take 12 or add the `// index 12
  reserved` comment the codebase uses elsewhere. `@Range: -1 10.0` with
  `@Values: -1:...` does pass `param_parse.py`, so it is style not CI.
  `@User` sits before `@Units`, unlike every neighbour. Reusing
  `EK3_RNG_USE_SPD` (a height-source switching speed) as the default for a
  velocity gate couples two unrelated tunings - defensible, since `R_OBS[2]`
  grows with `_terrGradMax * |v_xy|`, but say so.
- `filterStatus.flags.horiz_vel` gating a *vertical* observation is
  undocumented. It resolves to `someHorizRefData && filterHealthy` and is
  one step stale, both fine; and `healthy()` only fails on test ratios when
  all three of vel/pos/hgt exceed 1, so a height-only runaway does not
  disable the fallback. That reasoning belongs in the comment.
- `aglKfRngGapMax_ms` does two jobs (AGL KF decay threshold and velD
  freshness gate), so `b04875313b` changes behaviour of the already-merged
  bit 3 path for existing users. The commit message's A/B does cover it, but
  say explicitly that bit 3's flow scaling is affected.
- Autotest gaps: `window` is bound only inside the three stimulus branches
  and read unconditionally, so a call with no stimulus raises
  `UnboundLocalError` after SITL has booted and flown; `EK3_AGL_VD_SPD` is
  never set, so only the -1 inheritance path runs and the documented
  "zero disables" branch has no coverage at all; every leg ends
  `disarm_vehicle(force=True)` in the air, so the armed-on-deck path where
  `inFlight` stays latched is never entered; the speed-gate leg has no
  positive evidence that the speed gate rather than tilt closed the fusion
  (assert `XKFA.Valid == 1` across the window to pin it); and it omits
  `context_push()`/`context_pop()` unlike its immediate neighbours.
  What actually fails on revert is only the option bit and
  `b04875313b`'s decay fix - nothing fails if you revert the freshness gate,
  the `velDIsAglKfVel` aliasing exclusion, the hysteresis, the `sq(0.05)` R
  floor, or the parameter itself.

### Notes

- The hard reset sets `aglKfV = 0` with `aglKfValid` true and the timestamp
  refreshed, so the next step can fuse "velD = 0" during a descent - listed
  as open here. In practice it also sets `aglKfP[1][1] = 1.0`, so `R` is
  1.0, `K` ~ 1e-3 and the observation is near-inert until the KF
  reconverges. The `R = aglKfP[1][1]` choice genuinely mitigates this one;
  recording it so it is not re-raised.
- `hgtInnov` is identically zero when both sides are floored at `rngOnGnd`,
  so on-deck fusion is a numerical no-op that still refreshes
  `lastAglRngFuseTime_ms` and still takes the covariance update. The drift
  is common-mode with the main filter, so the harm is the covariance
  collapse of M2 rather than a state kick.
- `XKF3.IVD` silently becomes a terrain-relative innovation whenever this
  option fuses, with no flag inside XKF3; `XKFA.VFuse` covers it only within
  a 250 ms window.
- `static constexpr uint32_t aglKfRngGapMax_ms` is the only such member in
  that header. It links under `-std=gnu++11` because it is never odr-used,
  but a later use through a const reference would break the link.
- Mechanics clean: `diff --check` empty, the only non-ASCII in the diff is
  on a removed line (the PR replaces an en-dash in the existing OPTIONS
  description - a good drive-by), three commits one module each with correct
  prefixes, no Claude attribution, and the feature-off build is sound.
- Process: rebase onto current master (verified free), and since the head
  moved and #33585 was force-pushed to a4d8966c85, re-run the Replay and
  resolve log35/38/41 to fingerprints in `REPLAY_INDEX.md` before the table
  is cited to a maintainer.

## SITL A/B 2026-09-10: M1 confirmed, M3's cause was wrong

Two runs on the PR's own tree (head 2f1cc48977), Copter SITL.

### A/B 1: the fallback is inert on the shipped EK3_SRC1_VELZ. CONFIRMED.

Flow copter, `EK3_OPTIONS=24` (bits 3|4), `EK3_SRC1_POSXY=0` so it navigates
in AID_RELATIVE, baro for POSZ, single lane, rangefinder fitted. The only
difference between arms is the velZ source and whether a GPS is present:

| arm | EK3_SRC1_VELZ | SIM_GPS1_ENABLE | max GPS fix | XKFA.Valid | XKFA.VFuse |
|---|---|---|---|---|---|
| A | 0 (none) | 0 | - | 911/917 | **794/917 (86.6%)** |
| B | **3 (the default)** | 1 | 6 (3D) | 903/909 | **0/909 (0.0%)** |

Arm B never fuses, for the entire flight, with the AGL KF up and valid the
whole time. That is the shipped default `EK3_SRC1_VELZ` plus a GPS that
holds a fix and is never fused for velZ, which is the ordinary indoor and
urban flow case. Nothing in the log says why: `Valid` reads 1 and `VFuse`
reads 0.

Worth noting why the PR's own test cannot see this:
`configure_EKFs_to_use_optical_flow_instead_of_GPS()` sets
`EK3_SRC1_VELZ = 0`. Every leg of the shipped autotest calls that helper, so
the test configures around the defect it needs to catch.

### A/B 2: the headline number. M3's symptom is real, its cause was not.

Four arms, identical stimulus (`SIM_ACC1_BIAS_Z = 0.4`), same setup as the
PR's own test, varying only the option bits and the measurement window:

| arm | EK3_OPTIONS | hold / settle | max velD err | mean | fused |
|---|---|---|---|---|---|
| bit 3 only | 8 | 14 / 4 | **3.470** | 2.701 | no |
| bit 4 only | 16 | 14 / 4 | 1.139 | 0.973 | yes |
| bits 3\|4 | 24 | 14 / 4 | **1.154** | 0.964 | yes |
| bits 3\|4 | 24 | **45 / 35** | **0.172** | 0.122 | yes |

**The option-bit mismatch is immaterial.** Bit 4 alone (1.139) and bits 3|4
(1.154) are the same number. The earlier reading here - that the arms differ
in flow-scaling source and that this is why the result is not attributable -
is **wrong** and should not be repeated to a maintainer.

**The real mismatch is the measurement window.** The shipped test runs its
off leg with `bias_hold=14, settle=4` and its on leg with `bias_hold=45,
settle=35`. The last two rows above are the same firmware and the same
configuration, differing only in the window: 1.154 measured from 4 s in,
0.172 measured from 35 s in. So "3.47 without, 0.17 with" compares the off
leg's *transient* against the on leg's *settled* value, and the 20x is
mostly the window.

**The fusion does work.** Matched timing gives 3.47 -> 1.15, a 3x reduction
in peak velD error, with the fusion confirmed engaged. That is the number
the commit message should quote. The settled 0.17 can be quoted alongside it
provided it is labelled as settled - the off leg has no settled counterpart,
because with the fusion off the vehicle flies itself down, which is why the
shipped test made that leg short in the first place.

## Fixes 2026-09-10 (head e17a1c28bf): M1 predicate, and an honest headline number

**M1.** `haveGpsVelZ` now matches the condition the GPS block actually fuses
under - `useVelZSource(GPS) && useGpsVertVel && AID_ABSOLUTE && posxy_source
== GPS`, plus the existing freshness term. Three arms:

| arm | EK3_SRC1_VELZ | POSXY | GPS | VFuse before | after |
|---|---|---|---|---|---|
| A flow nav, no velZ source | 0 | flow | off | 86.3% | 85.9% |
| B flow nav, shipped default | 3 | flow | on, 3D fix | **0.0%** | **83.4%** |
| C GPS nav, GPS velD fused | 3 | GPS | on, 3D fix | - | **0.0%** |

Arm C is the regression guard and is the one that matters: with a real velZ
source being fused the fallback still stands aside and leaves velPosObs[2]
alone. Arm A is unchanged.

**M3.** The test now carries a leg with the same hold and the same window as
the off leg, so the only difference is the fusion:

| leg | max velD error |
|---|---|
| fusion off (bit 3), hold 14 / settle 4 | 3.47 m/s |
| fusion on (bits 3\|4), hold 14 / settle 4 | **1.15 m/s** |
| fusion on (bit 4), hold 45 / settle 35 | 0.17 m/s |

3.47 -> 1.15 is the number to quote; 0.17 is the settled error and is now
labelled as such. The off leg cannot be matched the other way round, because
with the fusion off the vehicle flies itself down.

Also dropped the stale "and takeoff_expected for armed-on-ground" clause from
the zero-velocity comment.

Outstanding: the commit message of `20baa4786b` still leads with 3.47 ->
0.17. That needs an amend.

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

Reproduced in SITL on `2f1cc48977`, 2026-09-05, and it needs no
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

All of the following are derived from the source, not measured. Recorded so
they are not rediscovered, not so they are believed.

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

### The autotest's own weaknesses

Also derived from the source, not measured. `EK3_AglKfVelForVelD` passes on
`2f1cc48977` (re-run 2026-09-05), but it proves less than it looks:

- **The A/B arms are not matched.** `agl_kf_optflow = 1 << 3` and
  `agl_kf_veld = 1 << 4` (`arducopter.py:2009-2010`), so the off leg runs bit
  3 alone and the on legs run bit 4 alone. Bit 4 enables the AGL KF
  automatically but does not make it supply the flow scale height, which bit
  3 does. The two arms therefore differ in flow-scaling source as well as in
  velD fusion, and the measured improvement cannot be attributed to the
  fusion alone. The covariance A/B above avoids this by using 8 against 24.
- **`EK3_AGL_VD_SPD` is never set.** Only the `-1` inheritance path runs
  (`arducopter.py:2148` reads `EK3_RNG_USE_SPD`), so the parameter this PR
  adds is not exercised directly and the documented "zero disables the
  fusion" branch has no coverage at all.
- **`window` is conditionally bound.** It is assigned only inside the
  `bias_z` / `vertical` / `fast` branches of `fly_leg()`
  (`arducopter.py:2075-2089`) and read unconditionally at `:2091`. All four
  current call sites set one, so it works today; a call with no stimulus
  raises `UnboundLocalError` after SITL has booted and flown.
- **Nothing lands.** Every leg ends `disarm_vehicle(force=True)` in the air,
  so the armed-on-deck path - where `inFlight` stays latched on a copter
  until disarm - is never entered.
- Fixed `delay_sim_time` calls where observables exist (`wait_climbrate`,
  `wait_groundspeed`), against the `Tools/autotest/CLAUDE.md` convention.

### Which archived numbers the 2026-09-05 changes moved

Checked before the changes were applied, per the repo rules. None of the
numbers above move, and the reason is the same in each case: every run that
produced them had no GPS velocity-down source, which is exactly the condition
under which the new aliasing guard is inert.

- The three flights (log35/38/41) and the Replay table both ran with
  `EK3_SRC1_VELZ = 0`, so `fuse_gps_vz` is false and the `velDIsAglKfVel`
  exclusion added to the bad IMU aliasing check cannot change the result.
  Those numbers describe code without the guard, and stand as recorded.
- The covariance A/B was run with the guard already in place, on flow-only
  legs with no GPS velZ, so it is equally unaffected by it.
- Moving `EK3_AGL_VD_SPD` from parameter index 12 to 15 changes no behaviour
  and no number; a vehicle carrying a stored value at the old index simply
  loses it and takes the default.

What would falsify this: a run with `EK3_SRC1_VELZ = 3` and a GPS outage
longer than one second while the AGL KF fusion is active. No such run exists
here, which is also why the guard's own effect is unmeasured.

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

## velTestRatio contamination fixed (2026-09-30)

The open item above ("`velTestRatio` can be contaminated") and AP-Review's
#33585 round-2 ISSUE (ExtNav VELZ gap, `useExtNavVel` latched, imax=2) are
the same family. Tier 2 (SITL) found a second route the review's suggested
fix (drop velD from the combined test on the claim step) misses: with
ExtNav as velD source the GPS block never writes `velPosObs[2]`, so on later
GPS steps the combined test still reads the AGL value the last claim left
there.

Fix `4328e0c925`: `imax = 1` when `velDIsAglKfVel`, and `velPosObs[2]` is
restored after `FuseVelPosNED()` on a step the AGL KF claimed it, so the AGL
value never outlives its step (non-claim steps behave as master, including
master's own stale-ExtNav behaviour, left alone).

Test `e12630f96f` EK3_AglKfVelMixedSources: GPS XY + ExtNav VELZ,
SIM_SONAR_SCALE /3 (range finder and AGL KF read 3x, consistently), Vicon
failed mid-climb at 2.5 m/s so the AGL KF claims with ~5 m/s residual.
max XKF4.SV (sqrt of velTestRatio) in the 3 s window:

| build | max SV | max abs IVD |
|---|---|---|
| e21558d163 (no fix) | 0.91, 1.04 | 2.64 |
| imax change only | 1.43 | - |
| restore only | 0.16 | 4.32 |
| both | 0.17, 0.17, 0.18 | 4.34-5.32 |

Threshold 0.5. The claim-step half is not visible in SITL: a single-step
spike when a GPS step coincides with a claim is overwritten before XKF4
logs at 10 Hz; it rests on AP-Review's extracted-code probe (ratio 2.67)
and inspection. EK3_AglKfVelForVelD still passes; EK3_FEATURE_OPTFLOW_AGL_KF=0
copter builds. Unpushed; #33585 and #34380 need rebasing onto it.

Squashed and force-pushed 2026-10-01 (tree identical to e12630f96f + review fixups): 6503f5f8d7 decay fix; a2320dfc88 = 1938fe4063 + 0a50ee9939 + 4328e0c925 (message now matches the gate code); a2210f10df = 69034ab1a7 + e21558d163; 57138444e8 = e12630f96f + test fixups (min XKF4 sample count; bits 3+4 kept - bit 4 alone gave SV 0.40, too close to the 0.5 line). Head 57138444e8. #33585 and #34380 still carry the old #33478 commits. Backup branch pre-squash/pr-ekf3-aglkf-veld-20261001-0945 kept until they are rebased.

## Round on AP-Review 2026-10-01 (head 57138444e8) and self-review (2026-10-02, local, not pushed)

Rebuilt on upstream/master 755258dbb4 by cherry-pick as pr-ekf3-aglkf-veld-v2 (conflicts only in tests1c registration). AP-Review's five: (1) body odometry did not stand the AGL KF aside - FuseBodyVel fuses all three body axes; gate on prevBodyVelFuseTime_ms (covers wheel odometry too); (2) noise floor - SITL A/B, 1 m range step under a 10 m hover: velD transient 0.36 m/s at floor 0.05, 0.25 at 0.2, but settled error 0.26 vs 0.17 m/s with 0.2, so floor kept and fixed-ground assumption documented (true height excursion ~1 m is Copter surface tracking, present with fusion off); (3) mixed-sources test did not guard the imax exclusion (confirmed: passed with it removed, SV 0.16) - added a GPS-height leg where every claim lands on a GPS step: 0.07-0.08 fixed, 1.6 without; baro leg guards the velPosObs[2] restore (1.4 without); (4) new EK3_AglKfVelYieldsToOtherVelD: GPS 241 and body odometry 242 claims with their gates removed, 0 with; (5) XKFA.VTR logged.
Self-review (Claude x2 + Codex cold): must-fix confirmed and fixed - UpdateAglKf ran after the mag load-levelling return in SelectFlowFusion (pre-existing on master, whose comment claimed every step), losing skipped steps' dt: climb/descent mean AGL KF velocity error 0.20 -> 0.02 m/s, velD max 0.51 -> 0.23-0.25; test limit tightened 0.25 -> 0.1 (0.19 with the fix reverted). Also: GPS gate keyed on received not fused (now gpsRetrieveTime_ms on dal.millis()); fusion waits for AGL KF P11 < 0.2^2 after a reset (range back mid-descent: first fusion 1.6 s later vs 0.04 s, velD err 0.01 vs 0.05 m/s); out-of-scope zero-vel comment edit reverted; docs for horiz_vel requirement, speed-gate hysteresis, RNG_USE_SPD=0. Disputed/noted: correlated observation (shares IMU; VTR <= 0.12 even under a 1 m step), velD-only source holds the AGL KF off though never fused (pre-existing).
Tier 2 at the local head: 14 tests pass (EK3_AglKfVelYieldsToOtherVelD needed a rerun after a SYSTEM_TIME harness stall); 5 mutations red; feature-off builds (AGL KF, external nav, flow, rangefinder) and copter/plane/rover/sub pass.

Folded and force-pushed 2026-10-02: #33478 head 1b6f63bff1 on upstream/master cafe674577 (master gained 4 unrelated commits between test run and fold; AP_NavEKF3 and autotest trees identical to the tested pre-squash/agl-20261002). Every commit builds, all vehicles, gate clean. Description rewritten.

Pushed 2026-10-03: 1b6f63bff1 -> dda9757668 (fast-forward).
Reply posted 2026-10-03: https://github.com/ArduPilot/ardupilot/pull/33478#issuecomment-5973856386

## 2026-10-08: flight over a ~0.7 m step (SFD beta 9d8e8053)

Flow-lane core, baro the height source over the lower ground. Crossing the
edge, the fused AGL KF velocity drove velD to -0.25 m/s for about 5 s (not a
brief transient) while baro was flat: 0.9 m of height error, baro
innovations reaching 1.4 m at a test ratio of 0.14. Replaying with bit 4 off,
the core tracks the GPS core within 0.1 m and lands at -0.21 m against +0.36 m.
Why it is sustained is not yet known; the #33507 bias learning on the AGL KF
is the first suspect. The primary was the GPS core, so the vehicle was not
affected.

## 2026-10-08: step hold for the velD fusion (fix/33478, not pushed)

Mechanism of the step-flight climb, measured in Replay: the AGL KF takes
R from EK3_RNG_M_NSE (0.5 m), so a 0.6-0.7 m single-sample range step is
absorbed over 3-5 s with the velocity 0.2-0.3 m/s wrong and VAglStd still
0.07. The GPS core's AGL KF does the same; only the fusing core moves.

Tried, scored on 12 replayed flights (velD error vs the GPS core where
fusion is possible):
- R inflated by K x innovation: halves the climb, cannot stop it (the
  observation is fused many times inside one correlated error).
- Hard gate on innovation size: fixes the flights but never fuses under
  an accel bias in SITL (the 2-state KF lags > 0.1 m).
- Re-centring the AGL height at a step: fixes 40/29/34, worse on
  32/33/37/39 (0.12 -> 0.50 m/s on one) - velocity lag read as a step.
- Hold velD fusion 5 s after a change in AGL innovation > 0.15 m + 25 ms
  x |v|: log40 0.089 -> 0.046, climb gone, 10 of 11 others better or
  unchanged, log32 at fusion-off. SITL step drift 1.07 -> 0.32 m.
  Range-scaled threshold: worse on 34/37/39.

Open: with SIM_SONAR_RND 0.1 the hold trips once as the bias-runaway leg
injects its 0.4 m/s/s step (0.155 against 0.150); the velD error then runs
past the AGL velD innovation gate during the hold and fusion never
resumes (4.1 m/s). Head fuses there. 0.2 noise passes. A learned noise
threshold (4x rms) does not change the SITL result and loses the gains
on 34/37/39. Hypothesis, not traced: any hold during a runaway leaves
nothing to bring velD back inside the gate.

## 2026-10-08: step hold, final shape (fix/33478 e1c297f748, not pushed)

The hold is tested at the velD claim and applies only while the height
fused on that step is trusted: a real source (not SourceZ::NONE), not in
ground effect (takeoff/touchdown expected), noise under 5 m. With nothing
else on velD, holding let a sudden accel bias run velD past the AGL velD
innovation gate and it was never recovered (SITL, EK3_ALT_M_NSE 10, range
noise 0.1 m: 4.1 m/s); without the hold there it is bounded as on the head
(1.16 m/s, forced ground step plus bias step).

SITL, trusted baro (EK3_ALT_M_NSE 1): 1 m ground step drift 0.94 m head,
0.22-0.24 m with the hold. Replay, 12 flights: unchanged from the fixed
hold (log40 0.046 m/s, climb gone, landing +0.25 m).

Rejected along the way, with the numbers in the commit message: a velD
reset to the AGL KF velocity after 2 s of rejections (forced a 3x-scale
range into the filter, SV 0.89), release on velocity agreement (velocities
never re-agree in a runaway), weak fusion with 1 m/s or 0.3 m/s extra noise
(runaway not bounded, or 0.62 m step drift), learned noise threshold (gave
up gains on logs 34/37/39).

Known limit: a range finder noisy enough to trip the detector (about
0.1 m and up) keeps the hold going while the height source is trusted,
which costs the velD observation, not the height.

## 2026-10-08: step hold flown (log44, SFD beta topup12)

The log40 sortie again. Core 1 against core 0 after each edge, hold vs a
Replay without it: +0.33 vs +0.99-1.33 m, +0.63 vs +1.36 m, within 0.12 vs
+0.79-1.16 m, -0.13..-0.32 vs +0.30..+0.71 m. Landing +0.05 m vs +0.41 m.
Pushed to the PR as e0d009ff31 and 6185109557 (head 6185109557).

## 2026-10-08: squashed after flight test

Head 6185109557 -> 0f6e2e789d, 9 -> 7 commits on the same base, content identical
(empty diff against the pre-squash head); every commit builds on its own. Only the three original test commits folded; the step hold and its test stay separate.

- 8166c6c166 AP_NavEKF3: only decay AGL KF velocity when the range finder is absent
- 30765aca4d AP_NavEKF3: fuse AGL KF velocity as a velD observation
- 91692c4cb8 AP_NavEKF3: run the AGL KF on every filter step
- 365c1b06dd autotest: add EK3_AglKfVelForVelD
- cf6d7649a1 AP_NavEKF3: do not fuse a range sample twice in the AGL KF
- 4a1e0994ed AP_NavEKF3: hold the AGL KF velocity out of velD after a range step
- 0f6e2e789d autotest: test a range step against the AGL KF velD fusion
