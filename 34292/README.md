# PR #34292 - optical flow minimum focus height (FLOW_HGT_MIN)

Analysis archive for [ArduPilot/ardupilot#34292](https://github.com/ArduPilot/ardupilot/pull/34292).
Branch `pr-flow-hgt-min` (andyp1per fork), base `master`, head
`a204212074`, pushed 2026-09-10 18:40Z. The three commits that added,
removed and then properly replaced the terrain-estimator flag were folded
into one before pushing, so the PR is 16 commits; verified as an identical
tree by an empty `git diff` and a range-diff. tridge's three threads are
answered in the PR.

**Two sessions worked this branch on 2026-09-10 and each force-pushed over
the other's base.** The tridge round below was built on `946708d630`,
rebuilt after a reword at `87131f91a7`, and rebuilt again onto `5def1557bd`
once the commit fold landed. Every rebuild was verified as an identical tree,
so the measurements keep their values; only the SHAs moved. The local
`pr-flow-hgt-min` is older still and never saw any of it. Check
`git fetch origin pr-flow-hgt-min` before trusting a head named here. The head was
`292ec09fef` when this record was opened; four review rounds have moved it
since, and the sections below say what changed. The tip was `84ec31a99d`
until a rebase renumbered it to `76d3538247`, then a rebase onto current
master renumbered the whole branch again to the `946708d630` series.

Split out of #33484 on 2026-09-04 after rmackay9 reviewed the parameter there
and asked for it to live in the flow library. The mechanism is unchanged from
the version flown on that branch; what moved is where the parameter lives and
how its value reaches the filter.

## Status

Mechanism flight-validated on the 4-inch quad as `EK3_FLOW_MIN_H` (log67, see
#33484's README). Re-implemented as `FLOW_HGT_MIN` in the flow library and
re-verified in SITL; the re-implementation itself has not been flown.

Under review. tridge's automated pass has run five times, most recently
2026-09-10 at `337cf08df6`; tridge himself left four inline comments on
2026-09-09, all answered; and peterbarker requested changes on 2026-09-04, his
six inline comments answered on 2026-09-05 and the review not withdrawn. Every
round is recorded under "Review" below, including the findings that were
rejected.

The 2026-09-10 round's two code findings were both fixed the same evening, at
`c08eaf0e43`, but the round itself has no reply, so the PR still reads as an
open BUG. See "Automated round of 2026-09-10" at the end.

A question raised on 2026-09-05 about whether the flown 0.1 m value sat under
the EKF's rangefinder clamp was resolved the same day from log67: it did not,
and the flight evidence stands. See "Open question: was the flown value inside
the rangefinder floor?".

## Review 2026-09-10: the floor fuses a zero-velocity measurement, and nothing says so

The reviewer built the branch and ran `test.Copter.OpticalFlowFocusHeight`:
passes, all three subtests, peaks 0.028 / 1.078 / 0.972 m/s, consistent with
the numbers below. Everything this record marks settled was re-verified
against the current tree and holds - see "verified clean" at the end.

**M1. The zeroed sample is fused as a full-confidence "zero ground motion"
measurement.** Zeroing `flowRadXYcomp` does not mark the sample absent - it
makes the observation "the LOS rate is zero", i.e. the vehicle is not moving
over the ground. `R_LOS` is set from `EK3_FLOW_M_NSE` and is **not** inflated
while the floor is active, and the fabricated zero passes through the
ordinary `EK3_FLOW_I_GATE` test. Two consequences that appear in neither the
description, the parameter doc, nor the code comment:

- On a vehicle genuinely translating below the floor, NE velocity is
  actively dragged to zero. `f66adf417c`'s own body concedes this and
  answers it with a 5 m clamp - but 5 m is high enough for a copter in
  flow-only Loiter to be doing several m/s underneath it. The clamp stops a
  typo, not a plausible mis-set.
- Fusion refreshes `prevFlowFuseTime_ms`, which feeds `flowFusionTimeout`,
  `optFlowUsed`, `attAidLossCritical`, `haveRecentFlowVel` and
  `doingFlowNav`. While the floor is active the EKF reports flow aiding
  healthy on data it did not measure, and the 5 s timeout that would drop it
  out of `AID_RELATIVE` cannot fire.

That second point is the design's actual content: not "ignore the flow" but
"substitute a zero-velocity pseudo-measurement and keep the aiding-health
timers alive on it". That may be right for the near-ground case, but it has
to be stated, with the answer to "what if it really is moving". Consider
inflating `R_LOS` while the floor is active so the fabricated zero acts as a
soft prior rather than a measurement.

**M2. The zeroed sample also reaches the terrain estimator - and on Plane
that is its only effect.** The new block runs *before*
`EstimateTerrainOffset(ofDataDelayed)`, which fuses `flowRadXYcomp` into
`terrainState`. Plane defaults `EK3_FLOW_USE=2`, so `fuse_optflow` is false
and `FuseOptFlow` only computes variances - **the terrain estimator is the
only live consumer of `FLOW_HGT_MIN` on Plane.** Failure: Plane with a
downward rangefinder for landing, `EK3_SRC1_POSZ` baro, GPS in use,
`AID_ABSOLUTE`, airspeed >5 m/s so `velHorizSq >= 25`. `cantFuseFlowData` is
then false and the zeroed `flowRadXY` trivially passes the `_maxFlowRate`
term, so on approach below `FLOW_HGT_MIN` the fabricated zero is fused. A
zero LOS rate at non-zero ground speed can only be reconciled by a larger
range, so `terrainState` is driven such that the aircraft appears *higher*
than it is - wrong direction on a landing, and systematic rather than
random. Arguably worse than the garbage it replaces. One-line fix consistent
with the intent: when the floor fires, make the terrain estimator **skip**
the flow (OR a flag into `cantFuseFlowData`), or zero only the copy handed
to `FuseOptFlow`. "Do not fuse" is right for terrain; "assume zero motion"
is only right for the nav path. Derived from source, not measured.

**M3. The parameter doc contradicts the code at the boundary.** The doc says
the value "only has effect above both RNGFNDx_MIN and RNGFNDx_GNDCLR". The
clamp is `rngOnGnd = MAX(ground_clearance_orient(...), 0.05f)`, so the real
condition is `FLOW_HGT_MIN > MAX(RNGFNDx_GNDCLR, 0.05)`. With `GNDCLR = 0`
the doc implies anything above 0 works; it must exceed 0.05. That is exactly
the flown airframe's configuration (`RNGFND1_GNDCLR = 0.0`, per the table
below), so the one case with flight evidence is the case the doc gets wrong.

### Should-fix

- **The protection releases exactly where the flow is worst.**
  `rngValidMeaTime_ms` is stamped only when the backend reports `Good`.
  Below `RNGFNDx_MIN` the backend reports OutOfRangeLow, the timestamp goes
  stale, and the 500 ms freshness term fails. With the shipped default
  `RNGFND1_MIN = 0.20` and `FLOW_HGT_MIN = 0.30`, the floor fires from
  0.30 m to 0.20 m and then releases for the last 20 cm - the part of the
  descent where the sensor is furthest out of focus. The flown airframe had
  `RNGFND1_MIN = 0.01`, so the flight evidence does not exercise this.
  Either latch the zeroing while the last valid range was below the floor
  and the vehicle has not since climbed above it, or say plainly in the doc
  that the feature covers only the band `[RNGFNDx_MIN, FLOW_HGT_MIN]`.
- **Nothing in CI exercises the new replay record with a non-zero value.**
  `Copter.Replay`'s OpticalFlow bit runs `OpticalFlowLimits()`, which never
  sets `FLOW_HGT_MIN`, so `_ROFM.minHeight` stays 0 and `check_replay`
  compares the *disabled* behaviour. Both real bugs this branch hit - the
  ROFH growth misparse and the ROFM dropped in a second log of one power
  cycle - lived in exactly this path and were invisible to the committed
  test. Setting `FLOW_HGT_MIN` in `test_replay_optical_flow_bit` is one line.
- **Fold the fixups: three commits ship known-broken code and three
  messages are stale at HEAD.** `e2253aa930` fails parameter-metadata CI
  until `d4d6cd08dd`; `a3853219dc` grows `log_ROFH` and misparses every
  older replay log until `b470551fbc`, ten commits later; `5d645e53e0`
  reads uninitialised stack and SIGFPEs under SITL until `e7195ee2fd`,
  eight later. A bisect landing in that range crashes. Stale at HEAD:
  `a3853219dc`'s "sits in the replay record beside the sensor position"
  (no longer true after `b470551fbc`) and `e2253aa930`/`5d645e53e0`'s "only
  has effect above RNGFNDx_MIN" (corrected by `f66adf417c` to include
  GNDCLR). Squashing gets this to ~6 commits and removes all three.
- **No diagnostic for whether the floor fired.** `XKF5` carries `FIX/FIY`
  (the terrain estimator's aux innovations) and `normInnov`; nothing
  distinguishes "the sensor reported zero" from "the floor replaced the
  sample". The flight analysis here had to infer it from `FIX/FIY`
  magnitudes. A status bit or one XKF5 flag would make the feature
  reviewable from a log, which matters more than usual for a change that
  silently substitutes a measurement.
- Autotest subtest 1's `wait_groundspeed(0, 0.5, minimum_duration=15,
  timeout=25)` leaves 10 s of slack. It settled immediately in the run
  above (first sample 0.06 m/s), but 40 s costs nothing on a loaded CI box.

### Notes

- The `#endif` on the new block has no trailing `// AP_RANGEFINDER_ENABLED`
  where the same guard elsewhere in the library does.
- The bare `500` literal matches an identical bare literal in
  `AP_NavEKF3_PosVelFusion.cpp` - consistent, but this is now the second
  copy and a shared named constant would be better.
- The gate compares vertical height (`rng * prevTnb.c.z`) where a focus
  limit is physically a slant distance. `tiltOK` bounds `c.z > 0.71`, so the
  vertical form fires up to ~40% early - the conservative direction, and it
  matches the parameter's wording. Worth one line in the doc.
- The new comment is six lines over a seven-line block, denser than the
  three-line comment immediately above it. Two of those lines were asked for
  in review; keep the `terrainState` rationale and cut the rest.
- `FLOW_HGT_MIN` reads as a limit on the vehicle rather than the sensor's
  focus limit; `FLOW_FOCUS_MIN` would say what it is. Low confidence - it
  does pair with `FLOW_HGT_OVR`.
- `get_height_min()` silently clamps to 0..5. A GCS will accept 50 and the
  vehicle will quietly use 5. Say so in the doc, or pre-arm on it.
- After an in-flight `InitialiseVariables()` the freshness check can read
  fresh on a stale range (`rngValidMeaTime_ms = imuSampleTime_ms` while
  `storedRange.reset()` empties the buffer, and `takeOffDetected` is not
  reset there). `rangeDataDelayed` keeps its last real value, so the
  practical effect is at most 500 ms of gating on a slightly stale range.
  UNCONFIRMED - which in-flight paths call `InitialiseVariables()` was not
  traced.
- `25c7364cb5` / `d70cb7a058` are the same patches as on #33484 under
  different SHAs; whichever lands second drops them.

### Verified clean on the current tree - do not re-raise

- The ROFH growth bug is genuinely reverted, not moved: `struct log_ROFH`
  and its `"ffffIffffB"` format string are byte-identical to the base, so
  old logs replay exactly as before.
- ROFM is correctly sized and formatted (`RLOG_SIZE` 7, one field, one-char
  units and mult strings), and old logs without it replay with the feature
  disabled because `_ROFM` lives in the zero-initialised DAL singleton.
- Ordering is right: ROFM is written before the ROFH it applies to, so
  `handle_message(log_ROFM)` lands first.
