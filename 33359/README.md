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

### Superseded 2026-10-11 in part by SITL and Replay with a source probe

"Copter's own `terrain_hgt_stable` is false unless taking off or
landing, so before this PR the on-ground switch could not fire" holds
only once the vehicle has flown in that boot. On a fresh boot the EKF
cores read the flag true until the first takeoff: a flow-only SITL
copter at `5c5441d830` plus a temporary statustext probe switched to the
range finder pre-arm with the flag reading true, and Replay of log29,
log30, log35 and log224 (upstream branch, same probe) shows it true at
the first arming. Mechanism, from the source and not measured:
`AP_AHRS::set_terrain_hgt_stable()` drops a value equal to its own
cached state, and Copter's first `false` arrives before the cores exist,
so they keep their initialised `true`. After a flight the flag is false
while disarmed, and there the override is what engages the switch on
the ground (log224's ground switch-ins, flag false, disarmed). The text
above is left in place because the arm-time reset is still disabled
whenever the switch is engaged at arming, by either route; the 1 -> 0
"with `EK3_RNG_USE_HGT` alone" is consistent with the stale flag
(interpretation, not re-measured). Item 4 of the 2026-09-10 review above
rests on the same sentence.

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

## 2026-10-08: first flight with the step-up fix (beta 9d8e8053)

One sortie over a ~0.7 m step, two excursions, landed on top. Replays
exactly. Touchdown altitude against before takeoff (0 is right), core 0 /
core 1:

| Replay | touchdown |
|---|---|
| as flown | -0.16 / +0.36 m |
| fix removed | -0.57 / +0.01 m |
| EK3_OPTIONS bit 4 off | -0.16 / -0.21 m |
| fix removed, bit 4 off | -0.57 / -0.69 m |
| threshold 0.2 m, bit 4 off | +0.10 / 0.00 m |
| threshold 0.15 m, bit 4 off | +0.26 / +0.20 m |

Third crossing: reset fired on core 0, switch-in step 0.15 m against 0.55 m
without the fix. Second crossing: disagreement 0.23 m, under the 0.3 m
threshold, no reset, a 0.27 m step on both cores identical with and without
the fix. The remaining error is baro drift over the excursion, which the
offset inherits whichever way the threshold goes; threshold left at 0.3 m on
one flight. Core 1's +0.36 m is #33478 (bit 4), not this PR.

## 2026-10-08: squashed after flight test

Head 1b221ab4a1 -> 5c5441d830, 12 -> 6 commits on the same base, content identical
(empty diff against the pre-squash head); every commit builds on its own. The three commits shared with #33478 are unchanged; "run the AGL KF on every filter step" already differed between the two PRs.

- 39dee56c7f AP_NavEKF3: use AGL KF for rangefinder height source switching
- 39dc3fe860 AP_NavEKF3: fuse AGL KF height as the rangefinder height source
- e09f450f30 AP_NavEKF3: only decay AGL KF velocity when the range finder is absent
- e94afecc47 AP_NavEKF3: run the AGL KF on every filter step
- d15264bc96 AP_NavEKF3: do not fuse a range sample twice in the AGL KF
- 5c5441d830 autotest: check the AGL KF height keeps up with a climb and descent

## 2026-10-11: AP-Review round at `5c5441d830`, fixes

Local branch `fix/pr-rng-aglkf-terrain` (not pushed), over
`5c5441d830`: `4ea485ebe2` fixup of the switch commit (T1),
`547d3f3402` fixup of the autotest commit (new test), and amend!
messages for `39dee56c7f`, `39dc3fe860`, `e94afecc47`, `d15264bc96`,
`5c5441d830` (T3). Bot review (COMMENT):
https://firmware.ardupilot.org/Tools/APReview/DevCallReviews/PRReviews/ardupilot/ardupilot/33359/9.html

### T1 (no speed gate without a velocity estimate): RESOLVED in `4ea485ebe2`

The override now needs `onGround || (filterStatus.flags.horiz_vel &&
PV_AidingMode != AID_NONE)`, and `aglOnlyStable` is
`terrainStable && !terrainHgtStable` so the step-up reset and the wait
follow the same condition.

Why not the bot's `horiz_vel` alone (measured, tier 2): after optical
flow is lost the EKF goes to constant position mode and `horiz_vel`
stays set (the mode's position reset clears the timeouts), while its
speed reads 0.0. With a probe at the head, both cores took the range
finder 0.04 s after "stopped aiding", the simulator at 4.8 m/s. So the
`!horiz_vel` branch the bot named is the narrow case; constant position
mode is the wide one, and `horiz_vel` alone leaves it open.

Why `onGround` (inspection): it is `!motorsArmed` in both branches of
`detectFlight()`, so it means disarmed on every vehicle, and it keeps
the pre-arm switch-in. Only Copter calls `set_terrain_hgt_stable()`, so
on every other vehicle `terrainHgtStable` stays at its initial true and
the override, gated or not, changes nothing.

Also measured: on all five logs below `horiz_vel` is set on the ground
from about 6 s after boot (probe), so "a flow vehicle on the ground has
`horiz_vel` false" is not what rules out the plain gate. A flow-only
SITL copter toggles it in constant position mode until relative aiding
starts on the ground, and holds it set from then.

SITL, new `EK3_RngHgtSwitchNoVelocity` (flow-only, `EK3_RNG_USE_HGT 12`,
`EK3_RNG_USE_SPD 2`, ALT_HOLD at ~2 m, flow lost at 3.5 m/s, then
`SIM_SONAR_OFFSET -1` for 5 s at 4.78-4.92 m/s with range 0.97-2.05 m):
worst EKF height against the simulator's, from the pre-loss offset.

| code | worst height error |
|---|---|
| fix (`4ea485ebe2`), two runs | 0.10 m, 0.10 m |
| fix reverted (= head) | 1.69 m (fails at the assertion) |
| head + probe build | 1.67 m |
| `horiz_vel` alone (bot's proposal) | 1.69 m |

Replay (tier 1b), upstream PR head against head + fix, each with the
probe. log29 (3408138/567), log30 (571), log35 (582) as flown;
log224 (260) and log225 (261) with `EK3_RNG_USE_HGT 3`, the
log280/281 setting. Every EKF message identical (log224/log225 output
BINs byte-identical; log29/30/35 differ only in 3-7 `OF` records with
garbage payloads, a format-table artefact of the fork logs), the same
height source sequence (8, 36, 12, 0, 36 switches), and the condition
the fix changes never arose on any of them. `replay_sweep.py --compare`
moved no row. These are head-against-fix numbers on the upstream branch,
not comparable with the beta numbers in the tables above.

UNCONFIRMED: log280, log281 and log31 are not under the local log roots
(`find_log.py` finds no match), so the indoor flights this PR is credited
with were not replayed with the change. Still owed: the change was pushed
on 2026-10-11 on the five flights that did replay identically. Not exercised by
any log or test: the `onGround` term with the vehicle flag false and the
EKF in constant position mode on the ground (a second flight in a boot
on a flow sensor reading quality 0 on the floor).

Measured and rejected, for the "Measured and rejected" habit: gating the
override on `horiz_vel` alone, argued for as the obvious fix by the bot
and by our own 2026-09-10 review (:100-105); 1.69 m in the test above,
the same as no gate.

### T2 (dependency on #33507): DEFERRED, answered

Safe by default: everything here is behind `EK3_OPTIONS` bit 3. With bit
3 set it should land after #33507, whose AGL KF accel bias state removes
the lag this fuses into altitude, and after #32768, because the
pre-arm switch disables the arm-time datum reset whose fix is on the
#32768 side (:310-314). The "0.3 m per 0.05 m/s2" in `39dc3fe860`'s
message is the 2026-09-10 model at `bba45ab742` (:54-58), taken before
`e09f450f30` changed the velocity decay it modelled; not re-run, so it is
dropped from the amended message rather than quoted as measured.

### T3 (commit text): RESOLVED by amend! commits

`39dee56c7f`: one subject and one account of the switch, without the
stale "This commit alone does not engage the switch" and "which the
series does not yet address". `39dc3fe860`: the tilt/terrain-gradient
term is added on both paths (the "drops" sentence is gone), and the
0.3 m figure is removed. `5c5441d830`: one subject, all three tests.
Also found: `e94afecc47` quoted a velD error with the AGL KF velocity
fused, which is #33478's feature, not this PR's; `d15264bc96` named
`EK3_AglKfVelForVelD`, a test on #33478 only. Both amended.
`e09f450f30` is unchanged.

### T4 (cross-covariance with the main filter's accel): DEFERRED

Still owed. `Tools/Replay` has no accel-bias injection (its options are
`--parm`, `--param-file`, `--force-ekf2/3`, `--progress`), and the
replayed IMU data come from the DAL, so the sweep needs a SITL
`SIM_ACC1_BIAS_Z` A/B instead.

### PR tests at the fix head (SITL)

`EK3_RngHgtSwitchStepUp` -0.06 m (worst 0.19 m), vehicle 0.35 m;
`EK3_AglKfVerticalMotion` worst 0.15 m (bias -0.03 m);
`EK3_RngHgtSwitchNoVelocity` 0.10 m. All pass; flake8 clean; copter and
Replay build.

Pushed 2026-10-11: `pr-rng-aglkf-terrain` `5c5441d830` -> `a1f5a87074` (force, autosquashed), 6 commits; final tree identical to the tested fix branch; copter and Replay build at every commit. Mechanical gate (/pr-review checks, with the new squashed-subject scan) clean. PR replies drafted, not posted.

Reply to the AP-Review round posted 2026-10-11 (issue comment 6110170529), the text drafted above.

## 2026-10-12: AP-Review round at a1f5a87074, fixes

Local branch `fix2/pr-rng-aglkf-terrain` (not pushed), over
`a1f5a87074`: `8363d97a20` fixup of the switch commit `ff486499a1`
(B1), `bb6c793f6f` fixup of `f032135480` (option text), `21e2645b65`
fixup of the autotest commit `a1f5a87074`, and amend! messages
`c953ae7afa` (for `ff486499a1`) and `e763ef9d19` (for `a1f5a87074`).
Autosquash order simulated on a scratch index: applies cleanly and gives
the branch's tree; `ff486499a1` plus its fixup builds copter and Replay.
Bot review (REQUEST CHANGES):
https://firmware.ardupilot.org/Tools/APReview/DevCallReviews/PRReviews/ardupilot/ardupilot/33359/10.html

### B1 (flow regained in flight): RESOLVED in `8363d97a20`

Reproduced first (tier 2). `EK3_RngHgtSwitchNoVelocity` gained a second
leg: after the flow-lost leg the 1 m rise is removed, flow is re-enabled
with the vehicle still at 4.9 m/s, and once core 0 reports "started
relative aiding" the 1 m rise is applied again for 5 s. At the PR head
the EKF height moved 1.49 m against the simulator's on that leg (the
bot's flight: 1.5 m).

Mechanism, from the SITL logs (tier 2): the bot's proposal, "wait until
flow has passed its innovation check since aiding started", does not
work as written, for two reasons.

- `flowFusionActive` (the "fusing optical flow" latch) is set in
  constant position mode. Core 0 printed "fusing optical flow" at
  38.96 s and "started relative aiding" only at 47.45 s, 8.5 s later
  (aiding restarts once `delAngBiasLearned`; master's
  `FlowAidingRestartsWithoutYawFusion` documents the same wait), so the
  latch is already true when relative aiding starts and zeroes the
  velocity.
- `prevFlowFuseTime_ms` is updated per flow axis. From the relative
  start XKF5.NI stayed between 160 and 255 for over 6 s, yet aiding did
  not time out: the axis across the track (flow near zero, EKF velocity
  zero) passes at any speed. A "pass since the start" test on that
  timestamp is satisfied within one flow sample.

The fix: per-axis masks `flowFusedAxes` and `bodyVelFusedAxes`, set in
the pass branches of `FuseOptFlow()` and `FuseBodyVel()`, cleared at the
AID_RELATIVE transition and in `InitialiseVariables()`. The override now
needs `onGround`, or `horiz_vel` with AID_ABSOLUTE, or `horiz_vel` with
AID_RELATIVE and every flow axis (0x3) or every odometry axis (0x7)
passed since relative aiding started. EKF-internal state only, so it
replays; no vehicle-specific term; the disarmed switch-in is unchanged.

SITL, `EK3_RngHgtSwitchNoVelocity` (flow-only, `EK3_RNG_USE_HGT 12`,
`EK3_RNG_USE_SPD 2`, GUIDED takeoff to 2 m then ALT_HOLD at 4.9 m/s),
worst EKF height against the simulator's, each leg from the mean error
over the seconds before it:

| code | flow lost | flow regained |
|---|---|---|
| head `a1f5a87074` | 0.16 m | 1.49 m (fails) |
| fix with the new condition removed (break run) | 0.15 m | 1.47 m (fails) |
| any flow pass since a stored aiding start time (first attempt) | 0.15 m | 1.49 m (fails) |
| no velocity condition (override on `aglKfValid` alone) | 1.61 m (fails) | - |
| `horiz_vel` alone | 1.60 m (fails) | - |
| fix, 7 runs | 0.14-0.16 m | 0.06 m every run |

The head run took off with the first version of the new leg (a final
wait on "fusing optical flow" that the fix run then showed cannot work,
see below); the flight up to the measured windows is the same. The two
"-" rows stop at the first leg. Leg-one numbers are on the rewritten
test and are a different measurement from the 0.10 m / 1.69 m of
2026-10-11 (LOITER takeoff then).

Measured and rejected, for the habit: gating on flow having passed
since relative aiding started, using `prevFlowFuseTime_ms` against a
stored start time. Argued for by the bot and by this round's brief;
1.49 m, the same as no gate, because the cross-track axis passes.
`flowFusionActive` as the signal: not run, ruled out by the measured
message order above (true 8.5 s before relative aiding started).

Not exercised: odometry relative aiding (no SITL leg); the mask is the
same per-axis bookkeeping in `FuseBodyVel()`, derived from the source,
not measured.

#### Superseded 2026-10-14 by a SITL turn leg: "passed since" is a latch

The mask above (pushed as `0c2e335f61`) only ever set bits, so it was
met once each axis had passed once. The 2026-10-13 review flew the
turn that defeats it (flow regained at speed, nose turned 73-80 deg
while holding the track, range finder taken at an EKF speed of 1.2-1.6
m/s against 4.5 m/s true); reproduced here at 1.47-1.49 m in 4 of 4
runs. Fixed in `3eeee55f04`, see "2026-10-14" below. The numbers above
stand for the regain leg, which has no turn.

### Test flake (takeoff, stale statustext): RESOLVED in `21e2645b65`

- Takeoff is now GUIDED to 2 m with `altitude_max` 2.5 m held for 2 s:
  the position controller stops the climb at the target, so a late
  altitude report cannot overshoot it. An `altitude_max` on the LOITER
  takeoff alone would not have caught the bot's failing run, first seen
  at 2.85 m inside a 3 m bound with the overshoot coming after. Seven
  takeoffs reached 2.02-2.07 m.
- The STATUSTEXT collection is cleared before flow is disabled and again
  before it is re-enabled, so "stopped aiding" and "started relative
  aiding" can only match messages after those points; the second now
  starts the measured leg.
- The landing no longer waits on a message. A wait on "fusing optical
  flow" after re-aiding timed out at 60 s on the first fix attempt:
  `flowFusionActive` (untouched by either attempt) was already set before
  aiding restarted, so the message does not repeat. Landing in ALT_HOLD
  needs no horizontal aiding.

7 of 7 runs at the fix head pass (5 alone, 1 with the other two tests,
1 earlier with the same flight). Observed, not acted on: the vehicle
touches down at about 3 m/s, as the old test's did, and with the fix
the EKF speed then rises to 5.6-5.7 m/s on the ground for about 7 s
until disarm, flow rejected on both axes with the AGL KF height at its
0.1 m floor. In the break run (range finder height through the leg) it
decayed from 3.9 to 1.1 m/s instead, with the AGL KF height held at
2.04 m. After the measured window; mechanism not investigated.

#### Superseded 2026-10-12 by more runs and a Replay A/B: pre-existing, not the fix

The break-run sentence above is wrong. It read core 0, but a lane switch
at 53.73 s had made core 1 primary, and XKF5/XKFA log only the primary,
so the 2.04 m "AGL KF height" was a value frozen at the switch. Core 1
fell to 0.37 m/s once flow passed at 61.6 s, then rose to 3.66 m/s on
the ground by disarm, and core 0 rose again to 2.0 m/s. Neither build
decays reliably.

Primary-core EKF speed, touchdown to disarm (about 12 s, vehicle still):

| build / config | runs | peak | at disarm |
|---|---|---|---|
| fix, bit 3 | 8 | 4.42-6.07 m/s | 0.06-0.10 (4 runs), 3.26-3.57 (4) |
| head and break builds, bit 3 | 3 | 4.28-4.33 | 3.30-3.61 |
| fix binary, `EK3_OPTIONS 0` | 3 | 4.48-6.06 | 0.09, 2.96, 3.43 |
| Replay of one bit-3 flight (`LOG_REPLAY 1`): head / fix / fix with `EK3_OPTIONS 0` | 1 | 4.27 / 4.51 / 4.53 | 3.35-3.51 / 3.35-3.40 / 3.43-3.45 |

The runs that decayed peaked near 6 m/s, and those that held peaked near
4.5 m/s, whatever the build or option. The fix Replay reproduces its
live flight (4.51/3.40).

Mechanism (tier 2, the same in every build): relative aiding restarts
at 4.9 m/s with the velocity zeroed. The along-track flow axis is
rejected, but the cross-track axis keeps passing, so aiding never times
out and resets. The EKF velocity keeps the whole error, so when the
vehicle slows before landing it swings to +2.4 to +2.8 m/s east against
a true -2.54. Touchdown adds about 2 m/s (IMU X -22.9 m/s/s at impact),
and on the ground flow at the 0.1 m height floor predicts tens of rad/s,
so the along-track axis stays rejected. This is the single-axis lockout
#33484 addresses (the TD25 class). Whether #33484 clears this flight was
not checked. No code change here; the test's measured windows end
before it.

### Option text: RESOLVED in `bb6c793f6f`

The bit 3 description said the AGL KF replaces the raw range in the
height switch; the switch used `terrainState - position.z`. It now says
the AGL KF gives the height the switch tests in place of the main
filter's height above its terrain estimate, and that bit 3 lets the
switch engage in hover and slow flight, not only during takeoff and
landing.

### Covariance (T4): DEFERRED

Still owed: the `SIM_ACC1_BIAS_Z` A/B.

### Replay at the fix (tier 1b)

Head `a1f5a87074` against the fix, `replay_sweep.py` and a per-type
record hash of the whole output. log29 (3408138/567), log30 (571),
log35 (582) as flown; log224 (260) and log225 (261) with
`EK3_RNG_USE_HGT 3`. log224/log225 outputs byte-identical. log29/30/35:
every message type identical except 4, 3 and 7 `OF` records whose
`TimeUS` is garbage (8115 us and similar, the artefact noted
2026-10-11); XKF1 PD identical on every re-run core; `--compare` moved
no row. A probe Replay shows relative aiding started only on the ground
in all five (core 1 of log29/30/35 and both cores of log224 at 5.2 s,
log225 never), and the state the fix gates on (airborne, `horiz_vel`,
AID_RELATIVE, not every flow axis fused) never arose. So these flights
cannot show the fix working, only that it changes nothing they did.
Limit: the #32553 record notes log224 drops 37% of DAL frames in the
air. UNCONFIRMED as before: log280, log281 and log31 are not under the
local log roots.

### PR tests at the fix head (SITL)

`EK3_RngHgtSwitchStepUp` -0.05 m (worst 0.17 m), vehicle 0.33 m;
`EK3_AglKfVerticalMotion` worst 0.15 m (bias -0.03 m);
`EK3_RngHgtSwitchNoVelocity` 0.14 m / 0.06 m. All pass; flake8 clean;
copter and Replay build.

### Note 2026-10-13: unflown fixes squashed into flown commits

The 2026-10-11 push (`a1f5a87074`) autosquashed review fixes that change behaviour into commits that had flown: the first commit now also gates the terrain-stable override on a measured velocity outside constant position mode. That breaks the rule now in the root playbook (never squash an unflown behaviour change into a flown commit), so the flight evidence recorded above for those commits covers the code before that push, not this part of it. Not rewritten again, to spare reviewers the churn; the beta carries the change as its own commit (topup15 `b2eaa6f864`), and flight results on it will be recorded against that commit. From 2026-10-12 review fixes that change behaviour go on top as new commits.

Pushed 2026-10-13: `a1f5a87074` -> `708c152394` (force). New commits on top: `0c2e335f61` (per-axis aiding gate), `708c152394` (regain leg and flake fixes). Only the EK3_OPTIONS bit 3 text was squashed, into `d50dcb9994`; every flown commit otherwise unchanged. Mechanical gate clean. Replies not posted yet.

Reply to the second AP-Review round posted 2026-10-13 (issue comment 6134598110).

## 2026-10-14: AP-Review round at 708c152394, fixes

Local branch `fix4/pr-rng-aglkf-terrain` (not pushed), over
`708c152394`: `3eeee55f04` (AP_NavEKF3, gate) and `9a76d63933`
(autotest, turn leg), both new commits on top; no fixup or amend, so
no flown commit changes. Numbers taken 2026-10-13 in SITL and Replay
on this branch. Bot review (REQUEST CHANGES):
https://firmware.ardupilot.org/Tools/APReview/DevCallReviews/PRReviews/ardupilot/ardupilot/33359/11.html

### B2 (the per-axis gate is a latch): RESOLVED in `3eeee55f04`

Reproduced (tier 2). `EK3_RngHgtSwitchNoVelocity` gained a third leg:
`EK3_RNG_USE_SPD 3`, flow lost and regained at 4 m/s, nose turned 80
deg with the lean held along the track, the 1 m rise as the turn ends.
With temporary per-sample probes (flow axis pass/fail, mask, override,
height source) at `708c152394`: the axis across the track passes from
the restart, fails from about 30 deg of turn, and the other axis first
passes at 65-80 deg; the latched mask is then full and core 0 takes the
range finder at once, with the EKF speed at 0.7-1.0 m/s against
3.7-4.4 m/s true in the runs that failed. The rise then lands under the
range finder height.

The fix: a bit is cleared when its axis's sample is not fused, so the
masks say which axes passed their latest sample; `allAxesFusedTime_ms`
is stamped whenever every flow axis (or every odometry axis) has its
bit; relative aiding counts as a measured velocity while that stamp is
under `ALL_AXES_FUSED_HOLD_MS` (500 ms) old. Stamp and masks reset at
the AID_RELATIVE transition. EKF-internal, so it replays; no
vehicle-specific term.

| code | flow lost | flow regained | regained, then turn |
|---|---|---|---|
| `708c152394` (= fix reverted), 4 runs | 0.15 m | 0.06 m | 1.47-1.49 m (fails, 4 of 4) |
| `3eeee55f04`, 6 runs | 0.15-0.16 m | 0.06 m | 0.09-0.17 m |
| per-axis hold (rejected, below), 2 runs | 0.15 m | 0.06 m | 0.10 m |

At the fix, probes show the mask full only after the rise, once both
axes pass with the EKF caught up; a switch taken then re-seeds the
terrain offset from the range (the step-up logic), so the height does
not move.

Choosing the hold (tier 1b for the flicker side). Per-sample flow
pass/fail from a Replay probe on the flow lane (core 1) of log29
(3408138/567), log30 (571) and log35 (582), 480 s airborne in relative
aiding; override drops counted offline for each hold:

| hold | log29 | log30 | log35 |
|---|---|---|---|
| none (clear on any rejected sample, the review's direction) | 7 | 44 | 9 |
| 100 ms | 3 | 15 | 2 |
| 200 ms | 1 | 7 | 0 |
| 300 ms | 0 | 5 | 0 |
| 500 ms (adopted) | 0 | 1 | 0 |
| 1000 ms | 0 | 0 | 0 |

Longest single-axis rejection run away from the ground: 0.28 s (log29),
0.23 s (log30), 0.17 s (log35). log30's longer runs (0.34-1.21 s) are
all in a touch-and-go at 0.1-0.3 m range, where the flight's own
lockout recovery (the beta carries #33484) logged four "flow vel reset
(axis lockout)" messages, plus 0.38 s at a takeoff. log224 (260,
`EK3_RNG_USE_HGT 3`) rejects 12-68% of its samples while relative
aiding (both cores); drops 1 and 3 at 500 ms. A SITL flow-only LOITER
(throwaway harness: 2 m, legs at 3 m/s and six 90 deg turns, 104 s)
rejected 1 sample per axis in 1043, at touchdown. SITL flow is too
clean to set the hold; the real logs set it.

Replay A/B, `708c152394` against `3eeee55f04` (tier 1b), same
`--parm` as before (log224/log225 with `EK3_RNG_USE_HGT 3`): log224 and
log225 outputs byte-identical; log29 and log35 every replayed XKF1
identical (raw-decoded, the input FMT desyncs DFReader on XKF1) and no
other C>=100 record differs. log30: the GPS lane (core 100) is
identical; the flow lane (core 101) differs from 198.97 s, max PD
difference 0.375 m. It left the range finder for 0.12 s at 198.84 (the
one hold expiry, the 0.55 s rejection) and for 0.45 s at 202.45 with
its mask full (not this gate; cause not traced). Landing back on the
step top at 225 s: PD 0.19 m against 0.30 m at the head (GPS lane 0.01
m both). No truth separates the two there. The as-flown limit stands:
log280, log281 and log31 are not under the local log roots.

Measured and rejected, for the habit:

- A per-axis hold: clear an axis's bit on a rejected sample once it has
  not passed for 500 ms (the obvious hysteresis, and #33484's lockout
  time). Passes the turn leg (2 runs, 0.10 m), but it can still
  be met mid-turn: the gap between the first axis's last pass and the
  second's first pass was 0.7-1.6 s in the SITL turns, 0.7 s in two of
  them, so a faster turn would put the second pass inside the hold
  (derived from the probe sequences, not flown faster). On log30 it
  drops the override 3 times, and its switch to baro at 202.85 s took a
  ground-effect baro sample: the flow lane's height stepped 0.75 m, and
  it landed at PD 0.01 m against 0.30 m at the head. The adopted
  stamp needs both axes passing at the same moment, so it has no
  turn-rate window and expired once on log30.
- No hold (clear on any rejected sample): kept the range finder out of
  the review's 32 yaw runs, but 60 override drops over the three logs
  against 1, table above.
- A consecutive-failure count: not built; the EKF takes flow at up to 20
  Hz and SITL sends 10 Hz, so a count is a different time on each.

Test design notes (for the next person to touch the leg):

- `SIM_SONAR_OFFSET` moves only the range finder; SITL flow uses the
  true height. With bit 3 the AGL KF scales flow by the shorter range,
  so over the rise the EKF speed settles near 0.6 of the vehicle's.
- Rise at the flow restart (as the regain leg): the axis across the
  track then keeps passing through the turn, the mask fills only with
  both axes passing, and the head passed (0.11-0.12 m, 2 runs).
- Rise before the mask fills (at 54-77 deg of turn): the switch-in
  waits for the AGL KF to agree with the range within 0.15 m, the EKF
  speed is above 2 m/s by then, and the head passed (0.10-0.21 m, 6
  runs).
- Rise after the switch-in at 4.4-4.9 m/s (lean 175-200 pwm): the EKF
  speed passed 3 m/s and the switch let go 1-1.6 s after taking the
  range finder in 13 of 16 runs (4 of them without probes), and the
  head passed at 0.14-0.31 m; 3 held and failed at 1.43-1.52 m.
- Adopted: 4 m/s (lean 150 pwm), yaw at 1650 pwm, the rise issued as
  the yaw stops at 78 deg. The rise lands 0.4-0.5 s after the switch-in
  and the switch holds, since 0.6 of 4 m/s is under the 3 m/s let-go:
  the head failed at 1.43-1.52 m in 9 of 9 runs at this speed (5 with
  probes, 4 final).
- The turn ends at 80-88 deg (final runs).

### Covariance A/B (T4): PARTIAL, the review ran it

The review's SITL A/B (2026-10-13, reviewer runs, not ours): a
`SIM_ACC1_BIAS_Z` step in a 2 m hover, core 0's height against the
simulator's, two runs per case.

| config | 0.1 m/s/s | 0.5 m/s/s |
|---|---|---|
| raw range fused (`EK3_SRC1_POSZ 2`, bit 3 off) | 0.31 m | 1.5 m |
| AGL KF height fused (bit 3 on) | 0.71-0.72 m | 3.3-3.4 m |
| this PR's configuration | 0.73-0.74 m | 3.4 m |
| baro, bit 3 off | 0.64 m | 3.2 m |

The accel bias state converged at the same rate in all four, so no
instability or slower bias learning, but the AGL KF height carries a
little over twice the raw range's accel-bias error, about the same as
baro, and its variance does not show it (0.11 m standard deviation
while 1.4 m off). It supports landing bit 3 after #33507, the T2 merge
order. Our own sweep is still not run.

### PR description (non-blocking): drafted, not posted

The description draft corrects the covariance statement (the AGL KF
variance floored at the range finder noise, plus the tilt and
terrain-gradient term `d50dcb9994` adds on both paths), and adds the
three autotests, the terrain offset re-seed, the merge order and a
short version of the A/B above.

### Not acted on

#33507, #32768 and #33478 still open; #33478 and #33507 conflict with
this head in three AP_NavEKF3 files (review's note, not re-checked).
Steps of 0.3 m or less are still not re-seeded (documented tradeoff).
Not exercised: hardware, the 0.70-0.71 tilt band, and relative aiding
from odometry; the odometry masks follow the same rule, derived from
the source, not measured. The gate commit is unflown.

### PR tests at the fix head (SITL)

`EK3_RngHgtSwitchNoVelocity` 0.15-0.16 / 0.06 / 0.09-0.17 m (6 of 6);
`EK3_RngHgtSwitchStepUp` -0.07 m (worst 0.21 m), vehicle 0.38 m;
`EK3_AglKfVerticalMotion` worst 0.15 m (bias -0.03 m). flake8 clean;
changed C++ lines astyle-clean; copter and Replay build.

Pushed 2026-10-14: `708c152394` -> `9a76d63933` (fast-forward): `3eeee55f04` (relative aiding counts as velocity only while all axes pass, 500 ms hold), `9a76d63933` (turn-after-reacquisition leg). Nothing squashed. Mechanical gate clean. Replies and description not posted yet.

PR description updated and reply to the third AP-Review round posted 2026-10-14 (issue comment 6153654857).
