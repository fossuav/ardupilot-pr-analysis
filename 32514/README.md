# PR #32514 - Expect a position in the EKF failsafe only where the mode or source set needs one

Analysis archive for [ArduPilot/ardupilot#32514](https://github.com/ArduPilot/ardupilot/pull/32514).
Retitled 2026-09-29; it was "Reset the EKF failsafe gate on a source-set
change". Branch `ekf-check-source-reset` (andyp1per fork), base `master`,
head `b1743055b1` (2026-09-29). Earlier heads: `b936c14b09` (2026-06-27),
rebased to `8c2114bfc1` on 2026-09-29, then redesigned the same day. No logs
committed; the field numbers are from real throws on the first design.

> **Read this before changing the code.** The design was replaced on
> 2026-09-29. See "Measured and rejected" for the designs that lost, and
> "Review findings" for what the old design got wrong. Every field number
> in this file was taken on the first design or without the PR, never on
> the current head.

## Status (one line)

Open, awaiting review. Four commits: the gate reset, a 12 s holdoff for the
EKF's aiding-mode transition, the EKFSourceSetFailsafe autotest, and
clearing a failsafe latched under the old set. Flown on the SmallFastDrone
4.7 branch on every throw since 2026-03; the 4.6 branch without it shows
the failure.

### Superseded 2026-09-29 by the redesign at b1743055b1

Open, awaiting review, head `b1743055b1`. Four commits, each builds:

- `99da93395d` AP_NavEKF3: `has_horiz_pos_vel_source()`, true when the
  primary core's source set has a horizontal position source, or a
  horizontal velocity source it fuses via `useVelXYSource()` (which counts
  the other sets' velocities under EK3_SRC_OPTIONS bit 0).
- `5a2e2e77cf` AP_AHRS: pass-through; EKF3 only, every other backend
  answers true, so nothing changes without EKF3.
- `0f08e17d82` Copter ekf_check: a missing position counts only if
  `flightmode->requires_position()` or the AHRS query is true, plus a 12 s
  holdoff on a missing position after a source set change.
- `b1743055b1` autotest: EKFSourceSetFailsafe rewritten with four legs.

None of the first design's commits survive; the line above describes
`b936c14b09`/`8c2114bfc1`, and the redesign has not been flown. rmackay9
objected to the first design in principle: the failsafe should fire, and
it takes no action in non-position modes anyway. The redesign answers the
first half for modes that need a position. It still leaves the failsafe
quiet in ALT_HOLD/STABILIZE on a set with no horizontal source, which is
now the intended behaviour.

### Superseded 2026-09-30: holdoff dropped (local, not yet pushed)

Local head `23c4bace02` over `b1743055b1`, carrying fixup and amend!
commits still to be autosquashed. AP-Review's third round (2026-09-30, on
`b1743055b1`) found the QURT build broken by a braced-list range-for, LAND
flying on position left without a failsafe, and the holdoff applying to
switches to a set with no source. The first two are fixed. The third
turned into dropping the holdoff: it had no measurement behind it and
nothing covered it (see "Holdoff A/B" below). What is left:

- `position_expected = requires_position() || landing_with_GPS() ||
  has_horiz_pos_vel_source()`; nothing else in ekf_check changes.
- EKFSourceSetFailsafe rewritten to five legs, each shown to fail with
  its term removed (see "Mutation A/B" below).

"A 12 s holdoff for the EKF's aiding-mode transition" in the status line
above, and the holdoff bullets in the redesign section below, describe
`b1743055b1`, not this head.

Pushed 2026-09-30 as `752a4bab8b`, autosquashed onto the same base
(`26c7363f64`); tree identical to the local head `1a1e62f1da` that the
round-3 numbers below were taken on, every commit builds for SITL copter.
Old to new: `99da93395d` -> `bfbd9d9382` (AP_NavEKF3), `5a2e2e77cf` ->
`fec5baecc3` (AP_AHRS), `0f08e17d82` -> `fb3dfea8ab` (Copter),
`b1743055b1` -> `752a4bab8b` (autotest).

## The problem

ekf_check latches has_ever_passed once position is available. An
intentional switch to a source set with no position (THROW_SRC_INI on a
GPS vehicle, or the RC/Lua/MAVLink selector on a flow vehicle) then reads
as a loss of position and the failsafe fires within 1 s of the switch.

### Restated 2026-09-29 for the redesign

The problem is unchanged; the PR description now leads with the RC
selector case (a compass-and-baro set for flying ALT_HOLD indoors) rather
than the throw. See "Open: THROW_SRC_INI under the redesign" below: the
throw case is no longer obviously covered.

## The conclusion and why

Treat a source-set change as a new start for the gate. On a MambaH743v4
quad without the fix (log3/log4, not committed) the failsafe fired within
1 s of the throw-entry switch with SV=0.00 and SP=0.00: the filter was
healthy, only has_position had dropped. On a MicoAir743v2 quad on the 4.6
branch (log22) the same switch at 159.2 s produced "EKF variance: position
lost" at 160.2 s while disarmed, then "EKF3 core 0 unhealthy" at 202.9 s,
and the pilot waited 145 s before the first arm. With the reset, the
identical configuration on the 4.7 branch produced no failsafe on the next
session (drop session 2, log2), none on a flow vehicle with
THROW_SRC_INI=3, and none across seven throws in a later session.

### Superseded 2026-09-29 by the redesign at b1743055b1

"Treat a source-set change as a new start for the gate" is withdrawn. It
reset has_ever_passed and fail_count, so one switch to a set whose
position never came back disabled the failsafe for the rest of the flight
(see "Review findings"). The redesign keeps has_ever_passed latched and
changes what counts as a failure instead:

- `checks_passed = !over_threshold && (has_position || !position_expected)`,
  with `position_expected = requires_position() || has_horiz_pos_vel_source()`.
- For 12 s after a source set change a missing position does not
  increment fail_count. Variance failures still do, `ekf_over_threshold()`
  runs on every call (so the vibration check's filtered variances keep
  updating), a latched failsafe is left alone, and a new holdoff cannot
  start until 24 s after the last one began, so alternating sets cannot
  postpone the failsafe.

The field numbers above stay as the evidence for the problem: log3/log4
and log22 show master-equivalent behaviour and remain valid. The "with the
reset" results (log2, the flow vehicle, the seven throws) were taken on
the first design and say nothing about `b1743055b1`.

## Key finding: protection resumes when a position set returns

The gate re-latches when the new set provides position, and it does. After
a throw that ran unaided through a heavy spin, THROW_SRC_SET restored the
GPS set at completion and the failsafe fired 3.4 s after disarm as the
diverged filter failed against the re-latched gate (MambaH743v4 quad,
2026-05-23 session, log1). That is the designed behaviour, and it was
harmless on the ground. The holdoff and the latched-failsafe clear in this
PR have not been exercised in flight.

Not this PR's problem, for anyone matching field reports: a Loiter to
AltHold demotion on an unchanged source set, where has_position dropped
because the terrain offset validity times out 5 s after the rangefinder
ceiling, is #33585's territory; has_ever_passed is not involved.

### Superseded 2026-09-29 by the redesign at b1743055b1

The finding is about the first design's re-latch, which no longer exists:
has_ever_passed is never reset now, so there is nothing to re-latch. It
stays because log1 is still the only field evidence of what happens when a
diverged filter meets the check after THROW_SRC_SET restores GPS. Under
the redesign that switch starts a 12 s holdoff (if none began in the
previous 24 s), which delays a "position lost" count but not a variance
failure. Whether log1's trip was a variance or a position failure was not
recorded here, so whether it would still fire 3.4 s after disarm is open.
Derived from the source, not measured. The latched-failsafe clear no
longer exists; the holdoff is still not flown.

## Open: THROW_SRC_INI under the redesign (2026-09-29)

Derived from the source at `b1743055b1`, not measured. ModeThrow's
`requires_position()` returns true, and THROW_SRC_INI (#32475, on the
SmallFastDrone branch, not master) switches the set from the mode's init.
So on a GPS vehicle whose THROW_SRC_INI set has no horizontal source,
`position_expected` stays true in THROW, and once the 12 s holdoff ends
the missing position counts: the log22 failure should come back about
13 s after the switch instead of 1 s. A flow vehicle (THROW_SRC_INI=3 with
flow velocity) is unaffected because its set has a velocity source. The
ThrowMode autotest does not use THROW_SRC_INI, so its pass does not cover
this. Needs a SmallFastDrone SITL run with THROW_SRC_INI pointing at a
no-position set, sitting disarmed in THROW for more than 13 s.

### Superseded 2026-09-29 (later): measured, and fixed in #32475

The prediction above was wrong about the failure. Measured in SITL on
#32475 `8b5882e6d1` with this PR's ekf_check stacked: an upward throw with
THROW_SRC_INI on a no-position set is **refused at arming** ("Arm: Need
Position Estimate") before any failsafe can count, with master's ekf_check
and with this PR's alike. Drops were never affected: a drop's
`requires_position()` is already false, and log22 and drop session 2 were
drops. #32475 now makes an upward throw's requirement follow
THROW_NEXTMODE (`1796d249cd`, local); with that and this PR, the throw
arms, waits 20 s and completes into ALT_HOLD with no EKF failsafe. An
upward throw into LOITER on a no-position THROW_SRC_INI set is still
refused at arming, which is correct. See `../32475/README.md`. Nothing in
this PR changes.

## A/B of the four legs (SITL, tier 2, 2026-09-29)

EKFSourceSetFailsafe as at `b1743055b1`, with only `ArduCopter/ekf_check.cpp`
swapped. A leg failure stops the test, so later legs are not reached.

| ekf_check.cpp from | result |
|---|---|
| master | fails leg 1: "EKF failsafe on a switch to a set with no position source" |
| `8c2114bfc1` (first design) | fails leg 3: "Failed to receive text: ekf variance" - never trips after a switch during a GPS failure |
| first redesign (set-only gate) | fails leg 4: no "EKF Failsafe" in LOITER after switching to the no-source set |
| `b1743055b1` | passes all four |

Legs: (1) ALT_HOLD, switch to set 2 (no horizontal source), no failsafe
for 20 s; (2) switch back to GPS, no failsafe for 15 s; (3) GPS disabled,
switch to set 3 (GPS), "EKF variance" within 60 s; (4) reboot, LOITER,
switch to set 2, "EKF Failsafe" within 60 s. Legs 1 and 2 accept either
"EKF variance" or "EKF Failsafe", because "EKF variance" is throttled to
one per 30 s from boot and would be missed early in a run.

The PR description's table also marks the first version as failing leg 4.
That cell was not reached in this A/B (the run stopped at leg 3); it
follows from the source (has_ever_passed reset and never re-latched, so
nothing trips) but is inspection, not a run.

Also at `b1743055b1`: EKFSource, ThrowMode, EK3_EXT_NAV_vel_without_vert
and GPSViconSwitching pass.

## Holdoff A/B (SITL, tier 2, 2026-09-30)

EKFSourceSetFailsafe as at `8c0fabdf60` (the four legs above plus a LAND
leg, LOITER leg timeout 11 s), with only `SOURCE_SWITCH_HOLDOFF_MS` set
from 12000 to 0 in `ArduCopter/ekf_check.cpp`: **passes every leg**. So
no leg needs the holdoff. Switching back to the GPS set reported "EKF3
IMU0 is using GPS" in the same log second as "Using EKF Source Set 1".
Leg (c) switched about 17 s after leg (b)'s switch, inside the 24 s
rate limit, so it never opened a holdoff at all (derived from the test's
timeline, not traced in the run).

## Mutation A/B (SITL, tier 2, 2026-09-30)

A different measurement from the four-leg table above: the test was
rewritten. EKFSourceSetFailsafe at `23c4bace02`, five legs: (1) ALT_HOLD,
switch to set 2, wait for EKF_STATUS_REPORT to lose POS_HORIZ_ABS and
POS_HORIZ_REL, then 5 s with no failsafe; (2) back to set 1, wait for
POS_HORIZ_ABS, 5 s with no failsafe; (3) GPS disabled, switch to set 3,
"EKF Failsafe" within 30 s; (4) reboot, LOITER, switch to set 2, "EKF
Failsafe" within 30 s; (5) reboot, LOITER to 20 m, LAND, switch to set 2,
"EKF Failsafe" within 30 s. Only `position_expected` in
`ArduCopter/ekf_check.cpp` changed per row:

| position_expected | result |
|---|---|
| `true` (master) | fails leg 1: "EKF failsafe on a switch to a set with no position source" |
| without `landing_with_GPS()` | fails leg 5: "Failed to receive text: ekf failsafe" |
| without `requires_position()` | fails leg 4: "Failed to receive text: ekf failsafe" |
| as committed | passes all five |

Legs 2 and 3 fail on no single term here; they guard against a gate
reset on a switch, which the code no longer has.

Also at `23c4bace02` (2026-09-30): EKFSource, GPSViconSwitching,
EKF3SRCPerCore and EK3_EXT_NAV_vel_without_vert pass. EKF3SRCPerCore had
failed in CI on `b1743055b1` ("VICON glitch did not raise SP in core 1");
it never changes the selected set, and it passes locally, so read as a
flake.

Round-2 cold Codex read of `23c4bace02` found one thing: leg 3 matched
"EKF Failsafe" as a substring, which "EKF Failsafe Cleared" also
satisfies, so a trip followed by a wrong clear would pass. Leg 3 now also
requires no "EKF Failsafe Cleared" within 5 s while GPS is still off.
Shown to discriminate (2026-09-30): with `position_expected` mutated to
drop the source-set term once the failsafe has latched on set 3, the test
fails leg 3 with "EKF failsafe cleared with GPS still failing"; as
committed it passes.

## Review findings (2026-09-29)

AP-Review on the first design (`8c2114bfc1`), all confirmed:

- One switch flick permanently disabled the failsafe if position never
  returned (has_ever_passed reset, never re-latched).
- The holdoff's early return skipped `ekf_over_threshold()`, blinding the
  vibration check; the next call's dt was about 12 s.
- Clearing a latched failsafe on a switch could leave the vehicle in LAND
  with the failsafe cancelled.
- The autotest ran inside the holdoff, so it could not see a failure.

Own review of the first redesign (round 1), all fixed at `b1743055b1`:

- BUG: gating on the set's source alone gave no failsafe in LOITER, AUTO
  or RTL after a switch to a no-source set. Fixed by the
  `requires_position()` term; leg 4 is the test.
- The holdoff suppressed variance failures too. Now only a missing
  position is held off.
- Alternating sets could keep restarting the holdoff and postpone the
  failsafe. Now it cannot restart, and a new one waits 24 s from the last
  start.
- EK3_SRC_OPTIONS bit 0 (FUSE_ALL_VELOCITIES) was ignored. The EKF3 query
  now goes through `useVelXYSource()`.
- The test only looked for "EKF variance", which is throttled in the first
  30 s after boot. Now also "EKF Failsafe".

No review findings have been rejected on this PR so far.

### Review round 3 (2026-09-30)

AP-Review on `b1743055b1`, all confirmed and fixed at `23c4bace02`:
QURT `<initializer_list>`; LAND flying on position gets no failsafe
(`ModeLand::requires_position()` is false, so `do_not_use_GPS()` was
never reached); the holdoff on switches to a set with no source.

Own /pr-review of `8c0fabdf60` (four Claude reviewers, Codex cold and
audit passes), resolved by dropping the holdoff:

- The fixup that ended the holdoff on a switch to a no-source set did so
  for one 10 Hz tick only; the next tick recomputed it from
  `source_switch_ms`. Codex's audit marked it CLOSED; that was wrong, and
  is recorded here so the next pass does not inherit it.
- The holdoff delayed a position-mode failsafe up to 13 s against
  master's ~1 s; alternating a GPS set and a no-source set every 12 s in
  a non-position mode kept the failsafe off indefinitely, contrary to the
  code comment; under EK3_SRC_OPTIONS bit 3 the selector started a
  holdoff with no change to the cores' sources (Codex rated must-fix); a
  switch inside the 24 s cooldown was never reconsidered.

Rejected or corrected in this round:

- A claim made during the round that the LOITER leg could pass on a
  stale "EKF Failsafe" from an earlier leg was wrong: `reboot_sitl_mav()`
  calls `context_clear_collections()`. The clears added for it were
  removed.

Still open, from the source, not measured:

- A LAND that trips now reports "EKF Failsafe Cleared" about 1 s later,
  because `do_not_use_GPS()` makes `landing_with_GPS()` false. Harmless.
- `has_ever_passed` can latch on a vehicle that has never had a
  position (a no-source set in a non-position mode), so a later switch to
  a set with a source and no position trips where master stayed silent.
- With FS_EKF_ACTION=3, ALT_HOLD on a set with no source no longer lands.
  Intended; the PR description should say so.
- rmackay9's 2026-04-28 comments and LupusTheCanine's question are
  unanswered in the thread.

Answered 2026-09-30 after the push, with the PR description rewritten for
the design without a holdoff: to rmackay9, that the default action only
reports in ALT_HOLD and lands with FS_EKF_ACTION=3, and that nothing is
reset or delayed on a switch so alternating sets cannot hold the failsafe
off; to LupusTheCanine, that a switch to a set with a position source
counts a missing position again whatever the mode (leg 3).

Known limits, documented in the PR, not coded (derived from the source,
not measured):

- With EK3_SRC_OPTIONS bit 3 (a source set per core) the holdoff keys on
  the selected source set, which the cores ignore, and a lane switch that
  changes the effective set starts no holdoff. The position requirement
  follows the primary core's set.
- With EKF2 active and EKF3 enabled, an RC source switch still starts the
  12 s holdoff, although EKF2 has no source sets.

## Measured and rejected

| Change | Argument for | Why rejected |
|---|---|---|
| Reset has_ever_passed and fail_count, clear a latched failsafe, 12 s early-return holdoff on every set change (`b936c14b09`/`8c2114bfc1`) | A switch is a new start; stopped every field false trip (log2, seven throws) | Four confirmed review findings above; fails leg 3 (SITL, 2026-09-29) |
| Holdoff only: keep master's gate, hold off a missing position for 12 s after a switch | Smallest change, Copter only, no EKF API | Drops the purpose: a set meant to stay without position trips once the holdoff ends. Offered to the author as option 2 on 2026-09-29; option 1 (mode or source-set gate) chosen. Not run |
| Round-1 redesign: position expected only if the set has a horizontal source (no `requires_position()` term) | The source set says what the EKF can provide | LOITER on a no-source set gets no failsafe; fails leg 4 (SITL, 2026-09-29) |
| 12 s holdoff on a missing position after a set change, one per 24 s (`b1743055b1`, `8c0fabdf60`) | A newly selected source can take seconds to align | No test leg needs it (Holdoff A/B, 2026-09-30); it delayed a position-mode failsafe to ~13 s and admitted four review findings. Dropped at `23c4bace02` |

## What is here

```
32514/
  README.md          <- this file
```

No logs committed. The autotest BIN could be added under data/.

## Reproduce

```
git checkout ekf-check-source-reset
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py --no-configure test.Copter.EKFSourceSetFailsafe
```

For the A/B, check out `ArduCopter/ekf_check.cpp` from master or
`8c2114bfc1` over `b1743055b1`, rebuild, and run the same test. The
first-redesign row has no commit recorded here, so it cannot be
reproduced from this record.

## Branches and people

- `ekf-check-source-reset` - the PR branch.
- Related: #32475 (THROW_SRC_INI/THROW_SRC_SET, which is what exposed this
  on GPS vehicles).
- rmackay9 - objected to the first design in principle.