- No double-logging on replay: both estimators get the same
  `_ROFM.minHeight`, both DAL writes match, `IFCHANGED` suppresses the
  second, and `AP_AHRS::writeOptFlowMeas` has exactly one caller.
- The `_end = 1` fix is correct and correctly general - `_end` sits outside
  the compared prefix and is cleared on a successful write; it fixes
  RISJ/REPH/REVH/RWOH/RBOH/RSLL/RTER too. `force_write` genuinely cannot
  cover this: it is set and cleared inside one `start_frame()` and
  push-based writers call `end_frame()` first.
- The SIGFPE is fixed: `flowDataToFuse` is the first term, so short-circuit
  prevents any read of the untouched stack local. No new division is
  introduced - the comparison is a multiply, and `prevTnb.c.z >
  DCM33FlowMin` is enforced by `tiltOK` in the same condition, so the three
  sibling divisions keep their existing guard. The `{}` fix would have been
  wrong.
- The #34305 sibling is not made worse: this PR only ever *writes*
  `ofDataDelayed` under `flowDataToFuse`, so merging it alone does not close
  that exposure either.
- The `#if AP_RANGEFINDER_ENABLED` guard is in scope and load-bearing -
  without it, `rngValidMeaTime_ms` stamped at init plus `rangeDataDelayed.rng
  == 0` would fire the gate for the first 500 ms on a rangefinder-less build.
- `takeOffDetected` is the right flag here despite the playbook's warning
  that it is flow state rather than flight state: this code only runs when a
  flow sensor is feeding samples, which is the only condition under which
  the flag is written at all, and it makes the new block mutually exclusive
  with the pre-takeoff block above it.
- No index collisions: `FLOW` group index 8 is free with no legacy
  conversion, `SIM` 37/38 are free. `param_parse.py --vehicle ArduCopter`
  runs clean and emits the block correctly.
- `flowCalSample` contamination is benign - the calibrator requires
  `|flow_rate.x| >= AP_OPTICALFLOW_CAL_ROLLPITCH_MIN_RADS`, so zeroed
  samples are dropped rather than skewing a scale factor.
- Default 0 is right and does not contradict the flown 0.1; flake8, `diff
  --check`, attribution, prefixes and body wrapping are all clean.

### What the tests actually catch

Subtest 1 (`FLOW_HGT_MIN=3.0`, floor above the vehicle) is the **only** one
that fails on a revert of the EKF3 gate: 0.028 m/s against a 0.5 bound,
where the other two arms show the phantom crossing 0.8 within seconds.
Subtests 2 and 3 pass unchanged on master - 2 is the disabled control, 3
catches a floor that fires at every height. Both are correct to keep, but
neither is a revert detector, so this is one revert detector and two
controls, not three tests. Uncovered: the entire DAL/Replay path with a
non-zero value, the second-log-in-one-power-cycle case, and the Plane
`EK3_FLOW_USE=2` terrain path of M2.

## SITL A/B 2026-09-10: M1 confirmed - the floor costs 5x on a translating vehicle

Run on the PR's own tree (head 76d3538247), Copter SITL, flow-only nav with
an analog rangefinder, hover ~3 m AGL. ALT_HOLD with a pitch stick input, so
the stick and not the estimator decides the real motion; truth is `SIM2`,
estimate is `XKF1`, averaged over samples where truth exceeds 1 m/s.

| arm | FLOW_HGT_MIN | mean truth speed | mean EKF speed | est/truth |
|---|---|---|---|---|
| floor off | 0.0 | 4.32 m/s | 4.32 m/s | **1.00** |
| floor on | 5.0 | 5.19 m/s | 1.07 m/s | **0.21** |

With the floor inactive the EKF tracks ground speed exactly. With the floor
active while the vehicle is genuinely translating underneath it, the
velocity estimate collapses to about a fifth of truth. That is the
fabricated zero being fused as a full-confidence measurement, not the sample
being discarded - discarding it would leave the estimate dead-reckoning near
the last good value, not pulled toward zero.

