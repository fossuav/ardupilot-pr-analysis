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

### Superseded 2026-09-15 by the four-way SITL A/B

GitHub head `1714711b33` (four commits, with an autotest), local tip
`d0347f265b` with four more unpushed. In the SITL rig the reset alone
changes nothing measurable, the fixed 5 s takeoff window alone changes
little, and the two together bring the terrain offset back to the ground
value. See "Four-way A/B: the reset works only once the takeoff window
tracks the band" at the end. Direction of the PR is an open decision.

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

#### Superseded 2026-09-15 by SITL, in part

In the 2026-09-15 rangefinder rig (tier 2) the reset does hold once PD
has recovered: with the takeoff window prototype, terrain offset and HAGL
stay within about 0.03 m of the ground value for the 20 s above 5 m, and
EKF height is within 0.03 m of truth in every variant. The "87% undone"
arithmetic above holds only while PD is still contaminated. log203's
drift back is what that would produce, but the record does not say
whether PD was still contaminated when that reset fired. The paragraph
stays because it describes the flown case. Numbers in "Without a
rangefinder the PR does nothing" at the end.

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

  *Superseded 2026-09-15 (round 3) by the flown-configuration rig, for
  vehicles that switch height source.* "Frozen throughout the window in
  which the reset can run" holds only while baro is the source for the
  whole window. With `EK3_RNG_USE_HGT > 0` the offset is learnt while the
  rangefinder is the source, from a baro in ground effect (probe: 0 ->
  -2.7 m during spool-up at a 3 m error), and the reset then runs after
  the switch back to baro using that learnt value. The flown form's raw
  baro was avoiding exactly this. Neither form fixes the error in that
  rig, though; see "Flown configuration" at the end. The bullet stays
  because it is right for the baro-source rig it was measured in.

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

## Second automated review round, and the four-way A/B (2026-09-15)

The 2026-09-13 dev-call follow-up (at `1714711b33`) kept REQUEST CHANGES
with four findings at head plus four carried over. Worked on
`pr-terrain-reset-ge-master` in the `pr-32553m` worktree. Four commits
added, unpushed:

| commit | what |
|---|---|
| `c2b6db5831` | autotest: count only samples with the rangefinder Good, measure against the on-ground offset, list the test in `disabled_tests()` |
| `fcdb0edd7d` | AP_NavEKF3: clear the pending reset whenever ground effect is active; comment says one reset per clear edge |
| `be5d764ed8` | AP_NavEKF3: add the `EK3_OGN_HGT_MASK` correction to the baro reconstruction |
| `d0347f265b` | autotest: take the on-ground value whatever the rangefinder status (it reads 0 m, below `RNGFND1_MIN`, on the ground, so it is never Good there) |

### The test metric: the frozen-value finding is right, and fixing it changes nothing

Confirmed on the head log (`1714711b33`, 2026-09-12): 468 samples above
5 m HAGL, only 192 with `RFND.Stat` Good. So the review was right that
most of the old average was a value frozen above `RNGFND1_MAX`.

Restricting to Good samples and subtracting the on-ground offset
(+0.100 m, the `rngOnGnd` clearance, not zero) moves the number from
+0.293 to +0.226 m on that log. It still fails the 0.15 m threshold. The
failure was never an artefact of the metric.

### Four-way A/B: the reset works only once the takeoff window tracks the band

Rig as in the 2026-09-12 section (`SIM_BARO_GEFF_M` 3.0, `RNGFND1_MAX`
10, `EK3_RNG_USE_HGT` 50, `GNDEFF_ALT` 2.0, `GNDEFF_TMO` 0, 25 s hover at
1.2 m, climb to ~12.8 m). Metric: mean and worst terrain offset above 5 m
with the rangefinder Good, relative to the on-ground offset. Threshold
0.15 m. Three runs each, 2026-09-15.

