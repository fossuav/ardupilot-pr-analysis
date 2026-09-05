# PR #33585 - Keep optical flow nav alive above the rangefinder range (EKF3)

Analysis archive for [ArduPilot/ardupilot#33585](https://github.com/ArduPilot/ardupilot/pull/33585).
Branch `pr-optflow-flat-ground` (andyp1per fork), head `62a3fbeaba`
(2026-09-05), base `master`. Stacked on #33478 (`../33478/`), whose three
commits are the first three on the branch.

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
| `OptflowAssumeFlatGnd` from the `writeTerrainData` gate | "Terrain data is preferred and does not need bit 2" |

All three confirmed on 2026-09-05. A leg asserting the bit 3 + bit 5
combination was
written and then removed: it could not have failed differently from the
bit-5-only leg, because `flatGroundAssumed()` does not reference the AGL KF and
both 5 s windows expire together. Its measurement is in the analysis topic.

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