Caveats worth keeping with the number: this is a deliberately mis-set floor
(5 m, the PR's clamp ceiling) and the flown value is 0.1 m, where the
exposure is far smaller. The point is that the 5 m clamp bounds a typo, not
a plausible mis-set, and that the failure mode is a vehicle which believes
it is nearly stationary while doing 5 m/s. It also confirms the mechanism
behind M2: the same fabricated zero reaches `EstimateTerrainOffset` before
`FuseOptFlow`, and on Plane the terrain estimator is its only consumer.

Not tested here: the Plane `EK3_FLOW_USE=2` terrain path of M2, and whether
`R_LOS` inflation while the floor is active would be enough to make the zero
behave as a soft prior instead.

## Fixes 2026-09-10 (head 337cf08df6): the terrain path and the parameter doc

**M2 fixed.** A sample zeroed by the focus-height check is now withheld from
`EstimateTerrainOffset`. The navigation states can use "no motion over the
ground" as a prior; the terrain estimator cannot, because the only way it can
reconcile a zero LOS rate at a non-zero ground speed is by growing the range,
which puts the vehicle higher than it is on an approach. Range data still
updates terrain as before. **Not measured**: this is the only path the check
reaches on Plane (`EK3_FLOW_USE` defaults to 2 there), and Copter defaults to
1, so no Copter test exercises it - reasoned from the fusion equations.
`OpticalFlowFocusHeight` is unchanged by it, which is the available
regression check.

**M3 fixed.** The description said "above both RNGFNDx_MIN and
RNGFNDx_GNDCLR"; the real bound is `MAX(RNGFNDx_GNDCLR, 0.05)`, so with
GNDCLR at 0 - the flown configuration - the documented "anything above 0" was
wrong by 5 cm.

**M1 documented, not changed.** The parameter description now says the
substitution asserts zero motion rather than discarding the sample, cites the
measured 1.07 m/s against 5.19 m/s of truth, and says to set the value no
higher than a real focus limit. Changing the nav-path fusion - inflating
`R_LOS` so the zero acts as a soft prior - would weaken the phantom
suppression the PR exists for, and there is no measurement here to price that
trade. Left as a design call.

## Review 2026-09-09: tridge on the DAL message ID and the fabricated zero

Four inline comments, all on head `76d3538247`.

**The new DAL message ID must go at the end of `LOG_IDS_FROM_DAL`.** ROFM had
been inserted after ROFH. Moved to the end after RTER, with
`LOG_STRUCTURE_FROM_DAL` kept in the same order. `test.Copter.Replay` passes.

The renumbering is real and was measured: the two A/B builds below differ only
in these files, and their flight logs give ROFH/ROFM/REPH/RTER as
157/158/159/164 mid-list against 157/164/158/163 at the end, so six DAL
messages move.

**The reason first written here for it was wrong, and is corrected in place.**
The claim was that Replay copies the input `FMT` records into its output while
also emitting its own format table, so a shifted ID leaves two names on one
type byte. Replay does not do that. It dispatches on the four-character name
from the log's own `FMT`; `LogReader::handle_log_format_msg` copies each input
`FMT` verbatim; `Write_Emit_FMT` suppresses any format Replay would add
outside types 220-230 in a Replay build; and Replay's own output messages sit
*before* the DAL block in the enum (`LOG_IDS_FROM_NAVEKF3` at
`AP_Logger/LogStructure.h:1288` against `LOG_IDS_FROM_DAL` at `:1341`, XKF1 is
type 44), so they do not move. Replaying `data`'s flow log through a
mid-list Replay binary and an end-of-list one gave **byte-identical output**,
and every scanned log has exactly one `FMT` per type byte.

So the rule stands as the maintainer's, and because stable on-disk numbering
matters to anything outside this tree that caches ID to name - not because a
failure was demonstrated. Do not quote a mechanism for it that has not been.

**"is zero right? if we're actually moving that seems like a bad idea"**,
followed by "possibly just set flowDataToFuse = false?". This is M1 of the
2026-09-10 review above, raised independently and answered the way that
review declined to: the sample is now discarded rather than zeroed. See the
A/B below for what that is worth, which is less than it sounds.

**"what does flowDataValue do??"**, on the pre-existing `flowDataValid = true`
in the carry-test block. It is freshness only - set from `flowValidMeaTime_ms`
being under 1 s old, which `writeOptFlowMeas` stamps only for samples passing
the quality and rate checks. Its three consumers are all reporting, not
fusion: `doingFlowNav` in `updateFilterStatus`
(`AP_NavEKF3_Control.cpp:771`), `getHeightControlLimit`
(`AP_NavEKF3_Outputs.cpp:94`) and `getTerrainAltVariance` (`:587`). The
pre-takeoff block forces it true because the driver reports quality 0 while
the vehicle sits on the ground, so the status flags would otherwise drop while
someone carries it around testing flow. The focus-height gate deliberately
leaves it alone: samples really are still arriving below the focus height, and
clearing it would take `doingFlowNav` down with it rather than letting the
normal flow fusion timeout declare the loss.

### Corrected 2026-09-22, re-derived at 54cd8177fa

"Its three consumers are all reporting" is wrong about one of them.
`getHeightControlLimit()` (`AP_NavEKF3_Outputs.cpp:94`) reaches
`AC_Avoid::adjust_velocity_z` through `AP_AHRS::get_hgt_ctrl_limit`
(`AC_Avoidance/AC_Avoid.cpp:459`), so it is the altitude limit the vehicle flies
to under flow nav, not a report. Clearing `flowDataValid` while the focus hold
is on would therefore switch that limit off at the moment flow is unusable,
which is the wrong direction. The other two (`doingFlowNav` in
`updateFilterStatus`, the range finder innovation report at `:587`) are
reporting as stated, and the fusion path is unaffected either way: the focus
check clears the local `flowDataToFuse`, and `flowDataValid` has no part in it.

Also worth stating in any reply: while the hold is on, samples keep arriving and
passing `writeOptFlowMeas`'s quality and rate gates, so the freshness flag stays
true on its own. The status only goes false when aiding times out.

## SITL A/B 2026-09-10 (head 126cf753c7): discarding halves the collapse, and does not cure it

Same shape as the A/B above and directly comparable: Copter SITL, flow-only
nav with an analog rangefinder, ALT_HOLD at ~2.7 m with a pitch stick input so
the stick and not the estimator decides the real motion. Truth is `SIM2`,
estimate is `XKF1` core 0. Restricted to samples where truth exceeds 1 m/s and
the rangefinder reads 2-4 m, which excludes the descent - both floor arms fail
their `land_and_disarm`, because a vehicle with no usable flow cannot navigate
home, and a raw "truth > 1 m/s" filter sweeps that in and reads 0.21/0.35.

| arm | code | FLOW_HGT_MIN | truth mean | EKF mean | est/truth | const-pos |
|---|---|---|---|---|---|---|
| zero | `946708d630` | 5.0 | 5.33 m/s | 0.93 m/s | **0.17** | 0% |
| discard | `126cf753c7` | 5.0 | 5.78 m/s | 2.21 m/s | **0.38** | 49% |
| control | `126cf753c7` | 0 | 5.11 m/s | 5.08 m/s | **0.99** | 0% |

The zero arm reproduces the 0.21 recorded on 2026-09-05 at head `76d3538247`
under the wider filter, which is what says the two harnesses measure the same
thing.

Two results, and the second is the one that matters:

- Discarding roughly doubles the tracked fraction, 0.17 to 0.38, and the
  filter now says it has lost aiding for about half the window
  (`XKF4.SS` bit 7, constant position mode) where zeroing never reports it at
  all. That is M1's second bullet closing: fusion of the fabricated zero kept
  `prevFlowFuseTime_ms` alive, so the 5 s timeout could not fire.
- **It does not fix the velocity collapse.** `AID_NONE` fuses its own
  synthetic zero velocity to constrain tilt errors
  (`AP_NavEKF3_Control.cpp:419-421`), so a vehicle held below a mis-set floor
  still believes it is doing 2.2 m/s while doing 5.8. The fabricated zero
  comes back through the no-aiding path. Anyone reading "discarding fixes the
  translating case" from the commit message alone would be wrong.

The plot is worth more than the mean here, because the discard arm is not a
flat under-read but a **5 s sawtooth**: the estimate dead reckons up toward
truth, reaches about 2.7 m/s, and snaps back to zero. The cycle is
`readyToUseOptFlow()` keying on sample *arrival*
(`imuSampleTime_ms - flowMeaTime_ms < 200`, `AP_NavEKF3_Control.cpp:561`)
rather than on anything being fused. Samples keep arriving below the focus
height, so the filter re-enters `AID_RELATIVE` immediately after dropping out
of it, `AP_NavEKF3_Control.cpp:448` resets `prevFlowFuseTime_ms` on that
transition, and `velTimeout` zeroes the velocity. Five seconds later the flow
fusion timeout fires again. The first dwell in `AID_NONE` is longer, about
11 s, because gyro bias variance grows without aiding and `delAngBiasLearned`
goes false until the no-aiding fusion pulls it back.

So "discard" gives a cleanly reported loss of aiding only if the vehicle
leaves the floor. Held under it, the filter oscillates. At a real focus limit
the vehicle passes through in well under 5 s and none of this happens, which
is the argument for the parameter's advice rather than for the mechanism.

Caveat carried from the earlier run: 5 m is the clamp ceiling and a
deliberate mis-set. At a real focus limit the vehicle is near the ground and
slow, and it passes through in well under the 5 s timeout, so neither arm's
number describes the intended configuration.

Data in `data/ab-2026-09-10-discard/`, figure
`plots/flow_hgt_min_discard_2026_09_10.png`, regenerated by
`plots/make_plots_2026_09_10.py`. The harness is a throwaway test method in a
scratch worktree; its failure to land is expected and not a finding.

## Fixes 2026-09-10 round two (head 126cf753c7): tridge's round

**M1 fixed, superseding "M1 documented, not changed" above.** The sample is
discarded (`flowDataToFuse = false`) rather than zeroed, which is what tridge
asked for. The earlier decision to document rather than change it is
superseded by his review, not by new evidence; the measurement above says what
it bought and what it did not.

**The M2 fix from `946708d630` was incomplete, and is now redundant.**
`flowBelowFocusHeight` only suppressed the flow-triggered call to
`EstimateTerrainOffset`. That function is also entered on `rangeDataToFuse`
alone - which is true on the Plane approach M2 describes - and it then fused
the fabricated zero anyway. Discarding the sample removes the zero, and the
flag goes with it; the `flowDataToFuse` flag is now passed into
`EstimateTerrainOffset` so "no usable flow sample" is one of the reasons
`cantFuseFlowData` is true. Derived from the source, not measured: no Copter
test reaches it, since Copter defaults `EK3_FLOW_USE=1`.

That parameter also stops the terrain estimator reading `ofDataDelayed` when
`recall()` failed, which is the #34305 exposure. `inhibitGndState` is
unaffected - the new term can only be true when `rangeDataToFuse` is, and that
already forces the branch the other way.

**The parameter description is rewritten again.** `6585d32dfd` had just
finished documenting the zero-motion substitution and quoting 1.07 against
5.19 m/s; none of that survives the change. It now says the flow is discarded
and that a vehicle held below the floor loses flow aiding, which is the
reason to keep the value at a real focus limit.

**The replay coverage gap from the should-fix list is closed.**
`test_replay_optical_flow_bit` now sets `FLOW_HGT_MIN=0.30`, so the ROFM record
carries a non-zero value through the log and the parse. It does not make the
gate fire - `OpticalFlowLimits` flies well above 0.30 m - so what it covers is
the record surviving the round trip, and a misparse reading large is what
`check_replay` would catch. Both bugs this branch hit lived in that path.

## Restructure 2026-09-10: 17 commits -> 12, head 5def1557bd

The three commits that shipped known-broken code mid-branch are folded into
the commits that introduced the defects, so a bisect no longer lands on any
of them:

| defect | was fixed | now |
|---|---|---|
| parameter metadata CI fails | 2 commits later | folded |
| `log_ROFH` grows, misparsing every older replay log | 8 commits later | folded |
| uninitialised stack read, SIGFPE under SITL | 8 commits later | folded |

Also folded: the FLOW_HGT_MIN bound and rangefinder-floor note into the
commit that adds the parameter, and the GUIDED altitude hold into the test
it fixes. The DAL `_end` retry fix moved ahead of the ROFM write it is a
prerequisite for, and the Replay ROFM handler now sits immediately after the
message it handles. The two stale claims are gone: no commit now says ROFH
carries the height, and the "above RNGFNDx_MIN" wording is right from the
start.

Verified per commit across all twelve, not just at the tip:

- `ROFH` format string byte-identical to master at **every** commit, so no
  point in the history misparses an older log.
- `param_parse.py --vehicle ArduCopter` passes at **every** commit.
- Each commit builds `./waf copter`.
- `git diff` between the old head and the restructured head is **empty**, so
  the fold changed no content.
- `OpticalFlowFocusHeight` passes at the head.

## What it does

An optical flow sensor cannot focus close to the ground and what it returns
there is not motion. Below the sensor's minimum focus height the EKF discards
the sample rather than dead reckoning a phantom velocity from it. The check is
driven by the rangefinder, which keeps reporting where the flow does not.

**Changed 2026-09-10 at `c08eaf0e43`: this was "treats the flow as zero motion"
until tridge asked for a discard instead.** The section below, and the M1
measurement, were written against the zeroing behaviour and are kept as
written; see "Zero became discard" for what moved and what it costs.

## Why the parameter moved

The height is a property of the sensor, not the estimator, and belongs beside
the mounting position and `FLOW_HGT_OVR` where someone configuring a flow
sensor will look.

The *decision* did not move with it, for two reasons found while doing the
work:

- The flow library has no height above ground - no rangefinder dependency and
  nothing beyond rover's static `FLOW_HGT_OVR`. Doing the comparison there
  needs its own rangefinder access and tilt correction, which is a second and
  worse answer to a question the EKF already answers at the fusion time
  horizon.
- Suppressing the sample in the library is not the same behaviour. Quality 0
  makes the filter stop fusing and dead reckon, which is the failure being
  prevented. Zeroing the rate leaves the body rate term in `flowRadXYcomp`
  (`ofDataNew.flowRadXYcomp = flowRadXY + bodyRadXYZ`), so the filter sees
  apparent motion equal to the gyro.

So the sensor states "this sample is untrustworthy" and the estimator decides
"therefore assume zero motion".

**Superseded 2026-09-10 by `c08eaf0e43`.** The estimator now decides "therefore
do not fuse this sample", which narrows the gap this bullet describes: not
fusing has the same aiding consequence as quality 0, because neither updates
`prevFlowFuseTime_ms`. What survives is the `flowRadXYcomp` point and the
placement argument - the decision needs the rangefinder and the tilt check, and
the library has neither. The bullet is left as written because it is the reason
the parameter is in the flow library while the decision is not, and that is
still the design.

## How the value reaches the EKF

As data travelling with the sample it describes, exactly as `FLOW_HGT_OVR`
already does: `AP_OpticalFlow::update()` -> `AP_AHRS::writeOptFlowMeas()` ->
`NavEKF3::writeOptFlowMeas()` -> `of_elements.minHeight`, and into the DAL so
Replay feeds the filter the value the flight used. Reading it out of the flow
library's parameters from EKF code would not replay.

`AP_NavEKF2` gains no behaviour but has to round-trip the field. Both
estimators write back through `AP_DAL::writeOptFlowMeas`; if only EKF3 passed
the value the two writes would differ on every sample and
`WRITE_REPLAY_BLOCK_IFCHANGED` would log two records per sample, which replay
would feed back as two samples.

### Superseded 2026-09-05: it rides in a new ROFM record, not in ROFH

The original implementation added `minHeight` to the existing `log_ROFH` DAL
record. That is wrong and tridge's first automated review caught it:
`AP_LoggerFileReader::update()` sizes its buffer from the format stored in the
log being replayed, while `MSG_CREATE` copies `offsetof(log_X, _end)` bytes
from the compiled struct. Growing the struct makes the copy run past the
record, and every field after the insertion point shifts.

Measured on logm2_log4 (ROFH `len=40`,
`fmt=ffffIffffB`) against a build that had grown `log_ROFH` to 44: flow
quality read a constant 89 where the true per-sample values were 70-102, and
`minHeight` read -1.15e14. It happened to be harmless on that log, because
quality is only tested for `> 0` and a negative height can never trip a
`rng < minHeight` cutoff, so the EKF output was bit-identical. Which way it
falls is up to the stack, not the design.

The review's suggested fix, `log_##sname msg{};`, does not work: the memcpy
overwrites the zeroed bytes. The fix used is a new message, `ROFM`, beside
`ROFH`, following `97b5b0448a` which split `RISJ` out of `RISI` for exactly
this reason. Old logs have no `ROFM` and replay with the height at 0, which
is the disabled behaviour.

The paragraph above is left in place because the "travels with the sample"
argument is still why the value is in the DAL at all, rather than read from a
parameter inside the EKF.

## Default

0, off, in the manner of `VISO_QUAL_MIN`. Sensors do not share a focus height.

The check only has effect above `RNGFNDx_MIN`, because below that the
rangefinder stops returning `Good` samples, `rngValidMeaTime_ms` goes stale
and the 500 ms freshness gate fails. With the `RNGFNDx_MIN` default of 0.20 m
a floor below that can never fire. The airframe this was flown on had a
rangefinder valid to 1 cm, which is why 0.1 m worked there - it is a property
of the rangefinder fitted, not a safe global default.

### Added 2026-09-05: there is a second floor, `RNGFNDx_GNDCLR`

Derived from the source, not measured. `NavEKF3_core::readRangeFinder()`
clamps the range the filter ever sees:
`rangeDataNew.rng = MAX(storedRngMeas[...], rngOnGnd)` with
`rngOnGnd = MAX(_rng->ground_clearance_orient(ROTATION_PITCH_270), 0.05f)`
(`AP_NavEKF3_Measurements.cpp:29` and `:85`).

`RNGFNDx_GNDCLR` defaults to **0.10 m** (`RANGEFINDER_GROUND_CLEARANCE_DEFAULT`
in `AP_RangeFinder.h:39`). So on a default airframe the comparison can never
see a range below 0.10 m, and any `FLOW_HGT_MIN` at or below that is a silent
no-op. The useful setting is above both `RNGFNDx_MIN` and `RNGFNDx_GNDCLR`,
which is now what the parameter description says.

Note the parameter is `RNGFNDx_GNDCLR`, not `RNGFNDx_GNDCLEAR`. It was renamed
and converted from cm to m; the old name reads as absent rather than as an
error, which is the trap the root playbook records under "Dead parameter names
read as absent".

## Open question: was the flown value inside the rangefinder floor?

Unresolved as of 2026-09-05. Not an argument against the mechanism - an
argument about whether log67 measured it.

log67 flew `EK3_FLOW_MIN_H=0.1` and descended through RFND 0.115 -> 0.054 m.
For the gate to have fired at all, that airframe's `RNGFND1_GNDCLR` must have
been below about 0.075. If it sat at the 0.10 m default, `rngOnGnd` clamped
the range to 0.10, `0.10 < 0.1` is false, and the floor never ran - which
would mean the improvement recorded in
`../../analysis/topics/optflow_horizontal_velocity_lockout.md` had another
cause.

What is known: `../../analysis/vehicles/FPV-4C.md:45` records
`RNGFND1_GNDCLR=0.075`, but on a *forward-declared* sensor
(`RNGFND1_ORIENT=0`) that the EKF never consumes, and `FPV-4C-J1.md:17`
records no rangefinder at all. The JK-4Inch's setting is not recorded in
`../../analysis`, and log67 is not in either repo.

**To settle it:** read `RNGFND1_GNDCLR` (or `RNGFND1_GNDCLEAR` on that
firmware vintage) from log67's parameter dump. Until then, quote the SITL
evidence rather than the flight evidence for this PR.

### Resolved 2026-09-05: the floor fired. The flight evidence stands.

Read from log67 (see `../REPLAY_LOGS.md` to resolve it):

| parameter | value |
|---|---|
| `RNGFND1_GNDCLR` | **0.0** |
| `RNGFND1_MIN` | 0.01 |
| `RNGFND1_ORIENT` | 25 (down), so the EKF does consume it |
| `RNGFND1_TYPE` | 24 (DroneCAN) |
| `EK3_FLOW_MIN_H` | 0.1 |
| `EK3_FLOW_USE` | 1 |
| active source set | 2 (`Using EKF Source Set 2`), `EK3_SRC2_VELXY=5`, optical flow |

`RNGFND1_GNDCLR = 0` gives `rngOnGnd = MAX(0, 0.05) = 0.05 m`, which is below
the 0.1 m floor, so the clamp never defeated it. 856 of the log's 1168 `RFND`
samples read below 0.10 m and 787 below 0.05 m; even the clamped ones enter
the comparison at 0.05, still under 0.1. The gate fired on every sub-floor
sample. `RNGFND1_MIN = 0.01` confirms the "valid to 1 cm" claim, and
`EK3_SRC2_VELXY = 5` confirms flow was the velocity source at the time.

**The criterion stated above was wrong, and this is the correction.** It is
not "GNDCLR below about 0.075", which was reverse-engineered from the 0.054 m
descent reading. The condition is simply

    FLOW_HGT_MIN > MAX(RNGFNDx_GNDCLR, 0.05)

because the clamp raises a low reading to `rngOnGnd`, not to `GNDCLR` itself.
log67 clears it (0.1 > 0.05).

The caveat in "Added 2026-09-05" is unaffected and still matters for everyone
else: with the `RNGFNDx_GNDCLR` default of 0.10 m, `FLOW_HGT_MIN = 0.1` is a
no-op, and the flown value only worked because that airframe had `GNDCLR`
zeroed.

## Evidence

Flight (as `EK3_FLOW_MIN_H`, 4-inch quad, log67, descent through the floor at
rangefinder 0.115 -> 0.054 m): `FIX/FIY` +/-2000-6700 -> +/-200-500, `NI`
pinned 255 -> 3-40, phantom `VN/VE` +/-0.5 -> +/-0.1 m/s, DesRoll/Pitch
+/-14 -> +/-2 deg. Operator: "althold type behaviour close to the ground but
no sudden lean". The rangefinder-clamp question raised against this on
2026-09-05 was resolved the same day in the section above: the floor fired.

SITL (`Copter.OpticalFlowFocusHeight`, three runs, **branch head 292ec09fef**,
the RC-descent version of the test): hover in an asserted altitude band below
the floor on flow-only nav, inject a one-axis flow rate offset with
`SIM_FLOW_OFS_X`. Peak EKF groundspeed 0.029-0.031 m/s with the floor set
against 0.90-1.22 m/s without it.

### Re-measured 2026-09-05 at head 84ec31a99d

The test was rewritten (guided descent, third subtest) so these are not the
same measurement as the numbers above, which are left alone. The hover is now
held at 2.00-2.01 m rather than in a 1.5-2.5 m band, and there are three arms
rather than two. Peak EKF horizontal speed inside the injection window, across
two runs of the current code:

| `FLOW_HGT_MIN` | meaning | peak XKF1 speed |
|---|---|---|
| 3.0 | above the vehicle, floor fires | 0.261, 0.264 m/s |
| 0 | disabled: master's behaviour | 1.125, 1.489 m/s |
| 1.0 | below the vehicle, must not fire | 1.404, 1.564 m/s |

The floor-active arm runs the full 15.8 s window and stays inside
0.02-0.26 m/s. The other two exit as soon as they cross the test's 0.8 m/s
bound, at about 6 s, so their peaks are where the test stopped looking and not
where the divergence ended.

The third arm is the one worth keeping: a floor that fired at *every* height
rather than below its value would pass both of the original two subtests,
because the second disables the feature outright.

## Plots

`plots/flow_hgt_min_ab.png` - the original, head 292ec09fef. One binary,
`FLOW_HGT_MIN` 3.0 against 0. The figure plots EKF horizontal speed from
`XKF1` over the whole 30 s window and peaks at 0.04 m/s against 2.50 m/s.
Those autotest numbers (0.029-0.031 against 0.90-1.22) are the same runs
measured differently: `wait_groundspeed` reports the first sample crossing its
bound rather than the peak, so it reads lower on the diverging arm. Neither is
wrong; quote the autotest bounds when talking about the test and the peaks
when reading the plot.

`plots/flow_hgt_min_ab_2026_09_05.png` - head 84ec31a99d, all three arms,
regenerated by `plots/make_plots.py` from `data/ab-2026-09-05/`.

`plots/flow_hgt_min_discard_2026_09_10.png` - zeroing against discarding on a
translating vehicle, regenerated by `plots/make_plots_2026_09_10.py` from
`data/ab-2026-09-10-discard/`. This one does need two builds, since the arms
differ by code and not only by parameter.

The floor is fully behind the parameter, so `FLOW_HGT_MIN=0` is master's
behaviour and no second build is needed for either figure.

## Known limit

Zeroed flow does not pin velocity against a continuous divergence force - a
1.5 m/s^2 accel bias ran to 27 m/s in an early test. That is not the
near-ground failure, which is bad flow on a nearly stationary vehicle, and is
what the lockout recovery in #33484 addresses.

## Review

### tridge automated pass 1, 2026-09-04 (head 292ec09fef)

1. Parameter metadata did not parse - the `_HGT_MIN` doc block sat between
   `_OPTIONS`' block and its own `AP_GROUPINFO`, so `param_parse.py` attached
   it to the wrong parameter and CI failed. Real, and the blocking one. Fixed
   by `d4d6cd08dd`.
2. `log_ROFH` grew a field and `MSG_CREATE` does not zero the struct. Real;
   see "Superseded 2026-09-05" above. The suggested fix was wrong.
3. Duplicate commits with #33484. Still open; see "Relationship to #33484".
4. The rangefinder height is taken at the IMU origin, so a large `FLOW_POS`
   biases the check. Real, documented in the parameter description.
5. "the EKF" where only EKF3 acts on the value. Fixed in the description.

Two claims in that review were wrong and are recorded here so they are not
re-raised: the suggested `log_##sname msg{};` does not fix the misparse
(memcpy overwrites the zeroed bytes), and "the first ROFH field whose garbage
value changes behaviour" is false - `heightOverride` was added identically in
2022 by `b15cb46d25` with the same `> 0` gate.

### tridge automated pass 2, 2026-09-05 (head 7d8ec8f344)

Its blocking finding was real, and it is the most valuable thing either review
produced. `AP_DAL::WriteLogMessage` returned early when `logging_started` was
false *without setting the `_end` retry flag*, so a record that is only written
when it changes is dropped and, because the struct has already latched the new
value, the memcmp matches forever and no record is ever written.

The first instance of this (before the first log opens) was fixed by
`7d8ec8f344`. The review found the second: a *later* log in the same power
cycle, because the struct stays latched across `stop_logging()`.

Reproduced, not just argued. Downloading a log between two flights in one
power cycle (`AP_Logger_File::get_log_data` calls `stop_logging()`):

```
log 2:  ROFH=2635  ROFM=1     flight 1, floor recorded
log 3:  ROFH=1302  ROFM=0     flight 2, floor absent
```

After the fix both logs carry `ROFM=1` with value 3.0. Note `LOG_DISARMED=0`
does *not* reproduce it: with `LOG_REPLAY=1` the rotate-on-disarm path in
`AP_Logger_Backend::vehicle_was_disarmed()` is explicitly suppressed, so both
flights land in one file.

Fixed generically, by setting `_end` on the `!logging_started` return, which
also answers peterbarker's `force_write` question below.

### peterbarker, CHANGES_REQUESTED, 2026-09-04 (head 7d8ec8f344)

- **"Isn't `force_write` supposed to take care of this?"** He is right that it
  should. It does not, because `force_write` is set and cleared inside a single
  `start_frame()` (`AP_DAL.cpp:46` and `:119`), so it only reaches records
  written from there. That is why `RISJ` escapes and a record written from a
  sensor callback does not.
- **NaN rather than 0 as the unused sentinel**, twice. Not taken: the
  `heightOverride` argument on the same call already means 0-is-unused, and
  the user-facing parameter documents "0 disables it". NaN would make the two
  arguments disagree.
- **"Why the rangefinder and not `terrainState`, like the block above?"** The
  choice is deliberate and the reasoning is now a comment in the code:
  `terrainState` is itself fused from optical flow, so gating flow on it is
  circular, and it is not updated at all when the rangefinder is the height
  source, which is a common flow-nav configuration. The block above gets away
  with it because it runs pre-takeoff.
- **"You check staleness where the above does not."** Necessary here:
  `rangeDataDelayed` holds its last value when the rangefinder stops
  reporting, which is exactly what happens below `RNGFNDx_MIN`.
- **"Tie into `gndOffsetValid`."** Not taken: 5 s staleness is far too loose
  for a sub-metre decision on a descending vehicle, and its
  `activeHgtSource == RANGEFINDER` disjunct is unconditionally true in the
  target configuration.
- **`DCM33FlowMin` ignored.** `tiltOK` added to the condition. It changes
  nothing today, since both consumers of the zeroed rates are already
  tilt-gated, but it makes the tilt projection in the comparison safe to read.
- **Autotest line splitting, and guided rather than RC.** Both taken; see the
  test note below.

## The SIGFPE this PR introduced, and the fix that was wrong

Found on 2026-09-05 after the second review round, from a report of four
crashed tests. Worth recording in full because the obvious fix is the wrong
one.

`ekf_ring_buffer::recall()` (`AP_NavEKF/EKF_Buffer.cpp:53`) only memcpys into
the caller's element `if (ret)`. On failure the local is left untouched, so
`of_elements ofDataDelayed;` in `SelectFlowFusion` is uninitialised stack
whenever `flowDataToFuse` is false - which is most IMU steps, since flow
arrives at about 10 Hz against a 400 Hz filter.

This PR's focus-height check read `ofDataDelayed.minHeight` *without* gating on
`flowDataToFuse`. SITL enables `FE_INVALID | FE_OVERFLOW | FE_DIVBYZERO`
(`AP_HAL_SITL/Scheduler.cpp:199-206`), and `>` and `<` are signalling
comparisons, so a NaN bit pattern in that slot is an immediate SIGFPE rather
than a wrong answer.

Demonstrated rather than inferred, by poisoning the struct with
`memset(&ofDataDelayed, 0xFF, sizeof(ofDataDelayed))` so it does not depend on
stack luck. Same build, one variable:

| gate | result |
|---|---|
| `flowDataToFuse &&` present | `Copter.OpticalFlowFocusHeight` passes, ~30 s |
| absent | `_sig_fpe (signum=8)` -> `SelectFlowFusion` at `AP_NavEKF3_OptFlowFusion.cpp:61` |

Master does not trip this on Copter: the only pre-existing read of the struct
(`MAX(ofDataDelayed.flowRadXY[0], flowRadXY[1]) > _maxFlowRate`, at
`AP_NavEKF3_OptFlowFusion.cpp:107`) sits behind
`_flowUse != FLOW_USE_TERRAIN` in a `||` chain, and `EK3_FLOW_USE` defaults
to 1 there.

**Zero-initialising the struct is the wrong fix, and was tried first.** `{}`
silences the crash but converts the UB into a deterministic fabricated
measurement: `MAX(0,0) > _maxFlowRate` is false, so `cantFuseFlowData` becomes
false where garbage would usually have made it true, and
`EstimateTerrainOffset` then fuses an invented zero flow rate into
`terrainState` whenever a rangefinder sample arrives without a flow one. That
path is live by default on Plane, where `EK3_FLOW_USE` defaults to **2**. The
fix shipped is the `flowDataToFuse` gate; the `{}` was reverted before the
branch was pushed a second time.

**Split out as #34305 on 2026-09-05:** line 107 reads the same uninitialised
struct. It turned out to need only a rangefinder, not a flow sensor, so any
Plane with one fitted is exposed for most of every takeoff and landing. Fixed
there by gating `cantFuseFlowData` on `flowDataToFuse`. See `../34305/`.

**Also unexplained:** the report was of four crashed tests, but CI was green
on all 30 checks at `7d8ec8f344` and neither analysis repo records an FPE, so
that run came from somewhere else. If the test names were all Copter it is the
line 61 crash fixed here; if any were Plane it points at line 107 instead, and
that becomes urgent rather than a follow-up.

## Gotchas worth remembering

Adding `minHeight` to `log_ROFH` without updating the `"ffffIffffB"` format
string made the binary refuse to boot with `Config Error: Log structures
invalid`. It surfaced as autotest failing with "Failed to set RC values" and
as every ad-hoc SITL probe reading nothing, which looked like a broken
plumbing chain for some time. The format string, the field-name list, the
units and the mult strings all have to grow together.

A DAL record written with `WRITE_REPLAY_BLOCK_IFCHANGED` from a push-based
sensor callback needs its record count checked in a real log, with the feature
configured and at its default, and in a *second* log in the same power cycle.
The code is correct, the autotest passes, and the field is simply absent.
Counting records is what caught it; reasoning about `IFCHANGED` did not.

`ArduCopter`'s autotest `takeoff()` helper documents the trap the test hit:
"in a manual-throttle mode such as STABILIZE the vehicle climbs fast and can
blow way past altitude_min... If your test cares about the altitude the
takeoff finishes at, take off in GUIDED."

## Autotest note

`Copter.OpticalFlowFocusHeight` climbs in ALT_HOLD, because flow is not
healthy while stationary on the ground, then descends to the test altitude in
GUIDED, which holds it. The old RC descent flew through its target by an
amount that depended on the speedup; the guided version held 2.00-2.01 m
across all three arms and all runs.

The measurement window is deliberately back in ALT_HOLD. A position-controlled
mode would fly the phantom velocity away instead of leaving it in the
estimate, which removes the very thing the test is reading.

## Relationship to #33484

Both branches add a field to `of_elements` and extend `writeOptFlowMeas`, so
whichever merges second needs a small rebase. Otherwise independent and
reviewable in either order.

Two commits are the same patch on both branches under different SHAs, so a
rebase will drop them by patch-id but they are not literally shared commits:

| patch | on #33484 | on #34292 |
|---|---|---|
| `SITL: add SIM_FLOW_OFS optical flow rate offset for fault injection` | `9d8e218d67` | `25c7364cb5` |
| `AP_OpticalFlow: apply SIM_FLOW_OFS offset to the SITL flow rate` | `2e02161d1a` | `d70cb7a058` |

Whichever lands second needs them dropped. This is noted in #34292's PR
description and in `../33484/split-and-quality-gate.md`.

## Reproduce

The SITL arms, from an ArduPilot checkout on `pr-flow-hgt-min`:

```
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.OpticalFlowFocusHeight
```

It leaves three flight logs in `logs/`, one per subtest in order
(`FLOW_HGT_MIN` 3.0, 0, 1.0). Each is identifiable by its first
`PARM FLOW_HGT_MIN` value, and the injection window by the `PARM
SIM_FLOW_OFS_X` transitions to 1.0 and back to 0.

`data/ab-2026-09-05/*.csv` holds `XKF1` core 0 (`t_s,VN,VE,alt_m`) extracted
from those logs at head `84ec31a99d`, with the injection window in the header
comment. The full BINs are about 41 MB and are not committed; the CSVs are
44 KB and carry everything the figure needs.

```
python3 plots/make_plots.py
```

The replay-record checks:

```
Tools/autotest/autotest.py test.Copter.Replay
```

For the two-logs-in-one-power-cycle case there is no committed test. It was
reproduced with a throwaway autotest that armed, flew, disarmed, stopped
logging with a MAVLink `log_request_data` (which calls `stop_logging()`), then
armed and flew again, and counted `ROFM` records per log.

## Zero became discard (2026-09-10, `c08eaf0e43`)

tridge, inline on 2026-09-09: "is zero right? if we're actually moving that
seems like a bad idea", then "possibly just set `flowDataToFuse = false`?".
Done at `c08eaf0e43`: the two `zero()` calls are gone, `flowDataToFuse` is
cleared instead and passed into `EstimateTerrainOffset()`, where
`cantFuseFlowData` now opens with `!flowDataToFuse`.

That one change also closed the terrain leak the flag had been added for, and
a pre-existing one beside it. `EstimateTerrainOffset()` is entered on
`rangeDataToFuse` alone - which is exactly the Plane approach case - so gating
only the call left the zero reaching `terrainState` anyway. `!flowDataToFuse`
is additionally a flow-**availability** check, because a failed `recall()`
leaves the flag false, so a never-recalled sample can no longer be fused as a
deterministic zero either.

**What it costs, and what is not measured.** Discarding is not neutral where
zeroing was not. A zeroed sample was fused, which kept `prevFlowFuseTime_ms`
alive; a discarded one is not fused at all, and at 5 s without a flow fusion
`flowFusionTimeout` fires (`AP_NavEKF3_Control.cpp:308`, acted on at `:315`)
and the filter drops to constant position. The next consequence after that,
`attAidLossCritical`, is bounded by `tiltDriftTimeMax_ms` at 15 s
(`AP_NavEKF3.h:493`), so 5 s is the binding one.

The defence, recorded in `3ff05c761a`'s commit message and the test comment,
is that a realistic `FLOW_HGT_MIN` is passed through in well under 5 s, and
that the autotest only sees the fallback because it holds the floor far above
any real sensor to keep it active long enough to measure. That is reasoning,
not a measurement: **no run establishes the dwell time below a realistic floor
on a real approach.** It is the obvious thing to measure next, and it is the
one place where the flown behaviour and the head's behaviour genuinely differ -
log67 flew the zeroing version.

Tier 3, derived from the source and the timeout constants, not measured.

## Automated round of 2026-09-10, triaged at `a204212074`

The round was taken at `337cf08df6` and posted 15:43Z. Four of the commits on
the branch are dated after it: `c08eaf0e43` has a commit date of 18:37Z, nearly
three hours later. So the round describes code that had already moved by the
time anyone read it, while all three of tridge's inline threads were answered
at 18:41Z and the top-level review comment was not.

Answered on the PR on 2026-09-11 with the triage below, plus the discard cost
recorded in the section above, which the round did not raise.

| finding | state at `a204212074` |
|---|---|
| BUG: terrain withhold bypassed when range data arrives in the same cycle | Fixed, `c08eaf0e43`. The fix is the one the round proposed - OR the flag into `cantFuseFlowData` rather than gating the call - and also tridge's own inline suggestion |
| ISSUE: range-only calls fuse fabricated zero flow (pre-existing) | Closed by the same change; `!flowDataToFuse` is the single availability check the round asked for |
| `LOG_ROFM_MSG` mid-enum | Fixed, `da78928a9b`; ROFM sits after RTER. Answered inline with the FMT-table numbers |
| No test coverage for the terrain path | Still true. Copter defaults `EK3_FLOW_USE` to 1, so no Copter test reaches the terrain-flow branch |
| peterbarker's CHANGES_REQUESTED still open | His six inline comments all have replies from 2026-09-05; withdrawing the review is his call |

The round's two self-corrections are worth keeping because they stop the
same suggestions coming back: the earlier claim about uninitialised
`flowRadXY` is wrong, `Vector2`'s default constructor zeroes both components;
and fixing the terrain leak does **not** make the parameter a no-op on Plane,
because withholding an unusable terrain-flow observation is itself an effect.

## Terrain path now has a test (2026-09-12)

Closes the one open item from the triage table above: "No test coverage for the
terrain path - still true."

`FlowHeightMinTerrainPath` sets `EK3_FLOW_USE = 2`, `FLOW_HGT_MIN = 5`, and
`WP_SPD = 12` so the vehicle clears the terrain estimator's 5 m/s floor, then
flies a guided leg at 3 m and another at 15 m. The observable is `XKF5.AFI`,
`auxFlowObsInnov.length()*1000`, which `EstimateTerrainOffset()` writes only on
the flow-fusion branch (`AP_NavEKF3_OptFlowFusion.cpp:209`).

| build | AFI below FLOW_HGT_MIN | AFI above |
|---|---|---|
| head | **0** | 62 |
| `!flowDataToFuse` removed from `cantFuseFlowData` | **2462** | - |

The high-leg assertion is what keeps it honest: a rig that never fuses terrain
flow would also read zero on the low leg, so the test requires the high leg to
be non-zero before the low-leg zero means anything.

The unfocused sample's innovation is about 40 times the focused one, which is a
useful number to have when arguing why the withhold exists at all.

Guided position targets rather than RC, per peterbarker's comment on the other
test in this PR. Note for future work: `fly_guided_move_local` silently
reported arrival without moving the vehicle in one run on #33568; this test uses
`send_position_target_local_ned` plus `wait_groundspeed`, which cannot report a
leg as flown when it was not.

## The stuck flow landing, and what FLOW_HGT_MIN does about it (2026-09-16)

Two SITL sightings on unrelated branches: #34380's removal branch (60 m flow
climb, LAND, never disarmed, 1.4 m touchdown position step, 30 deg lean on
the ground) and #33498 round 1 (LAND with a flow scale error, 30 deg roll held
on the ground). Question: is a phantom flow velocity at touchdown the cause,
and does this PR's floor fix it?

