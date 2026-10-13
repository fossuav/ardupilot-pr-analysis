# Copter: return to Loiter or PosHold when the EKF failsafe clears

**Open as [#34696](https://github.com/ArduPilot/ardupilot/pull/34696)**,
opened 2026-10-09 from `andyp1per/copter-ekf-fs-restore` at
`6d0d18631e`: three commits on master `1f1251a67e`. Record written
2026-10-09. *2026-10-13*: two commits on top, head `ec0722bbed`, pushed
and the description updated the same day; see "2026-10-13: flown, and
refused without a position".

| commit | subject |
|---|---|
| `b2a010eb09` | AP_Vehicle: add a mode reason for recovery from an EKF failsafe |
| `249d48a73c` | Copter: return to Loiter or PosHold when the EKF failsafe clears |
| `6d0d18631e` | autotest: cover the EKF failsafe mode restore |

## Status (one line)

Opened after three `/pr-review` rounds (verdict COMMENT, no must-fix
left); SITL only, not flown. `EKFFailsafeRestoreMode` has 14 subtests,
and 14 of the restore's conditions were each shown to fail their own
subtest when removed.

*2026-10-13*: flown on the SFD beta (`6f5d6dc0`, TD25, ten logs). With
#32514 alongside, the restore fired without a position and was refused
in 6 of 13 attempts; held until `position_ok()` in `0a4ae24f1e`, with a
15th subtest in `ec0722bbed`. Those two are SITL only.

## Where it came from

The TD25 QMIN failsafe flight of 2026-10-08 (bragg MicoAir743v2 flow
quad, SmallFastDrone `7b0e4dd8`, `EK3_FLOW_QMIN=75`; record owed in
`../../analysis/logs/td25_flyaway.md`). The #33484 quality latch took
flow out at 67.40 s and `FS_EKF_ACTION=2` put the vehicle in AltHold at
68.36 s. The pilot then asked for Loiter three times (88.4, 105.6 and
119.5 s) and was refused each time with "requires position".

This PR would **not** have helped that flight: the QMIN latch holds until
disarm, so position never came back. The cases it is for are brief
losses that do recover. The measured one in the record is the AltHold
demotion at the rangefinder ceiling, where `horiz_pos_rel` cleared for
5-6 s while navigation stayed healthy
(`../../analysis/topics/dow_althold_ekf_failsafe.md`).

It was asked for alongside an `FS_EKF_ACTION` value for VALT, which went
to #32270 instead (`d5672e0d6e`, `d40430bce0` on local `copter-valt-mode`,
not pushed). With both, a flow vehicle goes Loiter -> VALT -> Loiter.

*Updated 2026-10-11:* both commits were pushed to #32270 on 2026-10-09
(head `d40430bce0`). "The QMIN latch holds until disarm" above is true of
the flown firmware `7b0e4dd8` only; on #33484 as posted the latch clears
only when a flow sample arrives while disarmed (`../33484/README.md`,
2026-10-11).

## The design at `6d0d18631e`

`failsafe_ekf_event()` records the mode it changed from when that mode was
Loiter or PosHold and fewer than three restores have been made since
arming. `failsafe_ekf_restore_mode()` runs at the end of `ekf_check()`,
after the tick's own checks, and:

- cancels on: option clear, `land_complete`, mode LAND, or any
  `set_mode` call since the failsafe (`_last_reason`, written before any
  refusal, so a refused request cancels too);
- holds and restarts its 3 s timer on: any failsafe
  (`any_failsafe_triggered()`), `fail_count != 0`, no valid RC, roll or
  pitch off centre;
- makes one attempt, logged as `ModeReason::EKF_FAILSAFE_RECOVERY` (56).

Disarming clears the pending restore and the count at the top of
`ekf_check()`, before its early returns. Disabling the check
(`FS_EKF_THRESH <= 0`) clears a pending restore. Releasing a Loiter or
PosHold aux switch (RC options 56, 69) during the failsafe cancels a
restore to that mode, from `RC_Channel_Copter::do_aux_function_change_mode`.

## Measured: each condition fails its subtest

SITL, worktree at the final code, `mutations.py` in this directory, run
2026-10-09. Each row removes one term, rebuilds and runs the test.

