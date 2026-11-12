# PR #35147 - EKF3 sets the flow velocity when relative aiding starts in flight

Analysis archive for [ArduPilot/ardupilot#35147](https://github.com/ArduPilot/ardupilot/pull/35147).

Opened 2026-11-12 at `fd2a96d8f8`, branch `pr-ekf3-flow-vel-aiding-start`,
stacked on #34630 (`1ec664a625`), which is stacked on #33484; the top
ten commits are this PR's. From the SFD beta's refresh15 topup1
(`68c62facbf`, `dc7b9c66f2`, test from `24b7a1a5c0`); a new PR rather
than more commits on #33484, by decision.

## What it does

With EK3_OPTIONS bit 3 (AGL KF for flow scaling), relative aiding that
starts from none while armed sets the horizontal velocity from the
first flow sample that passes the lockout recovery's tests of the sample
and the range, instead of starting at zero. An AGL KF found lagging a
step in the range is restarted once from the next new reading and the
restart and its confirmation are waited for. The wait ends after 5 s.

The refactor commit was rewritten for master's two-state AGL KF (the
beta's has a bias state and a split fusion step); behaviour-neutral by
inspection, confirmed by both round 1 reviewers. `59f27f252d` (a
solve/apply split with one caller) was dropped.

## Flight evidence (tier 1, on the 4.7-based beta)

The init (`dc7b9c66f2`, code identical to `99126da8fa` here) flew on the
throw quad's logs 15-16: on six throws 1 s after the switch the flow
lane was 0.19-1.68 m/s out, against 1.71-6.82 m/s in a refresh15 Replay
(`../33484/`). Replay of log13: within 1 m/s of GPS 0.47-0.76 s after
the switch on throws 2-5, against 0.55-4.34 s; throw 1 worse (3.2
against 1.4 s, a sample in a 200 deg/s yaw spin). 344 of 355 fleet logs
unchanged; on one T25 flight a late set moved a correct velocity
0.5-0.9 m/s for about 1 s, which the second fix below addresses.

## SITL, 2026-11-12 (tier 2), EK3_FlowVelocityAtAidingStart

| leg | with | without |
|---|---|---|
| 3.5 m/s at the switch, AGL KF option off (baseline) | 3.52-3.58 m/s out at 0.3 s, no set | - |
| same, option on | 0.11-0.22 m/s out at 0.3 s | init disabled: 3.55 m/s |
| still, range out of range at the switch, back after 2 s | no set | without the drop once fusion has the flow: a late set |
| armed on the ground on a flow only set, flow brought in | no set | without the zero-flow gate: a set from the zero flow (2 of 2) |

Not measurable in SITL: skipping the second fusion of the set's sample
(0.18 against 0.19 m/s; XKV1 is logged at 2 Hz with a gap across the
set) and dropping a stale restart request; derived from the source.

## Review rounds (2026-11-12)

- Round 1: should-fix only. The set's sample was fused again with a
  stale linearisation; a pending set was never cancelled once fusion
  had the flow; the restart request outlived the set; the comment
  claimed the recovery's tests in full (it cannot run the other-axis
  test, as neither axis has passed). Fixed as commits on top. A yaw
  rate gate was not added: the beta tried one for a related set and
  dropped it, as its threshold came from one airframe.
- Round 2 (Codex): the set could take the zero that stands in for the
  flow under 0.5 m before takeoff on a copter armed on the ground
  (fixed); the "both axes passed since the start" test was not wrap
  safe.
- Round 3: the start time is the previous update's, as setAidingMode()
  runs before readIMUData(), so the round 2 change to count equal ages
  admitted a pre-transition pass; corrected to strictly younger ages.
  The set did not wait for the restart it asked for (fixed); the early
  return skipped refreshing the flow fusion timer (fixed); the 5 s
  wait's reason corrected; the takeoff gate narrowed to the exact
  zero-flow condition.

## Open

- Replay of the fleet logs through the five unflown fixes, on the beta
  once a refresh takes them.
- Only the start from no aiding is covered: an EKF still dead reckoning
  in absolute aiding when the flow set is chosen stays there; #35146
  ends that at the switch.
