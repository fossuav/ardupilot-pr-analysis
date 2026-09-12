# PR #32553 - Reset terrain offset from baro when ground effect clears (EKF3)

Analysis archive for [ArduPilot/ardupilot#32553](https://github.com/ArduPilot/ardupilot/pull/32553).
Branch `pr-terrain-reset-ge`, base master. No logs committed; numbers
are from a BF_X indoor quad (SmallFastDronev1 board, Mar 2026), cited
inline.

## Status (one line)

Two commits, no autotest; the 1.88 -> 0.3 m result in the PR body is
real but was obtained with the Copter-side HAGL release check (now in
#32472) also in place, the reset alone was measured to drift back, and
the current snapshot form of the reset has not been flown. On the same
vehicle the AGL-KF stack (#33359 + #33507) later achieved the target
without a reset, so the PR may be superseded.

## Review 2026-09-10: the reset targets the wrong state

Not superseded, but not justified either, and the mechanism cannot deliver
a lasting fix. Three findings, all traced from source.

**It is not superseded.** #33359 and #33507 are unmerged, and even on its own
branch #33359 does not remove the `terrainState` term from the rangefinder
height observation - `hgtMea -= terrainState` still runs in both its paths,
and all four of its commits sit behind an option bit that is off by default.
#32472 is merged, but on master `getHAGL()` returns `terrainState -
position.z` unless that same bit is on, so the release check that produced
this PR's good number is itself fed by the state this PR resets. "#32472
carries the check" does not mean "#32472 carries the fix".

**The loop this PR describes is real.** With the rangefinder as height
source, `hgtMea = rng - terrainState` and terrain estimation is inhibited,
so `terrainState` is frozen at `PD + rng` and `velPosObs[5]` reduces to the
contaminated `PD`. The filter is fed its own vertical state as a
measurement and the rangefinder contributes nothing. That is the persistent
1.88 m, and nothing on master or in the AGL-KF stack breaks it.

**But the reset cannot hold.** The same function's range fusion immediately
drags `terrainState` back toward `position.z + rng` - the PD-anchored value
it was escaping. At `EK3_RNG_M_NSE=0.5`, `Popt = 0.25` against `R_RNG =
0.5`, the first gain is 0.33 and the sequence decays as about `3/(n+3)`:
roughly **87% of the reset is undone within about 20 range samples, or one
second at 20 Hz**. It only sticks if the height source switches to
RANGEFINDER inside that window and freezes the state. log203's -0.19 m
drifting to -1.08 m in 25 s is this measured in flight. The PR body's
"normal terrain offset estimation continues afterwards" is not a caveat, it
is the whole story.

So the flown-good log206 number is most likely #32472's release check plus a
prompt source switch, not the reset persisting. That chain is **not
established** and is what this PR most needs.

**The conclusion, and it is a design point rather than a defect list.** If
the premise is "the baro is trustworthy again at ground-effect clear", the
state that is wrong is `PD`, not `terrainState` - which is slaved to `PD +
rng` by its own measurement update whenever the terrain filter runs.
Resetting `PD` at that edge (the #32768-at-arming pattern, or #32972's
protection of the fusion itself) fights the filter far less. The archive's
existing open question - why `aglKfH`, right at 0.85 m while `terrainState`
was 1.88 m, was not the reset source - is still unanswered and belongs in
the PR body.

### Must-fix, if it is kept

1. **It fires on the ground with a propwash-contaminated baro.** The 5 s
   takeoff cap is unconditional while `../32472/` records spool-ups of 3.7
   to 9 s and baro errors of -5 to -11 m at spool-up. The reset then places
   the terrain 5-11 m below a vehicle sitting on the floor, and the only
   constraint applied is a floor on the wrong side. Recovery is by
   innovation rejection, so the bad value persists up to 5 s, during which
   it reaches `getHAGL()`, `ekfGndSpdLimit`, `ekfNavVelGainScaler` and the
   height-source switch.
2. **The edge detector goes stale exactly when it matters.**
   `prevGndEffectActive` is updated only inside the branch that does not run
   while the terrain estimator is inhibited, which is the mid-flight source
   switch case. Ground effect can clear unseen and the reset then fires at
   an arbitrary altitude much later, against a snapshot from a different
   regime.
3. **The falling edge is not confined to near-ground.** `../34362/` measures
   `touchdown_expected` held for 51 s in a stationary 17.9 m hover. Every
   fall of that gate is a terrain reset at cruise altitude from a raw baro
   snapshot, on any vehicle whose rangefinder is in range at hover height.
4. **The commit messages name parameters that do not exist on the base.**
   `TKOFF_GNDEFF_ALT` and `TKOFF_GNDEFF_TMO` are SmallFastDrone-only; the
   base has neither and master calls them `GNDEFF_ALT` / `GNDEFF_TMO`.

Also: `Popt` is set from the rangefinder noise, claiming the baro-derived
reset is more certain than a rangefinder measurement; the reset
re-implements the baro-to-NED mapping and misses the `EK3_OGN_HGT_MASK`
term; it is not gated on `EK3_RNG_USE_HGT > 0`, so it perturbs vehicles
that cannot have the problem; and `prevGndEffectActive` is not reset in
`InitialiseVariables()` while every sibling terrain member is.

### What would settle it

Logs 200-206 are replayable and are the flights that exposed this. Three
Replay runs over log200 and log205 - master, master plus this PR, and master
plus #33359 and #33507 with the option bit set - comparing `XKF5.TOfs` and
`XKF1.PD` against `RFND.Dist`, decide it. Add log206 to check whether the
reset survives past the first second of range fusion. If the AGL-KF run
matches or beats the reset run, close this PR and say so in the thread.

It still merges cleanly onto master despite being 1824 commits behind; the
semantic drift is entirely #32472 landing underneath it.

## The problem

EK3_RNG_USE_HGT > 0: terrainState is seeded from PD + rng during
ground effect, PD is baro-contaminated, and the rangefinder height
observation hgtMea = rng - terrainState then reinforces the wrong PD.
log200 (not committed): hover with baro and rangefinder both reading
~0.96 m, EKF altitude -0.78 m, terrainState mean 1.88 m; the AGL KF
(HAgl) read 0.85 m throughout. The loop's strength: log205, a +/-0.5 m
innovation clamp at the normal K let per-sample PD motion of 0.02 m grow
the terrain offset to 131 m and the altitude to -140 m; the vehicle fell.

## The conclusion and why

Reset terrainState from baro plus rangefinder when the ground-effect
flags clear. Forms flown:

| log | baro used | offset at reset | later |
|---|---|---|---|
| 202 | offset-corrected (baroHgt - baroHgtOffset) | -0.61 m | - |
| 203 | raw baroDataDelayed.hgt | -0.19 m | -1.08 m after 25 s |
| 206 | raw, with the HAGL release check (becb063a13) | 0.3 m | stable |

The offset-corrected form is wrong because baroHgtOffset tracks the
contaminated PD through calcFiltBaroOffset. The PR now uses the raw
baro minus a baroHgtOffset snapshot taken at ground-effect entry, a
third form that maps raw baro into the NED-D frame; it has not been
flown. The second commit gates the reset on baro being the active
height source.

## Key finding: the reset needs the release check to fire, and is one-shot

- log204: with the release check on EKF altitude, ground effect never
  stayed clear (re-armed after every 5 s timeout), so this reset never
  fired. The 0.3 m figure comes from log206, after the HAGL check. A
  reviewer reading "1.88 -> 0.3 m" should know the PR is not
  sufficient on its own for that; #32472 is.
- log203: -0.19 m at the reset, -1.08 m 25 s later. The loop resumes
  as soon as normal terrain estimation continues. "Normal terrain
  offset estimation continues afterwards" in the body understates it.
- The obvious alternative, seeding terrainState from aglKfH (right at
  0.85 m while terrainState was 1.88 m), was not tried. #33359 uses
  aglKfH for the source switch, not for the terrain state. Worth an
  answer in the body.
- Possibly the same signature elsewhere: a ducted quad, log21 (not
  committed), EK3_RNG_USE_HGT 10, ends a 2 min hover 0.85 m below a
  healthy rangefinder after a spool-up in which PD drifted -0.5 m on
  the ground. The XKF5 terrain offset was not examined; hypothesis.

## Relation to the AGL-KF stack

The same vehicle later flew #33359 with `EK3_RNG_USE_HGT=3` (logs
283/285/286, not committed): `XKF5.TOfs` bounded -0.13 to +0.56 m
against +4.1 m in the original crash, AGL KF valid throughout,
`HAglStd` ~0.11 m and flat from 0.2 to 3.8 m, and at a 2.2 m hold the
baro read 0.4 m low while `TOfs` held ~0.2 m. The baro-to-terrain
coupling this PR resets is broken at the switch instead. Caveat: the
baro error exercised there was ~0.4 m, not the ~4 m of the crash case.
If this PR stays open, its description should say why it is still
needed once #33359 lands.

## What is here

```
32553/
  README.md    <- this file
```

No logs committed.

## Reproduce

No SITL reproduction exists. With #32472's SIM_BARO_GEFF_M, a SITL
rangefinder and EK3_RNG_USE_HGT > 0, take off in AltHold and compare
the XKF5 terrain offset against flat-ground truth (it should return to
the on-ground value); the PR body lists an autotest as outstanding.

## Branches and people

- `pr-terrain-reset-ge` - the PR branch (local matches GitHub head
  9031a31bba).
- SmallFastDrone-4.7-beta 6cfd575a1a (the flown form).
- Depends in practice on #32472 (release check); pairs with #33359.
- Review: rmackay9 asked for logs and repro steps; rishabsingh3003
  requested changes.

## SITL reproduction built, and the reset cannot work in it (2026-09-12)

The "Reproduce" section above proposed exactly the right rig and it has now
been built: `SIM_BARO_GEFF_M` (up to N metres of baro under-read on the ground,
decaying linearly to zero at 2 m AGL, applied only while the motors turn -
`AP_Baro_SITL.cpp:70-77`), a SITL range finder, and `EK3_RNG_USE_HGT = 50` with
`RNGFND1_MAX = 10` as in issue #32612.

The missing ingredient was dwell. A normal climbing takeoff barely spends time
below 2 m, so nothing accumulates. Hovering **inside** the band is what
reproduces it, which is also the flown case: a 25 s hover at 1.2 m, then a climb
to ~15 m.

Terrain offset measured above 5 m after the climb out, `GEFF_M` 3.0:

| GNDEFF_ALT | low dwell | without the PR | with the PR |
|---|---|---|---|
| 0.5 (default) | 25 s | 0.292 m mean, 1.20 worst | 0.283 m, 1.19 |
| 2.0 (matches the band) | 3.5 s | 0.091 m, 0.41 | 0.094 m, 0.47 |
| 2.0 (matches the band) | 25 s | 0.304 m, 1.24 | 0.293 m, 1.22 |

0.30 m mean and 1.24 m worst is the same order as the 1.88 m the PR body cites
from flight, so the rig is faithful. **The reset removes none of it.**

### Why, and why no parameter fixes it

`takeoff_expected` is capped at 5 s by `AP_GROUNDEFFECT_TAKEOFF_MAX_MS`.
`GNDEFF_ALT` can only *delay* the window's release, never extend it past that
cap, and the cap is a compile-time constant. On any hover longer than 5 s the
window therefore closes while the vehicle is still inside the error. Measured at
the falling edge: **HAGL 0.82 m, with 1.77 m of the 3.0 m error still present.**
The reset then reconstructs `terrainState` from a baro reading that is still
wrong, writing the contamination in rather than removing it.

Shortening the hover so the window closes above the band leaves no error to
correct (row 2). So there is no parameter choice for which the reset both has
something to fix and is able to fix it.

The premise is not wrong; the window is. `takeoff_expected` is supposed to mean
"baro is untrustworthy", and the 5 s cap breaks that promise for sustained low
flight - which is the indoor case this PR was written for. If the window tracked
the actual error the arithmetic here would work unchanged. That points the fix at
the detector, and overlaps #34362. Note this is the opposite direction from
`PLAN.md` fix 1a, which looked at whether the cap was too *long*.

Gating the reset on range finder AGL instead was considered and rejected: the
vehicle may not have one, and `AP_GroundEffect` already falls back to
height-since-takeoff in that case.

Test committed as `autotest: cover terrain offset recovery from the ground
effect baro error`, on branch `pr-terrain-reset-ge-master`. **It is red on
master and red with the PR**, and the commit message says so - it records the
case, it does not claim a fix.

### The three review findings, measured

The 2026-09-12 dev-call review raised three. All are structurally real; two have
no reachable effect.

- **The clear edge was consumed outside its consumer.** `prevGndEffectActive` was
  updated on every call while `gndEffectJustCleared` was only read inside
  `if (rangeDataToFuse)`. Real, but **measured unreachable**: 0 flow-only entries
  in 2231 calls to `EstimateTerrainOffset()`, including with `EK3_FLOW_USE = 2`.
  The latch is a robustness fix, not a bug fix.
- **No one-shot latch.** Measured 6 clear edges per flight (3 per core), all
  applied: takeoff at t=53.0 s, a *spurious touchdown at t=68.8 s with the
  vehicle at altitude*, and the real landing at t=97.1 s. The mid-flight one is
  the same spurious latching #34362 addresses. Each reset moved `terrainState` by
  **< 0.01 m** in clean SITL, so the repetition is not itself harmful there.
- **The `baroHgtOffset` snapshot was inert.** `calcFiltBaroOffset()` is the only
  writer and is guarded on `activeHgtSource != BARO`
  (`AP_NavEKF3_PosVelFusion.cpp:1363`), while the reset requires `== BARO`, so the
  offset is frozen throughout the window in which the reset can run. Where the
  snapshot and the live value *can* differ - a height datum reset, or a source
  change inside the window - the live value is the one `position.z` is consistent
  with, so the snapshot was the wrong one of the pair. Dropped.

**Correction to a claim made in this work.** The commit that added the latch said
the dropped edge was "the most likely reason it has been hard to observe at all".
That is refuted by the 0-of-2231 measurement above and the commit message needs
fixing before the branch is pushed.

### It does not fix #32612

Worth stating on the PR, since rmackay9 tested it against that issue and reported
the offset remained. #32612 is the rangefinder-to-baro height *datum* offset under
`EK3_RNG_USE_HGT`, reproduced with `SIM_BARO_GLITCH` and no ground effect
involved. This reset only fires on the ground effect clear edge with baro active.
The two do not overlap and the PR has never claimed otherwise in writing.

### Branch note

`pr-terrain-reset-ge` is based on a master from **12 May 2026** and predates
`libraries/AP_GroundEffect` entirely, so none of the current ground effect
framework or `SIM_BARO_GEFF_M` is available on it. The work above is on
`pr-terrain-reset-ge-master`, the three commits cherry-picked onto current
master; they applied cleanly.
