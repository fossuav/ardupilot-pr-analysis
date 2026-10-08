# PR #33359 - AGL KF for the optical-flow rangefinder height switch

Analysis archive for [ArduPilot/ardupilot#33359](https://github.com/ArduPilot/ardupilot/pull/33359).
Branch `pr-rng-aglkf-terrain` (andyp1per fork), base `master`, head
`bba45ab742` (2026-07-29). Real indoor flight logs are not committed here
(public repo); the numbers below are from Replay on those logs.

### Head superseded 2026-09-29: rebased onto master, head `f48c851e1b`

Rebased onto master on 2026-09-29; the GitHub head is now `f48c851e1b`.
Nothing has been re-measured at this head. Every number below keeps the
commit it was taken on, and any head named above is left as written
because it is the code those numbers came from.

### Head on 2026-10-06: `27991de5ef`

Rebased onto master on 2026-10-06 (`ca4bba4f4b`: the eight EKF commits
patch-identical, the test commit only moves its registration), then
`5d98f8175f` (step-up fix) and `27991de5ef` (`EK3_RngHgtSwitchStepUp`)
pushed the same day. See "Flight coverage, the step-up defect and its fix"
at the end. Earlier numbers keep the heads they were taken on.

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

## Fixed and pushed 2026-09-10: head bba45ab742 -> 640cd4a5fc

Comment and commit-message only - `git diff bba45ab742 640cd4a5fc` touches
nothing but comments, so the Replay and log281 validation still stands.

- The two em-dashes are gone; the branch adds no non-ASCII at all now.
- The "independent of baro" claim is corrected in all three places it
  appeared (two code comments and the first commit message) to say what is
  actually true: the AGL KF does not carry baro error *directly*, and baro
  reaches it through the accel bias the main filter learns.
- First commit said `EK3_OPTIONS` bit 4; now bit 3.
- Second commit's subject was 75 chars, now 67; all four subjects are under
  72 and no body line exceeds 75 columns.
- The second commit no longer claims the speed gate still applies in the
  `!filterStatus.flags.horiz_vel` branch, because it does not. The gap is
  named in the message instead - the code is unchanged.
- The 6-line freshness comment is down to 3.
- Commit 4's two false claims are corrected: its observation noise does not
  deweight on staleness (the floor applies for the whole 5 s validity
  lifetime), and what it drops is the *tilt*-dependent gradient term. It now
  also states the #33507 dependency and quantifies the lag.
- The two `(cherry picked from ...)` trailers, whose hashes are not
  upstream, are removed.

Still open, and deliberately not changed: whether to drop commit 4 pending
#33507, and the missing speed gate in the no-horiz_vel branch. Both are
behaviour decisions, not mechanical fixes.

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

## Round of 2026-09-30 (AP-Review at f48c851e1b), fixed 2026-10-03

On local branch fix/33359-carry (not pushed), over the PR head. SITL (tier 2)
unless stated.

- The lag blocker reproduced: new EK3_AglKfVerticalMotion (GUIDED 2 -> 9 -> 2 m,
  EK3_OPTIONS bit 3, analog range finder) puts the worst AGL KF height error at
  0.90-0.92 m on the PR head. Two causes, both already fixed in #33478:
  the velocity decay ran between healthy samples (fix alone: 0.50-0.51 m), and
  UpdateAglKf() sat after the magnetometer load-levelling return, so skipped
  steps lost their acceleration (fix alone: 0.83-0.84 m). Both: 0.15 m, which is
  the output predictor running ahead of the AGL KF's delayed horizon in the
  reference, not lag.
- #33359 now carries #33478's commits: 8166c6c166 byte-identical, 91692c4cb8
  with the velD option condition dropped (so it will conflict, trivially, when
  both are stacked), and the double-fusion guard c36643d41e + fixup, which
  91692c4cb8 makes necessary.
- Consumer: the AGL height stands in for the range only within DCM33FlowMin
  and with its last fusion under 200 ms old; the tilt/terrain-gradient noise
  term is restored on both paths; bit 3 description updated. Replay (tier 1b)
  of 14 logs on the beta stack: in-flight states move by at most ~0.03 m; the
  one larger change (log21 flow lane, 0.39 m) starts after disarm.
- Open, not selected for this round: terrainStable forced true under bit 3
  (a behaviour change for Copter with EK3_RNG_USE_HGT); the main filter's
  acceleration reused in the AGL KF and fused back (needs a SIM_ACC1_BIAS_Z
  A/B); a stale terrainState stepping height at the switch (unconfirmed);
  the cliff data promised on the thread.

Pushed 2026-10-03: f48c851e1b -> 8cbaa630a5 (fast-forward; f48c message kept, consumer fix as a new commit).
Reply posted 2026-10-03: https://github.com/ArduPilot/ardupilot/pull/33359#issuecomment-5973856689

## Flight coverage, the step-up defect and its fix (2026-10-06)

### Was the current head flown? (tier 1b)

Six outdoor flights on a beta carrying head `8cbaa630a5`, all with bit 3 set
and `EK3_RNG_USE_HGT 6` on a 15 m range finder (switch region below 0.9 m).
`activeHgtSource` is not logged, so each was replayed with a stdout probe on
it, and the replay checked against the flight (no paired XKF1 sample more than
2 cm apart where the replay firmware matched the flown one).

| log (ACC_ID/BOOTCNT) | range finder height in flight with the vehicle's terrain-stable flag clear |
|---|---|
| log31 (3408138/575) | ~72 s per core: a 21 s hover below 0.9 m after takeoff, a second low hover, the descents. HAGL against tilt-corrected range through the 21 s hover: 0.10 m rms, 0.24 m max |
| log35 (3408138/582) | 4.3 s, final descent |
| log32-34, log39 | 0 s: the flag was set wherever the switch engaged, as master would |

Flat ground only. Most flying was above 0.9 m; long low hovers, the original
indoor case, were not repeated.

### The step-up defect (tier 1b)

log29 (3408138/567) and log30 (3408138/571), head `f48c851e1b`, cross a
0.84 m step at about 0.45 m.

- Off the edge: range 0.45 -> 1.28 m, both cores hand back to baro within
  0.3 s, no altitude step.
- Back up: the terrain offset reset to the lower ground off the edge
  (core 0: 0.08 -> 0.87 m) and had recovered only to 0.65 m when the switch
  re-engaged the range finder 0.6 s after the crossing, with the vehicle flag
  clear. The source-change height reset (`ResetPositionD(-hgtMea)`,
  PosVelFusion.cpp ~1507) then pulled the altitude down, and Copter moved its
  target with it.
- Ground-to-ground altitude change, taking off from and landing back on the
  top (true change 0): **-0.45 / -0.46 m** as flown, **+0.23 / -1.04 m** with
  only the terrainStable override removed. Core 1's baro path carries
  #33478's AGL velD climb at the edge, so core 0 is the clean comparison.
  Same on the beta at `13cf7ed1a5` (current head): -0.45 / -0.58 against
  +0.23 / -0.89.
- log30's step sortie never engaged the range finder in flight.

Retraction: the 2026-10-06 comment first said log31's good switch-ins had the
terrain offset and the AGL height agreeing within 0.01 m. That was one core at
one switch; core 0 differed by 0.20-0.22 m. Corrected before posting.

### Measured and rejected: the step-up fix candidates

Replay of the beta (`13cf7ed1a5`, this PR's current head) with each candidate,
on log29/30/31/35. Altitude error on landings within 3 m of takeoff
(core 0/core 1, m; GPS drifted too far to be the reference). log31 carries
1-2 m of baro drift in every variant, so only differences between rows count
there.

| candidate | log29 step | log30 x2 | log31 x2 | log35 | verdict |
|---|---|---|---|---|---|
| head | -0.57/-0.63 | -0.14/-0.10, -0.11/-0.07 | +1.05/+0.40, +1.89/+1.02 | -0.13/-1.39 | the defect |
| override removed | +0.09/-0.89 | -0.08/-0.16, -0.12/-0.08 | +1.07/+1.01, +0.97/+1.28 | -0.30/-0.98 | loses the PR |
| gate on terrain vs AGL height, 0.15 m | +0.14/-1.09 | = head | +1.16/+0.43, +2.00/+1.08 | -0.13/-0.96 | rejected: blocks core 1 too long |
| same gate, 0.25 m | +0.14/-0.63 | = head | = head | -0.13/-1.23 | rejected: core 1's bad switch differed by only 0.18 m and passed; a gate bounds the error at its threshold |
| gate on terrain vs raw range, 0.3/0.4 m | +0.14/-0.82, -0.69 | = head | = head | = head | rejected: delays core 1's switch, still switches onto a stale offset |
| reset offset from AGL height at every switch | -0.23/-0.47 | -0.09, -0.05 ... | +1.47/+0.68, +2.37/+1.51 | -0.09/-1.05 | rejected: AGL lags in a descent and the lag is baked in |
| reset offset from raw range at every switch | +0.09/-0.14 | -0.06, -0.04 ... | +1.49/+0.65, +2.37/+1.42 | -0.13/-1.08 | rejected: on flat ground the old offset is the better reference; costs ~0.45 m on log31 |
| hybrid: reset from range only above 0.2 m | +0.08/-0.15 | = head | +1.48/+0.65, +2.32/+1.27 | -0.13/-1.05 | rejected: fires on flat-ground drift |
| hybrid 0.3 m | +0.08/-0.15 | = head | = head | -0.13/-1.05 | measured; superseded by the next row |
| hybrid 0.3 m + wait for AGL within 0.15 m of the fused sample (adopted) | +0.10/-0.35 | = head | = head | -0.14/-1.08 | adopted in `5d98f8175f` |

Why the wait: the source-change reset uses the AGL height, so a reset of the
offset from raw range still leaves the AGL KF's lag as a height jump, and
Copter climbs by it (SITL below). It costs 0.2 m on log29's core 1 at landing.

Thresholds: flat-ground terrain-vs-range disagreement at a switch stayed
<= 0.22 m in these flights; the step showed 0.66 m. 0.3-0.4 m is the band
that fixes the step without firing on log31; 0.3 was chosen after seeing
log29.

Further checks on the adopted logic:

- Indoor propwash flights log280 (3408138/327) and log281 (3408138/331),
  `EK3_OPTIONS` forced to 8: identical to head; no reset fires (the vehicle
  switches in once and stays). log281 low hover 0.07 m rms with the override,
  1.06 m without it, so the PR's benefit is intact.
- Terrain database feeding the offset (bit 2 cleared): results unchanged;
  log31/35 descents from above range engaged with the database-fed offset
  agreeing within 0.3 m. A database-fed offset descending onto ground SRTM
  does not hold is untested.

### SITL: `EK3_RngHgtSwitchStepUp`

Takes 3.5 m off the range (`SIM_SONAR_OFFSET -3.5`) in an ALT_HOLD hover at
~4.7 m with `EK3_RNG_USE_HGT 8`, `SURFTRAK_MODE 0`. Design notes, each found
by a failed attempt: a faked step *down* drives the vehicle into the real
ground (under range height it follows the ground down); GUIDED and surface
tracking follow the fake ground up and never enter the switch region.

| code | EKF height vs simulator after the step | vehicle movement at the step |
|---|---|---|
| no fix | -3.16 m (worst 3.30) | - |
| reset only (no wait) | -0.09 m, peak error 0.39 m | +0.42 m, peak +0.66 m |
| adopted (`27991de5ef`) | -0.07 to -0.08 m, worst 0.18-0.19 | 0.29-0.36 m (4 runs) |

On the beta (topup9): -0.01 m, worst 0.17; vehicle 0.32 m.

### Review triage (Codex rounds on the fix, AP-Review at `ca4bba4f4b`)

- Fixed: stale or glitched raw sample (switch now needs `rangeDataToFuse` and
  an AGL fusion under 200 ms); the lag jump (the wait); test windows tied to
  core 0's reset, peak bounded, range crossing asserted.
- Open, stated in the commit and on the PR: a fixed threshold cannot separate
  a step from baro drift; drift over 0.3 m at a re-engagement would be kept
  rather than corrected. Not reached in any of the six flights.
- Not done: refreshing `Popt`/`gndHgtValidTime_ms` on the reset (the existing
  5 s reset does not either). "The wait can hold off indefinitely": it falls
  back to baro, as master.
- AP-Review's blocker at `ca4bba4f4b` was this defect; its suggestion
  (re-seed at switch-in, or require agreement, plus a step test) is what was
  done. Still open from it: the hand-back side can hold a stale AGL height
  above the ceiling; the covariance argument for reusing main-filter accel.

Comments: flight results
https://github.com/ArduPilot/ardupilot/pull/33359#issuecomment-6017631963,
the fix https://github.com/ArduPilot/ardupilot/pull/33359#issuecomment-6019795040.

## 2026-10-08: AP-Review COMMENT at `27991de5ef`; the switch-out gate

The step-up blocker is closed (the bot reproduced EK3_RngHgtSwitchStepUp:
-0.06 m at head, -3.23 m with the fix reverted, 0.69 m worst without the
wait). Non-blocking items left: the switch used the AGL height without the
observation's gates, and the cross-covariance argument (still owed).

`1b221ab4a1`: the height the switch reads is the AGL KF's only within the
observation's tilt and freshness limits (DCM33FlowMin, fused within 200 ms);
otherwise the terrain offset path. Replay of log29/30/31/35/280/281 on the
beta (`fde4de75a6`) with and without it: identical PD and identical height
source sequences. The tilt band (c.z 0.70-0.71, ~45 deg sustained) cannot be
held in SITL, so no dedicated test. PR tests pass; feature-off build OK.

Measured and rejected (Codex cold read MUST-FIX): applying the same limits
to the terrain-stable override and to the step-up reset's AGL-only
condition. Replay: source changes log30 42 -> 46, log280 18 -> 20; log31
core 1 low-hover error 0.54 -> 0.73 m rms; nothing better. While the AGL KF
is stale the main filter fuses the raw range itself, so range height is
never held without an observation.
