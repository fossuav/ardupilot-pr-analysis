# PR #33484 - SITL A/B of the single-axis flow lockout response

Companion to `README.md`. That file records why the lockout happens and how
the recovery was tuned; this one records a SITL A/B of *what the filter should
do about it*, run 2026-09-04 because the reset trusts a measurement that has
just failed its own innovation gate.

## The question

A sustained single-axis flow innovation failure has two explanations and, in
flow-only nav, no independent arbiter - the only other horizontal velocity
information is the IMU, which is the hypothesis under test.

- **H1** - state wrong, flow right. Accel bias walks that axis's velocity
  estimate away. Resetting to the flow is correct.
- **H2** - flow wrong, state right. Stuck or biased sensor axis. Resetting
  *injects* the fault.

The merged behaviour assumes H1 unconditionally.

## Method

Scratch worktree off `pr-vel-flow-axis-gate` (40228e7624) plus the three
`pr-flow-quality` commits cherry-picked in. Four responses behind one scratch
parameter `EK3_FLOW_RECOV`, so a single binary covers every arm and only the
response differs - the detector (one axis rejected 500 ms while the other
passes) is identical throughout.

| arm | response |
|-----|----------|
| 0 | give up: latch flow aiding unhealthy, fall to AID_NONE |
| 1 | hard reset to the flow-derived velocity (merged behaviour) |
| 2 | bounded update: scale the gains by 1/testRatio, mirroring the `EK3_GLITCH_RAD<=0` GPS path |
| 3 | reset only if reported flow quality >= `EK3_FLOW_QMIN` (40), else give up |

Faults, injected in LOITER at ~3 m on flow-only nav so the position
controller acts on the corrupted estimate:

- **H1** `SIM_ACC1_BIAS_X=1.5`
- **H2** `SIM_FLOW_OFS_X=1.0`, quality left at its normal 51
- **H2b** `SIM_FLOW_OFS_X=1.0` **and** `SIM_FLOW_QUAL=10` - a defocused or
  poor-surface sensor, which reports false motion *and* says it is unhappy

Metric: maximum **true** distance travelled (SIMSTATE) in the 30 s after the
fault. Not the estimate error - what matters indoors is how far the airframe
actually goes. No-fault baseline is 0.27 m of normal LOITER wander.

## Results

Max true distance travelled, metres. Repeats separated by `/`.

| response | H1 (state wrong) | H2 (flow wrong, quality good) | H2b (flow wrong, quality low) |
|----------|------------------|-------------------------------|-------------------------------|
| *baseline, no fault* | *0.27* | - | - |
| 0 give up | 11.1 / 12.4 / 13.8 | 12.9 / 13.5 / 13.6 / 15.5 | 10.1 |
| 1 hard reset (merged) | **1.7 / 1.8 / 2.4** | **76.6 / 77.8 / 78.0** | 76.5 |
| 2 bounded update | 60.3 | 74.9 | - |
| 3 quality discriminator | **1.7 / 1.9** | 76.2 / 78.1 | **9.8 / 10.2** |

Spreads are tight; the ordering is not in doubt.

## Three mechanisms, all verified

**The bounded update is not merely slow, it is perverse.** The correction is
`(K/testRatio) * innov` and `testRatio` grows as `innov^2`, so the correction
scales as `1/innov` - it gets *weaker* as the error grows. The GPS path
tolerates this because glitches are transient and the underlying state is
good. Here the error is sustained, so arm 2 is worse than giving up under H1
(60 m) and nearly as bad as the reset under H2 (75 m). This refutes it as an
option.

**One reset captures the filter permanently.** Under H2 the log shows exactly
one reset per core and then silence - no churn, no unhealthy latch. Once the
state has been snapped onto the faulty sensor the two agree, so the lockout
never recurs. The 5-resets-in-10-s rate limiter watches for *oscillation*;
this failure is *capture*, and the limiter cannot fire.

**Giving up is silent - it does not land the vehicle.** Arm 0 reaches AID_NONE
correctly, and the copter then coasts 13 m while the EKF reports 0.04 m/s and
full health. The AID_NONE entry sets `velTestRatio = posTestRatio = 0`;
`NavEKF3_core::getVariances()` returns `sqrtF()` of exactly those
(`AP_NavEKF3_Outputs.cpp:478-479`); and `Copter::ekf_over_threshold()` watches
those variances. So dropping to AID_NONE *disables* the failsafe that would
otherwise land it. No mode change, no LAND, blind drift.

## What the quality discriminator buys

Arm 3 keeps arm 1's excellent H1 result (1.7-1.9 m against a 0.27 m baseline)
and converts the H2b catastrophe from 76.5 m to 9.8-10.2 m, a 7.5x
improvement, by declining to reset on a sample the sensor itself reports as
poor.

It does nothing for H2, where the sensor is confidently wrong: 76-78 m either
way. That is the honest residual.

How much that residual matters depends on how a real flow axis fails. Defocus,
poor surface and low light all drop reported quality and are therefore covered.
A pure additive one-axis offset with *undiminished* quality - which is what
`SIM_FLOW_OFS_X` injects - is the artificial case. Note a scale-factor error
(`FLOW_FXSCALER`) is not this fault: it produces an innovation proportional to
motion, so a stationary vehicle sees no offset and no lockout.

## The conclusion this points at

**None of the four responses is good enough for indoor space.** Typical clear
space is 3-8 m. The best non-catastrophic number here is ~10 m, and that is the
*give-up* path, which the copter flies blind because the failsafe cannot see it.