| variant | build | mean (m) | worst (m) |
|---|---|---|---|
| master EKF3 | `dd8cafa3ec` (PR tip, `AP_NavEKF3` at merge base `37ea692edb`) | +0.243, +0.244, +0.239 | 1.16, 1.16, 1.17 |
| PR | `be5d764ed8` | +0.216, +0.241, +0.236 | 1.08, 1.16, 1.16 |
| master EKF3 + window prototype | `8aea365a77` | +0.200, +0.178, +0.172 | 1.02, 0.96, 0.93 |
| PR + window prototype | `b00cbed1f1` | **-0.007, -0.004, -0.009** | **0.32, 0.34, 0.34** |

The prototype is one line in `AP_GroundEffect::update()`: the takeoff
window releases only once `height_m > GNDEFF_ALT`, dropping the
unconditional 5 s release. It is on local branches only and is not a
proposal as written.

What the logs show (run 1 of each, `XKF4.SS` bits 11/12 and `XKF5`):

- master and PR: `takeoff_expected` clears at 55-57 s, 5 s after the
  last on-ground anchor, at XKF5 HAGL 0.6-1.6 m. On the PR the reset
  fires at that edge and steps TOfs +0.31 -> +1.26 m. The low-hover
  offset then averages +0.72 m (master) and +1.03 m (PR).
- master + prototype: the window holds until 81.1 s, when the vehicle
  climbs past 2 m. The low-hover offset halves (+0.35 m) because the baro
  innovation floor is in force for the whole hover, but some
  contamination still gets in through the floored innovation and it
  survives the climb.
- PR + prototype: the window clears at 80.6 s on the climb, the reset
  fires from a baro that is now outside the error band and steps TOfs
  +1.53 -> +0.50 m, and range fusion settles it. The test passes.

So the premise of the PR holds in SITL, and the 2026-09-12 conclusion
("the premise is not wrong; the window is") is now measured rather than
argued: neither change is enough alone, and the pair is. Why the
contamination persists above 5 m on master once the baro is clean was
not traced here.

#### Superseded 2026-09-15 (round 3) for the flown configuration

That rig kept baro as the height source over the whole measured regime
(`EK3_RNG_USE_HGT` 50 of a 10 m range finder, metric above 5 m), so it
never exercised the rangefinder-height path the flights used. In a rig
matching the flown sensor set, with the true path held identical across
variants, neither the PR reset nor the flown reset form changes the height
error, with or without the window. The table above stands as a result for
that rig. See "Flown configuration" at the end.

What the prototype costs, by inspection only, not measured:

- The 5 s cap is the only release when `get_hagl()` fails and
  `height_m` falls back to `-pos_d - takeoff_alt`. That height is built
  from the baro-contaminated PD, so without a rangefinder the window
  could hold for as long as the error lasts, keeping the baro de-weighted.
  A production form would extend the window only on the `height_is_agl`
  path and keep the cap on the fallback.
- A vehicle that hovers below `GNDEFF_ALT` indefinitely keeps
  `takeoff_expected`, and with it the EKF baro floor and the EKF-GSF
  start condition, for the whole hover.
- It changes `AP_GroundEffect`, which is #32472's merged code and
  #34362's open follow-up, not this PR.

#### Superseded 2026-09-15 (later) for vehicles without a rangefinder

The first bullet's remedy, "keep the cap on the fallback", is contradicted
by the flight record for baro-only vehicles, which is the case it was
about. `../analysis/topics/baro_ge_47beta.md` (tier 1, SmallFastDronev1
with `RNGFND1_TYPE=0`): holding the baro protection while the contaminated
EKF altitude says "low" cost about 1.65 m of height error (log208), and
removing that low-altitude protection sucked the vehicle to the floor
(log210). The record's conclusion is that a baro-only vehicle needs the
protection held while low and pays the contamination. Mapping the SFD
4.7-beta re-enable of those flights onto master's 5 s cap is derived from
the source, not measured. The bullet stays because its mechanism (the
fallback height is baro-derived) is right. See "Without a rangefinder the
PR does nothing" at the end.

### Review findings at `1714711b33`, dispositions

