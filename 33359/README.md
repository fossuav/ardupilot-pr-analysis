# PR #33359 - AGL KF for the optical-flow rangefinder height switch

Analysis archive for [ArduPilot/ardupilot#33359](https://github.com/ArduPilot/ardupilot/pull/33359).
Branch `pr-rng-aglkf-terrain` (andyp1per fork), base `master`. Real indoor flight
logs are not committed here (public repo); the numbers below are from Replay on
those logs.

## Status (one line)

Indoor optical-flow altitude hold diverges by metres because the EKF's rangefinder height-source switch (a) keys off the baro-corrupted main-filter altitude and (b) only engages during takeoff/landing - so cruise/hover rides garbage baro. This routes the switch through the IMU-aided AGL KF, which already exists in master for flow velocity scaling. Replay-validated on two indoor flights and flight-validated on the vehicle (log281).

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
