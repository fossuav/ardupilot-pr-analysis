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

## 2026-11-13: Replay through the review fixes, the drop taken out, the ground leg, the fold (tiers 1, 1b, 2)

The SFD beta's refresh16 carried the PR head `fd2a96d8f8`'s review
fixes. Replay of the throw quad's logs 13-16 and 360 fleet logs through
it, against the beta (tier 1b):
- The drop of a pending set once ordinary fusion has passed both axes
  (`95862573e8`) cost log15's throws: core 0 within 1 m/s of GPS after
  2.81, 3.28 and 8.68 s on throws 1, 2 and 4, against 2.01, 0.60 and
  1.16 s without it. Just after aiding starts the velocity variance is
  wide, so on a throw a sample passes on each axis while the velocity is
  still metres per second out, and the drop threw away the set the
  throw needed. The late set it was added for does not show in the
  flow's disagreement with the state on the five flights it changed
  (each within 0.7 s). Taken out, with its test leg. On master alone,
  Replay of 14 logs through builds with and without it: 8 change, 182 s
  of flow more than 1 m/s out against 183 s; log15 and log16 do not
  change there, as without #35146 those throws do not start relative
  aiding from none.
- The ground leg was vacuous (tier 2): with the throttle down the copter
  auto disarmed 10 s after arming and relative aiding started about 7 s
  later, so the set was never armed. Rebuilt with auto disarm off and a
  check that it is still armed when aiding starts: it fails without the
  zero-flow check, the set made as aiding starts. AP-Review then found
  it failing in CopterTests1c: once an earlier test has loaded the CMAC
  terrain tile, SITL's range reads 0.545 m on the ground, above the
  0.5 m the flow is zeroed under. With `SIM_TERRAIN` 0 and the tile
  loaded it passes, and fails without the check.
- Whether a sample was zeroed is recorded where the flow is replaced,
  as testing the height again at the set read the terrain estimate after
  the range had moved it (AP-Review).

Flown on the beta's refresh16 topup1, the throw quad's logs 17-19
(tier 1): the set ran on all six throws, one step per lane, and the
sample it is set from was not fused again from the first set on. The
zero-flow check never acted: Replay is identical without it. The restart
wait held log19 throw 3's set 0.32-0.44 s; its drop of the request never
acted. #33484's restart confirmation held log18's set 0.28 s while both
cores were 8-9 m/s out, and the set then taken was worse over the next
2 s (1.29 against 1.14 m/s on core 0, 0.58 against 0.31 on core 1).

Heads: `fd2a96d8f8` to `b50cb64b60` (the drop out, the ground leg, the
recorded zero flow, the two restart commits squashed), `1ad3f411a7`
(`SIM_TERRAIN` 0), then the squash audit of the 11-12 and 11-13 flights
folded the sample not fused again into the set at aiding start, both
flown: 7 commits to 6, `fc67118e73`, tree unchanged.

## 2026-11-14: AP-Review at `fc67118e73`; rebased onto #34630's rebase, pushed `24e0e6970f`

AP-Review (COMMENT): should-fix, the merge conflict with master that
stopped CI. #34630 was rebased onto master (its record) and this PR's six
commits cherry-picked onto it, all `=` in the range-diff. Copter builds;
EK3_FlowVelocityAtAidingStart passes (tier 2). Pushed 2026-11-14, force
`fc67118e73...24e0e6970f`; mergeable.

Minor, left: the core commit's message credits the Replay and the six
thrown flights to a commit that since the 11-13 squash also holds the
not-fused-again change; that change flew on the throw quad's logs 17-19
(the squash audit), so the commit has flown as a whole, but the message
could say which flights ran which part. The range freshness and the PX4Flow
bus-thread latch stay noted for #34630.

## 2026-11-14: a set from one noisy sample in flight (tier 1, 1b)