| finding | disposition |
|---|---|
| test registered in tests1c and failing | FIXED `c2b6db5831`, in `disabled_tests()` with a reason |
| reset writes the baro error in rather than removing it | CONFIRMED (tier 2, table above); the fix is the window, not the reset |
| test cannot tell the change from master | CONFIRMED (tier 2): 0.216-0.241 against 0.239-0.244 |
| metric measures a frozen value | CONFIRMED and FIXED `c2b6db5831`/`d0347f265b`; verdict unchanged |
| 0.15 m threshold leaves little headroom | REFUTED for the new metric (tier 2): the passing variant reads -0.004 to -0.009 over three runs, and the failing ones 0.17-0.24 |
| latch not cleared when ground effect returns | FIXED `fcdb0edd7d`, by inspection; inert in this rig (no reactivation before the next range sample) |
| stale-range reset runs first and leaves the latch set | NOT CHANGED: the baro reset then applies on the next range cycle, which is what the premise asks for (inspection) |
| edges noticed late while `inhibitGndState` | OPEN: while the range finder is the height source the terrain state is frozen and `baroHgtOffset` tracks PD, so a late reset is close to a no-op (inspection, not measured) |
| "one reset per ground effect episode" comment | FIXED `fcdb0edd7d` |
| `EK3_OGN_HGT_MASK` term missing from the reconstruction | FIXED `be5d764ed8`, by inspection; default mask 0 unaffected, not exercised in SITL |
| reset not logged or counted | OPEN, optional |
| Popt handling differs from the stale-range reset | OPEN, consistency note only |
| commit messages and description stale | OPEN, needs a rewrite: `018befc712` says `baroHgtOffset` tracks the contaminated PD (refuted 2026-09-12) and names `TKOFF_GNDEFF_ALT`/`TKOFF_GNDEFF_TMO` (master: `GNDEFF_ALT`/`GNDEFF_TMO`); `9c866c162b` says the live offset "would re-import the contaminated PD", which `82f3c95a3b` reverses. `82f3c95a3b` already carries the corrected "not the reason it was hard to observe" wording. Squashing the four AP_NavEKF3 commits under one corrected message is the tidy form. |

### For the SmallFastDrone fork

Nothing measurable today. `SmallFastDrone-4.7.1-beta` carries the older
snapshot form (`9c866c162b`) and the same 5 s
`AP_GROUNDEFFECT_TAKEOFF_MAX_MS` cap, so in this rig it sits in the
"PR" row: no better than master. The flight number in the PR body
(1.88 -> 0.3 m, log206) came with #32472's release check and was not
shown to persist; the Replay runs proposed above are still not done.

## Without a rangefinder the PR does nothing (2026-09-15, later)

Asked to re-examine the work above for drones **without** a rangefinder,
which is what the PR was said to be for. The record and the code both say
the PR was written for, flown on, and can only act on a vehicle **with**
one.

### What the record says it is for

- The flights. `../analysis/topics/baro_ge_47beta.md` (tier 1): vehicle
  SmallFastDronev1, BF_X quad, **optical flow plus a VL53L1X rangefinder**,
  DPS310 baro, `EK3_RNG_USE_HGT=3`, indoor ALT_HOLD/LOITER on
  V4.7.0-beta2-SFD. log200 (the motivating hover) had baro and rangefinder
  both at about 0.96 m, EKF altitude -0.78 m and terrainState 1.88 m. The
  reset flew in log202 (-0.61 m, offset-corrected baro), log203 (-0.19 m,
  raw baro, drifting to -1.08 m in 25 s) and log206 (0.3 m, with the HAGL
  release check `becb063a13`). log204 never fired it; log205 diverged under
  a different change.
- The PR body. "With `EK3_RNG_USE_HGT > 0`", the formula uses the
  rangefinder, "Tested ... optical flow + VL53L1X rangefinder", and its own
  ticked test plan item: "Verify no impact on vehicles without rangefinder
  (no rangefinder data -> reset doesn't fire)".
- "Tested across 22 indoor flights" counts the campaign (logs 188-209),
  not the reset: it was only in the firmware from log202, and logs 207
  (`EK3_RNG_USE_HGT=-1`), 208 and 209 (`RNGFND1_TYPE=0`) cannot exercise
  it.
- What was wrong in flight (tier 1): **terrainState**, at 1.88 m against
  about 0, through `hgtMea = rng - terrainState` feeding PD. The AGL KF
  read 0.85 m throughout.
- The record's own no-rangefinder data (logs 196-198 with
  `EK3_RNG_USE_HGT=-1`, logs 208-210 with `RNGFND1_TYPE=0`) is about **PD**
  contamination during and after ground effect. The fixes it names are the
  ResetHeight suppression, the negative `EK3_GND_EFF_DZ` noise floor and
  the pre-takeoff baro reference, which are #32972, plus holding the
  low-altitude protection (log210). None of them is this PR.