So the detector is not the bottleneck - 500 ms of lockout costs only 0.5-1 m at
these speeds. The response is. The highest-value change is not a cleverer
choice between reset and give-up, it is making "give up" reach a **terminal
action**: AID_NONE has to be visible to the EKF failsafe so the vehicle lands
rather than coasting. That is a vehicle-side change and is not in this PR.

Ranking on the evidence: arm 3 > arm 1 > arm 0 > arm 2, with the caveat that
arm 3's advantage over arm 1 exists only for quality-degrading faults, and that
neither is sufficient on its own.

## Not tested

- Whether a shorter detection threshold helps once the response is capped.
- Any real flow sensor. Every fault here is synthetic.
- Arm 2 repeats - it was run once per hypothesis and abandoned once the
  mechanism explained the result.
- The yaw-decorrelation discriminator (a body-frame sensor bias stays on the
  same body axis through a heading change; a NED velocity state error does
  not). Free when the vehicle yaws, worthless when it does not.

## Reproducing

Scratch worktree only - none of the arms, the scratch parameters or the
harness are intended for the PR.

```
git worktree add --detach <scratch> pr-vel-flow-axis-gate
git -C <scratch> cherry-pick 39606c5e16 fab688bc1c f2ae031f6b   # quality plumbing
# add EK3_FLOW_RECOV / EK3_FLOW_QMIN and the ABFlowLockout harness
AB_ARM=<0|1|2|3> AB_HYP=<H1|H2|H2b|NONE> \
  python3 .claude/skills/autotest/run_autotest.py test.Copter.ABFlowLockout
```

## Follow-up: falling back to ALT_HOLD rather than landing

The conclusion above said the give-up path should reach a terminal action and
land. That was wrong for indoor flight: landing is a *controlled crash into
whatever is under the vehicle*, and it takes authority away from a pilot who
is standing right there. Copter already has the better action -
`FS_EKF_Action::ALTHOLD` (`ArduCopter/ekf_check.cpp`), which hands back direct
attitude control. The gap is unchanged: the failsafe still cannot fire,
because AID_NONE zeroes the test ratios it watches.

Modelled by switching to ALT_HOLD the moment aiding is dropped. Sticks stay
neutral - there is no pilot in this harness.

| fault | stay in LOITER on AID_NONE | fall back to ALT_HOLD, no pilot |
|-------|---------------------------|---------------------------------|
| H1 IMU/accel-bias fault | 11.1 / 12.4 / 13.8 m | **91.1 / 92.4 / 92.6 / 93.4 m** |
| H2 flow fault, quality good | 12.9 / 13.5 / 13.6 / 15.5 m | **3.1 / 4.0 m** |
| H2b flow fault, quality low | 9.8 / 10.2 m | **2.7 / 2.8 m** |

For a flow fault the fallback is a 3-5x improvement, and 2.7-4.0 m is the
first number in this whole exercise that fits inside a room. It also shows
that LOITER on AID_NONE is **not** a benign coast: the position controller
running on a frozen, zero-velocity estimate was actively making things worse,
and simply removing it recovers most of the distance.

For an IMU fault the same change is 7x *worse*. Likely mechanism, stated as a
hypothesis and not verified here: a 1.5 m/s^2 body-X accel bias tilts the
attitude estimate by about `asin(1.5/9.81)` = 8.8 deg, so ALT_HOLD holding
"level" per the estimate parks the airframe at a true 8.8 deg lean and it
accelerates continuously - measured EKF speed reaches 4.3-4.5 m/s. Whatever
LOITER was doing on its degraded estimate, it was at least opposing that.

**What this harness cannot measure is the entire point of the proposal.** The
case for ALT_HOLD is that a human is on the sticks; with neutral sticks the
H1 number is "ALT_HOLD with an absent pilot", which is the worst case rather
than the design. A pilot watching the vehicle drift would arrest it, and that
is exactly the authority ALT_HOLD restores and LAND removes. Any decision
resting on the H1 column needs a pilot-in-the-loop test, or a real flight.

The defensible reading: fall back to ALT_HOLD rather than LAND, and note that
the benefit is clear-cut for flow-origin faults - which is the failure this PR
is about - while an IMU-origin fault removes the last automatic restraint and
relies wholly on the pilot.

## The control I should have run first: master's own behaviour

The table above compares the alternatives to each other but not to the
merge-base. Adding that arm (no detection, no response) changes the reading of
the whole exercise.

| response | H1 | H2 | H2b |
|----------|----|----|-----|
| do nothing (master) | 81.5 / 101.5 m | 56.4 / 56.5 m | 56.7 / 57.0 m |
| hard reset (this PR) | 1.7 / 1.8 / 2.4 m | 76.6 / 77.8 / 78.0 m | 76.5 m |

So for the failure it was written for, the PR is roughly a **40x** improvement -
82-102 m down to under 2.4 m, against a 0.27 m no-fault baseline. That is a very
good result for the problem it targets.

And the H2 regression is smaller than it looked when the only comparison was
against the give-up arm. Master is *also* catastrophic under H2 (56 m): a
permanently rejected axis leaves that velocity component unconstrained and
LOITER chases it. The PR takes 56 m to 77 m. It makes an already unsurvivable
case about 35 percent worse; it does not turn a safe case into an unsafe one.
An earlier draft of this file implied otherwise by comparing only against arm 0,
which was misleading.

With `EK3_FLOW_QMIN` set, H2b goes from 57 m on master and 76 m on the PR to
10 m. That is the one column where the PR plus the quality gate is
comfortably better than master.