### Reproducer

SITL, tier 2. #34380's removal stack (`dc841b8fd1`, on #33585 `e18c7d6fc3`)
plus local probe commits (`probe.diff`: a PRFL dataflash message per flow
fusion call with innovations, per-axis test ratios, measured flow, EKF HAGL,
range, range age and position/velocity sigma, and an autotest knob set).
Flow-only copter, no GPS, `EK3_OPTIONS` 32 (bit 5), SITL analog rangefinder
(`RNGFND1_MAX` 40, `RNGFND1_MIN` 0, `RNGFND1_GNDCLR` default 0.10), default
`AVOID_ENABLE`. Take off in ALT_HOLD to 5 m, LOITER 10 s, full climb to 60 m,
hold 25 s, LAND, `SIM_WIND_SPD` 6 (runs vary turbulence 1 and direction 0, 45,
90, 135). About 8 s of wall time per run.

It is not minimal in the sense of short: with the same wind, climbs of 5, 20,
35 and 45 m all disarmed 2 s after touchdown, and a pilot reposition in LAND
released at 0.1-0.3 m (touchdown speed 0.18 m/s, 5 m climb, with or without
wind) also disarmed. Two things separate the stuck runs:

| climb | touchdown speed | position sigma 0.5 s before touchdown | outcome |
|---|---|---|---|
| 5 m | 0.02 m/s | 2.2 m | disarmed |
| 45 m | 0.08-0.09 m/s | 31 m | disarmed |
| 60 m | 0.11-0.27 m/s | 45-48 m | stuck |