Record inconsistency, not edited: `../analysis/logs/log201.md` and
`log202.md` describe a different pair of flights (the 4.6.3 TCAL/yaw
series) from the log201/log202 in the baro GE table above. Both are
SmallFastDronev1 with a rangefinder. `REPLAY_INDEX.md` has no fingerprint
for log200-log206, so which files these are is unresolved.

### The code at `d0347f265b`, without a rangefinder

All derived from the source, not measured.

| step | without a rangefinder |
|---|---|
| `rangeDataToFuse` | only set by `storedRange.recall()`, which `readRangeFinder()` never fills with no sensor: always false |
| `EstimateTerrainOffset()` call | needs `rangeDataToFuse`, or flow data with `EK3_FLOW_USE=2`. Copter defaults to 1, so on a Copter it is **never called** |
| edge latch (`82f3c95a3b`, `fcdb0edd7d`) | not reached on Copter; with `EK3_FLOW_USE=2` (Plane default) it can set, and nothing ever consumes it |
| the reset itself | inside `if (rangeDataToFuse)` and built from `rangeDataDelayed.rng`: **cannot run** |
| `EK3_OGN_HGT_MASK` term (`be5d764ed8`) | inside the reset: inert |
| `getHAGL()` | `gndOffsetValid` needs a terrain update in the last 5 s: false (without the AGL KF, which also needs a rangefinder) |
| `AP_GroundEffect` height | `get_hagl()` fails, so `height_m = -pos_d - takeoff_alt`, built from the baro-contaminated PD |
| use of terrainState | none for height: no range height observation and no valid HAGL |

A vehicle with a rangefinder fitted but excluded from height
(`EK3_RNG_USE_HGT=-1`, like Lucid v2) does run the reset, but it has no
`rng - terrainState` loop to break. There HAGL is `terrainState - PD`
with terrainState tracking `PD + rng`, which comes out as about `rng`
whatever PD's error. Inspection only.

### Which conclusions above survive

| conclusion | vehicles with a rangefinder | without one |
|---|---|---|
| "the reset cannot work in the rig" (2026-09-12) | refined: not alone; it works with the window held | not applicable - it cannot run at all |
| PR + window prototype takes the error to about -0.01 m | **survives**, and the re-analysis below shows it is HAGL, not just the metric | not applicable |
| "the prototype removes the only release without a rangefinder; keep the cap on the fallback" | n/a | mechanism right, remedy **reversed** by log208/log210 (superseded in place above) |
| `fcdb0edd7d` clear the latch when ground effect returns | survives (tier 3) | inert |
| `be5d764ed8` origin height term | survives (tier 3) | inert |
| `c2b6db5831`/`d0347f265b` count only range-valid samples | survives: the test needs a rangefinder because the reset does | not applicable - no no-rangefinder test of this PR is possible |

### Re-analysis of the same runs: HAGL, not just the metric

The terrain offset metric could have read well while PD stayed
contaminated, which would make HAGL wrong instead. Checked from the saved
2026-09-15 logs, above 5 m with range Good, against SITL truth. No new runs.

| variant | EKF height - truth (m) | XKF5.HAGL - RFND.Dist (m) |
|---|---|---|
| master EKF3 (2 runs) | +0.040, +0.038 | +0.368, +0.368 |
| PR (2 runs) | +0.036, +0.039 | +0.347, +0.371 |
| master + window (2 runs) | +0.031, +0.030 | +0.318, +0.297 |
| PR + window (2 runs) | +0.030, +0.033 | **+0.117, +0.125** |

