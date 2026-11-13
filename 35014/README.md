# PR #35014 - carry the EKF3 terrain state across a vertical datum reset

Analysis archive for [ArduPilot/ardupilot#35014](https://github.com/ArduPilot/ardupilot/pull/35014).
Opened 2026-11-04, branch `pr-ekf3-terrain-datum-carry` (andyp1per fork),
head `c75fc5a173`, three commits on master `802db19de1` (built locally as
`r1104/33585-carry2`). Split out of #33585 on 2026-11-04 after rmackay9's
dev call review asked why an external nav line sat in a flow PR
(`../33585/README.md`, 2026-11-04); #33585 stacks on it.

Pre-submission /pr-review, 2026-11-04: five Claude reviewers and nine Codex
cold reads on the first build (`c24c4d9155`), REQUEST CHANGES: the
description's flown example does not fail on master, which holds the
height at that switch during takeoff (`bb615f0f93`); numbers disagreed;
the measured-this-flight term had no test. Rebuilt as carry2 with the
motivation rewritten to master's failures, the numbers corrected, the
comments cut, and EK3_TerrainStateFollowsSourceChangeAboveRange (+0.00 m;
+9.98 m on master and with the term removed). Re-review: Codex audit 9 of 9
closed; remaining notes (the pre-arm latch wording, no test for the
external nav line or the other ResetPositionD() callers, the pre-existing
stale external nav velocity in ResetHeight()) are disclosed in the PR.

Superseded 2026-11-04 (later) by `r1104/33585-carry2` after the
pre-submission /pr-review; see "Review fixes" below. The paragraph above
names the branch the review read.

### Head superseded 2026-11-13: GitHub head `547d40894c`

Reordered with the flow height limit fix first, two tests strengthened
and four messages reworded; see "2026-11-13 (later)" at the end.

## What it fixes

The terrain state is a down position in the vehicle's vertical datum, so
a reset that moves the datum has to move it too, or height above ground
steps by the whole reset. Flown with EK3_RNG_USE_HGT=10 (logm2_log4,
4.6.3 SFD, tier 1): the switch off the range finder onto a drifted baro
moved position.z by 3.6 m, height above ground stepped 0.41 to 4.00 m and
the flow innovations saturated. The history of the carry, including the
external nav race and the drift-reset case it gives up, is in
`../33585/README.md` from 2026-09-12.

### Superseded 2026-11-04 by the review: that flight does not fail on master

The flight above is left as written because it is what the carry was
written for. It is not a master failure: the reset was the range finder
to baro switch about 2 s after arming, with takeoff expected set (RFRN
Flags 0x51 from 107.81 to 111.87 s, XKF4.SS bit 11 through 110.5 s; reset
at about 109.9 s), and master since `bb615f0f93` (#34432, 2026-09-18,
an ancestor of `802db19de1`) skips ResetPositionD() on a switch to baro
while takeoff or touchdown is expected (`baroInGndEffect`). Read from the
log and the source, not replayed. On master the carry is reached by a
height timeout reset after a rejected baro glitch, a range finder height
source falling back onto a baro that has stepped away (a drift is
absorbed by calcFiltBaroOffset(), so only a step leaves a datum move), a
height source change above the range, and an external nav start. The
commit message and the PR lead with those.

## Evidence (tier 2, SITL, 2026-11-04 at `c24c4d9155`)

| test | branch | master | mutation |
|---|---|---|---|
| EK3_TerrainStateFollowsHeightReset, in range | +0.00 m on -30.01 m | +30.01 m | - |
| same, range lost 1.6 s before the reset | +0.00 m | - | 500 ms window: +30.01 m |
| EK3_TerrainStateFollowsDatumReset | +0.00 m on -5.98 m | +5.99 m | source recorded before the reset: +5.99 m |
| EK3_TerrainStateHeldOnDriftReset | 2.2 m | 2.4 m | carried unconditionally: 51.8 m |

The external nav commit has no test; 2 of 10 starts took the race in the
2026-09-15 probe (`../33585/data/extnav_start_probe.diff`).

## Review fixes, 2026-11-04 (`r1104/33585-carry2`)

Pre-submission /pr-review of `r1104/33585-carry` (five Claude reviewers,
seven Codex cold reads). No must-fix in the code; the findings were the
motivation above, numbers, comments and an untested term. Rebuilt as
`r1104/33585-carry2` on `802db19de1`:

- `a8a836c318` AP_NavEKF3: carry - code identical to `9377819b2e` but for
  comments (the two 8-line carry comments cut to 3 lines each, the
  imprecise "goes false in the very cycle the source changes" dropped,
  the gndOffsetMeasured comment to one line). Message leads with the
  master failures above, corrects the numbers (2.2 m against 51.8 m; the
  range lost 1-2 s before the reset, not 1.2 s), names the other
  ResetPositionD() callers that now carry (a GPS receiver change with GPS
  height, an external nav position reset with external nav height), and
  states the trade-off below.
- `c5b65443f5` AP_NavEKF3: external nav line - code identical to
  `18577f4ff2`; the message no longer says "always": the vertical
  velocity is taken from external nav in flight when its velocity is in
  use and GPS vertical velocity is not, as it already was when
  selectHeightForFusion() ran first.
- `c75fc5a173` autotest - development-history comments removed, the flown
  example dropped from DatumReset's comment, a no-op RNGFND1_MAX set
  dropped, and a fourth test, below. Message corrected, and says
  HeldOnDrift passes on master by design.

### The gndOffsetMeasured term now has a test

Every reviewer found that no test reached the measured-this-flight term:
HeightReset is decided by gndOffsetValid, DatumReset by prevHgtSource,
HeldOnDrift by the timeout path. New
`EK3_TerrainStateFollowsSourceChangeAboveRange`: GPS copter, 8 m range
finder, ALT_HOLD at 4 m for 5 s, climb to 18 m, wait for
EKF_POS_VERT_AGL clear for 2 s (gndOffsetValid false), step the GPS
altitude 10 m (`SIM_GPS1_GLTCH_Z`, rejected by the GPS height reference
filter's 5-sigma gate, so baro and GPS heights stay 10 m apart), then
MAV_CMD_SET_EKF_SOURCE_SET 2 (GPS height). Height above ground across the
reset:

| build | result |
|---|---|
| carry2 (`844534a1`) | +0.00 m on -9.97, -9.96, -9.97 m resets, 3 of 3 pass |
| master `802db19de1` (`6f423fcb`) | +9.98 m, fails |
| carry2 with gndOffsetMeasured removed from both conditions (`90618d5b`) | +9.98 m, fails |

Same terrain tile (S36E149.DAT, 2 MB) in both worktrees. About 5 s wall
per run.

### Trade-off stated, derived from the source, not measured

With the range finder as the height source (EK3_SRCn_POSZ=2), a fall back
to baro and back now keeps the baro's datum for the rest of the flight:
position.z steps once and height above ground stays right. Master steps
position.z back on return and has height above ground wrong by the
difference while on baro. DatumReset disarms before the range returns, so
the return leg is unmeasured.

### Findings left as notes

- DatumReset may not always exercise the prevHgtSource term: a reset in
  the same cycle as the switch still sees the previous cycle's
  gndOffsetValid (true), so reverting only the reordering may pass about
  1 run in 5 (derived from the source; the single mutation run failed).
- A reset in the update after a range return that follows a gap of more
  than 5 s does not carry (gndOffsetValid is computed before that
  update's terrain fusion); one-update window, not changed.
- The extNav.useVel latch can reset vertical velocity from a stale
  external nav velocity: pre-existing master behaviour in ResetHeight(),
  now reached on every external nav start rather than only when
  selectHeightForFusion() ran first.
- Two-hop handover within 5 s (range finder to baro, then baro to
  external nav) does not carry on the second hop; 3 of 20 SITL starts in
  the 2026-09-15 probe. Not fixed here, since gndOffsetMeasured also
  authorises #33585's fallback above the range.

### Tests at the carry2 head (`c75fc5a173`, copter `844534a1`)

EK3_TerrainStateFollowsSourceChangeAboveRange (3 runs), FollowsHeightReset
(in range +0.00 m on -30.01 m; second leg 1.25 s after the last Good range,
+0.00 m), FollowsDatumReset (+0.01 m on -5.47 m), HeldOnDriftReset (worst
2.3 m), GPSViconSwitching, VisionPosition,
BaroGroundEffectRangefinderSwitch, OpticalFlow and Replay: all pass. Plane,
rover and sub SITL build with no warnings; copter builds with
EK3_FEATURE_OPTFLOW_FUSION 0 and EK3_FEATURE_EXTERNAL_NAV 0. Mechanical
gate clean; check_branch_conventions.py passes.

### Restacks

`r1104/33585-restructure2` (#33585 on carry2, top `079eda8a1e`): range-diff
against `c24c4d9155..17833af182` is identical for five commits; in
`86f0549fc3` (was `2c85876817`) only the gndOffsetMeasured comment
changed, now one comment for both uses. `r1104/34380-2` (#34380 on that,
top `2b5e51a1a8`): all five commits identical. Copter SITL builds at the
top; gates clean on both.

## Owed

- Replay of logm2_log4: a 4.6 log, and per the review not a master
  failure (above), so it no longer motivates the PR; whether master's
  Replay reads it is untested.
- #33585's and #34380's tests on the restacked branches were not re-run
  (only their code is unchanged).

## 2026-11-04 (night): AP-Review at `c75fc5a173`, the flow height limit

AP-Review, REQUEST CHANGES
(https://github.com/ArduPilot/ardupilot/pull/35014#issuecomment-6634896234):
one blocking, one minor.

Blocking, fixed. getHeightControlLimit() skips the terrain state when the
range finder is the height source. On master that skip costs only the
ground clearance at start, as the terrain state with range finder height
never moves. With the carry, a range finder -> baro -> range finder
episode moves the terrain state by the baro's displacement, and the flow
ceiling moves with it. The bot's probe raised a 13 m ceiling to 19.2 m;
with the baro step the other way it falls. The fix subtracts the terrain
state for every source (tier 3: with no fall back the limit changes by
the ground clearance at start, about 0.1 m).

`r1104/33585-carry3` on `c75fc5a173`, not pushed:

- `0b2bbcffb8` AP_NavEKF3: take the terrain state off the flow limit for
  range height (Outputs.cpp, +3 -4).
- `fb335374dd` autotest: EK3_FlowHeightLimitAfterRangeFallback. Flow, range
  finder height, 13 m ceiling; range finder pointed away for 3 s with the
  baro displaced 8 m, given back, then a 40 s full stick climb. Fails at
  7.6 m without the fix, 13.1 m with it (tier 2).

Fold: none. The fix stays on top as its own commit. The carry
(`a8a836c318`) is on the SFD beta, which also has the same skip in
getHeightControlLimit() (beta `AP_NavEKF3_Outputs.cpp:189`), so the beta
probably has this regression too. It is not ported, and no flight has
run the fix. carry3 replaces `r1104/33585-carry2` (`f9f9691d69`,
`6be92a12aa`, the same trees) only to shorten the subject and rewrap the
body that the gate flagged.

Minor, not applied: set gndOffsetMeasured when the carry leaves the range
finder, so a later second source change (baro to GPS or external nav)
still carries. Left out because #33585 reads that latch as "the ground has
been measured this flight" to allow its flat-ground fallback above the
range, and the "Two-hop handover" limit above was left for that reason.
Setting it on leaving the range finder would widen when #33585 falls back.
It needs Andy's decision.

Tests at carry2 `6be92a12aa` (tree identical to carry3), tier 2:
EK3_FlowHeightLimitAfterRangeFallback, EK3_TerrainStateFollowsHeightReset,
FollowsDatumReset, HeldOnDriftReset (worst 2.3 m),
FollowsSourceChangeAboveRange and OpticalFlowLimits pass. Mechanical gate
clean against upstream/master; check_branch_conventions.py passes.

Pushed 2026-11-05 as a fast-forward, `c75fc5a173..fb335374dd` on
`pr-ekf3-terrain-datum-carry` (carry3, the flow height limit fix and its
test). Reply posted:
https://github.com/ArduPilot/ardupilot/pull/35014#issuecomment-6654939868
(the fix, and the minor left as a disclosed limit).

## 2026-11-13: the carry flew (tier 1b)

Replay of the throw quad's seven logs 13-19 with the terrain carry
(`a8a836c318`) removed differs on all of them, by up to 19.5 m on log16,
and as flown is mostly better. The external nav height source fix
(`c5b65443f5`) did not run (no external nav), and the flow limit fix
(`0b2bbcffb8`) could not act, as its only consumer, AC_Avoid's vertical
limit, was off (`AVOID_ENABLE` 0); without it the flow ceiling would
have come within 2.9 m on logs 14, 15 and 19, against 5.9 m with it.
Nothing folded; a rewrite would mean restacking #33585 and #34380.

## 2026-11-13 (later): the review's four items, pushed as `547d40894c`

The full /pr-review of #33585 on 2026-11-13 read these five commits too:
no must-fix, four should-fix, all answered.

1. The series did not bisect: from the carry to its test, a range finder
   to baro to range finder episode with range finder height and flow
   moved the flow ceiling, which `0b2bbcffb8` fixed three commits later.
   That commit now comes first (`b5602b39ca`), its message reworded: on
   master alone it moves the limit by the ground clearance at start
   (tier 3). It builds on its own.
2. ARCH-1: after a fall back and return under range finder height the
   height keeps the baro's datum, and what reads the altitude above home
   or origin carries the part of the baro step the baro offset filter had
   not absorbed: the fence's ALT_MAX in those frames, AUTO and GUIDED
   relative-altitude targets, RTL_ALT, the altitude a GCS shows. The
   carry commit's message and the description now name them. Derived
   from the source, not measured.
3. The range finder exclusion in ResetPositionD() had no test. A second
   leg of EK3_TerrainStateFollowsDatumReset points a 20 m range finder
   away, lets the baro drift 5 m low while it is the height source, gives
   the range finder back and checks height above ground against SIM
   truth at the reset sample. Tier 2: 0.50 m off at a -5.39 m reset;
   with the exclusion removed, 4.87 m off. A first version (3 m drift,
   worst error over the next 3 s) could not tell them apart, 0.52 m
   against 0.86 m: without the exclusion, range height fusion pulls
   height above ground back within about 0.4 s (XKF5 trace, -0.86 m at
   the reset with the vehicle still climbing, near 0 by 0.4 s later). So
   the exclusion prevents a brief step, not the lasting error the review
   derived ("until range height fusion or the 5-10 s timeout reset").
4. EK3_FlowHeightLimitAfterRangeFallback never showed a datum reset had
   happened. It now requires the terrain state to step by 3 m or more at
   the fall back (5.56-6.05 m); with the baro step removed, the climb
   still stopped at 13.1 m, and the test now fails there.

Notes taken, as text: "with or without a flow sensor" is qualified to
builds with optical flow support; the two-hop gap is no longer "within
5 s" but any time while the range finder is still lost (#33585's range
height latch closes it, derived); the switch to AID_NONE writes
position.z from the take-off height directly (Control.cpp), neither
carried nor reported, as on master. Not acted on:
EK3_TerrainStateFollowsDatumReset catches a revert of the reset-before-
prevHgtSource order only about 4 runs in 5; the "ground measured in
flight" comment also latches a range fusion in the 5 s before arming.

Quick review: one Codex cold read of the changes and the five messages,
no findings. Gate and check_branch_conventions.py clean.

Pushed 2026-11-13, force `fb335374dd...547d40894c`. Old to new:
`0b2bbcffb8` `b5602b39ca` (moved first, message), `a8a836c318`
`4c34439be1` (message), `c5b65443f5` `0dda0e1fba`, `c75fc5a173`
`46d5287139` (the leg, message), `fb335374dd` `547d40894c` (the check,
message). No C++ changed; the flown carry commit's message did. The
description was updated the same day. #33585 is restacked on it
(`7b5453dd35`); #34380 still sits on #33585's 2026-11-05 head
`1cf2ecd440` and needs restacking.