Velocity sigma was 0.06-0.07 m/s in all of them. Position sigma grows through a
long flow-only flight; the 60 m climb goes above the 40 m range, which only the
bit-5 stack can navigate. An in-range 25 m flight held 120 s (sigma 34 m) with
a 0.18 m/s touchdown also disarmed, on the removal branch and on master alike,
so the above-range flight is part of the recipe, not just flight time.
`AVOID_ENABLE 0` stuck 2 of 3, so avoidance is not a factor; the earlier 4 of 4
disarms with it off were windless runs.

### Where the step starts

Per-sample PRFL at touchdown (stuck run `a_w6_c60_r2`, removal branch):

- rangefinder reading 0.17 and 0.13 m: measured flow 1.25 rad/s, innovation
  -0.15, test ratio 0.02. Normal.
- rangefinder reading below the 0.10 m ground clearance, EKF range clamped to
  `rngOnGnd` 0.10 while the SITL sensor range goes to zero: measured flow
  2.53 rad/s, innovation -0.87, test ratio 0.59, **fused**, about 0.16 s before
  touchdown.
- on the ground: SITL flow computes `v / range` with range near zero, so
  sub-millimetre motion reads as rad/s (and exactly zero height gives zero
  flow). Innovations of 0.9 to 1.6 rad/s are fused or rejected per axis over
  the next second, the EKF position walks 1.1-13.6 m against truth (5 stuck
  runs), and the roll/pitch demand reaches 30 deg within about 1 s, which holds
  `large_angle_request` and resets the land detector.