HAGL against RFND carries the 0.10 m ground clearance on every row. PD has
recovered by 5 m in every variant. What stays wrong is terrainState and
hence HAGL, by about 0.27 m above the clearance, until the reset runs
behind a correct window. That supports the PR's own premise, on a
rangefinder vehicle, in SITL.

### What this means for the PR

For drones without a rangefinder the PR is a no-op, and no change to it
can help them: there is no terrain state in use to correct. Their problem
is PD, and the work for it is #32972 plus low-hover ground effect
protection in `AP_GroundEffect` that holds without a rangefinder (log210).

For rangefinder vehicles the 2026-09-15 A/B stands, with two caveats from
the record. The June 2026 campaign (logs 283-286, AGL KF with
`EK3_RNG_USE_HGT=3`, tier 1) bounded TOfs to -0.13..+0.56 m with no reset,
though against a 0.4 m baro error rather than 4 m. And the flight improvement
has never been replayed.

#### Superseded 2026-09-15 (round 3)

"The 2026-09-15 A/B stands" for rangefinder vehicles is withdrawn for the
configuration they fly. See "Flown configuration" at the end.

## Flown configuration: the reset does not reach the error (2026-09-15, round 3)

The PR is for rangefinder vehicles. The earlier rigs kept baro as the
height source over the regime they measured. This one flies the sensor
set the flights used, with the vehicle's true path held identical across
variants. Local branches `r3-*` in the `pr-32553m` worktree; probe and rig
commits are marked not for the PR.

### The flown configuration, from the record

log200-log206 were not found (see "Log hunt"). The nearest flight of the
same campaign, log224 (same airframe, one firmware later), has these
parameters (tier 1):

- `EK3_RNG_USE_HGT` 3 with `RNGFND1_MAX` 30. That puts rangefinder height
  below 0.63 m and baro above 0.9 m, measured on HAGL.
- `EK3_OPTIONS` 24, `EK3_GND_EFF_DZ` -8.
- `TKOFF_GNDEFF_ALT` 0.5, `TKOFF_GNDEFF_TMO` 3.
- Flow velocity with baro POSZ.

