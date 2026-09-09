# PR #33585 - Keep optical flow nav alive above the rangefinder range (EKF3)

Analysis archive for [ArduPilot/ardupilot#33585](https://github.com/ArduPilot/ardupilot/pull/33585).
Branch `pr-optflow-flat-ground` (andyp1per fork), four commits as of
2026-09-09 (`535cfca48f`, `e98741fbb2`, `9afa402696`, `4d9c92035b`) plus
round seven's unfolded fixups; PR still at `f266fd0fd9`. Base `master`.
Stacked on #33478 (`../33478/`), whose three commits are the first three on
the branch.

## Status (one line)

`EK3_OPTIONS` bit 5 (`OptflowAssumeFlatGnd`) holds `horiz_pos_rel` above the
rangefinder ceiling instead of tripping a spurious EKF failsafe. Replay
validated on a real flight before submission (see
`../../analysis/topics/dow_althold_ekf_failsafe.md`); the authorisation guard
around it was rewritten twice after review and each term now has an autotest
leg confirmed to fail without it.

## The problem and the fix

Both are in the analysis topic, not here:
`../../analysis/topics/dow_althold_ekf_failsafe.md` carries the log308
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
  which `../../analysis/topics/dow_althold_ekf_failsafe.md` establishes and
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

- The log308 Replay in `../../analysis/topics/dow_althold_ekf_failsafe.md` was
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

The design rationale in `../../analysis/topics/dow_althold_ekf_failsafe.md` held that
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
`analysis/logs/logm2_log4.md` rather than against memory: the message said the core
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

## What is here

```
33585/
  README.md          <- this file
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