So the phantom starts below `RNGFNDx_GNDCLR`, not below `RNGFNDx_MIN`: SITL's
analog rangefinder reports Good all the way to 0, with the range age 0-50 ms.
The SITL flow near-zero-range amplification is a model feature, but a real
sensor below its focus height also reports non-motion, which is this PR's
premise.

### Variants (5 runs each unless stated)

| variant | disarmed | large innovations fused near touchdown | lean on ground |
|---|---|---|---|
| (a) removal branch, no #34292 | 0 of 5 | yes | 30 deg |
| (c) + #34292, `FLOW_HGT_MIN` 0 (default) | 0 of 5 | 1-7 per run | 30 deg |
| (b) + #34292, `FLOW_HGT_MIN` 0.3 | **5 of 5**, 2.0-2.1 s after touchdown | 0 | 0.9-4.3 deg |
| (e) as (b), `RNGFND1_MIN` 0.2 set in flight | 3 of 5 | 2-4 in every run | 30 deg in the 2 stuck |
| (f) as (e), gate freshness 500 ms -> 5000 ms (`stale5s.diff`) | **5 of 5** | 0 | 1.4-2.5 deg |

0.3 m was chosen above both `RNGFND1_MIN` (0 here) and the 0.10 m ground
clearance where the phantom starts, and is crossed in about 0.6 s at land
speed, well inside the 5 s flow fusion timeout. #34292's own commits were
cherry-picked onto the removal base; its last autotest commit `0374a23d84`
conflicted and was skipped, no C++ was skipped.

(e) is the realistic rangefinder: below 0.2 m it goes OutOfRangeLow, the last
Good reading freezes (0.279 m in `e_hm03_rmin02_r1`), and the gate keeps
discarding while the reading is under 500 ms old. At touchdown the age reaches
500 ms, the gate switches off, and ground flow is fused again (innovations
1.27, -0.86, -0.63 in that run). This is the staleness check the parameter
description already warns about, and it lands exactly on the touchdown.

### Master

`b2b1b3d279` plus the probe, in-range scenarios only, because master caps the
climb and has no above-range flow navigation: 25 m held 60 s in 6 m/s wind (3
of 3 disarmed), 25 m held 120 s with a 0.18-0.19 m/s touchdown (3 of 3, lean up
to 13.9 deg), 10 m held 240 s with `FLOW_FXSCALER` 200 and a reposition (2 of 2;
a third run failed in the harness before landing). The phantom innovations are
there on master too (1-4 fused above 0.5 rad/s per run), but no master landing
stuck in 8 measured runs. So the phantom is pre-existing; the stuck landing was
only reproduced after the above-range flow flight that #33585 and #34380 make
reachable. Not established whether a longer or faster master flight sticks.

### Conclusions and recommendation

- Mechanism: tier 2. Fused phantom flow at and after touchdown, below the
  ground clearance, moves a position estimate whose sigma has grown to tens of
  metres; the position controller cannot correct it on the ground, winds the
  lean past 15 deg and the land detector never completes.
- This PR fixes the reproducer, but only with `FLOW_HGT_MIN` set above the
  ground clearance (default 0 does nothing), and only while the rangefinder
  keeps reporting. With a rangefinder whose minimum is above the ground, the
  500 ms freshness check turns the gate off at touchdown and 2 of 5 still stuck.
- What should change, in order: (1) the gate should keep acting when the range
  finder has dropped out low rather than switching off after 500 ms - the 5 s
  window is the measured form, a narrower one (keep discarding while the last
  Good reading was below the floor and no newer reading exists, or while the
  vehicle is landing) is not measured, and the 5 s window's in-flight side
  effects are unmeasured (tier 3); (2) #34380's description should state the
  landing exposure and point at `FLOW_HGT_MIN`; (3) whether `FLOW_HGT_MIN`
  should default to a small non-zero value just above the default ground
  clearance is a maintainer decision - sensors do not share a focus height,
  which is why the default is 0, but the landing failure is at the ground
  clearance, not at the focus height.

Data in `data/flow-landing-2026-09-16/`: `c_hm0_r2` (default 0, stuck),
`b_hm03_r2` (0.3, disarmed), `e_hm03_rmin02_r4` (0.3 with `RNGFND1_MIN` 0.2,
stuck), `probe.diff`, `stale5s.diff`, `run_fl.sh`, `analyse_fl.py`,
`dump_window.py`. Branches are local only (`fl-control`, `fl-hgtmin`,
`fl-hgtmin-stale5s`, `fl-master`).

## The hold and the ground clearance floor (2026-09-16, later)

All three recommendations above done on `pr-flow-hgt-min`, local and unpushed,
five commits on `0374a23d84`:

| commit | what |
|---|---|
| `48c843a5ce` | AP_NavEKF3: hold optical flow off below FLOW_HGT_MIN after range dropout |
| `0ce208012c` | autotest: check flow stays discarded on a landing below RNGFND1_MIN |
| `837c7e1fbe` | AP_NavEKF3: skip the flow focus height hold without any range sample |
| `d83c4a9559` | AP_NavEKF3: discard optical flow at the range finder ground clearance |
| `6f1d116306` | AP_OpticalFlow: describe the FLOW_HGT_MIN hold and ground clearance floor |

`837c7e1fbe` fixes a regression `48c843a5ce` introduced: with no range sample
ever recalled, the carried height was the vertical position alone, so a vehicle
with `FLOW_HGT_MIN` set and no range finder would hold flow off near the origin
height. Derived from the source, not measured: a flow-only copter with no range
finder cannot arm in this harness ("Failed to get EKF.flags=271").

### The gate

`AP_NavEKF3_OptFlowFusion.cpp` at `6f1d116306`:

- `:59-61` record the tilt-corrected range and the vertical position whenever a
  range sample is recalled (`rangeDataToFuse`), and that one has been.
- `:69` the floor is `MAX(FLOW_HGT_MIN, rngOnGnd + 0.05)`.
- fresh range (under 500 ms, as before): discard below the floor.
- stale range, `:79-85`: carry the last sample forward by the height change
  since. A hold starts only on a descent through the floor (the previous check
  was above it), and then lasts while the range finder reported
  OutOfRangeLow in the last 500 ms (`AP_NavEKF3_Measurements.cpp:46`, stamped
  from `AP_DAL_RangeFinder::Status`, so it replays) or the carried height stays
  below the floor.
- ends: a fresh sample above the floor; the carried height back above the floor
  with no OutOfRangeLow; `takeOffDetected` clearing on the ground (disarm on
  Copter).

How it tells the cases apart (read from the source): `readRangeFinder()` at this
head stores only `Good` samples, so OutOfRangeLow and a dead sensor both leave
`rngValidMeaTime_ms` stale and `rangeDataDelayed` at its last value. The status
separates low from lost; the carried height separates a sensor lost at height
(carried height stays high) from one lost near the ground. Out of range high
leaves the last sample near the maximum. A vehicle below the floor at takeoff
does not start a hold from OutOfRangeLow alone, because there has been no
descent through the floor.

#### Superseded 2026-09-17 by a SITL run (the traverse repro in round 3 below)

"The carried height separates a sensor lost at height (carried height stays
high)" is true only over flat ground. Over ground that falls away the carried
height reads the old ground: climb to 30 m above an 8 m range finder, fly 1 km
over ground falling 13 m, descend, and the hold starts at 13.1 m true height
with the carried height at 0.24-0.27 m (range 266 s old), holding flow off up
to 31 s. The paragraph above was an inspection claim, not measured; it is left
in place because it is still what happens over flat ground. The 5 s bound in
round 3 is the fix.

### In-flight side effects, SITL, master-based

Probe branches `fl34292-old` (`0374a23d84`) and `fl34292-new` (`48c843a5ce`),
each plus a local PRFG dataflash probe. Flow-only copter, analog range finder.
"Held" counts samples the new hold discarded with a stale range; the old gate
has no hold to count, so compare fused counts.

| scenario | old: flow fused | new: flow fused | new: held with stale range | outcome |
|---|---|---|---|---|
| out of range high: `RNGFND1_MAX` 3, climb to 8 m, 20 s, back down (`FLOW_HGT_MIN` 1.0, `AVOID_ENABLE` 0) | 486 | 487 | 0 | same |
| range finder lost at 5 m (orientation changed), 20 s (`FLOW_HGT_MIN` 1.0) | 284 airborne | 301 airborne | 0 airborne | same in the air; LAND below 0.3 m true height fused 27 old, 0 new (held 191) |
| hover 1.1 m, `FLOW_HGT_MIN` 1.0, `SIM_SONAR_RND` 0.3 | 348 | 342 | 0 | same (fresh discards from noise on both) |
| dip: hover 3 m, 8 s at 1.5 m, back to 3 m (`FLOW_HGT_MIN` 2.0, `RNGFND1_MIN` 0) | stopped aiding 1.5 m, restarted at 2.20-2.32 m | stopped aiding 1.5 m, restarted at 2.18-2.42 m | 0 | same |
| dip, `RNGFND1_MIN` 1.7 set in flight | **never stopped aiding: 88 unfocused samples fused below the floor** | stopped aiding at 1.5 m after 5 s, restarted at 2.08-2.20 m | 624 | old gate released below the range finder minimum, the defect |

The lost-at-height row is the one behaviour change in flight: once the carried
height says the vehicle is below the floor, flow near the ground is discarded
with a dead range finder, where the old gate fused it. Disarm time was the same
(12.6 s). Single runs per cell, deterministic flights.

### The landing test

New subtest of `OpticalFlowFocusHeight` (`Tools/autotest/arducopter.py:4527`):
`FLOW_HGT_MIN` 0.3, take off, raise `RNGFND1_MIN` to 0.2 in flight (SITL's range
finder reads 0 m on the ground, so a minimum above it would stop arming on
flow), LAND, require disarm and zero changes in XKF5 `FIX/FIY/NI` from the
first RFND OutOfRangeLow to disarm (they change only when flow is fused).