The flown firmware decided the switch on `aglKfH` and trusted the terrain
whenever the AGL KF was valid (the #33359 commits). Master does neither.

### What master does with it (tier 2 unless marked)

- **When the rangefinder is the source.** Copter sets `terrainHgtStable`
  only while taking off or landing. `AP_AHRS` forwards the flag on change
  only, so a takeoff in a mode with no user takeoff leaves the cores at
  their initial true for the whole flight. The probe reads 1 throughout a
  STABILIZE takeoff.
- **Where the ground effect error goes.** While the rangefinder is the
  height source, terrainState stays right (0.11 m). `calcFiltBaroOffset()`
  instead learns `baroHgtOffset` from the ground effect baro: 0 ->
  -2.67 m on spool-up at a 3 m error. On the switch to baro,
  `ResetPositionD()` uses that offset and PD steps.

### Rig

- **Sensors:** SITL flow, analog rangefinder with `RNGFND1_MAX` 60,
  `EK3_RNG_USE_HGT` 3.
  - 60 m, not the flown 30 m: master switches on terrainState - PD rather
    than `aglKfH`, so the threshold has to clear a 0.9 m hover with margin.
    That gives rangefinder height below 1.26 m and baro above 1.8 m.
  - `EK3_OPTIONS` 8, which is master's AGL KF bit.
- **Ground effect:** `SIM_BARO_GEFF_M` 2, 3 or 4, with `GNDEFF_ALT` 2 to
  match the SITL band and `GNDEFF_TMO` 3 as flown. `EK3_GND_EFF_DZ` is left
  at default, because master has no negative noise floor.
- **Profile:** STABILIZE, with throttle closed on the simulated rangefinder
  in the test script, so the true path does not depend on the estimate.
  0.9 m hover for 13 s, two forward-back translations above
  `EK3_RNG_USE_SPD` (baro is the source during them), 20 s still hover,
  climb to 4 m, 12 s hold.
- **Not captured:**
  - The SITL error decays linearly to zero at 2 m, so a 0.9 m hover sees
    55% of it. In flight the baro was right at 0.96 m.
  - The master base lacks the flown firmware's AGL KF switch, terrain trust,
    noise floor and pre-takeoff baro reference.

### Result: EKF height minus truth (m), still hover mean and at 4 m after climb-out

Ground effect error 2 / 3 / 4 m, one run each, 2026-09-15.

| variant | still hover | at 4 m | reset fired |
|---|---|---|---|
| master EKF3 and ground effect | -0.25 / -0.21 / -0.23 | +0.44 / +0.93 / +1.25 | - |
| PR (`be5d764ed8` EKF3) | -0.25 / -0.17 / -0.16 | +0.46 / +0.89 / +1.38 | never |
| PR + window held while HAGL is available | -0.35 / -0.38 / -0.31 | +0.33 / +0.76 / +1.26 | once, at climb-out |
| window alone | -0.35 / -0.36 / -0.37 | +0.38 / +0.75 / +1.22 | - |
| flown reset form (`018befc712`, raw baro) | -0.24 / -0.22 / -0.17 | +0.50 / +0.85 / +1.32 | never |
| flown form + window (log206 analogue) | -0.35 / -0.35 / -0.37 | +0.42 / +0.76 / +1.17 | once, at climb-out |
| no offset learning in ground effect | -0.22 / (run failed) / -0.18 | +0.54 / (run failed) / +1.28 | - |
| no offset learning in ground effect + window | **-1.22 / -1.72 / -2.35** | **-0.00 / -0.01 / -0.01** | - |

In the last row terrainState is +1.21 / +1.70 / +2.34 m in the still hover,
with the rangefinder as the source 97% of the time.

What it shows:

1. **At a steady 0.9 m nothing self-reinforces**, on master or with either
   reset. The error drifts by 0.03 m or less over 18 s.
2. **The reproducible error is the climb-out step,** and it scales with the
   ground effect error: +0.44 / +0.93 / +1.25 m. It sits in PD through
   `baroHgtOffset`. terrainState follows PD, so HAGL is right and TOfs
   mirrors the error.
3. **Without the window neither reset form ever fires.** The 5 s release
   falls while the rangefinder is the source and `EstimateTerrainOffset()`
   is inhibited. The vehicle was rangefinder-sourced from before arming, so
   `prevGndEffectActive` never saw the flag set. With the window both fire
   once at climb-out and move nothing: the error is not in terrainState.
4. **Stopping offset learning in ground effect, with the window, removes the
   climb-out error and produces the log200 signature instead.** During the
   baro-sourced translations the ground effect baro enters PD, terrainState
   is rebuilt from PD, and it freezes wrong when the rangefinder takes over
   again. The flown failure and the climb-out step are two outlets of one
   contamination. A fix has to keep the ground effect baro out of
   `baroHgtOffset` and out of PD (and so terrainState) while the vehicle is
   in the band.
5. **Closed-loop runs show the consequence, but cannot rank variants.** In
   ALT_HOLD the vehicle reacts to its estimate, so paths diverge run to run.
   Floor strikes occurred with master, PR and PR + window. One master run
   ended with terrainState +3.0 m and EKF -2.9 m on the floor.

### Log hunt

708 logs across the support trees were fingerprinted from their headers:
firmware string, git hash, board, parameters and Replay records. None
carries `721f9986` or `becb063a` on this airframe; the one `becb063a` log
is a different airframe with no rangefinder. **log200-log206 are not on
this machine, so Replay cannot answer anything here.**

The nearest replayable flights are log224 (`STAT_BOOTCNT` 260, the flown
`EK3_RNG_USE_HGT` 3) and log225 (261, `EK3_RNG_USE_HGT` -1). Both are
`INS_ACC_ID` 3408138 on V4.7.0-beta3-SFD `fae5c01d`. Replaying log224
through master, the PR and the offset change is the next evidence that
exists. Not done here.

### What this means for the PR

In the configuration the flights used, SITL gives the terrain reset
nothing to do. The contamination enters through `baroHgtOffset` and PD,
and neither reset form touches either. log206's good result came on
firmware with the AGL KF switch, terrain trust and noise floor, which this
base lacks. Whether the reset contributed there can only be settled by the
flight, which is missing. The June campaign's AGL KF route (#33359, logs
283-286) bounded TOfs with no reset.

