# PR #32401 - Pending arm on switch for in-air arming

Analysis archive for [ArduPilot/ardupilot#32401](https://github.com/ArduPilot/ardupilot/pull/32401).
Branch `pr-copter-pending-arm` (andyp1per fork), base `master`. No logs
committed; the two field cases below are real drops.

## Status (one line)

Open, changes requested. Depends on #32202. The mechanism works as designed
in the field; two field cases show it retrying failures it cannot clear and
resetting an EKF that was not the problem. Neither is addressed in the PR
yet.

## The problem

A drop from a carrier needs the vehicle armed before release, and the EKF
on a vibrating, accelerating carrier is often not ready when the pilot
flips the switch. Pending arm lets the request stand and completes it when
the checks pass, with a one-shot EKF bootstrap reset after ARMING_PEND_TIM
to force convergence.

## The conclusion and why

The retry and the single reset both behaved: on a MatekH743 quad dropped
from a carrier aircraft (log18, not committed) pending entered on the arm
failure, the bootstrap reset fired exactly once (830.8 s, again at 844.1 s
on the second attempt), and the EKF recovered a full solution 1.3 s later.
The vehicle still never armed, because "Battery 1 below minimum arming
capacity" fails every retry, and it was released unarmed and fell for 9 s.
Pending arm today treats every pre-arm failure as transient.

## Key findings

1. Pending arm should only wait on failures that can clear themselves. On
   the carrier drop it waited forever on a battery capacity check. On a
   MicoAir743v2 quad in THROW with idling motors (t25 log, not committed)
   it waited forever on "Throttle (RC3) is not neutral", re-running the
   pre-arm at 4 Hz against a failure only the stick can clear. In both
   cases the pilot had no route to an armed vehicle short of fixing the
   underlying check, and in a drop the refusal is the crash.

2. The bootstrap reset should be gated on the failure being EKF-related.
   In the t25 case it fired at ARMING_PEND_TIM=1 s for a throttle-position
   failure, re-initialising the EKF while the vehicle sat in THROW: THRO
   logging stops at 11.18 s, exactly 1 s after the arm switch at 10.187 s,
   with a downstream ERR at 13.2 s. The same sequence on a moving carrier
   (MatekH743 quad, log32) cycled "Arm pending: EKF bootstrap reset" ->
   "Arm pending cancelled" repeatedly without ever converging.

3. The 3 s status display in this PR answers the other complaint from
   log18, that after "Arm pending" the pilot got no indication which check
   was blocking.

4. The PR description still says a failed rudder arm enters the pending
   state; commit 17204150e4 and the code say it does not (only the
   left-rudder clear remains). The description is stale.

## What is here

```
32401/
  README.md          <- this file
```

No logs committed.

## Reproduce

```
git checkout pr-copter-pending-arm
./waf configure --board sitl && ./waf copter
```

No autotest yet for either finding. A test that sets BATT_ARM_MAH above the
simulated capacity (or holds RC3 at mid-stick), toggles the arm switch and
asserts that no "EKF bootstrap reset" message is sent would cover both.

## Branches and people

- `pr-copter-pending-arm` - the PR branch.
- Related: #32475 (throw mode; the mid-stick arming exemption there is
  gated on THROW_MOT_START=0, which is what put the t25 vehicle into
  pending in the first place).