| build | runs | updates from range low to disarm (about 2.5 s) | result |
|---|---|---|---|
| `0ce208012c` | 4 | 0, 0, 0, 0 | pass |
| `6f1d116306` | 1 | 0 | pass |
| `0ce208012c` with `48c843a5ce` reverted | 3 | 19, 19, 20 | fail |

Deterministic in these runs (0 flakes in 8). Disarm alone does not
discriminate on master-based code: master's in-range landings disarm (8 of 8
above), which is why the assertion is on fusion.

On the #34380 stack with the hold, `FLOW_HGT_MIN` 0.3 and `RNGFND1_MIN` 0.2
(variant (e) above, which stuck 2 of 5 without the hold): 5 of 5 disarmed 2.1 s
after touchdown, no innovation over 0.5 rad/s fused, ground lean demand 1.6-2.9
deg.

### The default

Why it was 0, answered:

- tridge's automated rounds: "default 0 = disabled, so nothing changes on
  upgrade". That stays true of `FLOW_HGT_MIN` itself, which is still 0.
- this record's "Default" section: sensors do not share a focus height, and the
  flown 0.1 m was a property of that range finder, not a safe global value.
  Also still true; that is why a focus height is not guessed.
- the 2026-09-12 round's note that latching on a stale range "could withhold
  flow indefinitely": the hold is bounded by a fresh sample, the carried height
  and takeoff detection, and only a descent through the floor starts it.
  **Superseded 2026-09-17:** the carried height is not a bound when the ground
  under the vehicle has changed; the 2026-09-12 concern was right. See round 3
  below: the hold now trusts a carried height for 5 s only.

What changed the answer: the landing failure is not at a focus height. It
starts where EKF3's range clamp bites, at the range finder ground clearance, and
it continues on the ground until disarm. So the default is a floor tied to
`rngOnGnd` (`MAX(RNGFNDx_GNDCLR, 0.05)`) plus 5 cm, always on, and
`FLOW_HGT_MIN` only raises it. It does change behaviour on upgrade, in the last
5 cm of a landing and on the ground until disarm, and the tests below are the
evidence that nothing else moves.

The two framings, #34380 stack, stuck-landing repro (60 m flow climb, LAND, 6
m/s wind), no user settings:

| build | ground clearance | disarmed | innovations over 0.5 rad/s fused near touchdown | ground lean |
|---|---|---|---|---|
| no floor, `FLOW_HGT_MIN` 0 (variant (c) above) | 0.10 | 0 of 5 | 1-7 per run | 30 deg |
| A: `FLOW_HGT_MIN` default 0.15 | 0.10 | 5 of 5 | 0 | 1.5-2.5 deg |
| B: floor at ground clearance + 0.05 (chosen) | 0.10 | 5 of 5 | 0 | 1.2-3.6 deg |
| A | 0.30 | 3 of 3 | 2 per run | 6.0-13.2 deg |
| B | 0.30 | 3 of 3 | 0 | 1.8-2.5 deg |

A fixed default sits below the clamp on any airframe whose ground clearance
exceeds it; B follows the airframe. The 5 cm margin comes from the stuck runs:
samples at range readings of 0.13-0.16 m had innovations of 0.15 rad/s or less,
the first bad one arrived at the clamped 0.10 m.

Normal flow behaviour at `6f1d116306` plus a local SITL port switch only
(`fl34292-final`), all pass: OpticalFlowFocusHeight (with the landing subtest),
FlowHeightMinTerrainPath (the `EK3_FLOW_USE=2` terrain path Plane defaults to:
low leg AFI max 0, high leg 62), OpticalFlow, OpticalFlowLimits,
LoiterNoCompassYaw, OpticalFlowCalibration, Replay. Copter and plane build.

Model caveat: SITL's flow sensor sits at ground level when landed, so its rates
go to v/0 at touchdown and the phantom is larger than on a real vehicle, whose
flow sensor stays at its mounting height. The flight evidence for the real
near-ground phantom is the focus-height log above, not this.

Open for the push: `6f1d116306`'s subject is 73 characters (gate note), and
`48c843a5ce`'s message quotes the #34380-stack landing numbers without saying so;
both are for the rewrite at push time.

### Pushed and answered (2026-09-16)

Fast-forward push `0374a23d84` -> `29cfdb6ddc`, four commits, tree
byte-identical to the local `6f1d116306`:

| measured on | pushed as |
|---|---|
| `48c843a5ce` + `837c7e1fbe` the hold after range dropout (no-range-sample skip folded in) | `8f736ce1f0` |
| `0ce208012c` landing subtest in OpticalFlowFocusHeight | `5aeccff68e` |
| `d83c4a9559` the ground clearance floor | `8325d8d337` |
| `6f1d116306` parameter description, subject shortened | `29cfdb6ddc` |