A flow-only quad with a MAVLink flow sensor, flying VALT on the 11-12 SFD
beta (topup1's init, the forerunner of this PR), latched its flow out on
quality and released it in the air. After the second release relative
aiding restarted and the set took one sample: 0.15 to 3.92 m/s, while
the vehicle hovered level at 1.9 m and the raw flow read 0.41, 1.15,
-0.83 and 0.19 rad/s on successive samples at a reported quality of
84-89. The lockout recovery put the velocity back 0.6 s later (4.28 to
0.28 m/s). VALT needs no position, so nothing reached the control; in
Loiter it would have been 0.6 s of braking against a phantom 3.9 m/s.
Replay through refresh16 topup2, which carries this PR's head, makes the
same set at the same sample (the rework moves other records by at most
0.07 m/s), so the PR's tests of the sample and the range let it through.

## Open

- The restart wait's drop of its request on a timeout, and the zero-flow
  check, have not acted in flight.
- Only the start from no aiding is covered: an EKF still dead reckoning
  in absolute aiding when the flow set is chosen stays there; #35146
  ends that at the switch.
- One noisy flow sample can make the set (2026-11-14, 3.9 m/s from a
  hover); a check against a second sample, or against the IMU, is not
  written.

## 2026-11-14 (later): AP-Review at `24e0e6970f`; the set's restart request ends with its wait, the core message reworded

AP-Review round 5 (COMMENT, 11:58). New minor: the 5 s expiry of the set
at aiding start was checked only in InitVelocityFromFlow(), which runs
after UpdateAglKf(), so a restart asked for in the last range interval
before the deadline was still taken from the next new reading after the
set had given up: the AGL KF velocity zeroed and the lockout recovery's
resets held off for the restart's three confirming readings. Confirmed
from the source (tier 3).

`021bfa1b95` AP_NavEKF3: end the flow velocity set's wait ahead of the
AGL KF update. The expiry moves to SelectFlowFusion(), ahead of
UpdateAglKf(), gated on `flowVelInitPending`; `aglKfRestartRequested` is
set only while the set is pending and is cleared whenever it ends.
Unflown.

- Replay (tier 1b) of the throw quad's logs 13-19 through this PR's head
  and the fix: identical but for 8-32 bytes a log, every one of them in
  a timing field of one message that differs as much between two Replays
  of log17 through the same build (14 bytes, the same records). Flow
  velocity resets ran on the replayed cores in six of the seven (1-6 a
  core); log15 has none, as without #35146 its throws do not start
  relative aiding from none. The drop of the request never acted on
  these flights, as before.
- SITL (tier 2): EK3_FlowVelocityAtAidingStart passes. The case itself,
  a restart asked for within one range interval of the deadline, is not
  produced in SITL; derived from the source, as the drop was.

The round's other minor, the core commit's message: its Replay
paragraph was taken on a build (`dc7b9c66f2`) that did not yet keep the
set's sample out of fusion, while the six flown throws (topup1,
`59643f9f5b`) ran with it. `0f98f70cc6` (was `d3a6ba9c34`) now says which
ran which; tree unchanged, the other commits `=` in range-diff.

Stack: `1024d0cf57`, `0f98f70cc6`, `f92e8ec2c2`, `787713cfbd`,
`e15033f866`, `7b5a06b33f`, `021bfa1b95`. `/pr-review --quick`: gate
clean, Codex cold read of `021bfa1b95` found nothing, audit CLOSED on
both minors.

Pushed 2026-11-14, force `24e0e6970f...021bfa1b95`; mergeable.

Reply posted 2026-11-14: https://github.com/ArduPilot/ardupilot/pull/35147#issuecomment-6879718945

## 2026-11-18: rebased onto master with #35077, pushed `b90a80f909`

With #34630 and #33484: master `ad3f9dd6c3`, force-pushed
`021bfa1b95...b90a80f909`, 2026-11-18 09:40Z. `git range-diff`: 47 of
50 identical; #33484's two commits and this PR's core commit
(`0b46657a80`, was `0f98f70cc6`) changed in context only, the core
commit beside FuseOptFlow()'s `really_fuse = false`. No code changed.

