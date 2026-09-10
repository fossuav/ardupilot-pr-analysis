# PR #33359 - AGL KF for the optical-flow rangefinder height switch

Analysis archive for [ArduPilot/ardupilot#33359](https://github.com/ArduPilot/ardupilot/pull/33359).
Branch `pr-rng-aglkf-terrain` (andyp1per fork), base `master`, head
`bba45ab742` (2026-07-29). Real indoor flight logs are not committed here
(public repo); the numbers below are from Replay on those logs.

## Status (one line)

Indoor optical-flow altitude hold diverges by metres because the EKF's rangefinder height-source switch (a) keys off the baro-corrupted main-filter altitude and (b) only engages during takeoff/landing - so cruise/hover rides garbage baro. This routes the switch through the IMU-aided AGL KF, which already exists in master for flow velocity scaling. Replay-validated on two indoor flights and flight-validated on the vehicle (log281).

## Review 2026-09-10: four must-fixes, and commit 4 should be dropped

Upstream drift is a non-issue: `git merge-tree` against master is clean and
no upstream commit has touched `AP_NavEKF3_PosVelFusion.cpp` or
`AP_NavEKF3_OptFlowFusion.cpp` since the base. Everything the PR relies on
(`aglKfH/aglKfV/aglKfP/aglKfValid`, `EK3_FEATURE_OPTFLOW_AGL_KF`,
`Option::AglKfForOptflow`) is on master via 306d55abad. No DAL surface
change, so Replay exercises the change faithfully. Defaults are untouched:
`EK3_RNG_USE_HGT` is -1 and the option bit is off.

**1. `5f8baac0fc` says "EK3_OPTIONS bit 4"; upstream it is bit 3.** The fork
numbers it 4 and the cherry-pick carried that across. A user who follows the
commit message sets `EK3_OPTIONS=16`, gets nothing, and concludes the
feature is broken.

**2. The PR widens what bit 3 does and updates no documentation.** The
`@Bitmask` still describes bit 3 as height-above-ground for flow velocity
*scaling*. After this PR the same bit also redirects the `EK3_RNG_USE_HGT`
threshold, overrides the vehicle's terrain-stability veto, replaces the
switch's freshness gate, and makes `aglKfH` the height observation. Someone
who set bit 3 on 4.7 for flow scaling would find their primary altitude
source changed on upgrade. Either take a second option bit or rewrite the
parameter documentation.

**3. Commit 4 ships without the prerequisite this record already names.**
"Necessary, not sufficient: the fourth commit needs #33507" is a tier-1
finding here (logs 56/57/58), and #33507 is not in this branch - `aglKfP` is
still `[2][2]`. Simulating the shipped filter at default gains gives steady
`aglKfP[0][0]` = 0.0069 m2 (std 0.083 m, against the measured `HAglStd`
~0.11 m), `Kh` = 0.0276, a 1.8 s position time constant, and a height lag of
0.32 m per 0.05 m/s2 of residual vertical accel. The flight measured +0.33 m
on log56. The offset commit 4 injects is predictable from the gains.
Recommendation: drop commit 4 from this PR, or state the dependency and hold
it. Commits 1-3 stand on their own and carry the Replay and log281 evidence.

**4. `terrainStable = true` makes RANGEFINDER the height source before
arming, which disables Copter's arm-time height-datum reset.** While
`onGround`, `readRangeFinder()` synthesises `rngOnGnd` samples, so every term
of `belowLowerSwHgt && trustTerrain && prevTnb.c.z >= 0.7f` holds at rest and
the source switches pre-arm. `resetHeightDatum()` refuses when the source is
RANGEFINDER, but `AP_Arming_Copter.cpp` logs `EKF_ALT_RESET` and zeroes
`arming_altitude_m` regardless. Before this PR the switch could not fire
pre-arm because Copter's `terrain_hgt_stable` is `is_taking_off() ||
is_landing()`. This record puts the fix on the #32768 side, but #32768 is not
upstream, so on master this is an undisclosed regression: boot-to-arm baro
drift offsets altitude-above-arming-point for the whole flight and the log
claims a reset that did not happen.

### Correction to this record: the AGL KF is not baro-independent

The "Evidence (Replay)" section says the AGL KF "fuses IMU + rangefinder
only, so it is baro-independent and breaks the feedback loop". It breaks the
*dominant* loop - the direct `position.z` term, which is what the Replay
numbers demonstrate - but there is a second-order baro path:
`UpdateAglKf` integrates `-velDotNED.z`, which comes from `delVelCorrected`,
from which `correctDeltaVelocity` subtracts `inactiveBias[].accel_bias`,
which `learnInactiveBiases()` copies from `stateStruct.accel_bias` - learned
by the main filter from baro height while the switch is off. The +0.48/+0.51
`AZ` on logs 56/57 recorded below is that path. The same wording is in the
`5f8baac0fc` message and in the code comment.

### Also worth fixing before submission

- Commit 4's observation noise `MAX(aglKfP[0][0], sq(_rngNoise))` always
  returns the floor: 0.0069 m2 against 0.25 m2, 36x below. The commit
  message's "so it deweights when the rangefinder goes stale" does not
  happen - with no range fusion `aglKfP[0][0]` reaches only 0.066 m2 after
  the full 5 s `aglKfValid` lifetime. The only route above the floor is six
  consecutive innovation rejections (~0.3 s). And the deleted term
  `sq(rng*terrGradMax)*(1-cz^2)` is terrain gradient over the *tilt* beam
  offset, which has no analogue in `Qhgt` (gradient over distance
  travelled). Net: at tilt this fuses at full rangefinder weight where
  master deweights.
- In the `!filterStatus.flags.horiz_vel` branch, forcing `terrainStable`
  true makes `trustTerrain` unconditionally true, so the speed gate is
  removed entirely - contradicting `607d1211b9`'s "the existing speed gate
  still confines rangefinder height to slow flight". A copter
  dead-reckoning after GPS loss at 5 m/s over a slope takes the rangefinder
  as its height source with no speed gate.
- `aglKfValid` means only "the rangefinder was fused within 5 s". It is a
  weaker terrain-flatness signal than the variance gate the "Why the speed
  gate is kept" section below already rejected, on a log where terrain
  varied 1.2 m in-gate. That argument applies here a fortiori and the
  counter belongs in the PR description.
- `bba45ab742` carries two `(cherry picked from ...)` trailers whose hashes
  are not upstream; five commit body lines run 76-80 columns; the em-dashes
  at `AP_NavEKF3_PosVelFusion.cpp:1268-1269` are the only non-ASCII this PR
  adds (the one at :792 is pre-existing).
- `1d77bc7f08` attaches a 6-line rationale comment, duplicating its own
  commit message verbatim, to a 3-line change.
- `5f8baac0fc`'s "+/-5 cm during takeoff ground effect" is attributed to
  commit 1 alone, but log59 shows commits 1+2 never engaged the switch -
  which is why commit 3 exists. Name log281 and the firmware, or move the
  claim to the description where the whole stack is in view.
- No automated coverage: both `EK3_RNG_USE_HGT` and
  `test_rangefinder_switchover` run with `EK3_OPTIONS` at 0. `UpdateAglKf`
  needs no flow sensor, so a test is cheap - `EK3_OPTIONS=8` plus
  `EK3_RNG_USE_HGT=70`, assert non-zero terrain variance in a steady hover
  where master reports zero.
- `frontend->option_is_enabled(...) && aglKfValid` is triplicated in
  `selectHeightForFusion()`; one `const bool useAglKf` keeps them in step.
- Ordering: `selectHeightForFusion()` runs before `UpdateAglKf()` in the
  same cycle, so on the step a new range sample arrives `hgtMea = aglKfH` is
  the pre-fusion state - another ~50 ms on top of the 1.8 s time constant.
- `EstimateTerrainOffset` is inhibited once the source is RANGEFINDER, so
  `terrainState` freezes at the switch instant and the flight's altitude
  datum becomes whatever baro said then. The innovation at switch-on is ~0
  by construction: this stops drift, it does not correct accumulated error.
  On master that instant is takeoff or landing; after commit 3 it can be any
  hover moment, or pre-arm - which is probably why log281's numbers are so
  good, and is worth stating.
- The #33478 touchdown ramp cannot reach this switch: the branch is gated on
  `rangeFinderDataIsFresh` (500 ms) and `lostRngHgt` forces baro at the same
  threshold, bounding it at 500 ms / ~0.2 m. Worth saying, since the concern
  is on the record.

## The problem

`EK3_SRC*_POSZ` is baro (normal), with `EK3_RNG_USE_HGT` set so the rangefinder is used for height below a threshold. Two things stop that switch helping indoors:

1. The switch decision keys off `terrainState - position.z`, i.e. the main filter's vertical state, which is corrupted by baro ground effect. Bad baro raises the estimated height, trips the upper threshold, and locks the rangefinder out - leaving baro uncorrected. (Feedback loop.)
2. Engaging the rangefinder needs the vehicle's `terrain_hgt_stable` flag, and Copter only sets it during takeoff/landing (`Copter::update_ekf_terrain_height_stable()` = `is_taking_off() || is_landing()`). A steady hover never engages it.

So during indoor hover the altitude is baro-only, and indoor baro is wrecked by propwash. On flight A the EKF altitude ran to +5.7 m while the rangefinder (ground truth, never out-of-range-high) held the vehicle under 1.2 m; the vertical-velocity estimate hit 5.7 m/s. It is an estimation failure, not control (the throttle loop tracked the bad estimate), and is independent of the loiter/flow work.

## The change (four commits, all gated on AglKfForOptflow)

- Use `aglKfH` for the switch decision instead of `terrainState - position.z`. The AGL KF fuses IMU + rangefinder only, so it is baro-independent and breaks the feedback loop.
- Treat terrain as stable for the switch when the AGL KF is enabled and valid, so the rangefinder can engage in hover, not just takeoff/landing. The existing `EK3_RNG_USE_SPD` speed gate still confines rangefinder height to slow flight, so altitude over varying terrain in cruise is unaffected.

- Gate the switch on the AGL KF's own rangefinder fusion time rather than the legacy terrain estimator's stale timestamp (third commit; see below).
- Fuse `aglKfH` as the height observation when the rangefinder is the source (fourth commit); this depends on #33507, see below.

With the option off (default), behaviour is unchanged.

## Evidence (Replay)

`./build/sitl/tool/Replay --force-ekf3 <log>` re-runs EKF3 over the in-flight DAL data; the as-flown core (C=0) had the AGL KF but not these changes, the replayed core (C=100) has them. Altitude error vs rangefinder ground truth:

| | as flown (baro in hover) | with this PR |
|---|---|---|
| flight A std / max | 1.14 m / 5.40 m | 0.20 m / 0.66 m |
| flight A at the worst event | 5.40 m | 0.25 m |
| flight B std / max | 1.38 m / 2.96 m | 0.30 m / 0.95 m |

Forcing `POSZ=2` (rangefinder primary) also fixes it in replay (0.10 / 0.39 m) but bypasses the switch entirely, has no baro fallback, and assumes flat terrain - hence the switch-based approach. Residual (~0.66 m) is the flight's low `EK3_RNG_USE_HGT` ceiling still reverting to baro above ~0.9 m; pairing with a sane `RNG_USE_HGT`/`RNGFND1_MAX` tightens it further.

## Flight validation (log281)

Flown on the vehicle with this fix (firmware de783e08), same airframe, indoor optical-flow Loiter hovering ~0.3-0.6 m.

| | log280 (before, baro in hover) | log281 (with fix) |
|---|---|---|
| EKF alt range | -0.23 to +5.71 m | -0.29 to +0.62 m |
| EKF alt error vs rangefinder truth | std 1.14 / max 5.40 m | std 0.088 / max 0.384 m |
| vertical velocity excursion | peaked 5.7 m/s | max 0.62 m/s |
| alt-hold error (Alt - DAlt) | spikes to 2.3 m | max 0.65 m |

The divergence is eliminated; the estimate tracks the rangefinder to ~9 cm std despite the rangefinder dropping out 25% of the flight (the AGL KF bridges the gaps). It beats the Replay prediction (std 0.20 / max 0.66) because the hover stayed mostly below the 0.9 m switch ceiling that `EK3_RNG_USE_HGT=3` imposes on this airframe (left unchanged for the flight). The same flight also ran `EK3_FLOW_MAX=7.4` (matching the sensor's 7.4 rad/s spec), lifting the flow speed cap from 0.54 to 2.32 m/s at 0.36 m and letting the vehicle reach 1.61 m/s vs the prior ~0.5 m/s ceiling.

## Later findings on a second airframe (4-inch flow quad, logs 56-67)

Numbers are from real flights (not committed) on the SmallFastDrone branch,
which numbers AglKfForOptflow as bit 4 and logs the AGL KF as `XKF6`;
upstream it is bit 3 and `XKFA`.

### The switch was vetoed by a stale legacy timestamp (third commit)

With the first two commits flown (log59) the rangefinder never became the
height source even below the ceiling, and `XKF5.TOfs` stayed frozen at 0.
`belowLowerSwHgt` requires `gndHgtValidTime_ms` to be under 1 s old, and that
timestamp is set only by the legacy 1-state terrain estimator, which predicts
range from the baro-contaminated main-filter altitude. Near the ground its
innovation fails, its state freezes, the timestamp goes stale and the switch
is vetoed indefinitely: a second self-reinforcing lockout. The third commit
gates the switch on `lastAglRngFuseTime_ms`, the AGL KF's own clean fusion
time. Flown log62: the rangefinder engages (`HSrc=2`) through the low hover,
which it had never done before.

### The RNG_USE_HGT ceiling, in numbers

`rangeMaxUse = 0.01 * RNGFND1_MAX(m) * EK3_RNG_USE_HGT`; at the common 30 m
and 3 that is 0.9 m, and switch-on needs height below 0.7x that, 0.63 m. A
1-2 m hover never engages. For a sustained low hover set `EK3_RNG_USE_HGT`
to ~70 (21 m ceiling), `RNGFND1_MAX` to the sensor's real maximum (the ARK
Flow ToF is ~4-8 m, not 30), and `EK3_RNG_USE_SPD` ~4 over a flat floor so
repositioning does not drop back to baro.

### Necessary, not sufficient: the fourth commit needs #33507

Logs 57/58 flew the terrain-trust gate without the 3-state AGL-KF bias
(#33507) and without the `aglKfH` fusion. The AGL KF was valid and terrain
was forced stable, yet the height stayed on baro and ran 0.16 -> ~1.0 m
against a true 0.2 m (`VD` -0.2 to -0.5 m/s, `AZ` +0.48, `IPD` to -0.64).
Two reasons: the 2-state `aglKfH` itself drifted (0.1 -> 0.38 m against a
0.15 m rangefinder) from the same accel-Z bias, so the "reliable reference"
the switch leans on was not; and raw-range fusion does not cleanly re-anchor
an altitude already 5x diverged. The offset is systematic - on log56
`HAgl - RFND*cosTilt` was +0.33 m at `AZ` 0.51, decaying to +0.13 at 0.21 -
so fusing `aglKfH` as the height observation (fourth commit) injects it into
altitude unless the AGL KF carries its own bias state. That is #33507, whose
bias state was flight-validated on log59 (`Bias` -0.065, std 0.018, `HAgl`
tracking the rangefinder). This PR's fourth commit should be read as
depending on #33507; the description does not yet say so. Also note the
de-glitch benefit was zero on log56 (raw range median step 6 mm).

Once the rangefinder is selected the switch is no longer the lever: log66
had `HSrc=2` all flight and still ran away (1.16 m against 0.13 m) on a
residual +0.1 m/s vertical velocity from the AGL-KF bias being too stiff for
thermal drift. See `../33507/`. A related trap from another airframe: with
the rangefinder out of range low on the deck, `aglKfH` can ramp at ~0.4 m/s
for up to 5 s before `aglKfValid` expires (`../33478/`, finding 3), so a
switch keyed on `aglKfH` could see a false climb of up to ~2 m across a
touchdown. Not observed on this vehicle.

### Why the speed gate is kept

The obvious upgrade - replace `EK3_RNG_USE_SPD` with an AGL-KF height
variance gate - was modelled on a real outdoor flow-Loiter log with the AGL
KF reconstructed offline, and does not work. With ~20 Hz range fusion the
height std is pinned at the ~0.07 m measurement floor regardless of speed
(corr with speed -0.23); a >0.6 gate would have fired 0.0% while the speed
gate dropped the rangefinder 6-8%, over terrain that varied 1.2 m slowly with
every step in-gate. Variance measures internal consistency, not whether the
rangefinder is a valid datum reference; the filter was confidently wrong.
The signal that does carry terrain information is the terrain rate
`aglKfV + velocity.z` (mean/p95/max 0.064/0.168/0.512 m/s on the flat pass,
0.108/0.376/1.084 on the rougher one). A terrain-rate gate is sketched, not
built, and low priority: the speed gate was active 6-8% of those flights and
was not their problem.

### Relation to #32553

The same vehicle that motivated #32553 (a persistent 1.88 m terrain offset
in hover) later flew this AGL-KF stack with `EK3_RNG_USE_HGT=3` (logs
283/285/286, not committed): `XKF5.TOfs` bounded -0.13 to +0.56 m against
+4.1 m in the original crash, AGL KF valid throughout, `HAglStd` ~0.11 m and
flat from 0.2 to 3.8 m, and at a 2.2 m hold the baro read 0.4 m low while
`TOfs` held ~0.2 m. The baro-to-terrain coupling that #32553 resets is
broken at the switch instead. Caveat: the baro error exercised was ~0.4 m,
not the ~4 m of the crash case. See `../32553/`.

## Reproduce

```
git checkout pr-rng-aglkf-terrain   # andyp1per/master + the four commits
./waf configure --board sitl && ./waf --targets tool/Replay
./build/sitl/tool/Replay --force-ekf3 <indoor-flow-log>.bin
# compare XKF1.PD core C=0 (as flown) vs C=100 (replayed) vs RFND.Dist
```

## Relation to #33318

Independent of the AC_Loiter drag PR, but the same theme: route the clean AGL KF height into the consumers that were using drift-prone estimates. [#33318](../33318/) does it for the flow speed cap (`getEkfControlLimits`); this does it for the rangefinder height switch.

## Relation to #32768 (found 2026-09-05)

The third commit's `terrainStable = true` override is what lets the height switch engage while the vehicle is parked: Copter's own `terrain_hgt_stable` is false unless taking off or landing, so before this PR the on-ground switch could not fire. Combined with a fresh `lastAglRngFuseTime_ms` and `heightAboveGnd = aglKfH`, every term of `belowLowerSwHgt && trustTerrain && prevTnb.c.z >= 0.7f` holds at rest, and `activeHgtSource` is RANGEFINDER before the vehicle ever arms.

That is correct for this PR's purpose and is not being changed here. It did, however, silently disable [#32768](../32768/)'s arm-time baro drift reset, which refused any height source but baro or GPS: `EKF_ALT_RESET` at arm went 1 -> 0 with `EK3_RNG_USE_HGT` alone (measured 2026-09-05, see `../32768/README.md`). The fix is on the #32768 side - allow the reset when the *configured* primary is baro or GPS and the vehicle is stationary - so nothing here moves. Recorded in both directories because either PR read alone looks complete.