## Posted findings, and Replay of log224 (2026-09-15, round 4)

### Posted

Comment 5681318760 on the PR, 2026-09-15 13:51Z. It was built from the
round 3 draft with two changes: the four local commit hashes removed,
since they are unpushed, and a caveat added that each table cell is one run
and the master-based rig lacks the AGL KF height switch and the noise
floor. The PR was not marked draft; that was the user's choice.

### log224 by itself (tier 1)

Fingerprint: `INS_ACC_ID` 3408138, `STAT_BOOTCNT` 260, V4.7.0-beta3-SFD
`fae5c01d`, `LOG_REPLAY` 1. It holds two flights.

Flight 1 (armed 567.2 s): LOITER on flow, `EK3_RNG_USE_HGT` 3,
`RNGFND1_MAX` 30, `EK3_GND_EFF_DZ` -8, `TKOFF_GNDEFF_ALT` 0.5 and `_TMO` 3.

- **On the ground, armed, before liftoff (6.4 s):** takeoff_expected is
  set. PD drifts to +0.19 m, below ground, with the baro within 0.1 m.
- **Liftoff at about 574 s:** once airborne the baro reads high, +3.6 to
  +5.3 m against a rangefinder of 0.3-2.3 m. The SITL model under-reads, so
  the flight's error has the opposite sign.
- **About 9 s airborne:** takeoff_expected clears and re-latches twice.
  EKF height (PD from arm) ranges from 1.75 m below to 0.6 m above the
  rangefinder; at 578.4 s `XKF5.HAGL` is 2.02 m against a 1.17 m
  rangefinder.
- **Motor emergency stop at 583.6 s, then on the ground from 584 s:** baro
  +0.1 to +0.6 m, rangefinder 0 (below its minimum), AGL KF 0.06 m. EKF
  height reads +3.06 m and `XKF5.HAGL` 2.7 m for 19 s, until disarm. An EKF
  variance failsafe triggers at 589.4 s.

So the flight shows the log200 signature, EKF height wrong by 3 m while
baro and rangefinder agree. It shows it on the ground after landing rather
than in a hover. There is no clean climb-out step.

Flight 2 (armed 687.3 s) followed parameter changes that set
`EK3_RNG_USE_HGT` -1 and GPS sources, so it is not the PR's configuration.
It ends with the same post-landing error, 2.6 m.

### Which state the flight points at (tier 3, from logged values)

- **The observation was offset.** After landing, `XKF3.IPD` reads -0.03 to
  -0.31 m while EKF height and baro disagree by 3 m. At 600 s that puts the
  fused height observation at about 2.8 m, 2.5 m above a baro reading
  0.3 m. There are two candidates.
- **Candidate 1, the SITL mechanism:** `baroHgtOffset`.
- **Candidate 2, this firmware's pre-takeoff synthetic observation.** With
  takeoff_expected set, a negative `EK3_GND_EFF_DZ` and `time_flying_ms`
  zero (all true again after the landing), it fuses `meaHgtAtTakeOff`.
  That is the baro filtered while takeoff_expected is clear. In its last
  clear window (580.7-582.4 s) the airborne baro read 1.8-3.0 m, against
  the 2.8 m reference IPD implies at 600 s.
- **Flight 2 favours candidate 2 for the post-landing error.** It had no
  rangefinder height source and so no offset learnt across a source switch,
  and it ends the same way. Neither state is logged, so neither candidate is
  established.
- **The same exposure may remain in #32972.** Its current head holds PD
  (`posDownGndEffectRef`, captured while takeoff_expected is clear and
  dropped past a 5 m innovation) rather than a filtered baro. A PD captured
  in the air from a contaminated estimate would anchor a landing the same
  way. Derived from the source, not measured; it belongs to #32972, and this
  flight is the evidence.

### Replay: cannot answer on this log

**The build.** Replay was built at `fae5c01d` with `--debug --ekf-single`
and `AP_INERTIALSENSOR_LOW_NOISE=1`.