| term removed | subtest that failed | failure |
|---|---|---|
| the whole restore | Loiter comes back once the checks have passed | no "restored" text |
| Loiter/PosHold only | an autopilot mode is not restored | restored |
| cap of three | at most three restores a flight | restored |
| cap reset on disarm | a new flight can restore again, PosHold too | no "restored" text |
| cancel on disabled check | disabling the EKF checks cancels the restore | restored |
| option check | no restore without the option | restored |
| `land_complete` cancel | landing during the failsafe cancels the restore | restored |
| LAND cancel | a landing the failsafe started is not undone | restored |
| `_last_reason` cancel | a mode the pilot chose during the failsafe is kept | restored |
| `_last_reason` -> reason only | a refused mode request during the failsafe cancels the restore | restored |
| aux release cancel | releasing a Loiter switch during the failsafe cancels the restore | restored |
| other-failsafe hold | no restore while another failsafe is active | restored |
| timer restart on hold | no restore while the pilot holds the roll or the pitch stick | 0.8 s after a stick input |
| roll term | (same) | restored |
| pitch term | (same) | restored |
| 3 s delay | Loiter comes back once the checks have passed | 0.6 s after clearing |

Passing run on the same code: restore 3.6 s after the failsafe cleared
and 3.8 s after the last stick input; the Land subtest still 7.5 m above
home at its check.

Not covered by a subtest: the valid-RC term, and `fail_count != 0` on its
own. The second was not mutated. By reading, without it the restore still
comes at least 3 s after the clear, which the test accepts. The extra
0.6-0.8 s over 3 s in every passing run is consistent with checks failing
intermittently while GPS re-acquires and restarting the timer; that is
inference, not instrumented.

## 2026-10-13: flown, and refused without a position

The SFD beta at `6f5d6dc0` carries this PR with #32514 and #32270's
`FS_EKF_ACTION=4` (VALT). TD25 flew the field plan's T2-T4 with
`FS_OPTIONS=80` and a source set switch to set 2, which has no horizontal
source: 16 failsafe cycles over seven logs (`t2f1`-`t3f3`, `t4`; the
private record is `../analysis/logs/td25_sfd472_field.md`). These are
the first flights of the restore.

| outcome | cycles |
|---|---|
| restored | 7 |
| **refused**: "Mode change to Loiter failed: requires position", restore spent, Loiter never came back | 6 |
| cancelled by the pilot choosing Acro | 1 |
| not attempted: fourth in a flight (cap) | 1 |
| not attempted: sticks never centred 3 s | 1 |

Every refusal came 3.0-3.2 s after the sticks were last off centre, all
on set 2. Mechanism, derived from the source and then reproduced in
SITL: in VALT on set 2 #32514's check expects no position, so
`fail_count` reaches 0 and the failsafe clears 1.0 s after it triggers;
the restore tested `fail_count`, other failsafes and the sticks, never
the position. On master the checks need a position, so `fail_count == 0`
implies one and it cannot happen: it is this PR meeting #32514.

The stick hold, the cap and the mode-change cancel all behaved as the
subtests say. Two restores came 3.1 s after the switch back to set 1
with the sticks already centred for longer, which looks like one failed
check at the switch restarting the timer (inference, not instrumented).

### The fix: `0a4ae24f1e`, test `ec0722bbed`

The restore also holds while `!position_ok()`, the test `set_mode()`
applies to Loiter and PosHold. A commit on top rather than squashed,
because the commits below it have flown. New subtest "on a source set
with no position the restore waits for one": Loiter, switch to a set
with no horizontal source, AltHold, sticks centred 6 s, no restore and
no "requires position", switch back, Loiter restored. Run 2026-10-13:

| tree | without the hold | with it |
|---|---|---|
| SFD beta `9a15a8a32c` + subtest | fails: cleared on set 2, then "requires position" | passes; restored 3.1 s after the switch back |
| this PR `6d0d18631e` + subtest | passes: no clear on set 2 | passes |

So the subtest discriminates only with #32514's check. The whole test
passes at `ec0722bbed`. Not re-run: the mutation table above, which
predates the new term.

"Not covered by a subtest ... `fail_count != 0` on its own" below is
unchanged by this.

Quick review at `ec0722bbed` (2026-10-13; full reviews are kept for
opening a PR and its first push): the gate, a framing-free Codex cold
read and one reviewer agent. No defects. Left as they are:

- The test's subject is 73 characters (gate note).
- "requires position" is matched whole; the PosHold text is 54
  characters and arrives split, so the check would miss it if the leg
  ever used PosHold. It uses Loiter (47).
- "they pass a second after the failsafe": strictly the checks pass at
  once and the failsafe clears a second later, which is what the
  restore keys on.
- The agent marked "fails without the hold on the beta" UNCONFIRMED,
  finding no transcript; the run above is that reverse run (beta
  `9a15a8a32c` plus the leg, "restore attempted without a position").

## Review history

Three rounds, each a set of Claude reviewers plus Codex cold, verification
and audit passes (`/pr-review`, 2026-10-08/09).

