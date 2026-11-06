# PR #32401 - Pending arm on switch for in-air arming

Analysis archive for [ArduPilot/ardupilot#32401](https://github.com/ArduPilot/ardupilot/pull/32401).
Branch `pr-copter-pending-arm` (andyp1per fork), base `master`. No logs
committed; the two field cases below are real drops.

### Head superseded 2026-09-29: rebased onto master, head `4bc594f1c6`

Rebased onto master on 2026-09-29; the GitHub head is now `4bc594f1c6`.
The RC_Channel change was split into its own commit, the net of the
Copter commit's addition and the follow-up's removal.
Nothing has been re-measured at this head. Every number below keeps the
commit it was taken on, and any head named above is left as written
because it is the code those numbers came from.

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
   MicoAir743v2 quad in THROW with idling motors (Q25 log, not committed)
   it waited forever on "Throttle (RC3) is not neutral", re-running the
   pre-arm at 4 Hz against a failure only the stick can clear. In both
   cases the pilot had no route to an armed vehicle short of fixing the
   underlying check, and in a drop the refusal is the crash.

2. The bootstrap reset should be gated on the failure being EKF-related.
   In the Q25 case it fired at ARMING_PEND_TIM=1 s for a throttle-position
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

## 2026-10-31: the bootstrap reset made GPS 24 s late, SFD-O4 log67

This PR's `4bc594f1c6` calls `reset_configured_backend()` once the pending
arm has waited `ARMING_PEND_TIM` (5 s). On log67 the switch came at 24.77 s
with "PreArm: Need Position Estimate"; the reset fired at 29.87 s ("Arm
pending: EKF bootstrap reset") while the GPS checks were already passing
(XKF4.GPS 0). The EKF first uses GPS about 30 s after it initialises
(34.4-35.9 s on the other five boots), and the reset restarted that wait:
"EKF3 IMU0 is using GPS" at 59.56 s, 24 s late. A reset cannot make a GPS
arrive, so firing it on a position wait costs time and gains nothing.

`InitialiseFilterBootstrap()` (upstream `41744c884d`, compiled out there by
default) writes no DAL event, so Replay cannot follow it: the beta's Replay
matches log67 to 1e-7 until 29.87 s and differs from then on (yaw 1.7 deg,
VD 0.08 m/s). It also flew on the Q25 (q25-0cb4, 14.68 s, `ARMING_PEND_TIM
2`).

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
  gated on THROW_MOT_START=0, which is what put the Q25 vehicle into
  pending in the first place).

### 2026-11-06: AP-Review fixes on `r1106/32401-fix3` (`9bf9ddc25d..749911703c`, 11 commits on `c2a704089d`, not pushed)

GCS disarm while disarmed now cancels a pending arm (the GCS handler never
called disarm() then) and Copter's disarm() clears it before its early
return; a pending request is dropped once the vehicle is armed by any route;
the EKF reset waits for `AHRS::pre_arm_check(false)` to fail, so it no longer
fires while waiting for GPS; arm-time failures follow the 3 s pre-arm
cadence through a quiet flag in AP_Arming; ARMING_PEND_TIM is compiled out
without AP_AHRS_EKF_RESET_ENABLED and tagged Copter, and ARMING_OPTIONS bit
3 documented as Copter-only with no time limit.

SITL, PR head against the branch (fresh builds in a private directory):
GCS disarm while pending armed 0.8 s after the check cleared, now stays
disarmed; force-arms 1.775-1.915 s into a 2 s ARMING_PEND_TIM reset the EKF
on the armed vehicle 5/5, now 0/11; `SIM_GPS1_LCKTIME=40` (log67's late
first fix) armed 39.2 s after the fix, now 10.2 s with no reset; GPS off at
runtime 35.8 s after it returned, now 1.8 s; "Throttle too high" 30 texts in
10 s, now 4. An AHRS inconsistency still gets one reset.

PendingArmOnSwitch (`569aa098f5`, `749911703c` after a Codex cold read
found three gaps): each leg fails with the commit it covers reverted - the
late-GPS leg (switch raised before the fix) with 580e434977 reverted, the
3-6 report bound with an always-quiet build (1) and the PR head (30), the
force-arm-before-the-deadline leg with c8ee610aab reverted (2/2, reset then
EKF failsafe). That leg's arm at 1.8 s sits 25-100 ms inside the window it
needs; correct code passes either side of it.

The branch is rebuilt by cherry-pick with `4bc594f1c6` reworded as
`c2a704089d` (its message described rudder pending and a position-
controller reinit the commit does not contain) and the last test commit's
subject shortened; the tree is identical to the tested head.

Kept Copter-only, as decided on 2026-11-06, in answer to peterbarker's
CHANGES_REQUESTED ("If this is done it shouldn't be
Copter-specific"): 926a50aa6b documents it for Copter only; the request flag
and its cancel paths are in AP_Arming and RC_Channel. Open: Notify's arming-failed
event still fires on every failed retry; failures that cannot clear
themselves (battery, throttle) still wait.

Pushed 2026-11-06: `pr-copter-pending-arm` `4bc594f1c6...749911703c` (forced, first commit reworded). Description updated. Reply posted: https://github.com/ArduPilot/ardupilot/pull/32401#issuecomment-6690423927