- The SmallFastDronev1 hwdef defines that flag, and the SFD EKF3 uses it
  for the initial gyro bias uncertainty and limit. Without it the replay
  diverged from the first sample, reaching 31 deg of yaw difference by
  arming.
- `--ekf-single` needed two simulator-only cast fixes to compile at that
  commit.

**The ground phase replays.** Over the 560 s before flight 1: yaw within
0.2 deg, mag offsets within 1 mG, PD equal to 0.01 m. `check_replay` still
counts mismatches, because the build is not bit-exact across ARM and x86.

**The flight does not.** Within 80 ms of the rangefinder coming into range
at 574 s, the flight fused 0.17 m where the replay fused the 0.05 m
on-ground substitute. At 574.07 s replay HAGL is 1.65 m against the flight's
0.16 m.

| flight 1 segment | PD replay minus flight, mean | max |
|---|---|---|
| airborne | 0.80 m | 1.59 m |
| on the ground after the stop | 1.09 m | 1.43 m |

**The cause is the logger.** It was saturated from arming. `DSF.Dp` is 0 at
567.2 s and 72449 by 584.3 s, with the free-buffer minimum at 0. `RFRH`
frame records fall from 200/s on the ground to 125/s in flight 1, with gaps
of 20-95 ms. 37% of the DAL frames in the air are missing. The high-rate
rate and PID logging is the likely load (734k `PIDA` records).

**What was not run.**

- The variants (PR reset form, offset freeze), because a baseline that does
  not reproduce the flight gives them nothing to be measured against.
- The takeoff window change could not be tested in Replay in any case.
  Replay re-feeds the recorded takeoff and touchdown flags, and this flight
  recorded both, with takeoff_expected re-latching twice in the air in
  flight 1.
- log225 (`STAT_BOOTCNT` 261) is a 7 s boot with no flight, so there is no
  control.

### What this means

- **The SITL mechanism is untested by flight.** The `baroHgtOffset` account
  is neither confirmed nor refuted: log224 cannot test it.
- **A #32972 mechanism may explain the flight's error at least as well.**
  The pre-takeoff synthetic height reference, which the SITL rig did not
  contain, is at least as good an account of the post-landing error.
- **Nothing in log224 argues for the terrain reset.** Neither candidate
  involves terrainState.
- **A flight that can settle it needs clean logging.** `LOG_REPLAY` with
  the high-rate PID and RATE log bits off, so `DSF.Dp` stays 0 in the air,
  flown in the flown configuration: `EK3_RNG_USE_HGT` 3, low hover, climb,
  landing.

### Pushed 2026-09-15 as `1aca58844c`

The branch was squashed into two commits on the same base `37ea692edb` and
force-pushed over `1714711b33`: `f5fb7d164d` (AP_NavEKF3, folding
`018befc712`, `9c866c162b`, `82f3c95a3b`, `fcdb0edd7d` and `be5d764ed8`)
and `1aca58844c` (autotest, folding `1714711b33`, `c2b6db5831` and
`d0347f265b`). The tree is byte-identical to `d0347f265b`, so every number
above taken on the local commits holds for the pushed head. The commit
messages drop the claim that the live `baroHgtOffset` is frozen while the
reset can run and the old `TKOFF_GNDEFF_*` names, and say that the
flown-config rig puts the error in the offset. The PR body was replaced the
same day with the template sections and a status list pointing at the
13:51Z findings comment; the old body's "22 indoor flights", raw-baro
formula, non-ASCII arrows and tool attribution are gone. `AIReview` was
already on.

## SIM_TERRAIN 0 (2026-09-18)

A terrain tile for home left in the run directory by an earlier test puts the
SITL ground 0.55 m below home, so the preconditions failed by test order. With
SIM_TERRAIN 0 the test reaches its measurement every run and fails for its
designed reason: +0.211, +0.225 m at `3216b0579e`. Not yet taken up: the
2026-09-17 review's suggestion to assert on HAGL against the range finder
during the dwell, where it measured a 1.8x RMS separation (0.22 vs 0.40 m).