AP-Review rounds 6 (at `021bfa1b95`, 2026-11-14 15:41Z) and 7 (at
`b90a80f909`, 2026-11-18), COMMENT. Both ask for the same description
fix and nothing else: the description still says "only the top six
commits" and lists not fusing the sample again among the unflown fixes,
where the PR has seven commits and the core commit's message says the
six flown throws ran with that change. Round 7 checked that the set is
made only from fused samples, so never below the focus altitude, and
that the ground leg and master's OpticalFlowFocusAlt pass at this head.
Minors unchanged: range freshness (fine on #34630) and the PX4Flow
latch (note).

The description fix was owed since round 6 and is still owed.

## 2026-11-19: restacked, and the description fix drafted, local `sq/35147-1119` (`06299bca20`), pushed 2026-11-19

Its seven commits cherry-picked onto #34630's `f7be321b60`. One stop, in
`arducopter.py`, where its tests and #33484's new leg both add at the
end of EK3_FlowAxisLockoutRecovery; both kept. The library patch has the
same patch-id as `b90a80f909`'s. EK3_FlowVelocityAtAidingStart,
EK3_FlowAxisLockoutRecovery, OSDEKFLanes, Rover OSDEKFLanesDCMFallback
and OpticalFlowFocusAlt pass (tier 2).

The description fix rounds 6 and 7 asked for is drafted, not posted:
seven commits, the sample kept out of fusion flew with the six throws,
and the three unflown fixes named.

Found while drafting it, derived from the source and not run:
`8380f829ac` (no set from the zero flow before takeoff) rests on "a
copter is off the ground in the EKF as soon as it is armed". Since
#35105 an armed, landed Copter is on the ground in EKF3, and the set is
armed only `!onGround`, so on master the set is not made on the ground
anyway on Copter, and EK3_FlowVelocityAtAidingStart's ground leg would
no longer fail without that commit once this PR is on a master with
#35105 (its base `ad3f9dd6c3` predates it). The commit still covers
other vehicles. Not acted on.

## 2026-11-19 (later): the zero-flow commit measured against #35105 (tier 2)

The stack (#33484 16 commits, #34630 29, #35147 7) cherry-picked onto
master `321896137f`, which carries #35105, with no conflict and every
commit `=` in `git range-diff`; local test branches, not pushed.
EK3_FlowVelocityAtAidingStart's last leg ("no set from the zero flow
before takeoff": flow-only set, armed on the ground in STABILIZE at zero
throttle, flow brought in so relative aiding starts there), each side
built and md5-checked, the commit removed by taking `flowSampleZeroed`
out of `InitVelocityFromFlow()`'s guard:

| base | with `8380f829ac` | without it |
|---|---|---|
| `ad3f9dd6c3` (the PR's, no #35105) | passes | fails: both lanes "flow velocity set at aiding start" as aiding starts |
| `321896137f` (with #35105) | passes | passes: aiding starts on both lanes, no set in 6 s |

On master with #35105 the leg no longer discriminates. Derived from the
source, not measured separately: the set is armed only `!onGround`, and
a landed, armed Copter is now on the ground in EKF3. The commit still
guards a vehicle that is armed, not reported landed and under 0.5 m
before takeoff: on master, vehicles that do not report landing (derived,
none run); in the SFD stack also a THROW carry held low (#32475 reports
it off the ground) and an in-air re-arm reaching the ground (#32768).
Decision pending: drop the commit and its leg from the PR once it moves
onto #35105, or keep it with a leg on a path that still reaches it.

### 2026-11-19 (later): the zero-flow commit dropped, the stack restacked onto master with #35105

Andy's decision: drop `8380f829ac` and its test leg. The stack
cherry-picked onto master `321896137f` (#33484 `8ed697cba1`, #34630 `746f2908cb`)
and this PR's five other commits on top (`27bb095723`); four `=`, and the
wait-end commit resolved onto the guard without `flowSampleZeroed`. The
library difference from the seven-commit restack is exactly that commit
reversed; the test file loses only its leg. Not flown: none of the
dropped code had flown.

SITL at `27bb095723` (tier 2): EK3_FlowVelocityAtAidingStart,
EK3_FlowAxisLockoutRecovery, OSDEKFLanes, Rover OSDEKFLanesDCMFallback,
OpticalFlowFocusAlt and OpticalFlow pass; at #33484's `8ed697cba1` alone,
EK3_FlowAxisLockoutRecovery (reset 0.54-0.58 s after the FLOW_ALT_MIN
return) and OpticalFlowFocusAlt pass.

`/pr-review --quick`: gate clean (diff-size note). Codex audit: nothing
at the new head refers to what the dropped commits added. Codex cold
read of the resolved wait-end commit: no test reaches its 5 s expiry
(already noted at round 6; not addressed here). Description updated for
five commits and the dropped change, posted with the push.

Pushed 2026-11-19, force: #33484 `8316113fbb...8ed697cba1`, #34630
`f7be321b60...746f2908cb`, #35147 `06299bca20...27bb095723`; all three
mergeable. Description posted the same day.

## 2026-11-20: ground leg restored, pushed `a84d999b56`

`a84d999b56` restores the leg the #35105 rebase dropped, reworded as
"no set when aiding starts on the ground": it passes at the head and
fails with `&& !onGround` removed from the set's gate. Range freshness
(#33484's `14ea671178`) is carried into `flowResetRangeState()`. In
FuseOptFlow the set's early return comes before #33484's timer restart,
so a sample the set consumes is not counted as tested.
Replied (issuecomment-7051121123).

## 2026-11-23: restacked on #33484's test fix, pushed `fc082533e1`

Every commit `=` in `git range-diff`. The tree differs from `a84d999b56`
only by #33484's 7-line autotest change (`255fe24724`). The description's
commit count, which said five, was corrected to six and posted the same
day. CI on this head had not finished when this was written.

## 2026-11-23 (later): ACCEPT at `fc082533e1`, restacked as `e55b2fac24`

Round 12 accepted `fc082533e1`, with two notes. The head then moved to
carry #34630's comment-only commit, so this PR's six commits are unchanged
but the new head needs its own round. CI and AP-Review on this head had not finished when this was written.

## 2026-11-24: AP-Review at `e55b2fac24`, ACCEPT

Nothing asked; the two standing notes (zeroed sample before takeoff
detection, the bus-thread quality latch) stay information only.
