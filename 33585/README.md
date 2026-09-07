# PR #33585 - Keep optical flow nav alive above the rangefinder range (EKF3)

Analysis archive for [ArduPilot/ardupilot#33585](https://github.com/ArduPilot/ardupilot/pull/33585).
Branch `pr-optflow-flat-ground` (andyp1per fork), head `0d996214f9`
(2026-09-07, two commits after the review fold; PR still at `f266fd0fd9`), base
`master`. Stacked on #33478 (`../33478/`), whose three
commits are the first three on the branch. Head was `62a3fbeaba` until the two
autotest fixes of 2026-09-05 below.

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