The hold and floor commit messages now say their landing numbers were taken
after a flow flight above the rangefinder range with the height limit removed
(#34380), which is what makes that flight reachable. PR body: the "Defaults to
0, off" paragraph replaced with the floor, the hold and FLOW_HGT_MIN raising
the floor. Reply posted 21:40Z
(https://github.com/ArduPilot/ardupilot/pull/34292#issuecomment-5704968854)
with the variant table, the hold, the default decision answering the earlier
review's reasons, and the SITL flow sensor caveat. `AIReview` and `DevCallEU`
are on.

Still open from the 2026-09-12 automated round and not addressed in this push:
the no-hysteresis note at the floor, the ROFM units note, the wiki note, and
the test message `high and len(high)` at `Tools/autotest/arducopter.py:15167`,
which raises TypeError instead of the intended NotAchievedException when
`high` is empty (one-line fix, `len(high)`).

## Round 3: rebase, the staleness bound, and the review items (2026-09-17)

Local branch `pr-flow-hgt-min-rebased` at `d8646651c2`, 17 commits on
upstream master `af8525911b`, not pushed. The pushed `pr-flow-hgt-min`
(`29cfdb6ddc`, 21 commits) is untouched. It was built by cherry-picking; no
rebase, reset or amend. Two intermediate local builds of the same tree
(`b074c1e98c`, `e7bc82096a`) were renumbered only to rewrap one message and
shorten three subjects, and each was checked by an empty `git diff`, so tests
run on them count for `d8646651c2`.

Answering the AP-Review round of 2026-09-16 23:27Z at `29cfdb6ddc` (REQUEST
CHANGES), plus peterbarker's "Just remove = 0.0", rmackay9's HAGL question
and tridge's flowDataValid question. Nothing posted yet.

| new | pushed commits it carries | what changed |
|---|---|---|
| `faf196c7f8` | `7a21adc9b7` | - |
| `5ff8e6d955` | `6cc360296e` | - |
| `7ab39bbf9e` | `8f9cc3def6` | subject shortened |
| `a5fc1f5613` | `1d611f8200` + `da78928a9b` | ROFM at the end of the list; HgtMin units `m`/`0`, @Field gives the unit; no `minHeight` default |
| `55974f2bb8` | `0fe236c37d` | no default |
| `6a7ca4e6d8` | `b663d6a39e` + `c08eaf0e43` | zero and discard folded into one "discard" commit; no defaults |
| `ffd889251e` | `fce7aeb7cd` | no default |
| `4df235f773` | `381f63065f` + `1059db3b0f` + `7719b7e78c` | parameter description fixups folded |
| `3905197b1d` | `d840c82089` | moved after the signature chain |
| `0629e79be5` | `c26e69f3f7` + `3ff05c761a` + `a204212074` | test note and the Replay FLOW_HGT_MIN folded |
| `7dfa4fd76a` | `0374a23d84` | `len(high)` (was a TypeError); AFI comment; master conflict (adjacent new test) resolved keeping both |
| `165624875d` | `8f736ce1f0` | 5 s bound; carry used while fresh too; out of range low time per range finder; `flowFocusAbove` removed |
| `f484800eac` | `5aeccff68e` | landing subtest sits armed on the ground about 12.5 s |
| `abf88bed84` | `8325d8d337` | resolved onto the new gate |
| `024a434b71` | `29cfdb6ddc` | description covers the bound |
| `eebffab54b` | new | RNGFNDx_GNDCLR description names the flow floor |
| `d8646651c2` | new | old-range subtest |

Without the defaults, `a5fc1f5613`, `55974f2bb8`, `6a7ca4e6d8` and
`ffd889251e` do not build alone (measured: `./waf copter` at each commit).
The DAL and the estimators call each other, so no per-subsystem order
compiles. Every other commit builds. Upstream took the same shape for
heightOverride, `5d3e636d71`..`abcacec25f`. Mechanical gate at the tip: 0
findings above note after the subject and wrap fixes.

### The staleness bug, reproduced

SITL on the #34380 stack (the flight needs the height limit removed),
flow-only copter, 8 m analog range finder, CMAC terrain, `FLOW_HGT_MIN` 0.3.
The local StaleHoldProbe climbs to 30 m, flies GUIDED 1 km at bearing 30 deg,
where the ground falls about 13 m, descends to 0.25 m by the EKF, hovers 20 s
and LANDs. Gate as pushed (`29cfdb6ddc`):

| run | first false hold | carried height | last range, age | longest hold above 1 m true | aiding |
|---|---|---|---|---|---|
| r0 | 13.12 m true | 0.27 m | 7.91 m, 265.7 s | 30.9 s | stopped every 5 s |
| r2 | 13.14 m true | 0.24 m | 7.91 m, 266.4 s | 31.3 s | stopped every 5 s |

r1 stalled in SITL and is not counted. LAND after the traverse does not disarm
in this rig. The vehicle sits at 0.56 m true height on the terrain, a SITL
terrain artefact, so near-ground cases were measured on flat ground instead.

### Options (tier 2, one run per cell unless stated)

| gate | traverse | 1 s out of range low injected at the low hover | range finder killed at 0.6 m in LAND (flat) | killed at 5 m, then LAND (flat) |
|---|---|---|---|---|
| as pushed | holds, above | not run | 5 fused below 0.3 m true, then held | 0 fused, held |
| (a) out of range low to start | 0 held above 1 m | 32.8 s hold, aiding stopped every 5 s | 28 fused | 27 fused |
| (b) carried height valid 5 s | 0 held | 0 held | 4 fused, then held | 28 fused |
| (a)+(b) | 0 held | 0 held | 27 fused | 27 fused |
| final (b + carry while fresh + per-sensor time, no `flowFocusAbove`) | 0 held (2 runs) | 0 held | 1 fused, then held | 28 fused |

27-28 matches the pre-hold gate's 27 from round 2. In one final run and one
injection run, 6-7 held rows sit at 3.5-7.3 m true height. Both are the SITL
terrain collision: true height went to -9 m in one sample and the range read
0, so these are not gate faults.

Chosen: (b). (a) alone fails the injection. (a)+(b) differs from (b) only by
refusing starts without out of range low. That loses the hold for a range
finder lost within 5 s of the floor, and for drivers that map a lost return
to out of range high (Benewake, LightWare: derived from the driver source, not
measured on hardware).

### Carry while fresh (new, tier 2)

The 500 ms fresh path compared the last recalled range. That range lags
behind the median of three, so the carried height is now used there too.

- ALT_HOLD touchdown at about 2.5 m/s, subtest rig: without the carry, 4, 4
  and 5 XKF5 flow updates after out of range low (3 runs); with it, 0, 0, 1,
  0, 0 (5 runs).
- Stuck-landing repro, RNGFND1_MIN 0.3 (5 runs): fused below the 0.15 m floor
  2-3 on (b), 2 on final-without-carry, 1-2 with carry. Innovations over
  0.5 rad/s near touchdown: 2 of 5 runs had one on (b), 0 of 5 with carry.

### Tests at the tip (fl34292-test worktree, plus the local serial port switch)

- OpticalFlowFocusHeight 5 of 5 pass:
  - landing subtest: about 12.5 s armed on the ground after out of range
    low, 0 updates;
  - old-range subtest: 83 updates in 8.4 s.
- Mutants (landing subtest measured at `27eb15bf9b`, same gate):
  - bound also applied to out of range low: 74 updates, fail;
  - hold reverted: 118, fail;
  - no 5 s bound: old-range subtest 0 updates, fail (2 of 2).
- FlowHeightMinTerrainPath (AFI low 0, high 62), OpticalFlow, OpticalFlowLimits,
  LoiterNoCompassYaw, OpticalFlowCalibration, Replay (155 s) all pass. Copter,
  plane and Replay build.

Stuck-landing repro (60 m flow climb, LAND, 6 m/s wind at 90, 90 turb 1, 45,
135, 0 deg), final gate on the #34380 stack:

| settings | disarmed, after touchdown | innovations over 0.5 rad/s fused | ground lean |
|---|---|---|---|
| FLOW_HGT_MIN 0.3, RNGFND1_MIN 0.2 | 5 of 5, 2.1-2.2 s | 0 | 1.3-3.8 deg |
| RNGFND1_MIN 0.3 (floor 0.15) | 5 of 5, 2.1 s | 0 | 1.0-5.1 deg |
| no settings | 5 of 5, 2.1 s | 0 | 0.6-4.0 deg |
| RNGFND1_GNDCLR 0.3 (3 runs) | 3 of 3, 2.0-2.1 s | 0 | 2.1-3.4 deg |

### Low hover and hysteresis (tier 2)

Local LowHoverProbe: GUIDED hover for 15 s, `SIM_BARO_RND` 0,
`SIM_SONAR_RND` 0.05 (uniform +/-5 cm). "Fused" counts flow samples, about 153
in the window.

| gate | GNDCLR 0.10 (floor 0.15): 15 / 18 / 20 cm fused | transitions | GNDCLR 0 (floor 0.10): 15 / 18 / 20 cm | aiding stops |
|---|---|---|---|---|
| (b) no band | 54 / 107 / 131 | 38 / 34 / 21 | 129 / 152 / 152 | none |
| (b) + release 2 cm above floor | 14 / 99 / 130 | 7 / 20 / 8 | 135 / 155 / - | 2 at 15 cm, GNDCLR 0.10 |
| (b) + start 2 cm below floor | 69 / 145 / 154 | 26 / 4 / 0 | 151 / 156 / - | none |
| final | 53 / 99 / 144 | 36 / 37 / 14 | 139 / 154 / 153 | none |

Without noise at 18 cm: 156 of 156 fused. Not adopted. A band above the floor
loses aiding in a 15 cm hover. A band below it is the floor moved down on the
way in. The chatter costs samples, not aiding.

### HAGL against the carried range (rmackay9, tier 2 plus source)

Final gate logs, HAGL is `MAX(terrainState - posD, rngOnGnd)`, no AGL KF option.

- LAND at 0.5 m/s, 18 runs over four configurations: the floor is crossed
  +0.07 to +0.12 s after truth by the carried range and +0.07 to +0.10 s by
  HAGL.
- Armed 12 s on the ground, GNDCLR 0.10:
  - HAGL 0.100-0.131, carried 0.06-0.12;
  - with RNGFND1_MIN 0.2, carried -0.006 to 0.071.
- Armed 12 s on the ground, GNDCLR 0: HAGL 0.050-0.081 against floor 0.10,
  carried 0.025-0.068.
- After the LAND runs, HAGL on the ground peaks at 0.131-0.141 across 15 runs.
- With GNDCLR 0.3: HAGL 0.333 and carried 0.31-0.32, floor 0.40.
- Noisy hover, share of rows below the floor:

  | hover | range | HAGL | truth |
  |---|---|---|---|
  | 18 cm, GNDCLR 0.10 | 35% | 0% | 0% |
  | 15 cm, GNDCLR 0.10 | 66% | 58% | 85% |
  | 15 cm, GNDCLR 0 | 11% | 0% | 0% |

- Range as the height source (`EK3_RNG_USE_HGT` 70, or `EK3_SRC1_POSZ` 2):
  HAGL still tracked, 0.174-0.226 in an 18 cm hover and 0.100-0.130 on the
  ground.
- Derived from the source, not measured: with the range stale and nav flow,
  `EstimateTerrainOffset` is not called, so HAGL is the same dead reckoning.
  terrainState is fused from flow only on the `EK3_FLOW_USE=2` path, where
  gating on it would be circular.

Kept the range. The comment at `AP_NavEKF3_OptFlowFusion.cpp:54-57`
overstates both of its reasons: the first applies only to the terrain path,
and the second is true but measured harmless. The reply draft says so and
offers to reword it.

### flowDataValid (tridge, tier 2 plus source)

Set at `:40` from sample arrival (`Measurements.cpp:235`) and forced at `:51`.
Read by:

- `updateFilterStatus()` (horiz_vel, horiz_pos_rel);
- `getHeightControlLimit()` (removed by #34380);
- `getTerrainAltVariance()`.

Setting it false inside the limit does not change fusion. Latched while held:

- horiz_pos_rel true 46 of 152 samples in a 15 cm hover (148 of 148 now);
- with an EKF origin set, "EKF variance: position lost" and an EKF failsafe
  to LAND 12 s in, and EKFCHECK/EKFINAV errors while armed on the ground.

Set only on the discarded sample, the flag flickers (116 of 146). LAND results
are unchanged. Not adopted. Brief for Andy written, no drafted reply.

With the current code horiz_pos_rel stays true through a 12 s ground hold
(105 of 105). The aiding timeout restarts relative aiding every 5 s on sample
arrival. That is pre-existing.

### Measured and rejected (this round)

| change | argument for | measured | why rejected |
|---|---|---|---|
| (a) out of range low required to start the hold | a start needs the sensor to say it is low; suggested by AP-Review | a 1 s spurious out of range low after the traverse held 32.8 s | the sustain rule then carries the stale height indefinitely |
| (a)+(b) | strictest start | same fixes as (b); range finder dead at 0.6 m fused 27 where (b) held | gives up starts without out of range low that are right |
| hysteresis, 2 cm release band above the floor | stops sample-by-sample chatter (AP-Review) | 15 cm hover at the 0.15 floor: 14 of ~153 fused, aiding stopped twice | the log58-style low hover loses aiding |
| hysteresis, 2 cm start band below the floor | less chatter, more flow in a noisy hover | 18 cm: 145 fused against 107, 4 transitions against 34 | it is the floor lowered by 2 cm on the way in |
| gate on HAGL instead of the range | filters range noise (rmackay9) | 18 cm noisy hover: 0% below floor against 35%; on the ground 1-2 cm under the default floor against 3-12 cm | ground margin, same dead reckoning when stale, circular on the terrain path |
| flowDataValid false while held | tridge's reading of `:51` | EKF failsafe in a 15 cm hover and on the ground with an origin set; landings unchanged | status consumers fail with no fusion gain |
| log the hold state | AP-Review note | not built | XKF4.TS is a timeout bitmask; a new XKF5 field changes the format |

### Cross-check against the flights (2026-09-17, tier 3)

On the log67 airframe (GNDCLR 0) the default floor is 0.10 m, the flown
value, so the same samples are gated with no parameter set. The hold is inert
there while the DroneCAN rangefinder reads Good to 1 cm. The staleness bound
must not end a hold sustained by out-of-range-low, or the log65/66
floor-dwell phase re-fuses unfocused flow. Discard has not been flown; before
merge, fly a 15-20 cm hover over 10 s and an armed floor dwell over 5 s, at
default and real GNDCLR. Details in
../../analysis/topics/optflow_horizontal_velocity_lockout.md.

The bound as built satisfies the dwell constraint. The landing subtest sits
armed 12.5 s on the ground with 0 updates, and the mutant that bounds out of
range low too fuses 74.

### Open

- Push: needs a force-push grant for `pr-flow-hgt-min`, pushing
  `pr-flow-hgt-min-rebased` to it. Then post the replies, patch the body
  (Summary "zero motion", the not-flown sentence, the design paragraph) and
  refresh this record's head.
- Replay of log65/66/67 through `d8646651c2` is owed. The logs are on the
  primary machine; REPLAY_LOGS.md row not yet updated.
- Flight: a 15-20 cm hover for over 10 s, and a landing that sits armed on
  the floor for over 5 s, at default and real GNDCLR.
- Wiki page for FLOW_HGT_MIN and the floor: follow-up PR.
- tridge's thread: Andy to answer in person.

### Round 3 pushed and answered (2026-09-17)

Force-pushed `29cfdb6ddc` -> `d8646651c2` (17 commits, rebased onto master
`af8525911b`; GitHub reports it mergeable). PR body: summary says discarded
not zero-motion, testing notes the unflown discard/hold/floor and the 0.10 m
vs 0.15 m floor, description explains the carried height and its 5 s trust.
Posted 12:27Z:

- the round-3 reply to AP-Review, including the correction of the
  2026-09-16 "lost at height starts nothing" claim
  (https://github.com/ArduPilot/ardupilot/pull/34292#issuecomment-5714340890);
- peterbarker's defaults thread (https://github.com/ArduPilot/ardupilot/pull/34292#discussion_r4036797099);
- rmackay9's HAGL question, range kept with measurements and an offer to
  reword the :54-57 comment
  (https://github.com/ArduPilot/ardupilot/pull/34292#issuecomment-5714341564).

tridge's flowDataValid thread is left for Andy's own reply (tridge asked for a
non-AI reply); the facts brief was prepared locally and is not in this repo.

## Round of 2026-09-17 (AP-Review at d8646651c2), answered 2026-09-18

- Blocker, `rngOutOfRangeLowTime_ms` unguarded: guarded with
  `EK3_FEATURE_RANGEFINDER_MEASUREMENTS` (declaration and memset), and the flow
  block's `AP_RANGEFINDER_ENABLED` changed to match. Folded into the commits
  that added them. SITL copter with `define AP_RANGEFINDER_ENABLED 0`: fails at
  the old head with the CI error, builds at the new one.
- `flowFocusRngPosD` across height resets: moved by the reset step in
  `ResetPositionD()`, `ResetHeight()` and the AID_NONE entry (Codex found the
  third). Not cleared as suggested: clearing drops the landing hold on any reset
  while held on the floor. Tier 3 (exact by construction); not flown end to end.
- Out of range high sustain: named in the FLOW_HGT_MIN description, not fixed.
- The :54-57 comment reworded to the reasons in the reply to rmackay9.
- tridge's flowDataValid question: he asked for a non-AI reply. The answer is
  under "what does flowDataValue do??" above; left for Andy to post.
- New commit from the SFD refresh6 stack: flow held off counts as not ready in
  `readyToUseOptFlow()`. FlowFocusHoldAfterLanding fails without it on the
  master base ("Relative aiding restarted while held below the focus floor").
  Restart heights 0.3-0.6 m over 4 runs; the lower bound moved from 0.25 m to
  the 0.15 m floor after a 0.3 m run, and a 2 m upper bound added (Codex).
- 10 of 10 at the new head: OpticalFlowFocusHeight, FlowHeightMinTerrainPath,
  FlowFocusHoldAfterLanding, OpticalFlow, OpticalFlowLocation,
  OpticalFlowLimits, OpticalFlowCalibration, EK3_RNG_USE_HGT,
  LoiterNoCompassYaw, Replay.
