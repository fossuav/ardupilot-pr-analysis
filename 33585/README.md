# PR #33585 - Keep optical flow nav alive above the rangefinder range (EKF3)

Analysis archive for [ArduPilot/ardupilot#33585](https://github.com/ArduPilot/ardupilot/pull/33585).
Branch `pr-optflow-flat-ground` (andyp1per fork). PR head `e18c7d6fc3`
(pushed 2026-09-15, the rebased stack below); before that `76f3428d1a`
(pushed 2026-09-12). Base `master`. Stacked on #33478 (`../33478/`).
#34360, which the PR head also carries, merged on 2026-09-15; the local
branch `pr-optflow-flat-ground-rebased` is the same work on current master
and current #33478 - see the 2026-09-15 section at the end.

### Head superseded 2026-09-29: rebased onto master, head `6a1200d267`

Rebased onto master on 2026-09-29; the GitHub head is now `6a1200d267`.
Nothing has been re-measured at this head. Every number below keeps the
commit it was taken on, and any head named above is left as written
because it is the code those numbers came from.

### Head superseded 2026-11-04: GitHub head `6dcb4f2b2d`, split locally

The GitHub head on 2026-11-04 is `6dcb4f2b2d`, four commits on master
`802db19de1`, no longer stacked on #33478. Bit 5 is gone: the fallback is
the default, gated on height, and anchored to terrain data where it
reaches the EKF. After rmackay9's dev call review that day the datum
carry was split onto its own branch and the anchored height moved into
FuseOptFlow(), local only; see "2026-11-04: rmackay9's dev call review"
at the end.

### Head superseded 2026-11-13: GitHub head `833e3b3276`

Force-pushed 2026-11-13 from `1cf2ecd440`: two EKF commits on top for
range finder height, review fixes folded into earlier commits, and test
work; see "2026-11-13: range finder height" at the end. Numbers above
keep the heads they were taken on.

### Head superseded 2026-11-13 (later): GitHub head `e6600ca1f1`

Force-pushed again the same day from `833e3b3276`: peterbarker's
rename folded in, and the flow drift warning moved to arming under
11 m; see "2026-11-13 (later)" at the end.

### Head superseded 2026-11-13 (night): GitHub head `7b5453dd35`

Restacked on #35014's review fixes, its own commits unchanged; see
"2026-11-13 (night)" at the end.

## Status (one line)

`EK3_OPTIONS` bit 5 (`OptflowAssumeFlatGnd`) holds `horiz_pos_rel` above the
rangefinder ceiling instead of tripping a spurious EKF failsafe. Replay
validated on a real flight before submission (see
the private analysis repo); the authorisation guard
around it was rewritten twice after review and each term now has an autotest
leg confirmed to fail without it.

## The problem and the fix

Both are in the analysis topic, not here:
the private analysis repo carries the log308
diagnosis, the mechanism, the Replay A/B showing the velocity estimate is
bit-identical with and without the option, and the full history of how the
guard grew from `option && !hgtTimeout` to its current form and why. Read that
first - this file only carries what is specific to the PR.

## Review, 2026-09-04 to 09-05

Maintainer review (tridge, automated pass) raised five points. Two were defects
in the guard, both real:

- `gndHgtValidTime_ms != 0` is a permanent latch, cleared only at full EKF init,
  so one valid terrain height authorises the assumption for the rest of the
  boot.
- `!hgtTimeout` is satisfied by the synthetic constant-zero height fused at
  14 Hz when `EK3_SRCn_POSZ = NONE`, so both halves pass with no real height
  source.

A self-review pass (four Claude reviewers over the commits plus a whole-diff
dev-call reader, three Codex cold reads with no framing) then found the first
fix was itself wrong, and found two more defects. Details in the analysis topic
and in `../33478/` for the stacked half.

### Refuted findings

Kept because a later reader will otherwise re-raise them.

- **`status.flags.dead_reckoning` was not extended alongside `horiz_pos_rel`.**
  Raised by two reviewers, one with a copter-with-drag-fusion scenario ending in
  a DeadReckon RTL at the ceiling. It cannot fire: `dead_reckoning`
  (`Control.cpp:817`) requires `doingWindRelNav`, and `horiz_pos_rel`
  (`Control.cpp:798`) takes `|| doingWindRelNav` as well, so in every state
  where `flatGroundAssumed()` can change `horiz_pos_rel`, `doingWindRelNav` is
  false and `dead_reckoning` is false regardless. Bit 5 cannot move that flag.
- **"Use parameter index 12."** Correct against `upstream/master`, where
  `var_info2` ends at 11 and 12-14 are free. Wrong once the sibling open PRs are
  counted - see `../33478/`.
- **"Legs 3-5 of the autotest never ran."** Inferred from
  `buildlogs/ArduCopter-EK3_OptflowAssumeFlatGnd.txt`, which was a stale
  transcript of the two-leg predecessor. Those legs had run; the negative-check
  runs failed with assertion strings that exist only in them. The underlying
  concern was still right for a different reason - the legs were timing races -
  and that is fixed.

### The autotest could have passed with the feature compiled out

`delay_sim_time()` calls `get_sim_time(drain_mav=False)` and never drains the
link; `assert_receive_message` does a blocking `recv_match` that returns the
*oldest* queued message. So the wait for the terrain offset to go stale could be
sampled from before it went stale. Every wait is now on `EKF_POS_VERT_AGL`,
which is `gndOffsetValid` published (`AP_AHRS.cpp:2225`), and each leg checks
the flag set as well as clear so that losing flow aiding cannot satisfy the
negative half.

### Negative checks (the test's own qualification)

Each guard term removed in turn, other terms left in place, binary rebuilt, test
re-run:

| term removed | leg that fails |
|---|---|
| `gndOffsetMeasured` (reverted to `gndHgtValidTime_ms != 0`) | "The assumption does not carry over from an earlier flight" |
| `activeHgtSource != SourceZ::NONE` | "With no height source and no terrain data the assumption is refused" |
| `OptflowAssumeFlatGnd` from the `writeTerrainData` gate | "Terrain data is preferred and does not need bit 2" (leg replaced 2026-09-07, below) |
| the height check on the terrain term (`flowScaleHgtUsable()`) | "With no height source terrain data does not authorise it either" |
| the option itself, end to end | "The failsafe it prevents: LOITER survives the ceiling" - bit clear goes to LAND on the way up, bit set holds at 21 m |

All three confirmed on 2026-09-05. A leg asserting the bit 3 + bit 5
combination was
written and then removed: it could not have failed differently from the
bit-5-only leg, because `flatGroundAssumed()` does not reference the AGL KF and
both 5 s windows expire together. Its measurement is in the analysis topic.

## Two test defects found by running it, not reading it (2026-09-05)

Both found while re-running the whole SmallFastDrone suite after a refresh, and
neither had been caught by any review or development pass on this PR. Pushed as
`46653b7436` and `f266fd0fd9`.

- **The test never had terrain data.** `EK3_OptflowAssumeFlatGnd` needs
  `install_terrain_handlers_context()`; without it the run failed for missing
  terrain rather than for the behaviour under test, which also invalidated an
  earlier attempt to reproduce the failure on master. A test that fails for the
  wrong reason reads as a red gate for the right one.
- **It waited for the terrain offset to go stale while still on the ground.**
  The "does not carry over" leg called `wait_terrain_offset_stale()` before
  takeoff. On the ground the offset does not go stale, so the wait could only
  time out; the leg's real subject is the in-flight rangefinder-ceiling case,
  which the private analysis repo establishes and
  which the wait was not testing.

Neither touches EKF3 code, so no number in this record moves. Worth recording
because the guard here has been rewritten twice against review and both defects
were in the test that qualifies it, not in the guard.

## Maintainer review 2026-09-05 (rmackay9) and the restored terrain gate

rmackay9, who wrote bit 2 (`OptflowMayUseTerrainAlt`, #30718), asked why the
vehicle would assume flat ground when it could use the terrain database, and
suggested combining the two option bits into one "do your best" mode.

He was right that the description should not have been telling users to set
two bits. That was a dropped hunk, not a design: `NavEKF3::writeTerrainData()`
forwarded terrain data to the cores only under bit 2, so with bit 5 alone
`terrain_srtm_alt_valid` could never become true and the flat assumption was
the only path even where the database had coverage. The SmallFastDrone branch
widens that gate to either option; it was lost when the change was split for
upstream. Restored in `a874302eee`, so bit 5 alone is now
terrain-where-covered with flat ground as the fallback, and the "set bit 2 as
well" line is gone.

Why terrain does not simply replace the assumption, which is what he was
asking: `AP_Terrain::update()` only calls `ahrs.writeTerrainAMSL()` when
`ahrs.get_location()` succeeds. A GPS-denied vehicle never has terrain data
written at all, whatever the option bits say, so indoors there is nothing to
prefer. Derived from the source and confirmed by the autotest leg below.

**Open, with him:** whether to merge the bits outright. Merging changes bit
2's contract - today bit 2 over terrain without database coverage drops
relative
position and the vehicle failsafes; merged it would navigate on a terrain
offset frozen at the takeoff point, which over rising ground scales the flow
velocity in the direction that makes the vehicle drift rather than stop. Left
as his call since it is his option. Asked in
<https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5552536715>.

### A correction, and what it cost

Predicted that widening the gate could not affect the autotest, on the grounds
that `get_location()` fails without GPS. It does not: in `AID_RELATIVE` it
works from the EKF origin plus the relative position, so terrain data does
reach the cores. SITL has terrain data, and the terrain path then held
`EKF_POS_HORIZ_REL` valid through the legs meant to prove the flat-ground path
was refused - a green test measuring the wrong thing.

Two consequences, both now in the test. `TERRAIN_ENABLE = 0` is set for the
legs that test the flat-ground assumption, matching how the log308 Replay
isolated it. And the terrain path, which this file previously had no way to
cover, gets a leg of its own: with only bit 5 set and `EK3_SRC1_POSZ = None`,
`flatGroundAssumed()` is false, so relative position staying valid can only
come from terrain altitude reaching the core.

### Which archived numbers this moved

Checked before applying, per the repo rules.

- The log308 Replay in the private analysis repo was
  run with `TERRAIN_ENABLE=0`, so no terrain data was written to the DAL and
  the widened gate cannot change it. Numbers stand as recorded.
- The bit 3 + bit 5 flow-scale table in the same file was measured on
  2026-09-04 on the branch **before** the gate was widened, with `EK3_OPTIONS
  = 40` and terrain left at its default. The gate was still bit-2-only then,
  so no terrain data reached the core and the table is of the flat-ground
  path. On the current code the same configuration would take the terrain
  path where there is coverage. The numbers are not restated here; they
  belong to that code state.

## Stacked with #32232 the leg failed, and the leg was the thing at fault (2026-09-07)

On a tree carrying both this PR and #32232 (ground clearance fusion,
`rishabsingh3003:ek3_gnd_clear`, head `a628150687`) the "does not carry over"
leg failed. A handoff attributed that to `gndOffsetMeasured` re-latching inside
the 5 s freshness window on a pre-takeoff measurement, and concluded #32232
needed no change.

First measurement, on the leg as it then stood (it killed the range finder with
`RNGFND1_MIN` above `RNGFND1_MAX`), Copter SITL, `EK3_IMU_MASK=1`:

| #32232 substitution | this PR's guard | leg |
|---|---|---|
| as published (`!takeOffDetected`) | as committed | fails - `terrain_alt` set all flight |
| as published | `inFlight && takeOffDetected` | fails - same reason |
| bounded with `!inFlight` | as committed | fails - `terrain_alt` clears at 48.7 s, `horiz_pos_rel` stays set |
| bounded with `!inFlight` | `inFlight && takeOffDetected` | passes |

The first two rows refuted the handoff: with #32232 as published the flag is
held up by `gndOffsetValid`, not by `flatGroundAssumed()`, so no change to this
PR could have made the leg pass. `XKF4.SS` bit 6 never clears in the second
flight and bit 10 (`takeoff_detected`) never sets, because #32232 substitutes
`rngOnGnd` for a range finder reading `OutOfRangeLow` while `!takeOffDetected`,
and with the sensor dead `detectTakeoff()` has only its gyro criterion left,
which a SITL climb does not reach. That is a real defect in #32232 and it is
recorded in `../32232/`.

### The correction: the leg could not tell the two cases apart

`RNGFND1_MIN` above `RNGFND1_MAX` does not deny the EKF range data, it makes
every reading `OutOfRangeLow` - which is still data on any build that
substitutes a ground clearance for a short reading. So the leg could not
distinguish "this flight measured no terrain offset" from "this flight measured
its own ground clearance", and rows three and four above are not about carrying
anything over from an earlier flight at all: they are about whether the guard
swallows a substituted ground-clearance reading taken during *this* flight.

`kill_rangefinder()` now points the sensor away from `ROTATION_PITCH_270`
instead, which `readRangeFinder()` skips outright whatever the backend reports.
With that, the whole test passes on this branch alone **and** on the stack with
#32232 as published, unmodified (both measured 2026-09-07). The interaction was
a test artefact; #32232's own defect stands, but this test no longer sees it and
that PR needs its own coverage.

### The guard change that was tried and withdrawn

`gndOffsetMeasured` was briefly changed to require the terrain offset to have
been updated while `inFlight && takeOffDetected`. Withdrawn for two reasons,
either sufficient:

- `libraries/AP_NavEKF3/CLAUDE.md` already records both flags as unreliable.
  The fly-forward branch of `detectFlight()` sets `inFlight` only from GPS
  ground speed, so on a GPS-denied fly-forward vehicle it never sets;
  `takeOffDetected` is written only from `writeOptFlowMeas()`.
- It is unqualifiable on master. A leg was written to fail without it - arm,
  kill the range finder on the ground, climb - and it passed either way. On a
  copter the only window in which the two guards differ is the sub-second one
  between the last ground-clearance reading and the vehicle climbing above its
  ground clearance, which no autotest can hit reliably.

### What did land

`!inFlight` -> `onGround` for the flight scoping, which is the portable term the
playbook names ("the one term that means the same thing on every vehicle") and
is identical on Copter, where `onGround` is `!motorsArmed` and `inFlight` latches
until disarm. On a GPS-denied fly-forward vehicle the old form could never
authorise the assumption at all. Negative check re-run on the new leg: with the
scoping removed entirely the carry-over leg fails, so the term is still
qualified.

And the leg now asserts its own precondition. It took off, landed, killed the
range finder, took off again and asserted the flag was clear - but never
established there was an authorised assumption to carry over, its only positive
check being at 4 m where `gndOffsetValid` satisfies `horiz_pos_rel` on its own.
It now kills the range finder in the air, waits for the offset to go stale and
asserts the flag is still set, which only `flatGroundAssumed()` can do, before
landing. `EKF_CONST_POS_MODE` is checked clear at the negative assertion so that
losing flow aiding cannot be what satisfies it.

## The self-correcting argument is refuted (2026-09-07)

The design rationale in the private analysis repo held that
a wrong flat-ground assumption is self-correcting - "the innovations grow, fusion
stops, and the flag drops". It is not. SITL A/B with `RNGFND1_SCALING` doubled, so
the terrain estimator places the ground twice as far below the vehicle: a scale
height 1.99x too large gives a reported speed 2.14x too large, the flow innovation
ratio peaks at 0.13 of its rejection threshold, and `horiz_pos_rel` stays valid
throughout. The above-range leg, where `flatGroundAssumed()` is the only term
holding the flag, biases speed ~20% on a datum 5.7 m too deep. Control run with the
scaling correct: height ratio 1.00, speed ratio 1.00.

That matters for the terrain-forwarding finding below: there is no backstop behind
the authorisation. Whatever reaches `heightAboveGndEst` is believed. Full table,
harness and both logs: `data/`, superseded section in the topic.

## Review fold, 2026-09-07

`/pr-review` at `e630acb0be`, single-sourced (Codex unavailable on this account:
its default model 404s). The mechanical gate was clean; the findings that
mattered came from the PR thread, which tridge's 2026-09-06 pass had left at
REQUEST CHANGES with four open items.

**The blocker, fixed.** `optflow_gnd_offset` is a plain OR, so once this PR
forwarded terrain data for bit 5 the `terrain_srtm_alt_valid` term satisfied it
with none of `flatGroundAssumed()`'s checks - measured by tridge at a flow scale
height of 0.10 m against a true 20.26 m AGL, flag valid throughout. The height
test is now a helper, `flowScaleHgtUsable()`, and the terrain term carries it
where the data arrives for bit 5:

```cpp
const bool terrainAltUsable = terrain_srtm_alt_valid &&
                              (option_is_enabled(OptflowMayUseTerrainAlt) || flowScaleHgtUsable());
```

Bit 2 is untouched, and with a working height source the change is a no-op. Note
his numbers prove the missing authorisation, not the sign bug in the same
expression: with `EK3_SRC1_POSZ=None` the vertical state is pinned near zero, so
`terrain_srtm_alt - pd` and `(-pd) - terrain_srtm_alt` both clamp to `rngOnGnd`.
The sign is separately wrong (error = 2x `terrain_srtm_alt`, hence invisible at
CMAC where the origin sits on the terrain) and it is master's, not this PR's.

**The leg that covered the forwarding inverted.** "Terrain data is preferred and
does not need bit 2" asserted `horiz_pos_rel` *valid* with no height source -
exactly the state the fix now refuses - so it is replaced by its negative, which
fails without the new gate.

**What is now uncovered, deliberately.** After the fix no leg can isolate the
bit-5 terrain forwarding on a GPS-denied vehicle: terrain writes need
`get_location()`, which needs `horiz_pos_rel`, which needs the range finder or
the assumption itself, and `gndOffsetMeasured` latches from the on-ground reading
inside the same 5 s window that terrain validity expires in. Every configuration
that separates the two also fails the height check. The forwarding's remaining
effect is on the flow scale height above the range, which no log field exposes.
Recorded rather than papered over with a leg that would pass for another reason.

Also fixed in the fold: the `@Description` claimed the option does not raise the
optical flow altitude limit, which is false wherever terrain data is available
(`getHeightControlLimit()` returns no limit on `terrain_srtm_alt_valid`); the
carry-over leg's `EKF_CONST_POS_MODE` guard was vacuous, since that flag is ANDed
with `filterHealthy` just as `horiz_pos_rel` is, and now needs `EKF_ATTITUDE` as
the health witness; "landing" scopes nothing, disarming does; and the commit
series is two commits, the three autotest ones folded into one with the
cross-PR bookkeeping dropped.

**Still open, prose only:** the PR body carries the `get_location()` inference
this record already corrected, and the bit-3/bit-5 table in the topic was measured
before `writeTerrainData()` was widened - the body cites it without that
condition.

## Second review round, 2026-09-07

Re-ran the pipeline at `0d996214f9`. Three reviewers plus a partial Codex pass (its
account hit a usage limit mid-pool; only the autotest verification finished, which
confirmed five of six claims and adjusted the sixth). The round found more than the
first, because the first round's fix had moved the problem rather than closed it.

**The height check was at the reporting layer only.** `optflow_gnd_offset` was
gated, but `FuseOptFlow` still took `terrain_srtm_alt - pd` as the flow scale height
with no check, so the EKF went on fusing flow on a height the status flags had just
judged unusable. The same gate now sits on the fusion path.

**A height source switch orphans the frozen offset.** `ResetPositionD()`
(`AP_NavEKF3_PosVelFusion.cpp:260`) moves `stateStruct.position.z` and leaves
`terrainState` behind, and it is called on any in-flight source change (`:1561`) -
including the `EK3_RNG_USE_HGT` switch, which happens at the ceiling, exactly where
this option takes over. `ResetHeight()` does handle the terrain state, so the two
reset paths disagreed. The state is now carried with the datum, conditioned on the
offset being meaningful.

That condition comes from `../32768/`, not from reasoning: it measured carrying the
state across a datum move at 0.000 m post-arm excursion against 0.648 m for master,
and then measured that carrying it *unconditionally* is worse than not, because with
nothing fusing into it the state is only the floor a previous reset left. The
condition here (`gndOffsetValid || gndOffsetMeasured`) is that rule plus the case
this PR creates, where the offset is deliberately stale but was measured this flight.

**The measurement I could not get.** Two SITL probes aimed at the datum step both
failed to isolate it - the first because `SIM_BARO_DRIFT` made ALT_HOLD chase the
drifting estimate (`wait_altitude(relative=True)` reported 12-16 m at a true 4.6 m),
the second because the open-loop STABILIZE climb overshot the range finder's height
band, so no in-flight switch carried an accumulated disagreement. The two runs came
out within 0.02 m of each other: **no measured difference**. The defect is certain
from the source - `terrainState` and `position.z` are D coordinates in one datum and
only one of them moves - and the fix's shape is backed by #32768, but the magnitude
in flight is unmeasured here and the PR text must not imply otherwise.

**Two legs added.** A bit-2 control leg, which is both the positive witness that
terrain data is reaching the core (a cleared flag is also what no terrain looks like,
and counting served TERRAIN_REQUESTs cannot tell them apart because SITL reads the
tile from `terrain/*.DAT`) and the first coverage bit 2 has ever had in the tree. And
a LOITER pair, which is the only leg that sees what the option is for: `ekf_check`
takes no action in a mode that does not require position, so every earlier leg
asserted the flag without the user-visible half. With the bit clear the vehicle goes
to LAND during the climb, before the ceiling; with it set it holds at 21 m.

Every negative assertion now carries `EKF_ATTITUDE` and `EKF_CONST_POS_MODE`
witnesses, since both `EKF_POS_HORIZ_REL` and `EKF_POS_VERT_AGL` are ANDed with
`filterHealthy` and a cleared flag otherwise proves nothing. Codex noted the residual
gap: `EKF_CONST_POS_MODE` witnesses the aiding mode, not `flowDataValid`, so the
optical flow sensor's own health is checked alongside it - as close as MAVLink gets.

### A fold that had to be undone

The round-two fixes were staged with `git add libraries/AP_NavEKF3/`, which swept
the untracked `CLAUDE.md` and `CLAUDE.md.bak` playbooks into the EKF commit - 1,864
lines of them. The mechanical gate's `stray-file` check caught it; a `git rm
--cached` fixup folded the addition away so the files never appear in the PR's
history, and the working copies were checksummed before and after. The rebase also
refused to start until the untracked copies were moved aside, because the commit it
was replaying adds those same paths. The root playbook already warns against
directory-scoped `git add`; this is what it warns about.

**The current head has not been through a review pass.** Rounds one and two ran at
`e630acb0be` and `0d996214f9`; everything since is fixes and folds. `pr_review.py
state` records `23dfeccb54` only so a re-run can diff against it - a third round is
outstanding, and the Codex EKF verification is worth re-running when that account's
limit resets.

## Third review round, 2026-09-08 - two of my own fixes withdrawn

Three reviewers plus a full Codex cold pass (its quota had reset, so all three
tasks completed this time). Verdict REQUEST CHANGES, and most of what it found was
in the round-one and round-two fixes rather than in the original change.

**The `ResetPositionD` terrain carry is withdrawn.** Four independent lines against
it, one of them decisive and verified here: when the height source switches *to* the
range finder, `hgtMea = MAX(rng*c.z, rngOnGnd) - terrainState`
(`AP_NavEKF3_PosVelFusion.cpp:1501-1508`), so `ResetPositionD(-hgtMea)` re-anchors
`position.z` *within* the datum - the reset exists to make `terrainState -
position.z == rng`. Carrying `terrainState` destroys that identity and injects a
non-zero first innovation. Beyond that it fired on every vehicle with
`EK3_RNG_USE_HGT > 0` or `POSZ=2` with no flow sensor at all, reaching `getHAGL()`,
the control limits and the switch hysteresis; it was a *partial* datum fix
(`posDownAtTakeoff`, `posDownAtLastMagReset` and the beacon offsets stay behind);
and two probes failed to measure it. The defect it addressed is real and stands
recorded for a PR of its own, which will need to tell a datum move from a re-anchor
and handle `ResetHeight()` as well.

**The `FuseOptFlow` height gate is withdrawn too**, which reverses round two's
must-fix 1. The argument for it was that gating the report while the fusion used the
same height was half a fix. The argument against, from the cold read and confirmed
here: when `flowScaleHgtUsable()` is false the fallback at `OptFlowFusion.cpp:320`
is `terrainState - pd`, differenced against the *same* pinned state, so the gate
swaps one meaningless height for another - while silently changing bit 2, whose flag
path the same commit deliberately exempts. It protected nothing and broke a promise.

With both out, the EKF commit ships no behaviour change to a vehicle with
`EK3_OPTIONS = 0`, which is what the deferred split was for on the estimator side.
What remains of that question is only whether bit 5 should forward terrain data at
all.

**Autotest.** The flow-liveness witness added in round two was inert twice over: it
sampled a fresh `SYS_STATUS` *after* the helper had already force-disarmed, and
`AP_OpticalFlow_SITL` publishes every cycle regardless of AGL, so it could not fail.
The replacement is `EKF_VELOCITY_HORIZ` from the same captured flags word - in this
configuration `someHorizRefData` reduces to `doingFlowNav`, because `AID_RELATIVE`
sets `posTimeout`/`velTimeout` and neither airspeed nor drag fusion runs, so that
one bit witnesses live flow aiding and filter health at the instant asserted. The
LOITER leg now pins which failsafe fired (`wait_statustext("EKF variance: position
lost")`) instead of accepting any arrival in LAND. The bit-2 positive leg runs
before the negative terrain leg, because a cold tile cache is the CI case and the
cold-cache outcome must not be the passing outcome.

**A comment of mine that was wrong about this machine.** I had written that counting
served `TERRAIN_REQUEST`s cannot witness terrain because SITL reads the tile from
`terrain/*.DAT`. That directory is gitignored - the files here are artifacts of
earlier local runs. On CI the cache is cold and the requests do go over MAVLink,
rate-limited to one per 2 s, which the test does not wait for. The comment is
corrected; the timing dependency is still untested.

Still open: the commit messages describe both withdrawn changes and need rewriting
before any push; `gndOffsetMeasured` can be authorised by a measurement up to 5 s
before arming, which also weakens the mid-air re-arm protection the text advertises;
the option is inert with the range finder as height source, documented nowhere; and
`status.flags.dead_reckoning` still reads bare `gndOffsetValid`.

## Rounds five and six, 2026-09-08 - two more of my own fixes withdrawn

**The SRTM fail-low guard is withdrawn.** Round five added a guard so that where
`(-pd) - terrain_srtm_alt` came out below `rngOnGnd` the terrain estimator's height
would be kept instead. Round six killed it on two counts. The premise was false: the
old expression could go negative too, wherever the ground sits further below the
origin than the vehicle sits above it, so the collapse to `rngOnGnd` is pre-existing
and the sign fix only moves which geometry triggers it. And the guard fell through
to a `terrainState` that the enclosing `if (!gndOffsetValid && ...)` has already
declared stale. The commit message kept describing the guard for two more rounds -
see below.

**The statustext claim flipped three times.** Round four said ekf_check's text was
suppressed and could not discriminate; round five adopted it as a witness; round six
measured the actual margin and found a passing run cleared the 30 s boot throttle by
only about 8 s. The LOITER leg now samples the flag and the altitude while the cause
is still true, rather than waiting for a text that may or may not be sent.

## Seventh review round, 2026-09-09

Three reviewers plus a Codex cold pass. The must-fix was in a commit message, not in
code, and it was the one round six had already been told about.

**`535cfca48f` still described the withdrawn guard.** Its third paragraph claimed the
corrected expression "can also go negative, which the old one could not", and that a
disagreeing database height "no longer collapses the scale height to the on-ground
range". Neither is true of the diff: the `MAX(..., rngOnGnd)` is untouched and the
old expression could go negative as well. Rewritten to say the collapse is
pre-existing and not closed, and that falling back to `terrainState` is the obvious
repair and does not work.

**The carry commit was wrong about its own flight.** Cross-checking against
the private analysis repo rather than against memory: the message said the core
"recovered only when the terrain estimator's 5 second re-anchor fired". The re-anchor
did fire, at 114.9 s, and it repaired the terrain state - `RI` back to 0.00 - but not
the core, whose velocity had already diverged. That core dead reckoned to 20.66 m/s
and 331 m from a vehicle hovering indoors until an aiding reset at 147.8 s put the
altitude demand 3 m above it at 0.77 throttle. The message now says so. The reset
itself is now named: with `EK3_RNG_USE_HGT=10` the height source left the range
finder shortly after takeoff, and the switch to a drifted baro is what moved
`position.z`. `activeHgtSource` holds the *new* source at the reset site
(`AP_NavEKF3_PosVelFusion.cpp:1569-1572` assigns `prevHgtSource` before the call), so
that flight's switch does fire the carry and a switch *into* the range finder is
excluded - which is the round-three objection the reinstated commit was built to
answer.

**A real code defect: the altitude limit did not carry the option's height check.**
`getHeightControlLimit()` returned "no limit" on bare `terrain_srtm_alt_valid`
(`AP_NavEKF3_Outputs.cpp:98`). Before this PR that could only be bit 2, but the bit-5
commit forwards terrain data as well, so setting bit 5 with `EK3_SRC1_POSZ=0` and
terrain coverage removed the `AC_Avoid` altitude cap in exactly the configuration
where `flatGroundAssumed()` and `terrainAltUsable` both refuse to hold the flag: the
vehicle climbs higher than it would have without the option, then fails safe anyway.
The predicate `updateFilterStatus()` already computed is now a member,
`terrainAltUsable()`, used in both places. Bit 2 short circuits first, so it is
byte-identical.

Alongside it, `terrain_srtm_alt_ms` is never initialised and nothing guarded it, so
`terrain_srtm_alt_valid` read true for the first 5 s after boot with
`terrain_srtm_alt` still zero - the same zero-timestamp trap that `gndHgtValidTime_ms`
was explicitly guarded against one expression away. Guarded now.

**The option is inert with the range finder as the height source, and now says so.**
`EstimateTerrainOffset()` sets `inhibitGndState` and returns without touching
`gndHgtValidTime_ms` whenever `activeHgtSource == RANGEFINDER`
(`AP_NavEKF3_OptFlowFusion.cpp:111`), so `gndOffsetMeasured` never latches under
`EK3_SRC1_POSZ=2` - the indoor rangefinder-primary configuration the option exists
for. Round three listed this as "documented nowhere"; it is now in the `@Description`.
Making the latch cover that case is a design change with no measurement behind it and
is not in this round.

*Superseded 2026-11-13: the latch now covers it. A step whose range height
passed its innovation check counts as measuring the ground, and the range
finder does not take the height back while flat ground is engaged; Replay
of a customer flight and SITL behind it are in "2026-11-13: range finder
height" at the end. The paragraph is left as written because it is what
was true at that round's head.*

**The speedup fix from round six was wrong, and measurement is what said so.**
Round six slowed the simulation to 10x for the open-loop climb, on the theory that
`get_altitude` sampling was too coarse for a 6 m window. Measured across the run: 1.36
m per sample at speedup 100, 1.49 m at speedup 10. Slowing the sim made it slightly
*worse*, because `poll_message` blocks on the next `SYSTEM_TIME` and so samples once
per *simulated* second whatever the speedup. The step between samples is the climb
rate. Replaced with rc3 1560 against a 4-7 m window, which also keeps the leg inside
the 8 m range where the offset is actually measured.

**The failsafe leg has an un-throttled witness after all.** `"EKF Failsafe: changed
to %s Mode"` (`ArduCopter/ekf_check.cpp:215`) is sent whenever the failsafe acts and
is not subject to the 30 s "EKF variance" throttle. The leg now waits on it with
`check_context`, which ties the mode change to this failsafe rather than to any other
arrival in LAND.

**The set that is knowingly not fixed.** Round three had already enumerated it:
`ResetPositionD()` also leaves `posDownAtTakeoff` and `posDownAtLastMagReset` behind,
and both are differenced against `position.z` - at 1.5 m for the takeoff and landing
detector (`AP_NavEKF3_VehicleStatus.cpp:389,399`) and 0.5 m for the mag reset
hysteresis (`AP_NavEKF3_MagFusion.cpp:76`). The 3.6 m move in the flight above would
have tripped both. They are left alone and the commit message now says why: there is
a flight behind the terrain state and none behind those, and they reach mag and land
detection rather than flow scaling.

**What the Codex cold pass added.** It confirmed both defects found here
independently, naming the local fixups as the corrections - useful, because it was
reading the committed snapshots and reached the same two conclusions from a cold
start. Three findings were new:

- The terrain height is not per-core. AP_AHRS subtracts the one public origin
(AP_AHRS.cpp:1998) and hands the same figure to every core, which then
differences it against its own position.z. Lanes aligned against different
receivers under EK3_AFFINITY can hold different origin altitudes, so the figure
is only right for a core whose origin matches the public one. The message
disclosed an origin caveat but framed it as ekfGpsRefHgt drift alone; it now
names the mechanism.

- canDeadReckon (AP_NavEKF3_Measurements.cpp:660) is gndOffsetValid ||
flatGroundAssumed(), while the status expression is gndOffsetValid ||
terrainAltUsable() || flatGroundAssumed(). The commit message claimed it gained
"the same condition". It did not - the terrain leg is missing, which with bit 0
set means a vehicle that can dead reckon on terrain still admits the first
reacquired GPS fix without the alignment checks. Left as code, because adding
the term would change what bit 2 does with bit 0, and round three withdrew a
fix for exactly that. The mismatch is upstream's and predates this PR; the
message now says so.

- The glitch case is a regression, not just an unhandled case. Where a range
finder glitch drives position.z away and the baro fallback corrects it, master
leaves terrainState alone and the height above ground comes out right, where
this carries the glitch into the ground and stays wrong until the 5 s re-
anchor. The message called that "the case this does not handle"; it now says
plainly that it is worse than master there, bounded at 5 s, and traded against
a datum case that has a flight behind it and no such bound.

Codex also raised the 32-bit millisecond wrap against the zero-timestamp trap.
Unsigned subtraction handles the wrap correctly for a vehicle that has ever
received terrain; the failure is only for one that never has, where
terrain_srtm_alt_ms stays 0 and imuSampleTime_ms wraps back under 5000. The !=
0 guard covers both that and the boot window.

**Still not covered by a test.** Reaching the carry needs a height source change,
which needs `EK3_RNG_USE_HGT` set, and needs the baro to disagree with the range
finder or the reset delta is zero and the leg passes either way. Two earlier probes
were confounded and measured no difference. `SIM_BARO_DRIFT` is the lever that has
not been tried.

### The test found the fix did not fire in its own motivating case (2026-09-09)

Writing EK3_TerrainStateFollowsDatumReset took three attempts, and each failure was
information rather than a flaky test.

1. A hover then climb with EK3_RNG_USE_HGT never switched height source at all. The
switch also needs terrainHgtStable, and Copter::update_ekf_terrain_height_stable()
only reports that while flightmode->is_taking_off() or is_landing(), where
is_taking_off() is a commanded takeoff rather than a stick climb. The only reset that
route reached was on the way down, into the range finder, which is the excluded case -
and the test flagged it as a failure, because height above ground is meant to snap onto
the range there.

2. Switching by EK3_SRC1_POSZ=2 and killing the range finder produced a reset of 0.09 m.
calcFiltBaroOffset() (AP_NavEKF3_Measurements.cpp:806) tracks the baro against the
current height source at 10% per sample whenever the baro is not the source, so the
fallback is seamless by design and a SIM_BARO_DRIFT ramp is absorbed entirely. Only a
step outruns it, so SIM_BARO_GLITCH is the lever - the two earlier probes recorded as
"confounded" were measuring a mechanism that works.

3. With an 8 m glitch the reset was 5.48 m and the carry did not fire. XKF4.SS bit 6
shows gndOffsetValid going false at 52.24 s, one sample before the reset at 52.34 s, and
XKF5.TOfs never moves while HAGL steps 3.03 to 8.51 m on a vehicle sitting still at
2.95 m. The cause is the bit-5 dead zone again: EstimateTerrainOffset() is inhibited
while the range finder is the height source, so gndHgtValidTime_ms is stale and
gndOffsetValid is held up by the activeHgtSource == RANGEFINDER term alone - which is
exactly the term that disappears in the cycle the source changes. gndOffsetMeasured is
false for the same reason. The carry was inert in the configuration the commit cites as
its motivation.

The round-seven EKF reviewer looked straight at this and cleared it, writing that "on a
RANGEFINDER->BARO switch the stale gndOffsetValid is true from the previous cycle's
rangefinder source, which is the value you want". That is wrong, and only the log shows
it: SelectFlowFusion() does run after SelectVelPosFusion() in the cycle, but the source
has already changed by then, so the value the reset reads on the next cycle is the
recomputed false one. An ordering argument that reads as airtight went the other way
when measured.

Fixed by recording prevHgtSource after ResetPositionD() rather than before, and
accepting prevHgtSource == RANGEFINDER as a reason to carry. gndOffsetMeasured is
deliberately untouched, so bit 5 still requires an offset it measured itself and its
documented dead zone stands. Measured on the same flight profile: datum 5.48 m with
height above ground moving 5.48 m before the fix, datum 5.97 m with height above ground
moving 0.00 m after.

## The sign fix is measured, and extracted to its own PR (2026-09-10)

`535cfca48f` closed with "Not measured", and named what was wanted: "the
flight with terrain enabled over sloping ground that the flat-ground work has
been asking for". That measurement exists now, and the fix is moving out of
this PR.

Reaching the branch needs `gndOffsetValid` false with terrain still valid,
which the earlier probe could not get because the terrain offset stayed valid
for its whole leg. Putting the rangefinder out of range with terrain coverage
present does it. SITL at `--home KalaupapaCliffs`, `RNGFND1_MAX=8`, bit 2 set,
holding 40 m above an origin the ground falls to 160 m below, GPS navigating
so both builds fly the same trajectory:

| | old expression | corrected |
|---|---|---|
| peak `XKF5.NI` (ratio x100, capped 255) | 255 | 0 |

(An earlier version of this entry also quoted peak flow innovations of
31.833 against 0.148 rad/s. Those are int16 aliasing artefacts - XKF5 logs
the innovation as 1000x in an int16 and the old expression drives it past
the wrap - and are withdrawn. The ratio saturates its own cap and is the
sound statement. Numbers re-taken at 60 m over the traverse window; see
`../34360/`.)

**This corrects one thing recorded above.** The 2026-09-07 fold said the
forwarding's remaining effect "is on the flow scale height above the range,
which no log field exposes", and left it uncovered. No field carries the
scale height, but `XKF5.NI` carries the consistency ratio it drives, and it
discriminates 3 against 255. The new PR's `EK3_OptflowTerrainScaleHeight`
autotest reads exactly that, so the path is coverable after all.

Extracted to #34360, `../34360/` (branch `ekf3-srtm-flow-scale-sign`, base
master `4891432f35`), opened 2026-09-10 and cross-referenced on this PR at
<https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5615951633>. This record already
said the defect "is master's, not this PR's"; acting on that shortens this PR
by one commit and gets the fix to bit-2 users without waiting on seven rounds
of unrelated review. Rebase this branch onto it once it is open, and drop
`535cfca48f` here.

Round six's withdrawal of the fail-low guard stands and is carried into the
new PR's record, so it is not re-argued there.

### Rebased onto #34360 and the sign commit dropped (2026-09-10)

Head `4fd131e6bf`, seven commits of its own on top of #34360. `535cfca48f`
(pushed as `d32f4ea2cb`) is gone from this branch: #34360 carries it, and
until this rebase both did, which `git merge-tree` confirmed would conflict.
The `terrain_srtm_alt_ms != 0` guard that lived inside the bit-5 commit here
has moved to #34360 as well, so that commit is one hunk smaller and this PR
no longer fixes two master defects on its way past.

The rebase moved the base forward **1348 upstream commits**, from
`20622a3900` to #34360's `4891432f35`. Only one conflict, the SRTM block,
resolved in favour of #34360's version.

**Two of the three autotests then failed, and it was master's API, not the
rebase.** `takeoff()` was renamed upstream between the two bases: `alt_min`
and `max_err` became `altitude_min` and `altitude_max`, and the semantics
differ - `max_err` is a tolerance, `altitude_max` a ceiling, with the old
body doing `wait_altitude(alt_min-1, alt_min+max_err)` against master's
`wait_altitude(altitude_min-1, altitude_max)`. Five call sites translated as
`altitude_max = alt_min + max_err`, so `takeoff(4, max_err=2)` became
`takeoff(4, altitude_max=6)`. This is the trap `PR_REVIEW_RULES.md` records,
and this branch would have hit it the moment it rebased for merge whether or
not #34360 existed.

All three now pass: `EK3_OptflowAssumeFlatGnd`,
`EK3_AglKfVelForVelD`, `EK3_TerrainStateFollowsDatumReset`. Note the first
of those fails on the SmallFastDrone beta branch for the flat-ground
carry-over reason recorded above, and passes here on master.

## What is here

```
33585/
  README.md                  <- this file
  data/flow_scale_*          <- the 2026-09-11 flow scale A/B: harness diff,
                                script, control and x2 SITL logs
  data/extnav_start_probe.diff <- 2026-09-15 probe for the external nav
                                start reset: PRBE/PRB2 dataflash records
                                and the ten-start test, against 76f3428d1a
                                plus the fix
```

No logs committed. The SITL .BIN behind the bit 3 + bit 5 table in the analysis
topic was a scratch autotest run and was not kept.

## Reproduce

```
git checkout pr-optflow-flat-ground
./waf configure --board sitl && ./waf copter
python3 .claude/skills/autotest/run_autotest.py test.Copter.EK3_OptflowAssumeFlatGnd
```

For the negative checks, remove one guard term at a time - two live in
`flatGroundAssumed()` in `AP_NavEKF3_Control.cpp`, the third is the
`OptflowAssumeFlatGnd` clause in `NavEKF3::writeTerrainData()` - rebuild, and
re-run. The test must fail, on the leg named in the table above.

The test sets `TERRAIN_ENABLE = 0` itself for the flat-ground legs. Do not
remove that: SITL has terrain data, and with it enabled those legs pass
through the terrain path instead of the one they are testing.

## Automated review round, and the head move to `36f86f06eb` (2026-09-11)

REQUEST CHANGES at `4fd131e6bf`, 2026-09-10. Its decisive observation was
that the PR's own production code had not changed since the round before -
the head movement was a rebase onto #34360 plus five `takeoff()` argument
translations - so both headline findings stood unanswered. Three findings
from the previous round were withdrawn by the reviewer, two of them because
the reasoning was already in commit `905aafac31` and had not been engaged
with.

One finding fixed this round. Head is now `36f86f06eb`.

### Fixed - the third consumer of the terrain datum was never gated

`FuseOptFlow()` used bare `terrain_srtm_alt_valid` to decide whether to
scale flow from the terrain database, where `terrainAltUsable()` exists for
exactly that decision and had only two callers.

Verified this is **this PR's doing, not inherited**, which the review did not
establish. At the base `5b73047ce8`, `writeTerrainData()` returned early
unless bit 2 was set, so terrain data never reached a core without bit 2 and
the bare flag was equivalent to `terrainAltUsable()`'s bit-2 branch. This PR
adds bit 5 to that gate so the flat-ground fallback can prefer the database.
That opens one case the helper refuses and the bare flag accepts:

    bit 5 set, bit 2 clear, and !flowScaleHgtUsable()
    i.e. a height timeout, or EK3_SRC1_POSZ = None

in which flow was scaled by differencing the terrain height against the very
vertical position state that has no source. Identical in shape to the
`getHeightControlLimit()` defect fixed in `905aafac31` during the seventh
round; that round fixed two consumers and missed the third.

Byte-identical under bit 2, which short circuits the helper.

**Tier 3 (inspection).** Established by reading the write gate at the base
and at the head, not by running anything. No A/B, no autotest leg. The
configuration is reachable but off by default, and nothing in the existing
test set covers it.

### Still open, and what they need

- **BUG - a datum reset does not carry the measured terrain AGL.**
  `ResetPositionD()` (`AP_NavEKF3_PosVelFusion.cpp:248`). The reviewer's
  independent probe reproduced it: a -6 m reset preserved the terrain-state
  AGL at 3 m while the database-derived AGL moved 3 -> 9 m. It withdrew
  "permanent for the flight" as too strong - it persists until something
  re-establishes the offset.
- **BUG (new) - the height-timeout path bypasses the same carry.**
  `ResetHeight()` from `PosVelFusion.cpp:1165-1166`; its airborne branch at
  `:294` only clamps the terrain state and neither carries the measured
  offset nor invalidates `gndOffsetMeasured`. The reviewer explicitly
  withdrew its earlier clearance of this path.
- **ISSUE - terrain-offset uncertainty is pinned while the flat-ground
  assumption is active**, so `ekf_check` keeps seeing a healthy filter and
  `XKF5.Herr` keeps reporting a confident terrain error.
- **Description** - the stack is two PRs deep (#34360 and #33478) and six
  commits are out of scope, not three; "existing vehicles are unaffected" is
  not true of the terrain-state reset carry, which is independent of bit 5.

Neither BUG was touched this round. Both are reset-path changes in the code
this PR's history has already cost three withdrawn fixes in, so they want a
measurement before a patch, not after.

### Owed

Replay against log308 has not been re-run since the 2026-09-10 force-push and
is now two heads behind. The autotest coverage was carried over from an
earlier round's mutation table rather than re-proven, so the reviewer marked
it unconfirmed; that stands.

## The datum-reset BUG cannot be fixed by carrying terrain_srtm_alt (2026-09-12)

Worth recording before it becomes a fourth withdrawn fix, because the obvious
patch is the wrong one and it looks right.

The finding itself is arithmetic and holds. `FuseOptFlow()` derives the database
AGL as `(-pd) - terrain_srtm_alt` (`AP_NavEKF3_OptFlowFusion.cpp:328`), while
`ResetPositionD()` moves `pd` by `posResetD`. `terrainState` is carried by
`c390226e4c` so the measured AGL is preserved, and nothing carries
`terrain_srtm_alt`, so the database AGL moves by the whole reset. That is exactly
the reviewer's probe: a -6 m reset, measured AGL held at 3 m, database AGL 3 -> 9 m.

**The symmetric patch does not survive.** Mirroring the terrain-state carry with
`terrain_srtm_alt -= posResetD` inside `ResetPositionD()` is erased within about
100 ms:

- `AP_Terrain::update()` is scheduled at 10 Hz (`ArduCopter/Copter.cpp:235`,
  `SCHED_TASK(terrain_update, 10, 100, 144)`).
- Every pass with a valid position and a valid tile calls
  `ahrs.writeTerrainAMSL(height)` (`AP_Terrain.cpp:382`).
- That converts with `alt_above_origin_m = alt_amsl_m - state.origin.alt*0.01`
  (`AP_AHRS.cpp:1654`) and stores it verbatim: `terrain_srtm_alt = alt_m`
  (`AP_NavEKF3_Measurements.cpp:1182`).

`state.origin` does not move when the height datum does, so the vehicle keeps
writing an origin-referenced number at 10 Hz over whatever the reset wrote.

### What the defect actually is

Not a missing carry. After a datum reset `position.z` is no longer referenced to
the EKF origin, while `terrain_srtm_alt` always is, so the subtraction mixes two
frames. Any fix has to convert between them rather than nudge one of them once.

The EKF does carry such a term - `ekfGpsRefHgt`, "the WGS-84 reference height used
to convert GPS height to local height", maintained at
`AP_NavEKF3_Measurements.cpp:705` and :852 and already used for exactly this kind
of correction at `AP_NavEKF3_PosVelFusion.cpp:1502` and :1532
(`hgtMea += ekfGpsRefHgt - 0.01*EKF_origin.alt`). So
`(-pd) + (ekfGpsRefHgt - 0.01*EKF_origin.alt) - terrain_srtm_alt` is the shape of
a correct conversion.

**But it is GPS-maintained**, and this PR's case is optical flow with no GPS,
which is where it will be least trustworthy - set once from the origin at
`Control.cpp:711` and `PosVelFusion.cpp:411`, and thereafter only moved by GPS
height innovations. So the term that would fix it is the term that is absent in
the configuration that needs it. That is the open design question, and it is not
answerable by reading more source.

**Tier 3 (inspection).** The 10 Hz overwrite is established from the scheduler
table and the call chain, not from a run. A SITL confirmation would take the
existing `EK3_TerrainStateFollowsDatumReset` trigger plus
`install_terrain_handlers_context()` and `TERRAIN_ENABLE 1`, and would need
temporary instrumentation because the database AGL is a local in `FuseOptFlow()`
and is not logged anywhere.

### The other reset-path BUG is unaffected by this

`ResetHeight()`'s airborne branch (`AP_NavEKF3_PosVelFusion.cpp:294`) does
`terrainState = MAX(stateStruct.position.z + rngOnGnd, terrainState)`, which
floors the terrain state rather than moving it with the datum. That one is a
straight parallel to the carry `c390226e4c` already makes in `ResetPositionD()`
and does not involve the origin frame at all, so it is the tractable half of the
pair. It still wants the measurement the section above owes.

### The ResetHeight() BUG is measured and fixed (2026-09-12)

The tractable half of the pair, done the way the section above asks: measured
first, patched second.

Trigger: a copter hovering at 10 m with an analog range finder fusing the
terrain state, `EK3_IMU_MASK=1`, and a baro glitch held past
`hgtRetryTimeMode12_ms` (5 s). `lastHgtPassTime_ms` only advances when the
height innovation check passes, so a rejected glitch alone reaches the timeout
and `ResetHeight()`; no source change and no disabled sensor are needed.

**The glitch has to be big enough to be rejected.** 8 m is inside the gate -
5 sigma on `sqrt(P + EK3_ALT_NSE^2)` - so the filter simply follows it and no
reset happens at all. The first run of this probe measured a largest
single-sample datum move of 0.19 m and would have been read as "no defect" if
the gate had not been checked. 30 m is rejected and reaches the reset.

Measured at the reset, before and after the carry:

| datum move | AGL move, unfixed | AGL move, fixed |
|---|---|---|
| -30.00 m | **+30.00 m** | +0.00 m |
| +30.24 m | -30.48 m | -0.19 m |

Unfixed, the filter came out of the reset believing a vehicle hovering at 10 m
was 39.5 m above the ground.

Fix is `de33b1f5a4`, conditioned exactly as `c390226e4c`'s carry in
`ResetPositionD()` and keeping the existing floor after the carry. Test is
`76f3428d1a`, `EK3_TerrainStateFollowsHeightReset`, which fails on the unfixed
code with "height above ground moved +30.00 m across a -30.00 m datum reset"
and raises rather than passing if no reset is found at all.

## Automated review round at `76f3428d1a` (2026-09-13), answered 2026-09-15

REQUEST CHANGES, one finding at the head plus seven carried over. Local
branch now `b42ab3936b`; nothing pushed.

| commit | what |
|---|---|
| `49985b005a` | AP_NavEKF3: name the external nav height source before its start reset |
| `09540d6623` | autotest: tighten EK3_TerrainStateFollowsHeightReset |
| `b42ab3936b` | AP_NavEKF3: record why the terrain database flow height ignores a datum reset |

### The external nav start reset skips the carry - measured, and it is a race

The finding: `setAidingMode()` calls `ResetHeight()` when absolute aiding
starts on external nav with `EK3_SRCn_POSZ = ExtNav`, from
`controlFilterModes()`, before `selectHeightForFusion()` has updated
`activeHgtSource` in the same update. Leaving a range finder height source,
the carry's `activeHgtSource != RANGEFINDER` exclusion then reads the source
being left and skips the carry.

**It is real, and it is not every time.** Which runs first after a source set
change depends on whether the update before the change recalled an external
nav sample (`extNavDataToFuse` is set in `SelectVelPosFusion()` and read by
the next `controlFilterModes()`). If it did not, `selectHeightForFusion()`
switches the height source first, `ResetPositionD()` carries the terrain
state, and the aiding-mode reset that follows moves nothing.

Probe: `data/extnav_start_probe.diff`. Source set 1 flow + range finder
height (to arm), set 3 range finder height with no horizontal aiding, set 2
external nav for everything. Ten starts from set 3 into set 2, 22 s apart so
the filter falls back to AID_NONE between them, `SIM_VICON_GLIT_Z`
alternating -30 and 0 so each start moves the datum by about 30 m,
`SURFTRAK_MODE 0`. A `PRBE` record written around the aiding-mode
`ResetHeight()` logs the height source it saw; `PRB2` logs every
height-source-change reset.

Two things had to be learned to see it at all:

- **The first scenario could not show it.** With the range finder still
  delivering after the handover, the terrain estimator's own re-init -
  `terrainState = rng + position.z` when `gndHgtValidTime_ms` is more than 5 s
  old (`EstimateTerrainOffset()`) - fires on the first range sample. A range
  finder height source inhibits the estimator throughout, so that timestamp
  is always stale by then. In that run 2 of 10 starts took the aiding path
  first with the range finder as the stale source and the carry was skipped
  (`PRBE` terrain move 17.37 m and 0.00 m against datum moves of +30.01 and
  -29.98 m), yet `XKF5.HAGL` did not move at 10 Hz. So the defect is masked
  unless range data stops at the handover.
- **The vehicle climbs out of range.** With ALT_HOLD surface tracking on, a
  10 m hover reached 32 m within 10 s of the first start, past
  `RNGFND1_MAX`, which silently turned every later start into a baro start.
  With `SURFTRAK_MODE 0` it climbed about 3 m per start instead and stayed in
  range for all ten. Surface tracking reacting to the datum reset is the
  likely cause; not investigated further.

With `RNGFND1_ORIENT` set away at the handover, so the re-init cannot hide it
(`76f3428d1a` plus the probe, 2026-09-15):

| start | source `ResetHeight()` saw | datum move | HAGL |
|---|---|---|---|
| 2 | RANGEFINDER | +30.02 m | **12.64 -> 0.06** (the `rngOnGnd` floor) |
| 3 | RANGEFINDER | -17.40 m | **16.18 -> 33.59** |
| 4, 10 | two-hop, see below | +6.58, +23.48 m | 19.71 -> 13.13, 1.57 -> 0.04 |
| the other 6 | EXTNAV (height source switched first) | about 30 m | unchanged |

With `49985b005a` (same probe, same scenario):

| start | source before the fix line | datum move | terrain move | HAGL |
|---|---|---|---|---|
| 2 | BARO | +30.02 m | +30.02 m | 12.78 -> 12.79 |
| 5 | RANGEFINDER | -29.98 m | -29.98 m | 15.83 -> 15.83 |
| 6 | RANGEFINDER | +29.98 m | +29.98 m | 18.91 -> 18.92 |
| 10 | two-hop, see below | +12.49 m | 0.00 m | 25.12 -> 12.64 |
| the other 6 | EXTNAV | about 30 m | carried | unchanged |

The fix sets `activeHgtSource = EXTNAV` before that `ResetHeight()`.
`selectHeightForFusion()` would pick the same source in the same update
(`POSZ = ExtNav` and a recalled sample implies fresh data), and
`prevHgtSource` is left alone, so the source-change reset that follows still
fires with a near-zero delta. It also makes `ResetHeight()`'s external nav
vertical velocity branch (`inFlight && useExtNavVel && activeHgtSource ==
EXTNAV`) behave the same whichever order the race resolves in.

**Rejected: the review's first suggestion, "test `prevHgtSource` rather than
the not-yet-updated `activeHgtSource`".** On this path neither has been
updated, and the probe shows both reading RANGEFINDER (`PHS = 2`), so
excluding on `prevHgtSource` skips the carry exactly as before. Its second
suggestion, carrying unconditionally on this path, would work; naming the
source keeps the existing authorisation terms instead.

**No autotest committed for it.** The ten-start harness takes about 280 s of
simulated flight, and which starts take the race path is set by scheduling
phase, not by anything the test controls: starts 2 and 3 in two unfixed runs,
starts 5 and 6 in the fixed one. A green run would not show the path was
taken. The evidence is the probe A/B above (tier 2).

**Found while measuring, not fixed: a two-hop handover inside 5 s.** In
three of the twenty starts across both runs the parameter latency pointed
the range finder away far enough ahead of the source set change that the
height source fell back to baro first: RANGEFINDER -> BARO (carried, e.g.
`PRB2` +17.49 m in the fixed run's start 10) and then BARO -> EXTNAV through
`ResetPositionD()` with no carry (+12.49 m datum, 0.00 terrain, HAGL
25.12 -> 12.64). The fix does not touch this path, which is why it shows in
both tables. The second hop is not authorised because
`prevHgtSource` is BARO, `gndOffsetValid` is false (the estimator never ran
while the range finder was the height source) and `gndOffsetMeasured` is
false (it latches only when the estimator runs in flight). So it is confined
to a vehicle whose range finder has been the height source for the whole
flight so far, changing source twice within 5 s. Measured once; no fix
attempted, because `gndOffsetMeasured` also authorises `flatGroundAssumed()`
and changing what sets it is the kind of change this PR has withdrawn three
times.

### The test notes

`09540d6623`: the comments said `hgtRetryTimeMode12_ms` (5 s); with GPS
vertical velocity in use `hgtRetryTimeMode0_ms` (10 s) applies, so the glitch
is now held 16 s rather than 12. A reset with no XKF5 sample on one side now
fails instead of being skipped. The 0.5 m tolerance is unchanged: the unfixed
failure is 30 m, and the review agreed its -0.20 m reading on the recovery
reset is descent between samples. At `09540d6623`: resets of -30.00 m
(AGL +0.00) and +30.25 m (AGL -0.13), pass.

### The two lower items

- **SRTM route after a datum reset.** Documented rather than fixed
  (`b42ab3936b`). The route is chosen by `gndOffsetValid`, which is master's
  rule and this PR does not change it; the database height cannot be carried
  because AP_Terrain rewrites it against the origin at 10 Hz (section of
  2026-09-12 above). Fixing it needs a frame conversion through
  `ekfGpsRefHgt`, which is GPS-maintained and so least trustworthy in the
  flow-only case. Still open as a design question.
- **Frozen `Popt`.** Derived from the source, not measured: `Popt` has two
  consumers, `EstimateTerrainOffset()` itself and `XKF5.Herr`. It freezes
  whenever the estimator is inhibited, which on master is any time range data
  stops, bit 5 or not; on re-acquisition after 5 s the terrain state is
  re-initialised from the range, so the stale variance does not steer the
  state. It is stale log accounting. Not worth a change in this PR.

The bit 2/5 merge question stays with rmackay9, and the squash suggestions
with the author.

### Rebased onto master and current #33478 (local only)

`pr-optflow-flat-ground-rebased` = `upstream/master` at `bf08027404` (the
#34360 merge) + #33478's five commits at `e21558d163` (including the missing
`0a50ee9939` GPS gate) + this PR's nine commits including the three above.
Every cherry-pick applied cleanly; the three #34360 commits and the stale
#33478 copies drop out. Copter and plane build; the mechanical gate is clean.
Passing on it, 2026-09-15: `EK3_TerrainStateFollowsHeightReset`,
`EK3_TerrainStateFollowsDatumReset`, `EK3_OptflowAssumeFlatGnd`,
`EK3_AglKfVelForVelD`, `EK3_OptflowTerrainScaleHeight`.

Pushing it replaces the PR branch, so it needs the user's grant.

### Owed

- Replay against log308. Still not re-run since `36f86f06eb`, now five
  commits behind. `log308.bin` does not resolve under the log roots
  configured on the machine used (2026-09-15).
- The PR body, which still describes a two-commit PR on #33478 and #34360.

## Pushed 2026-09-15

`pr-optflow-flat-ground-rebased` force-pushed as `pr-optflow-flat-ground`,
head `e18c7d6fc3`: master, then #33478's five commits at `e21558d163`, then
this PR's ten. The three 2026-09-15 commits map as:

| measured on | pushed as |
|---|---|
| `49985b005a` name the external nav height source before its start reset | `7050b23964` |
| `09540d6623` tighten EK3_TerrainStateFollowsHeightReset | `67caf21bc4` |
| `b42ab3936b` record why the terrain database flow height ignores a datum reset | `e18c7d6fc3` |

The rebased branch's test results in the 2026-09-15 section were taken on
`e18c7d6fc3` itself.

Reply posted 2026-09-15 11:23Z
(https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5679360111) covering the ExtNav
start race and its fix, the declined `prevHgtSource` suggestion, the two-hop
gap left open, the test fixes, the SRTM handover comment and Popt. The PR body
was rewritten for the new stack: five #33478 commits then ten of this PR's,
the three autotests, and the terrain carry on all three reset paths.
`AIReview` was already on; the 2026-09-13 round is stale from the push.

## rmackay9: make it the default and remove the height limit (2026-09-16)

rmackay9 (2026-09-15 23:30Z): make "use terrain, or whatever we've got" above
the rangefinder range the default, and remove the AHRS/EKF
`get_hgt_ctrl_limit()` and the AC_Avoid vertical limit #34380 touches. That
also answers his bits 2/5 question.

Decided with the user 2026-09-16: agree, retire bit 5 by making the behaviour
the default here, and turn #34380 into the height-limit removal stacked on
this PR (removing the ceiling first would let a default-configured flow
vehicle climb into the failsafe the limit keeps it away from). Reply posted
16:00Z (https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5700538642)
with the flight evidence (Loiter held at 24 m on flow and baro with velocity
within about 0.2 m/s of GPS, the private analysis repo;
relative position held for a whole flight with the rangefinder unusable 46% of
it, `log7` there) and three caveats to settle before the default flips:

- Uneven ground: a GPS-denied vehicle has no terrain data, so the default is the
  terrain offset frozen at the last range measurement, which over rising ground
  drifts instead of failing safe. To be measured in SITL over sloping terrain
  (the Kalaupapa rig above) against today's failsafe before flipping. Folding
  bit 2 in changes its contract the same way.
- EKF2 publishes the same limit with no above-range mode; proposed to remove it
  there too unless rmackay9 objects.
- The limit is the only thing stopping a climb to where the flow sensor stops
  resolving texture; without it the EKF drops flow and fails safe higher up.

Consequence for the tests: master's `OpticalFlowLimits` asserts the 35 m
ceiling and changes with the removal.

## Uneven ground: what a default flat-ground assumption costs (2026-09-16)

The first caveat in the 2026-09-16 reply to rmackay9, measured. Question: if
navigating on flow above the rangefinder range becomes the default, a
GPS-denied vehicle flies on the terrain offset frozen at the last range
measurement. Over sloping ground, how wrong is that, what does the vehicle do,
and how does it compare with today?

### The rig (tier 2, SITL)

- Code: `e18c7d6fc3` (this PR as pushed) plus local-only probe commits on
  `uneven-ground-ab` (`a9827e3354` .. `fc06a4fd17`, diff in
  `data/uneven-ground-2026-09-16/probe.diff`). The probe logs a `PRBU`
  message: the height FuseOptFlow actually scaled flow with, the simulator's
  true height above terrain, `flatGroundAssumed()`, `terrainAltUsable()`,
  `gndOffsetValid`/`gndOffsetMeasured`, `horiz_pos_rel` and the aiding mode.
  An env switch withholds terrain data from the cores.
- SITL does model this. `hagl()` in `SIM_Aircraft.cpp` subtracts the terrain
  database height at the true location, and both the SITL optical flow range
  (`AP_OpticalFlow_SITL.cpp:67-69`) and the SITL rangefinder use it, with
  `SIM_TERRAIN=1` and `TERRAIN_ENABLE=1`. Confirmed: true AGL minus the
  rangefinder reading, while in range, median +0.01 m in every run.
- Copter, CMAC home, `SIM_GPS1_ENABLE=0`, `EK3_SRC1_POSXY=0`, `VELXY=5`
  (flow), `POSZ=1` (baro), `VELZ=0`, compass yaw, `EK3_IMU_MASK=1`,
  `RNGFND1_MAX=8`, `AVOID_ENABLE=0` (the height limit would stop the climb),
  `COMPASS_DEC=12.4 deg` with autodec off (with no GPS the EKF frame is
  otherwise rotated 12.4 deg from truth, which reads as position error).
- Profile: ALT_HOLD takeoff, LOITER, climb to 35 m (above the 8 m range),
  15 s for the offset to go stale, then a GUIDED velocity of 5 m/s (EKF frame)
  on a fixed bearing for 1000-1200 m, then 60 s of LOITER in a 4 m/s crosswind,
  then LAND. The fall-low case climbs to 6 m only, in range, and flies off the
  slope, so the range is lost in motion.
- Terrain under the path (SRTM, relative to home): flat, bearing 150, within
  3 m; rise, bearing 240, +16 m by the end of the flown distance; fall,
  bearing 30, -14 m (35 m cases) and about -19 m then rising again (fall-low).
- Truth: `SIM2` position and velocity against `XKF1`, displacements measured
  from the traverse start.
- Two rigs, because Copter's `ekf_check()` returns immediately when the EKF has
  no origin (`ArduCopter/ekf_check.cpp:36-39`): rig A has no origin at all; rig B
  sets one by `SET_GPS_GLOBAL_ORIGIN` at CMAC before takeoff. In rig B, "bit 5,
  terrain withheld" is the GPS-denied frozen-offset case and "bit 5, terrain
  allowed" is the terrain database path.

### Today, bit 5 clear, origin set (rig B)

| run | what happened |
|---|---|
| climb, r0 / r1 | `horiz_pos_rel` cleared at 14.2 / 14.3 m true AGL; "EKF variance: position lost", LAND 1 s later at 15.1 / 15.0 m; horizontal drift during the landing 2.3 / 1.1 m |
| fall-low, r0 / r1 | range lost in motion; LAND 1 s later after 43 / 38 m of traverse; still moving at 5.8 / 5.7 m/s, it carried 19.6 / 19.7 m while landing |

### Bit 5 set: traverse error against truth

EKF-frame 5 m/s commanded. Position error is the EKF displacement minus the
true displacement at the end of the traverse. A and B columns are the two
rigs; with terrain withheld they are the second run of the same cell.

| case | terrain to the EKF | true / EKF distance (m) | true / EKF speed (m/s) | position error (m) | flow height / true AGL at end |
|---|---|---|---|---|---|
| flat | withheld (A, B) | 853, 849 / 838, 835 | 4.32, 4.29 / 3.75, 3.76 | 15.0, 14.3 | 36.6 / 38.0 |
| rise +16 m | withheld (A, B) | 739, 740 / 916, 918 | 3.69 / 4.59, 4.61 | 177.2, 178.8 | 36.8 / 21.6 |
| rise | allowed (B) | 807 / 814 | 4.07 / 4.09 | 9.6 | 19.7 / 19.8 |
| fall -14 m | withheld (A, B) | 1038, 1048 / 884, 889 | 4.39, 4.42 / 3.40, 3.42 | 154.8, 159.0 | 36.9 / 51.1 |
| fall | allowed (B) | 1003 / 981 | 4.24 / 3.86 | 23.8 | 49.4 / 50.2 |
| fall-low from 6 m | withheld (A, B) | 2041, 2033 / 1091, 1094 | 9.71, 9.65 / 4.59, 4.57 | 950.5, 940.0 | 7.8 / 8.7 (median ratio 0.54) |
| fall-low | allowed (B) | 1307 / 1195 | 5.50 / 4.84 | 113.7 | 24.4 / 23.4 |

With bit 5 set, `horiz_pos_rel` held for 100% of every traverse and no
failsafe fired in either rig. The 60 s crosswind hold afterwards was stable in
every case (true drift 5-35 m, position error 2-9 m). The drift was largest
on the flat, where the 4/HAGL gain scaler at 37 m detunes the loiter.

### What the vehicle does (tier 2)

- Rising ground makes the frozen height too large, so flow velocity is
  overestimated. The vehicle flies slower and less far than it believes (24%
  here) and in a hold its effective gain goes up. That errs towards stopping.
- Falling ground makes the frozen height too small, so velocity is
  underestimated. The vehicle flies faster and further than commanded. From
  low altitude over a slope the true height roughly doubled, the vehicle flew
  at 9.7 m/s on a 5 m/s command, and ended 940-950 m from where it believed it
  was. That is the "drifts instead of failing safe" case, and it is real: it
  does not stop, and nothing reports a problem.
- The error is proportional to the fractional change in height above ground.
  A few metres of slope matters little at 35 m and a lot at 6-10 m.
- With terrain data reaching the EKF (an origin and coverage) the same flights
  come in at 1-2% of distance over steady slopes and about 9% when flying off
  the slope from low altitude.

### What is and is not new with the default

Derived from the source, and consistent with the runs: flow fusion is not
changed by bit 5. Today's firmware scales flow with the same frozen offset
above the range; bit 5 only changes the status flags and `canDeadReckon`.
So the velocity errors above already exist today. What bit 5 removes is the
reaction to them:

- With an EKF origin (outdoors with GPS present but not a source, or an
  origin set by a GCS), today's vehicle loses relative position about 5 s
  after the range goes stale and the EKF failsafe lands it 1 s later, within
  about 20 m. With bit 5 it keeps flying on the wrong scale indefinitely.
- With no origin, `ekf_check()` never runs, so today's vehicle does not fail
  safe either. In rig A with bit 5 clear, LOITER carried on above the range
  for about 100 s with position invalid, and only GUIDED was refused ("requires
  position"). For these vehicles bit 5 changes which modes can be used, not
  what the vehicle physically does. One rig A bit-5-clear traverse run
  (`v2_falllow_r0`) lost the SITL link about 22 s into the traverse and timed
  out after 28 minutes. It is discarded and was not explained.

### Verdict

- Terrain database path (origin plus coverage): safe to make default. The
  errors are small, and this is what "use terrain" means in the proposal.
- Flat-ground assumption without terrain data: do not make it the default.
  On vehicles that have an origin it removes a failsafe that today lands the
  vehicle within about 20 m, and replaces it with unbounded flight on a scale
  that can be half the truth over falling ground. Keep it opt-in (bit 5) for
  the known-flat indoor case it was built for.
- Untested idea for a safer default: trust the frozen offset only while the
  horizontal distance flown since the last range measurement stays under a
  few times the frozen height. A hover or slow indoor flight keeps it; a
  traverse away from the measured ground ends it and the vehicle falls back to
  today's behaviour. Needs its own A/B before anyone proposes it.
- Caveats: SITL terrain is SRTM with bilinear interpolation, so there are no
  cliffs, buildings or vegetation, and a flow sensor looking at a real slope
  sees more texture variation than SITL models. Wind was off during the
  traverses. The runs are deterministic: the A and B pairs agree within about
  1%.

Data: `data/uneven-ground-2026-09-16/`, containing `probe.diff`,
`run_uneven.sh`, `analyse_uneven.py`, `results.txt` (analysis of every run
cited) and three gzipped SITL logs: `b_v1_falllow_r0` (terrain withheld),
`b_v1t_falllow_r0` (terrain allowed) and `b_v2_falllow_r0` (today, origin set).

### Uneven ground result posted to rmackay9 (2026-09-16)

Posted 19:15Z (https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5703152857):
the end-of-traverse table above, that bit 5 removes the failsafe rather than
changing flow fusion (the frozen offset already scales flow on master), and the
proposal that the default becomes the terrain database path when there is an
origin and coverage, with the flat-ground assumption kept opt-in behind bit 5.
The untested "trust the frozen offset only within a few heights of the last
range reading" middle ground is mentioned as an option.

Consequence for #34380, stated in the same comment: with the terrain path as
the default, a vehicle with an origin, no terrain coverage and bit 5 clear
would climb past the range and failsafe-land from height once the limit is
removed (the removal measurement: failsafe at 51.4 m where the limit holds
27.1 m). #34380 is held until the default is agreed; rmackay9 is asked
whether to keep the limit for that one case or accept the failsafe there.

### Superseded 2026-09-30 by a gated default

The verdict above (flat ground without terrain data stays opt-in) is kept:
it is still right about what an ungated default costs. What changed is the
gate. Decided with the user 2026-09-30 after /pr-review of the local stack:
make the fallback the default, but only above the optical flow height limit
(0.7 x RNGFND max - 1 m, the value getHeightControlLimit() publishes) and
only with optical flow as a velocity source.

Why the gate is height, not range finder status (tier 3, source): the base
class reports OutOfRangeHigh only above RNGFNDx_MAX, but Benewake, LightWare,
TeraRanger, JRE, DTS6012M and Ainstein substitute max + 1 m when every
reading is invalid (a lost return at any height), and VL53L1X / MaxBotix
I2C / serial timeout give NoData above their reach. Status alone cannot tell
a climb from a fault in either direction; the EKF's height above the last
measured ground can.

Local commits (unpushed, fixups to fold): c51c52e093 default, ee6dd8ee75
ground effect (fold into 27f59f2b3d), c52dc87edf + 16f9fff804 + 0a01435789
height/source gate and AP_RANGEFINDER_ENABLED guard, 684f94cd45 + amend!
fa7505fd32 test legs. Head fa7505fd32.

Tier 2 (SITL), each test shown red with its fix removed:
- BaroGroundEffectRangefinderSwitch fails 2/2 without ee6dd8ee75 (1.28,
  1.35 m below truth), passes with it.
- Range data lost at 2.5 m (SIM_SONAR_GLITCH=1, which reads as out of range
  high like a lidar with no return) drops relative position; holds it without
  the height term in flatGroundAssumed().
- POSZ=2 climb out of range: drops without terrain data, holds with it;
  holds-leg fails if the default terrain path returns false.
- getLLH() only returns a location while horiz_pos_rel/abs is set, so
  AP_Terrain cannot feed a flight that never had a position; the default
  terrain path can only continue a position, not start one (same for bit 2).
- AP_RANGEFINDER_ENABLED=0 copter build fails without the guard ("no member
  named rangefinder"), builds with it; EK3_FEATURE_OPTFLOW_SRTM=0 builds.
- EK3_TerrainStateFollowsDatumReset flaked 1 of 3 on the switch back onto
  the range finder after disarm; d3110bc6b2 closes the window at disarm, 3/3.

Still open: the terrain database height is not carried across a vertical
datum reset (documented in 6a1200d267); now reachable by default above the
limit. AP-Review's bit 4 velTestRatio item (in #33478's commits).

Pushed 2026-09-30 after autosquash (tree identical to the reviewed head): #33585 head adb78f41cb (ground effect fix folded into 656483fc61), #34380 head 219075df1e. Descriptions rewritten; comments posted on #34380 (reply to rmackay9), #33585 and #33568.

## Decoupled from #33478, AP-Review round 3 fixed (2026-10-01)

#33585 rebased onto master 26c7363f64 without #33478 (head 9bfb10b15b, 15 commits). The coupling was textual only: bit 5 sat beside #33478 bit 4 in the EK3_OPTIONS enum and parameter text, and the tests sat beside EK3_AglKfVelForVelD. Applied alone, copter and plane build and all seven #33585 tests pass.

AP-Review round 3 (head adb78f41cb): B1 the height limit was lifted by default on terrain data (getHeightControlLimit used terrainAltUsable); now lifted on terrain only with bit 2. Leg: TERRAIN_ENABLE=1, default avoidance, 8 m range finder, full climb stops at the gate; without the fix 36.8 m. I1 origin altitude error carried the terrain gate: the fallbacks now need every available HAGL (measured offset and database) over the gate (aboveFlowHgtLimitAllSources). Leg: no GPS, origin +10 m, range lost at 2.5 m must drop rel pos; held without the fix. I2 (database below gate vetoes flat ground) closed by the same check, by reading only. I3 velTestRatio fixed in #33478, not carried here any more. N1 description wording. Range finder height source (POSZ=2) measures no offset, so the database decides alone there - disclosed.

#34380 restacked (head 571ed7318c, 3 commits); its EKF hunk supersedes the bit 2 test on the limit; the B1 leg there asserts the climb passes 15 m with rel pos held. Regression on both heads: 12 tests pass incl. Replay. Feature-off builds (AP_RANGEFINDER_ENABLED, EK3_FEATURE_OPTFLOW_SRTM) pass. Descriptions updated; reply to AP-Review and merge-order note on #33568 posted.

## v4: review round fixes (2026-10-01, local, not pushed)

Branch pr-optflow-flat-ground-v4 (../rv-final) on master 26c7363f64: 0e1e634d82 AP_DAL logs every RTER write (EKF3 judges terrain staleness by arrival time, Replay must see each one); 6a5a13dd50 fallback; 0195a1fce6 datum carry; 42ec79bbe5, e0084de1cf tests.

Changes against v3, from the pr-review round (reviewer subagent + Codex cold reads):
- moveEKFOrigin() now shifts gndKnownNE. Without it the 10 x bound was measured in a stale frame after GPS flight moved the origin. Leg: 300 m on GPS then switch to flow source set, must be refused; held 300 m away without the shift (tier 2).
- Fallback engages only once gndOffsetValid has gone false, and never without terrain data when 0.7 x max - 1 < 1 m (sensors under 2.9 m), where nothing tells a failure from a climb. Leg: RNGFND1_MAX 2 climbed out of, must be refused; held without the floor check (tier 2).
- Short-sensor and carry-over legs now assert the range finder reading before killing it (polled RANGEFINDER, not streamed by default), so they cannot pass on the height gate instead. Anchored test waits for terrain tiles before the climb.
- Carry commit: "that core never recovered" dropped - unverified, and EstimateTerrainOffset re-initialises terrainState after 5 s without fusion (tier 3, reviewer). Drift-reset numbers made consistent: 2.4 m worst against 54.8 m carried (tier 2; 2.2 m on the v4 run).

Results on v4 (tier 2): EK3_OptflowAboveRangefinder passes (bound dropped at 212 m at about 21 m); EK3_OptflowAnchoredTerrain 0.3 m worst over 8.2 m rise; datum tests pass (DatumReset moved -5.97 m, HAGL +0.00 m). Regression on the #34380 v4 head: OpticalFlow, OpticalFlowLocation, BaroGroundEffectRangefinderSwitch, EK3_OptflowTerrainScaleHeight, MaxAltFenceAvoid, MinAltFenceAvoid, GPSViconSwitching, VisionPosition, Replay all pass. Per-commit builds, off_rf/off_srtm/off_flow builds, copter/plane/rover/sub pass. Mechanical gate clean.

Disclosed, not changed: anchoring runs on any vehicle with range finder and terrain data, GPS included (only the logged terrain state changes; getHAGL is invalid while the offset is stale); 5 s handover step before anchored terrain takes over; anchored and frozen terrain states are not carried on a height-timeout reset.

## Database error: SITL harness, SFD-O4 measurement, startup warning (2026-10-01)

Dev call 2026-09-30 (on #34361) preferred AGL logic outside the EKF (AP_HAGL). Use-case review: flat ground alone meets the real flights (log308, SFD-O4 log5; SFD-O4 log7/8 flew bit 2), but not GPS loss far from takeoff, long traverses without GPS, or rmackay9's default. The user's call: those three are the point of the PR, so anchoring stays.

Tier 2, harness DatabaseErrorProbe (rv-base, scratch only): SIM_TERRAIN=0 gives flat SITL ground while AP_Terrain serves real SRTM shape, so the database relief from the start is a known injected error. 1 km traverses at 5 m/s, 8 m range finder. Position drift ~ 0.4 x error/height (ratio 0.34-0.6 in 9 of 10 runs): 7 m error 30/16/8% at 10/20/35 m; 13 m 52/29/15%; 2 m 3.5/1.8/1.5%; zero-error controls 0.5-2%. Error with database ground too high drops the EKF height below the flow gate and the failsafe lands (fails safe); too low overestimates velocity, unreported.
Comparison over real relief (SIM_TERRAIN=1): flat ground 0.2-2.8 m error but drops at its 10x bound (105 m at 10 m, 205 m at 20 m, then failsafe); bit 2 with a 5 m origin error 22-46% at 10 m, 13-24% at 20 m (it uses -pd - terrain_srtm_alt, so XKF5.HAGL does not show the error). Anchoring cancels that error.
Tier 1, SFD-O4 logs 5-17 (db_error_real.py: TerrH against POS.Alt - range x cos tilt, Good range only, 1 Hz): change in database error between points 0-50 m apart median 0.5 m, p90 1.6 m; 50-100 m median 1.2, p90 3.4 m. Nothing beyond ~100 m: a 15 m range finder only sees ground near takeoff. Longer lines rest on SRTM's ~6 m spec.

Decision (user): no minimum height; warn at startup, since nothing can be done in flight. 7bbc877e8b: with optical flow in any source set and a downward range finder max under 20 m, "EKF3: rangefinder max Xm, flow above may drift" once after the filter initialises. 68d2af7997 adds AP_NavEKF_Source::optflow_enabled(). SITL: the message arrives on reboot (EK3_OptflowAboveRangefinder now waits for it); a GCS connecting after boot can miss it, MSG keeps it in the log. #34380 restacked as pr-avoid-flow-ceiling-v5.

## Review round on v4/v5, fixes, rebase onto master (2026-10-01, local, not pushed)

pr-review (5 Claude reviewers + 4 Codex cold reads) on v4/v5: REQUEST CHANGES. Fixed: the anchored path skipped the last-good-reading check and floor, so a range finder dying between the gate and 0.7 x max engaged the fallback with no database error (now both paths, new AnchoredTerrain leg); anchoring now gated on sources.optflow_enabled() (GPS-only vehicles unchanged); dead_reckoning now uses optflow_gnd_offset (FS_DR with drag fusion); ExtNav-start ResetHeight carries remembered ground (source change); warning re-checked every 5 s while disarmed (late DroneCAN backends); messages: DAL rate 10 Hz, AC_Avoid back-down qualified (zero demand or AVOID_BACKZ_SPD=0 do not back down), airframe name removed. Test fixes: no-height-source leg had been killing the sensor at 9.7 m (beyond max) - now asserted in range; hover-band legs settle ~0.6 m above where the climb stops; warning check moved to its own commit after the warning. Refuted: "OpticalFlowLimits will fail" (read before the test commit). Disputed, for the PR text: real reach < 0.7 x max (master equally broken), RNG-primary no fallback (design), fallback commit alone without carry (same PR).

Rebased onto upstream/master 755258dbb4 (conflicts only in tests1c registration lists). Final heads: pr-optflow-flat-ground-v4 0f428b222e (8 commits), pr-avoid-flow-ceiling-v6 fe5288ab4d (+2). Every commit builds; off_rf/off_flow/off_srtm; copter/plane/rover/sub; gate clean. Tier 2: all 16 tests pass (VisionPosition needed a rerun after a harness heartbeat stall post-flight); AnchoredTerrain 0.3 m; DatumReset -5.98 m move, +0.01 m HAGL; DriftReset 2.4 m; bound drop ~211 m at ~21 m; FlowCeiling back at 16.8 m. All 10 mutations red at their own assertions (no_anchor 7.9 m, anchored_skip, no_check, no_floor, no_bound, no_shift, no_warn, old_carry 51.3 m, never_lift, rng_lift). Untested: dead_reckoning change, ExtNav-start carry.

Pushed 2026-10-03: 0f428b222e -> 6034b82053 (fast-forward, 5 new commits). EK3_OptflowAboveRangefinder passes on it alone.
Reply posted 2026-10-03: https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-5973644513

## 2026-10-08: squashed after flight test

Head dbc79586ae -> b0c3cb87ce, 6 -> 4 commits on the same base, content identical
(empty diff against the pre-squash head); every commit builds on its own. Review and test follow-ups folded into their commits.

- 4c036f5be8 AP_DAL: log every terrain height write
- 0e008302ec AP_NavEKF: add optflow_enabled() for any source set
- 784c750af1 AP_NavEKF3: keep optical flow nav alive above the rangefinder range
- b0c3cb87ce autotest: cover optical flow nav above the rangefinder range

Pushed 2026-10-11: `pr-optflow-flat-ground` `b0c3cb87ce` -> `7f5f8ffe85` (force, autosquashed), 4 commits, messages only (every tree unchanged). Mechanical gate (/pr-review checks, with the new squashed-subject scan) clean. PR replies drafted, not posted.

Reply to the AP-Review round posted 2026-10-11 (issue comment 6110171140), the text drafted above.

2026-10-12: the raw-sample timing of the 2 s and 500 ms return checks (`784c750af1`'s lines, AP-Review's non-blocking point) is fixed on #34380 (`fix2/pr-avoid-flow-ceiling-backup` `4c3f1a7724`, test `7aa5017103`); #33585 unchanged. See ../34380/README.md, "2026-10-12: AP-Review round at 732913562e, fixes".

## 2026-10-23: #34851 changes what gndOffsetValid means

#34851 (opened 2026-10-22, `da86aaa70f`) keeps `gndOffsetValid` true for
5 s after the last range finder height fusion that passed its innovation
check, where master drops it in the cycle the height source leaves the
range finder. This PR reads the old meaning in two places, derived from
the source and not measured against #34851:

- the `ResetPositionD()` comment that `gndOffsetValid` "goes false in the
  very cycle the source changes", which is why the carry gate names
  `prevHgtSource == RANGEFINDER` separately; with #34851 that term is
  redundant for 5 s, not wrong;
- the terrain-anchor fallback on `!gndOffsetValid && terrainAnchorValid`,
  which would start up to about 4.5 s later after range finder height
  ends.

Whichever of the two merges second re-checks these. The SFD beta carries
both since refresh11 topup1 (2026-10-22), with #34851's term also added
to the flat-ground restore's recompute in `Control.cpp`.

## 2026-10-30: SFD-O4 log61, the open SRTM collapse in flight

log61 (3408138/639) on the beta `52b1d36f`, which carries this PR's anchor
(`8332e10826`); `EK3_OPTIONS 94` (bit 2 set), `EK3_SRC_OPTIONS 8`,
`TERRAIN_ENABLE 1`. Core 1 (flow) was primary through an acro sortie to
40 m over a 15 m range finder. LOITER at 255.8 s, at 26 m and 13 m/s, held
a 32 deg lean and sped up: core 1 read 0.3-0.9 m/s.

This is the collapse round seven recorded as "pre-existing and not closed",
reached by a route that record does not cover. With bit 2 set the anchor is
bypassed and `FuseOptFlow` scales flow by `(-pd) - terrain_srtm_alt`.
`AP_Terrain::update()` looks the SRTM height up at `ahrs.get_location()`,
the primary's position, and `NavEKF3::writeTerrainData()` gives that value
to every core (derived from the source, not measured). Core 1 had drifted
200-340 m from GPS after velocity resets (`../34941/`)
onto ground the database puts 25-35 m higher, so the scale height went
below zero and clamped to `rngOnGnd`. The main filter's own HAGL
(`terrainState - pd`, frozen above range) stayed close to GPS height.

| Time | Lookup position from GPS | RTER (m above origin) | `-PD - RTER` | GPS height above origin |
|---|---|---|---|---|
| 218.8 s | 3 m | 4.1 | 23.8 | 27.7 |
| 226.9 s | 114 m | 5.9 | 11.2 | 11.5 |
| 230.9 s | 169 m | 24.6 | -3.1 | 22.2 |
| 235.0 s | 286 m | 35.3 | -8.2 | 30.3 |
| 255.2 s | 277 m | 27.6 | -0.6 | 24.6 |

Replay on the beta (built at smallfastdrone `0cb49e7dfb`, `52b1d36f` plus
an autotest commit) reproduces core 1 to 0.1 m/s through 256 s. Core 1
speed at 254-260 s, against GPS 13.1-14.5 m/s:

| Run | Core 1 |
|---|---|
| as flown, bit 2 set | 0.3-3.9 m/s |
| bit 2 off (`EK3_OPTIONS 90`, this PR's anchor) | 4.5-6.8 m/s |
| bit 2 off, RTER records stripped from the log (flat ground only) | 20-30 m/s |

All three are identical from 222 to 234 s. The anchor follows the
database's shape at the same drifted position, so it is misled by the same
lookup; flat ground over-reads. None gives a usable speed, because core 1
was already wrong. What this adds: the database height can be wrong without
the database being wrong, when it is looked up at the position of a lane
that has no absolute fix, which is not a location (root playbook ARCH-16).
No fix written.

## 2026-11-04: rmackay9's dev call review; the datum carry split out, the anchored height moved into FuseOptFlow()

rmackay9 left five inline comments at `6dcb4f2b2d` during the 2026-11-04
dev call. Andy's decisions: (a) the external nav line at Control.cpp:492
belongs to the datum carry, so the carry becomes its own PR; (e) the
anchored flow height is chosen in FuseOptFlow() beside bit 2's. (b) the
anchor itself was answered by Andy on the PR. (c) the restore that undoes
a brief return and (d) the 10 x bound are undecided and unchanged. The
triage of all five is in the session scratch (`33585.md`), not here.

All local, nothing pushed, no /pr-review run yet.

### Branches

- `r1104/33585-carry` on master `802db19de1`, needs nothing else:
  `9377819b2e` AP_NavEKF3 carry (ResetPositionD/ResetHeight, the
  prevHgtSource ordering, the gndOffsetMeasured latch), `18577f4ff2`
  AP_NavEKF3 external nav names its height source before its reset,
  `c24c4d9155` autotest the three datum tests. Draft PR text in the
  session scratch (`carry-pr.md`). Record: `../carry-split/`.
- `r1104/33585-restack`: the carry plus `f1e2b2c311` AP_DAL,
  `9327116332` AP_NavEKF, `2c85876817` the fallback without the carry,
  `30d50f8bc1` its tests. `git diff 6dcb4f2b2d 30d50f8bc1` is empty, so
  carry plus restack is the GitHub head's tree exactly.
- `r1104/33585-restructure`: the restack plus `2e9c3a1e6e` autotest
  (AnchoredTerrain checks speed against truth) and `17833af182`
  AP_NavEKF3 (the anchored height chosen in FuseOptFlow()).
- `r1104/34380` (worktree `r1104-34380`): #34380's five commits
  cherry-picked clean onto the restructure, `1812f5690f`..`12b1f83aee`.
  Its own +/- lines are identical to `6dcb4f2b2d..9bb072fa82`; only two
  context lines differ.

Every code commit builds copter; at `17833af182` plane, rover, sub, heli
and Replay build, and copter with EK3_FEATURE_OPTFLOW_SRTM=0,
EK3_FEATURE_OPTFLOW_FUSION=0 and AP_RANGEFINDER_ENABLED=0.

### The carry, each test against what it covers (tier 2)

At `c24c4d9155`, against master `802db19de1` and three mutations of the
carry:

| test | carry | master | mutation |
|---|---|---|---|
| FollowsHeightReset, in range | +0.00 m on -30.01 m | +30.01 m | - |
| FollowsHeightReset, 1.6 s after range loss | +0.00 m | (first leg fails) | 500 ms window: +30.01 m |
| FollowsDatumReset | +0.00 m on -5.98 m | +5.99 m | source recorded before the reset: +5.99 m |
| HeldOnDriftReset | 2.2 m | 2.4 m (passes) | carried unconditionally: 51.8 m |

The external nav line has no test: which start takes the race depends on
the scheduling phase (2026-09-15 probe, 2 of 10 starts).

### The restructure

SelectFlowFusion() no longer writes the anchored height into terrainState.
FuseOptFlow() chooses it in an `else if (terrainAnchored())` beside bit
2's block. The flow speed limit and nav gain scaler, the flow height
limit, the flat-ground checks (height limit, 10 x bound) and XKF5.HAGL
read it through flowTerrainState(), so they still judge the ground flow
is scaled by; XKF5.TOfs is the terrain state, so TOfs - HAGL is no longer
PD while anchored. The range finder height switch keeps reading the
terrain state, as for bit 2. The restore's descent check takes the held
ground from the saved anchor and the latest terrain height, where it took
the height when the return began (at most 2.5 s earlier). Derived from the
source: no test separates the anchored height from the held one in the
fallback's own checks, because no anchored traverse comes near the limit
or the bound.

Measured and rejected on the way:

| change | why it looked right | what settled it |
|---|---|---|
| log the flow scale height as a new XKF5 field | XKF5.HAGL would otherwise show the held ground | XKF5's labels are at the 64-character limit: the logger refused the structure at boot and SITL took no RC input. A new message costs a scarce log ID, so HAGL reads flowTerrainState() instead |
| terrainAnchored() on the cached gndOffsetValid alone | the old code's write used it | Replay of log61: one XKF5.HAGL record differed (10.07 against 11.73 m at 176.6 s), the step a range return was first fused. The old code re-initialised terrainState from the range before FuseOptFlow() in that step; the cached flag still said anchored. Now it also requires no range fusion in the last 5 s; the Replay then matches |

### Evidence

- EK3_OptflowAnchoredTerrain read the anchor only through XKF5.HAGL,
  which flowTerrainState() now feeds, so it would pass with the anchor
  gone from FuseOptFlow(). It now also checks true speed against the
  EKF's once the ground has risen 5 m (within 10%): restack 1.011,
  restructure 1.010; anchor removed from the restack 0.829 (height
  check also fails, 7.8 m), from FuseOptFlow() on the restructure 0.819
  (height check passes, 0.3 m). Tier 2.
- Replay of log61 (SFD-O4, 3408138/639) through this branch's own
  master-based Replay (it runs the EKF on this 4.7.2 beta log), `30d50f8bc1`
  against `17833af182`. With EK3_OPTIONS 90 (bit 2 off, the anchor in
  use), every byte of XKF1-4, XKFS, XKQ and XKFA is identical; XKF5
  differs only in TOfs, 1049 records from 175.6 to 300.4 s (held -6.06 to
  -1.51 m against the anchored -37.78 to -1.11 m), which is the point.
  With 94 (as flown, bit 2) nothing in the EKF differs. Three OF records
  differ in TimeUS in both, a Replay timing artefact. The output mixes
  beta and master formats, so a parser sees bad headers; the comparison
  was made byte by byte. Tier 1b for "changes nothing", on a master-based
  EKF, not the beta's.
- Uneven-ground rig (2026-09-16 rig, origin set at home, 8 m range finder,
  1 km traverses at 5 m/s from 35 m, bit 2 clear), restack against
  restructure, end-of-traverse position error. Closed loop, so runs vary:

  | case | restack | restructure |
  |---|---|---|
  | flat | 4.8 m | 4.2 m |
  | rising | 11.5, 5.5, 6.6 m | 8.6, 9.5, 9.8 m |
  | falling | 7.7 m | 7.9 m |
  | off a slope from 6 m | 30.9 m | 28.6 m |
  | rising, origin 30 m low | 12.3, 9.0, 8.7 m | 7.0, 8.8, 11.6 m |
  | no terrain data (bound) | LAND at 369 m, 2.4 m | LAND at 370 m, 2.2 m |

  Harness, runner, analyser and every number in
  `data/uneven-ground-2026-11-04/`. Tier 2.
- Pass on the restructure: EK3_OptflowAboveRangefinder,
  EK3_OptflowAnchoredTerrain, the three datum tests, OpticalFlow,
  OpticalFlowLocation, OpticalFlowLimits, EK3_OptflowTerrainScaleHeight,
  BaroGroundEffectRangefinderSwitch, Replay. On #34380 restacked, against
  #34380 as pushed (`9bb072fa82`): FlowCeilingBacksDownIntoRange,
  FlowCeilingShortRangeFinder, EK3_OptflowAboveRangefinder,
  EK3_OptflowAnchoredTerrain (1.011 both), OpticalFlowLimits,
  MaxAltFenceAvoid and MinAltFenceAvoid pass on both.

### Not run

- logm2_log4, the flight behind the carry (4.6.3 SFD, EK3_RNG_USE_HGT 10):
  not under AP_LOG_ROOTS on this machine, so not replayed. It is a 4.6
  log; whether master's Replay reads it is untested.
- log308: still not resolvable here.

### Owed

- /pr-review on `r1104/33585-carry`, `r1104/33585-restructure` and
  `r1104/34380` before anything is pushed.
- Opening the carry PR, and #33585's and #34380's descriptions rewritten
  for the split; replies to rmackay9 on (a) and (e).
- The SFD refresh: prs.txt gains the carry PR ahead of #33585.

## 2026-11-04: what the anchor cancels on SFD-O4, and bit 2 against the anchor in Replay

Asked after the dev call: do the SFD-O4 flights back the anchor (the
database's shape layered on the range finder's ground) against the
database used directly (bit 2)?

### The database ground against the range finder's (tier 1)

33 flights in 31 SFD-O4 logs (log5-7, 18-21, 31-44, 61-71; the
refresh28 logs carry no RTER records), every Good downward range sample
in flight at under 20 deg of tilt and above 0.6 m. Bit 2's height above
ground error is `(-XKF1.PD - RTER) - range x cos(tilt)` on core 0, where
RTER is the SRTM height minus the EKF origin altitude
(`AP_AHRS::writeTerrainData()`); it is the EKF's altitude of the ground
under the vehicle against SRTM's. The anchor removes its value at the
last in-range moment and keeps how it changes.

- At takeoff (median over the first 5 s in range): median -0.34 m,
  |error| median 0.37 m, p90 1.40 m, worst 2.23 m (log41) and -2.20 m
  (log70). As a flow velocity scale error above the range that is 3.7%
  median and 22% worst at 10 m, 1.8% and 11% at 20 m, 1.2% and 7.4% at
  30 m.
- How much it changes in range, against the takeoff value: per-flight
  medians 0.06 to 2.37 m within 50 m of takeoff (median 0.40 m, in line
  with the 2026-10-01 0.5 m); 1.7 to 5.4 m at 50-100 m on the eight
  flights that reached it (10-24 samples each, few). This includes the
  EKF's own height drift over the flight, so it is an upper bound on
  the database's shape error. log70's 50-100 m bin (20 m) is a lookup at
  a drifted primary's position, the log61 mechanism, not the database.
- GPS altitude against SRTM ground over the same samples: per-flight
  means -5.8 to +3.3 m. The EKF origin altitude agreed with SRTM better
  than in-flight GPS did on these flights; why was not established.

So at these sites the constant part the anchor exists to cancel was
small: no larger than the part it keeps. The flights do not show the
anchor helping. They show what it costs and saves is under half a metre
here; the several-metre case (an origin altitude taken from a poor GPS
fix) is SITL only, 22-46% velocity error at 10 m with a 5 m origin
error, cancelled by the anchor (2026-10-01).

### Bit 2 against the anchor, Replay (tier 1b)

Replay built from the beta `a8487f02aa` (scratch worktree), each log
replayed with EK3_OPTIONS | 4 (bit 2) and & ~4 (the anchor); every
flight also had bit 3 (the AGL KF scales flow while it is valid).
Replay logs its own cores as C=100+, which a first pass missed. Flow
core (core 1, source set 2 on flow) horizontal velocity against GPS,
airborne, range finder not Good and the GPS core above 12 m, samples
where the flow core's position was more than 20 m from core 0's left
out; columns are more than 5 s after the last Good range reading:

| log | s | bit 2 rms / worst m/s | anchor rms / worst m/s |
|---|---|---|---|
| log5 | 14 | 0.33 / 1.2 | 0.33 / 1.2 |
| log6 | 118 | 1.77 / 7.0 | 1.77 / 7.0 |
| log7 | 87 | 1.06 / 8.8 | 1.07 / 8.8 |
| log31 | 96 | 1.09 / 3.1 | 1.07 / 3.1 |
| log35 | 94 | 0.89 / 3.1 | 0.88 / 3.1 |
| log37 | 42 | 0.68 / 1.4 | 0.69 / 1.4 |
| log41 | 16 | 0.48 / 1.0 | 0.46 / 1.0 |
| log42 | 81 | 0.88 / 2.9 | 0.87 / 2.9 |
| log32 | 38 / 43 | 3.96 / 7.8 | 4.52 / 8.6 |
| log33 | 26 | 3.75 / 6.4 | 3.74 / 6.4 |
| log34 | 34 / 24 | 3.32 / 9.3 | 2.73 / 6.4 |
| log20 | 3 / 17 | 2.70 / 3.4 | 3.41 / 6.0 |
| log61 | 30 | 3.31 / 9.9 | 3.30 / 9.9 |
| log65 | 15 / 17 | 2.81 / 6.3 | 2.88 / 6.5 |
| log69 | 11 / 10 | 3.67 / 7.8 | 3.72 / 7.8 |
| log70 | 7 / 4 | 3.99 / 7.7 | 4.43 / 7.9 |

The first eight are flights where the flow lane stayed with GPS; there
the two are within 0.02 m/s rms. The rest lose most of their samples to
the drift filter, and where the filter leaves different samples in each
run (two figures in the s column) the difference is in what is compared,
not the estimator; neither wins. Flow innovation ratios (XKF5.NI, core
1) have the same median (0-15) and p95 (1-50) in both, with at most 2%
rejected. log39 and log43 have no qualifying samples. Replay re-feeds the
terrain heights the flight looked up, at the flown primary's position,
so both arms get the same database heights; where the primary was the
GPS core that is the true position, which favours both equally, and it
says nothing about a lookup at a drifted flow lane (log61).

### What this means for SFD-O4's bit 2

Clearing bit 2 on SFD-O4 is not measurably better or worse at its sites
in Replay, because the database's absolute height there was within half a
metre of the ground the range finder measured. It would make the next
flights run the anchor in flight, which nothing has yet, and the anchor
then carries the evidence rmackay9 asked for. To show a benefit a flight
needs a large origin altitude error, which these sites did not have.

## 2026-11-04 (later): the review fixes Andy chose

Branch `r1104/33585-fix` (worktree `r1104-33585-fix`) on
`r1104/33585-restructure2` (`079eda8a1e`, on carry2 `c75fc5a173`). Local
only, nothing pushed, /pr-review owed.

Andy's decisions after the /pr-review of the restructure: move #34380's
brief-return timing fix here; log the anchored ground as XKF5.TOfs; hand
the anchored ground over to the terrain state when the anchor ends
without a range return. Plus the bot's 1.6 s flake and two comment and
message fixes.

| commit | what | folds into at push |
|---|---|---|
| `f29e662721` | AP_NavEKF3: time a flat-ground return on fused range readings (was #34380 `c411ebb3a2`) | stays its own commit |
| `0e864d3a57` | autotest: cover range readings the terrain gate rejects (was #34380 `d6b7baa236`) | stays its own commit |
| `2c87bf81dc` | AP_NavEKF3: log the anchored ground as XKF5.TOfs | `079eda8a1e` |
| `c2d4f9724a` | AP_NavEKF3: keep the anchored ground in the brief-return snapshot | `079eda8a1e` |
| `10bcc97e16` | AP_NavEKF3: hold the last anchored ground when the anchor ends | `079eda8a1e` |
| `7034d5c40d` | autotest: check the ground held once the anchor ends | stays, after the restructure |
| `9ad154f164` | AP_NavEKF3: say what flowTerrainState() returns | `079eda8a1e` |
| `847d6d90e7` | autotest: fly a brief return again when it misses its window | `9928db2fc6` |

Folding `c2d4f9724a` ahead of `f29e662721` may need a trivial context
fix in updateFlatGroundAssumed(). Message rewords drafted in the session
scratch: `86f0549fc3` "as the commit below moves" becomes "as
#CARRY_PR moves"; `079eda8a1e`'s message is rewritten for the folded
result.

### The snapshot change, not asked for

`c2d4f9724a` goes beyond the three decisions. The restructure kept the
held terrain state in the brief-return snapshot and worked the anchored
ground out again in the descent check from the latest terrain height,
which a reviewer flagged as a second copy of the anchor formula and an
unflown change to that check. Saving flowTerrainState() in the snapshot
restores the descent check line to the pre-restructure code exactly and
makes an undone return put the anchored ground back, as before. Derived
from the source; the log61 Replay below covers it only where the flight
reached it.

### The hand-over

A flag (`terrainAnchorInUse`) records whether the anchor was in use at the
last update; when it stops being used and no range sample was fused in
the last 500 ms, the anchored ground is copied into the terrain state
once. terrainAnchored() also now requires optical flow in a source set,
as the old write did, so removing flow from the source sets is one of
those transitions. SITL (tier 2), EK3_OptflowAnchoredTerrain's new leg
(bit 2 set in flight after 8 m of rising ground, 5 s hold, XKF5.HAGL
against SIM.Alt - TERR.TerrH):

| build | worst error after the anchor ended |
|---|---|
| without the hand-over: `c2d4f9724a`, with `7034d5c40d`'s test | 7.9 m, fails at 3 m |
| with it: `10bcc97e16`, the head `847d6d90e7`, `r1104/34380-3` | 1.4 m, 1.2 m, 1.5 m |
| pre-restructure `95a93964b2` plus the timing fix | 1.2 m |

### Replay of log61 (tier 1b)

log61 (SFD-O4, 3408138/639) through master-based Replay builds of the
pre-restructure code plus the timing fix (`95a93964b2` + `f29e662721`),
the head (`847d6d90e7`), and the head less the hand-over. EK3_OPTIONS 90
(bit 2 off, the anchor in use from 175.6 to 300.4 s) and 94 (as flown):

| comparison | 90 | 94 |
|---|---|---|
| pre-restructure + timing fix against the head | 5 bytes, all OF | 3 bytes, all OF |
| head against head less the hand-over | 6 bytes, all OF | 5 bytes, all OF |

Every EKF record, XKF5 included, is byte-identical: with TOfs logged from
flowTerrainState() the 1049 XKF5 records that differed at `17833af182`
no longer do, and the hand-over never fires in this flight (the anchor
ends on range returns). The OF bytes are the Replay timing artefact seen
before; 90 against 94 differs in 152622 bytes across XKF1-5, XKQ, XKFM,
XKTV, which shows the comparison sees EKF changes.

### What still differs from the anchor writing the terrain state

Derived from the source: while the anchor is in use the terrain state is
the ground held from before it. The range finder height switch reads it
but cannot act above the range; with EK3_FLOW_USE 2 the terrain
estimator's flow fusion starts from it; the clamp keeping the terrain
state below the vehicle no longer applies to the anchored ground once
terrain data has stopped.

### Tests at `847d6d90e7` (tier 2)

- EK3_OptflowAboveRangefinder 5 of 5, no retries needed (1.6 s case
  measured 1.4-1.6 s). With its window narrowed to 1.60-1.61 s it flew
  the case three times and failed "proves nothing", so the retry path
  runs and cannot pass a case that never meets its window.
- Pass: EK3_OptflowAnchoredTerrain (8.1 m rise, 0.3 m, speed 1.011),
  EK3_TerrainStateFollowsHeightReset, FollowsDatumReset,
  HeldOnDriftReset (2.2 m), FollowsSourceChangeAboveRange,
  OpticalFlowLimits, OpticalFlow, OpticalFlowLocation,
  EK3_OptflowTerrainScaleHeight, BaroGroundEffectRangefinderSwitch,
  Replay.
- Copter, plane, rover and sub build; copter with
  EK3_FEATURE_OPTFLOW_SRTM 0, EK3_FEATURE_OPTFLOW_FUSION 0 and
  AP_RANGEFINDER_ENABLED 0 each. Mechanical gate clean against carry2;
  check_branch_conventions.py passes.
- #34380 restacked without the two moved commits: see `../34380/`.

## 2026-11-04 (late): round-two fixes and the fold for push

Round two of the review (one Claude reader, six Codex tasks) at
`847d6d90e7` found nothing that must change. Should-fixes applied on
`r1104/33585-fix`, then the branch folded into `r1104/33585-final`:

- `terrainAnchorInUse`'s comment says what it holds (terrainAnchored() at
  the last update), not that flow was scaled by the anchored ground.
- `anchoredTerrainState()` is the one place `terrainAnchorOffset -
  terrain_srtm_alt` is written; flowTerrainState() and the hand-over use
  it. Comments now say the terrain state is also written at the hand-over
  and by an undone brief return, and that what falls back at the
  hand-over is the ground the limits, flat-ground checks and XKF5 read
  (and flow where no other height scales it); the folded message names
  the range finder becoming the height source as a fourth trigger.
- XKF5 TOfs goes through float_to_int16() as HAGL does. Master casts
  terrainState with `(int16_t)` and no saturation; the anchored ground
  can lie further from the origin, so it is likelier to need it.
- EK3_OptflowAnchoredTerrain checks that XKF5 TOfs less HAGL follows
  XKF1 PD over the traverse (its spread, since PD is the output
  observer's): 0.03 m at the head; 8.27 m with TOfs logging the terrain
  state held from before the climb, which fails the 1 m check.
- The brief-return retry restores SIM_SONAR_SCALE, and EK3_SRC1_VELXY in
  the drop-flow case, with an acknowledged set after each flight, so a
  lost unacknowledged restore cannot compound across attempts.

Tests at `69cbfa2176` (tier 2): EK3_OptflowAnchoredTerrain (rise 8.1 m,
worst 0.3 m, speed 1.010, TOfs spread 0.03 m, 1.5 m after the anchor
ends), EK3_OptflowAboveRangefinder 3 of 3 with no retries, the four
datum tests, OpticalFlowLimits and Replay pass. Replay of log61 at
EK3_OPTIONS 90 and 94 through Replay built at `69cbfa2176` against the
one built at `847d6d90e7`: every EKF record identical (8 bytes of 33 MB
differ, outside the EKF records).

The fold (`r1104/33585-final`, on `r1104/33585-carry2`), one cherry-pick
group per commit, copter built at each: `34fedc1b50` AP_DAL, `638be3258d`
AP_NavEKF, `4f913ceab6` keep flow nav alive (with the freshness comment
and the `#CARRY_PR` reword, placeholder still in), `be7d7a34f7` the
above-range tests (with the retry and the acknowledged restore),
`711ba1116e` the anchored speed check, `927f8db52a` the restructure (with
the TOfs, snapshot, hand-over, comment and helper fixes and the updated
message), `b60954a47f` and `d9ce030040` the moved timing fix and its
test, `94f37c4e0f` the hand-over test with the TOfs check. `git diff
r1104/33585-fix r1104/33585-final` is empty; range-diff pairs every
commit, the timing fix differing only in context. Gate clean against
carry2; check_branch_conventions.py passes. Not pushed.

## 2026-11-04: pushed after the dev call rework

Force-pushed `6dcb4f2b2d` -> `79800dbe59` (twelve commits: #35014's three, then nine), built as `r1104/33585-push`, tree-identical to `r1104/33585-final` with #35014's number in the one message that names it. Reviewed in three rounds (Claude reviewers and Codex cold reads, audit 7 closed, the rest maintainer design points or disclosed limits; round three found only that no test drives TOfs into saturation). All #33585 tests pass at the final head; copter, plane, rover and sub build, and copter with EK3_FEATURE_OPTFLOW_FUSION, EK3_FEATURE_OPTFLOW_SRTM or AP_RANGEFINDER_ENABLED off. Description and the five replies to rmackay9 drafted, not yet posted.

Description replaced 2026-11-04 (the stack on #35014, the evidence tier, the head's numbers, the restore and bound paragraphs, the known limits; the previous body is not archived on the PR). Replies posted to rmackay9's five dev call comments: (a) https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4469311438 (b) https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4469311955, correcting the earlier "in my testing" to say the comparison was SITL and giving the 33-flight offset and the 16-log Replay (c) https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4469312291 (d) https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4469312721, offering the EK3_TERR_GRAD tie or opt-in flat ground (e) https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4469313167. Open with rmackay9: (b) whether the anchor stays, (c) the restore, (d) the bound.

## 2026-11-04 (night): AP-Review at `79800dbe59`, the anchor hand-over

AP-Review, COMMENT
(https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-6635357075):
one minor, the same finding as #34380's should-fix of the same evening.
Fixed, together with #34380's minor on the stimulus checks in
EK3_OptflowAboveRangefinder.

The hand-over. When the range finder becomes the height source while the
anchor is in use (a source set with range finder height, then a descent
back into range), selectHeightForFusion() forms the range height against
the terrain state, which still holds the ground from before the anchor,
and resets the height to it. SelectFlowFusion() writes the anchored ground
in one step later, so the height above ground steps by the difference
until a height timeout reset. The fix writes anchoredTerrainState() into
the terrain state and ends the anchor in selectHeightForFusion(), after
this step's source is chosen and before the range height is formed. Once
the anchor is ended the later SelectFlowFusion() hand-over finds nothing
to do.

`r1104/33585-r4` on `r1104/33585-carry3` (`fb335374dd`, #35014 with its
fix), not pushed:

- `131e45c62b` AP_NavEKF3: hand the anchored ground over before range
  height is formed. Fold into `22ad1aa947` "choose the anchored flow
  height in FuseOptFlow()" (was `b490318ffc`; the restructure is not on
  the beta, so it is unflown).
- `f28d923b5a` autotest: retry the range finder bands in
  EK3_OptflowAboveRangefinder. The 4.8-5.5 m leg after a climb out and
  back, and the 5.8-7.9 m open loop climb with no height source, are
  flown up to three times, with a force disarm and reboot after a miss,
  as the brief returns already are. Fold into `65e6d04ee9` "cover optical
  flow nav above the rangefinder range" (was `e2cc5b54a7`).
- `af48119e41` autotest: EK3_OptflowAnchorToRangeHeight. Terrain on, an
  8 m range finder, origin set with no GPS. It climbs to 30 m under baro
  height, traverses 100 s over ground about 10 m higher, switches to a set
  with range finder height and descends into range: XKF5 HAGL must stay
  within 2 m of SIM truth for 15 s. Without the fix, -8.8 m and relative
  position lost; with it, -0.3 m (tier 2). Own commit.

Range-diff against `79800dbe59` pairs all nine earlier commits: seven
`=`, and `2dc5af4764` (keep flow nav alive) and `22ad1aa947` (the
restructure) differ only where #35014's fix conflicted in
getHeightControlLimit(), resolved to the unconditional subtraction
(`height -= terrainState`, then `height -= flowTerrainState()`). r4 replaces `r1104/33585-r3` (same tree) to shorten
two subjects that the gate flagged.

Tests at r3 `ddc9c1f43a` (tree identical to r4), tier 2:
EK3_OptflowAboveRangefinder, EK3_OptflowAnchoredTerrain (rise 8.2 m,
worst 0.3 m, speed 1.010, TOfs spread 0.02 m, 1.4 m after the anchor
ends), EK3_OptflowAnchorToRangeHeight (-0.2 m), the four datum tests,
EK3_FlowHeightLimitAfterRangeFallback, OpticalFlowLimits, OpticalFlow,
BaroGroundEffectRangefinderSwitch and Replay: all 12 pass.

Replay of log61 (tier 1b), at EK3_OPTIONS 90 and 94, through Replay built
at r3 against Replay built at `r1104/33585-final` (tree-identical to the
pushed head): 0 EKF records (C >= 100) differ at either setting. Mechanical
gate clean against carry3; check_branch_conventions.py passes.

## 2026-11-05: the two review fixes folded (`r1104/33585-r5`, not pushed)

Rebuilt by cherry-pick on `r1104/33585-carry3`: `131e45c62b` (the
hand-over) folded into the restructure, now `2f02cfd690`, its message
gaining a paragraph on the hand-over with the -8.8 m / -0.3 m SITL
numbers; `f28d923b5a` (the band retries) folded into the test, now
`23a783c47f`, with one sentence. Tree identical to r4; range-diff shows
only the folds and those message lines. Copter SITL builds at
`2f02cfd690`, the only commit whose C++ changed (the later ones add tests
only). Mechanical gate clean against carry3; check_branch_conventions.py
passes. Head `1cf2ecd440`.

Pushed 2026-11-05 (force, `79800dbe59...1cf2ecd440` on
`pr-optflow-flat-ground`), the folded r5 on #35014's new head. Reply
posted:
https://github.com/ArduPilot/ardupilot/pull/33585#issuecomment-6654940173

## 2026-11-07: bit 2 off in Replay of SFD-O4 logs 87-88 (tier 1b)

The SFD beta (refresh13 topup1) carries this PR at `1cf2ecd440`. Replay
of SFD-O4 log87 (3408138/699) and log88 (3408138/701), flown with
`EK3_OPTIONS` 94 (bit 2 set, so the anchor bypassed), again with 90 (bit
2 clear, so the anchor can engage; whether it did was not checked). Core
1, the flow lane, through ACRO mostly above the 15 m range finder,
against core 0 (GPS): median velocity error 6.84 -> 6.71 m/s on log87 and
3.41 -> 3.49 m/s on log88; position error at the end of the window 127
-> 160 m and 174 -> 314 m. Neither height path helps; the error comes from
the time past the 45 deg flow tilt gate (#34941's record, 2026-11-07).

## 2026-11-10: above a 15 m range finder on a customer quad (tier 1)

Beta `7b00f3b5`, one IMU, ARK Flow and its 15 m AFBR range finder on
DroneCAN, no GPS. log16 (1245450/44, replays exactly) was out of range
high 251.8-265.0 s, the range 15.7-17.3 m, in LOITER.

- The AGL KF stayed valid on its 5 s coast to 256.8 s, reading 1.0-1.3 m
  below the range: its velocity decayed while still integrating the
  climb's deceleration (-0.48 against the EKF's -0.08 m/s), so the flow
  was scaled about 10% low meanwhile (from the source; hypothesis).
- After that the flat-ground height (terrain offset frozen at -0.82 m)
  tracked the range within 0.1-0.9 m and aiding held: EKF speed against
  flow x range 0.98 over 24 windows, against 0.99-1.02 in range.
- When the range came back the terrain offset re-anchored by 0.48 m.

## 2026-11-12: above a 15 m range finder in ACRO, SFD-O4 logs 89-90 (tier 1)

Core 1 is the flow lane beside a GPS lane (`EK3_SRC_OPTIONS` 8), not
primary in these segments; its velocity is compared with the GPS lane's
every 0.1 s. log89 (3408138/707, `56d1905e`), 158 s of ACRO to 45 m and
22.8 m/s, much of it above the range: median 1.6 m/s apart (p95 3.5, max
4.9), and its height up to 2.75 m below the GPS lane's. In the Loiter
that followed at 20-30 m, above the range: median 1.1 m/s (p95 4.9, max
6.0, at 11-13 m/s). log90 (3408138/711, refresh15 `c42bd1fb`), 94 s of
ACRO to about 28 m, mostly inside the range: median 0.68 m/s (p95 2.4,
max 3.2). This is the drift the boot message warns of ("rangefinder max
15m, flow above may drift"), measured; nothing here flew on it.

## 2026-11-13: range finder height (`EK3_SRCn_POSZ` 2), reviewed and pushed as `833e3b3276`

Range finder height was a hole. With `EK3_SRCn_POSZ` 2 the terrain
estimator is skipped, so `gndOffsetMeasured` never latched and the
fallback never engaged (the round-seven note above left it out of that
round). Replay of the customer quad's log16 (1245450/44, see 2026-11-10)
with `EK3_SRC1_POSZ` overridden to 2, on the `1cf2ecd440` code (tier
1b): relative position dropped at 246.8 s on the climb above the 15 m
range finder. As flown, with baro height, the flight never reaches it.

Two commits on top, reworked after a full `/pr-review`:

- `2c094ce5b1` hold range finder height off while flow holds the ground.
  With range finder height the range finder took the height back on its
  first fresh reading and reset the height to it, so a return from
  something passed over above the range moved the height onto it. While
  flat ground is engaged the height stays on baro; the fallback ends
  after 2 s of fused range and the range finder takes the height then.
- `8155747547` let flat ground engage under range finder height. A step
  whose range height passed its innovation check (`rangeDataToFuse`,
  the range finder both active and configured, `lastHgtPassTime_ms ==
  imuSampleTime_ms`) counts as measuring the ground: it latches
  `gndOffsetMeasured` and sets `gndKnownNE` and `lastGoodRngMeas`.
  `gndHgtValidTime_ms` is not touched.

The first version of the second commit (`e68e4bd4d8`, never pushed) set
`gndHgtValidTime_ms` and `lastGoodRngMeas` in `EstimateTerrainOffset()`'s
skip branch. The review found that it held `gndOffsetValid` (and with it
`EKF_POS_VERT_AGL`, `getHAGL()` and flow relative position) for 5 s
after the fallback to baro, overlapping #34851; counted samples the
height gate had rejected; and made anchor creation depend on a timing
window. Replay showed the first (tier 1b): at touchdown in log16 with
POSZ 2 it kept relative position until 284-286 s, where `1cf2ecd440`
and the rework drop it by 280 s (2 s samples). The rework never
anchors from range height.

The hold changed what `EK3_OptflowAnchorToRangeHeight` covers. Under
flow navigation the terrain estimator now measures the ground, ending
the anchor, before the range finder takes the height, so the hand-over
in `selectHeightForFusion()` was no longer reached: with it removed the
test still passed at -0.3 m. The -8.8 m of 2026-11-04 (`af48119e41`) is
from before the hold. A second flight in a source set without flow
reaches it again. In that flight the XKF5 HAGL check alone does not see
the hand-over missing (worst -0.7 m), because HAGL stays consistent
while the vehicle flies down; the height-step and holding-height checks
added with it do.

Measured, tier 2, SITL, on the code pushed as `833e3b3276` unless a
head is named; "fix removed" is a mutation of that code:

| test, leg | with the fix | fix removed |
|---|---|---|
| AboveRangefinderRangeHeight, climb out of an 8 m range | relative position held | lost at about 8 m, EKF failsafe (at `1cf2ecd440`) |
| same, 1 s return of 2.5-3.5 m at 20 m, XKF1 against SIM | height moved 0.04 m, 15-16 readings in band | hold removed: -18.7 m. First `e68e4bd4d8` without the hold: 9.4 m, on relative_alt in an earlier version of the test |
| same, back in range at 5 m, 5 m baro drift | vehicle stayed at 5.37-5.38 m, baro +0.64-0.66 hPa | fallback never ending: followed the baro to 6.91 m |
| same, range lost at 5 m | refused (flags 39) | last good reading check removed: held |
| same, climb out | held | last reading not recorded under range height: lost |
| AnchorToRangeHeight, flow (SRC2, LOITER) | HAGL -0.2 to -0.3 m, height -0.2 m, baro +0.67 hPa | hand-over removed: -0.3 m, passes |
| same, no flow (SRC3, ALT_HOLD) | HAGL -0.6 m, height -0.5 m, held 3.4-3.5 m, baro +0.63 hPa | hand-over removed: height stepped -8.7 m (ground rose 8.0 m), flew into the ground |
| AboveRangefinder, range lost after a climb out, descent to 2.4-3.0 m | refused | height limit removed: held |
| same, brief return held 1.65 s, 1.7-1.95 s window | not taken as the ground; 1.9 s on the first attempt, 3 runs | end timed on the clock: taken as the ground at 1.7 and 1.9 s |

The descent leg replaced one at 2.5 m that the last good reading check
refused on its own, so it could not fail with the height limit removed.
The 1.6 s case's old 1.6-2.0 s window sat on both thresholds; 1.7-1.95 s
with five attempts is what replaced it. Each of fourteen flow, terrain
and range finder tests, `EK3_RNG_USE_HGT` among them, passed on the
pushed C++ with its pushed test code.

Replay of log16 at the rework (tier 1b): as flown, every record is
byte-identical to `1cf2ecd440`. With POSZ 2, relative position held
248-258 s above the range where `1cf2ecd440` dropped it, and dropped at
touchdown at 280 s as `1cf2ecd440` does.

Also in this push: "landing" corrected to "disarm" in two comments and
in the core commit's message (EKF3 `onGround` is `!motorsArmed` on both
`detectFlight()` branches); `updateFlatGroundAssumed()` described above
its definition; the four copies of the EKF flag read, three of the
terrain tile wait and two of the rising-ground traverse made methods.

Rejected: the quick review's cold read said `SelectFlowFusion()`'s
magnetometer deferral could miss the range height bookkeeping in a step
`SelectVelPosFusion()` had fused. Both are called unconditionally in the
same `runUpdates` block and defer on the same test
(`magFusePerformed && dtIMUavg < 0.005f` and their own flag), so they
defer together; the terrain estimator's existing range fusion relies on
the same.

Pushed 2026-11-13, force `1cf2ecd440...833e3b3276`. Rewritten, old to
new: `7ab5467649` `dbd53233b4` (message only), `23a783c47f`
`8010498c5b` (the two legs above, message), `b968e0ff2e`
`4c88fcf711`, `2f02cfd690` `c80a3845da`, `8bb9b58062` `405349e057`
(comments), `143a175526` `0a3bcda601`, `1cd6570c02` `8fd57cc9ee`,
`1cf2ecd440` `fe50276196`; new
`2c094ce5b1`, `8155747547`, `55e7a8551d`, `047ac1a7fa`, `833e3b3276`.
#35014's five commits are unchanged. The PR description was updated the
same day: range finder height in the summary and a detail paragraph, and
the Replay line.

Flight status: the two EKF commits are unflown; the SFD beta carries
this PR at `1cf2ecd440`. Not run: range finder height with terrain data,
the feature-off builds since the rework, any board but SITL.

Open: peterbarker's review of 2026-11-11 (six comments, answers drafted,
none posted; three need code: the `optflow_enabled()` rename, the
`20.0f` constant, the one-shot warning); #35014's four review items.

## 2026-11-13 (later): peterbarker's review answered, pushed as `e6600ca1f1`

peterbarker's six comments of 2026-11-11 answered, three of them in
code, as replies on each inline comment:
https://github.com/ArduPilot/ardupilot/pull/33585#discussion_r4569252565
and the five after it.

- The rename he suggested, `optflow_enabled()` to
  `optflow_enabled_on_any_source()`, folded into the commits that added
  the function and its three callers (`a0166ebf95`, `197b465ba7`,
  `8b7b156247`), each built on its own. No behaviour change.
- The flow drift warning, as its own commit `08d9ca53a2` on top, since
  the boot warning has flown (the message is in SFD-O4 log89, see
  2026-11-12):
  - once each time the motors arm, rather than once 5 s into boot. The
    trigger is the soft-armed flag, so a motor test counts too; a range
    finder that appears late warns once it is there.
  - under 11 m rather than 20 m. The 6 m SRTM figure behind 20 m had no
    good source; the record's tier-1 figure, the database's error
    changing by 3.4 m (p90) between points 50-100 m apart (2026-10-01,
    SFD-O4 logs 5-17), is 30% of 11 m, and 30% remains a judgement.
    Vehicles with 11-20 m range finders, the 15 m ones among them, no
    longer warn.
  - not under 2.86 m, where there is no fallback, unless bit 2 is set
    with terrain support compiled in. The 2.86 m test is shared with
    the fallback as `rngMaxAllowsFlatGround()`.
  - Left as it is: with bit 2 set, terrain support compiled in and
    `TERRAIN_ENABLE` 0, a range finder under 2.86 m still warns; the EKF
    cannot see that terrain is disabled.

Measured, tier 2, SITL, on the code pushed as `e6600ca1f1`:
`EK3_OptflowAboveRangefinder` passes, with the 8 m warning at all 19
armings and never at 2 m or 11 m. Fix removed: decided while disarmed,
it fails "went out before arming"; once per boot, no warning at the
second arming; without the 2.86 m test, it warns at 2 m; with a 12 m
threshold, it warns at 11 m. Copter builds with each of
`EK3_FEATURE_OPTFLOW_FUSION`, `AP_RANGEFINDER_ENABLED` and
`EK3_FEATURE_OPTFLOW_SRTM` off (full rebuilds, the define confirmed in
`hwdef.h`), the last again after the bit 2 term changed. That closes
"the feature-off builds since the rework" in the entry above.

Review. A quick review before the push found four things in the first
version, which checked only on the disarmed-to-armed step: a late
DroneCAN range finder got no warning all flight; "at each arming"
overstated the soft-armed trigger; the 11 m test leg configured 15 m;
no second arming was tested. All fixed. The re-review's audit closed
them and peterbarker's "why 30%" point; its cold read found the bit 2
term warning with terrain support compiled out, fixed. Rejected: "the
amend! commits have invalid subsystem prefixes"; they were squashed
before the push.

The replies: the RTER record needs no timestamp, as the EKF stamps
terrain data on arrival and Replay feeds it back at the same point in
the frame sequence, at most 70 B/s and only with `LOG_REPLAY`; the
rename, the "relative error" comment, the one-shot and the 20 m point
each name the commit. On the label: #35014 was split out of this PR
after DevCallEU went on here and should carry it instead. peterbarker
took the label off this PR on 2026-11-11; #35014 does not have it yet.

The PR description's paragraph on the warning was updated the same day.

Pushed 2026-11-13, force `833e3b3276...e6600ca1f1`. Rewritten, old to
new: `4beeb51492` `a0166ebf95` (renamed, message), `dbd53233b4`
`197b465ba7` (callers), `8010498c5b` `34f9074f8b`, `4c88fcf711`
`d7735909bf`, `c80a3845da` `8b7b156247` (caller), `405349e057`
`53d1ade829`, `0a3bcda601` `21f9076020`, `8fd57cc9ee` `7232aa09b0`,
`fe50276196` `8069fd83d7`, `2c094ce5b1` `f211e98080`, `8155747547`
`08b25c9121`, `55e7a8551d` `11087b5a94`, `047ac1a7fa` `b74d83b790`,
`833e3b3276` `bb475612b5`; new `08d9ca53a2`, `e6600ca1f1`. #35014's
five commits and `18dd1828f8` are unchanged.

Open: #35014's four review items, and DevCallEU on #35014. The two
range finder height commits and the warning commit are unflown.

## 2026-11-13 (night): restacked on #35014's review fixes, `7b5453dd35`

#35014 was reordered and two of its tests strengthened (its record,
2026-11-13 later). This branch was rebased onto it with no conflicts:
all 17 of its own commits are patch-identical (`git range-diff`), and
its tree is the previous head's plus exactly #35014's test changes. It
builds, and EK3_TerrainStateFollowsDatumReset (0.50 m at the range
finder return) and EK3_FlowHeightLimitAfterRangeFallback (6.05 m step,
13.1 m) pass on it. Pushed 2026-11-13, force
`e6600ca1f1...7b5453dd35`. #34380 still sits on `1cf2ecd440` and needs
restacking onto this head.

## 2026-11-14: AP-Review at `7b5453dd35`; the EK3_RNG_USE_HGT hold and the retries, pushed `9709e5fd42`

AP-Review (COMMENT, 2026-11-14 01:59). Three commits on top, unflown,
fast-forward `7b5453dd35..9709e5fd42`:

- `4eb6efe39e` AP_NavEKF3: hold EK3_RNG_USE_HGT off while flow holds the
  ground. The should-fix: the automatic switch to range finder height now
  waits for the flat-ground fallback to end, as the configured range
  finder height does since `c8b579277e`.
- `f8dbff27e9` the leg, in EK3_OptflowAboveRangefinderRangeHeight: baro
  height, EK3_RNG_USE_HGT 70, LAND above an 8 m range finder, a 1 s return
  reading 1.9-2.5 m. The brief-return leg's measurement became a helper
  both use.
- `9709e5fd42` the minor: a wait_altitude() timeout in the three retry
  loops (EK3_OptflowAboveRangefinder twice, the range height test once) now
  counts as a missed attempt instead of leaving the retries.

What the switch does without the hold (tier 2, SITL, read from the log):
it is taken, but it does not step the height. Under baro height the
terrain estimator fuses the first return first, and as its ground is 5 s
stale it resets the terrain state onto the object, so the range height
formed against it agrees with the EKF height at the switch. XKF5.RI then
freezes, as only the terrain estimator writes it. In SITL the scaled range
reading follows the vehicle down at an eighth of its rate, so the range
height then lags truth (1.08-1.16 m by the end of the return); over a
fixed object the height would follow the object's top instead, until the
reading changes again. So the leg checks the switch itself: the number of
distinct XKF5.RI values over the return's last 0.6 s. With the hold, 5-6
in three runs (height moved 0.22-0.29 m); without it, 1, and the leg fails
"the range finder took the height on a brief return in a landing". A first
version of the check counted values over the whole return; a Codex cold
read pointed out a switch part way through would pass it, so it reads the
end of the return, and a 0.4 s window (4 values against a threshold of 3)
was widened to 0.6 s for margin.

Tests at `9709e5fd42`, tier 2: EK3_OptflowAboveRangefinderRangeHeight,
EK3_OptflowAboveRangefinder, EK3_RNG_USE_HGT,
BaroGroundEffectRangefinderSwitch, EK3_OptflowAnchorToRangeHeight,
EK3_OptflowAnchoredTerrain, EK3_FlowHeightLimitAfterRangeFallback and
EK3_TerrainStateFollowsDatumReset pass; copter and plane build.
`/pr-review --quick`: gate clean (notes only), Codex audit CLOSED on both
findings, cold read's one finding fixed as above. Pushed 2026-11-14.

Interaction with #34851, found while answering #34380's round (that
record): #34851 keeps `gndOffsetValid` 5 s after range finder height
ends, and this PR's fallback waited for `gndOffsetValid` to drop before
engaging, so with both the hold on range finder height started 5 s late
after a climb out (a return 2 s after the range was lost moved the height
7.3 m). #34380 carries #34851 and the fix (`02ea1b667c`: the fallback
engages on the terrain estimator's or range height's ground, not on
`gndOffsetValid`). Whichever of this PR and #34851 merges second takes it.