- Round 1 at `e2f7024804` - REQUEST CHANGES, 3 must-fix. It restored any
  mode, so AUTO (a restart under `MIS_RESTART=1`), RTL climbing against a
  descending pilot, and Drift switching throttle semantics. A GCS failsafe
  that took no action in AltHold acts only on its own transition, so a
  restore into Guided or AUTO bypassed it. "Clear for 3 s" was the latched
  flag, with the sticks sampled once. Fixed by restoring Loiter/PosHold
  only, one continuous timer, the hold-offs, the `_last_reason` cancel and
  the cap.
- Round 2 at `2886c8b6a7`: the restore ran on the previous tick's checks,
  an aux switch release did not cancel, ADS-B/terrain/battery failsafes did
  not hold it, and roll was never held on its own in the test. All fixed.
- Round 3 at `d921be6174`: the disarm reset was skipped while the check was
  disabled, the retry path was effectively unreachable, the save-time
  option check was redundant, and nothing covered a landing or the option
  cleared mid-failsafe. Fixed by making the restore one-shot, moving the
  disarm reset first, dropping the save-time check and adding three
  subtests.

A mistake of mine, kept here because the next reader will be offered the
same wrong number: the round-2 reviewer proposed `RC7_OPTION=39` for the
Loiter aux leg, and it went in unchecked. Option 39 is precision loiter;
Loiter is 56 (`RC_Channel.h:212`). The subtest failed until debug output
showed the cancel was never called.

Squashed 2026-10-09: `460bc52fc2` (15 commits) -> `6d0d18631e`, empty
content diff.

## Disputed, and left as is

- Codex round 3, must-fix: with `FS_THR_ENABLE=0` a lost receiver leaves
  its last stick values in `radio_in`, and `has_valid_input()` does not
  test freshness, so centred stale sticks allow a restore. Not changed: the
  vehicle is already flying AltHold on those same stale inputs, and Loiter
  holds position where AltHold drifts. Stated in the PR description.
- `MAV_SEVERITY_INFO` for the "restored" text, as Plane's short RC failsafe
  restore uses. A GCS that speaks only higher severities will not announce
  it.
- Naming: `failsafe_ekf_restore_mode()` is an update function with a verb
  name. Left.

Design questions a maintainer will raise, all in the PR description:
Copter otherwise restores only after ADSB avoidance (`AVD_F_RCVRY`); an
`FS_OPTIONS` bit rather than an `FS_EKF_ACTION` value; the saved mode
rather than the mode switch position; why 3 s.

## Cross-references

- **#32514 on the SFD branch.** SFD's `ekf_check()` has an extra early
  return while landed (`6930f37f1f`). A port must clear the pending restore
  there as well. Otherwise a restore survives a landing on which the checks
  fail on the ground, as a flow vehicle's do below its focus height, and
  fires after the next takeoff.
- **SRCF** (`SmallFastDrone-4.7.0-gps-optflow-fallback`) took `FS_OPTIONS`
  bit 6 and `ModeReason` 56 for its own drift fallback. That branch is not
  on the beta or upstream, so it renumbers on its next refresh
  (`../../analysis/topics/srcf_gps_flow_fallback.md`). Its 3 s
  continuous-position debounce, from Brake bouncing on a stale-valid
  estimate, is the measured support cited for this PR's 3 s.
- **SFD top-up owed**: this PR and #32270's VALT action, hand-ported to
  4.7, where `FS_EKF_ACTION` is still a set of `#define`s.

### Superseded 2026-10-09 by a SITL mutant on the beta (the #32514 bullet)

The landed-branch cancel was written into the beta port and then removed.
A mutant without it passed `EKFFailsafeRestoreMode` on the beta, including
a version of the landing subtest that regains GPS only after the
re-takeoff. In that run `LAND_COMPLETE` was logged at 395.03 s and the
motors stayed `SPOOLING_DOWN` until 395.54 s. The early return needs ground
idle or stopped, so it did not apply on those ticks, and the normal
`land_complete` cancel ran first. A copter landing under power always
spools down after `land_complete` sets, so no port change is needed. The
bullet is left because it is the reasoning a reader of the two diffs side
by side will arrive at.

The top-up itself was done 2026-10-09 as topup14 on
`SmallFastDrone-4.7.2-beta` (`f209d485e5` to `38c627cb2b`, not pushed).
The test bodies are identical to the PRs', and `EKFFailsafeRestoreMode`,
`ModeVAltHold` and `EKFSourceSetFailsafe` pass on that stack.

## Reproduce

```bash
# worktree at the PR head, SITL submodules initialised
./waf configure --board sitl && ./waf copter
Tools/autotest/autotest.py test.Copter.EKFFailsafeRestoreMode
# the mutation table; about 25 minutes
python3 34696/mutations.py <worktree> <log dir>
```
