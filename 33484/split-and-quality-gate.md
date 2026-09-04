# PR #33484 - what changed on 2026-09-04

Addendum to `README.md`, which was written before this and is superseded on
two points: the branch no longer carries `EK3_FLOW_MIN_H`, and the PR
description has since been rewritten. Everything the README says about the
mechanism, the flights and the Replay tuning still stands.

Head is now 56c465d716, eight commits.

## The floor moved to its own PR

rmackay9 reviewed the `EK3_FLOW_MIN_H` parameter and asked for it to live in
the flow library. It is now #34292 as `FLOW_HGT_MIN`, with the parameter in
`AP_OpticalFlow` and its value travelling to the filter with the sample.
Reasoning and the plumbing detail are in `../34292/README.md`.

The split was verified conservative: comparing this branch's contribution
before and after, every removed line belongs to the floor and nothing was
added.

## New: EK3_FLOW_QMIN

The recovery re-anchors horizontal velocity to a flow measurement that has
just failed its own innovation gate. That is right when the state has drifted
and the flow is good, and wrong when the flow is the faulty one, and with flow
as the only horizontal aiding source the filter has no independent reference
to tell them apart.

The sensor's own surface quality is one signal that does distinguish them, and
the filter was throwing it away - `writeOptFlowMeas` tested `rawFlowQuality`
for non-zero and discarded it. It is now carried to the fusion time horizon
(replay-safe: the DAL already logged it), and below `EK3_FLOW_QMIN` the
recovery stops using flow instead of re-anchoring.

Defaults to 0, off, following `VISO_QUAL_MIN`. Quality scales are not
comparable between sensors.

Measured in SITL, LOITER at 3 m on flow-only nav, peak true distance travelled
in 30 s after the fault:

| response | state wrong | flow wrong, quality good | flow wrong, quality low |
|----------|-------------|--------------------------|-------------------------|
| master | 81.5 / 101.5 m | 56.4 / 56.5 m | 56.7 / 57.0 m |
| this PR, no quality gate | 1.7 / 1.8 / 2.4 m | 76.6 / 77.8 / 78.0 m | 76.5 m |
| with EK3_FLOW_QMIN set | 1.7 / 1.9 m | 76.2 / 78.1 m | 9.8 / 10.2 m |

It does nothing for a sensor that is confidently wrong. Full method and the
two rejected alternatives are in `ab-lockout-response.md`.

## Index 13, not 12

`EK3_FLOW_QMIN` took `var_info2` index 13 and 12 is now free, because
`EK3_FLOW_MIN_H` occupied 12 as an `AP_Float` on builds that have been flown.
Rebinding that index to an `AP_Int16` risks reinterpreting a stored value on a
real vehicle. A cosmetic gap is the cheaper mistake.

## Anticipated review point

The same "put it in the flow library" argument will likely be made about
`EK3_FLOW_QMIN`. The answer differs: "I cannot focus below 0.3 m" is a sensor
fact, but "quality good enough to justify a velocity reset" is estimator
policy, and normal fusion of a low-quality sample continues either way. That
is unlike `VISO_QUAL_MIN`, which gates whether data is sent to the EKF at all.

## Commits

```
56c465d716  autotest: cover the optical flow quality gate on lockout recovery
d3a0ac1e6e  AP_NavEKF3: do not re-anchor velocity to a poor optical flow sample
6b4d125c95  AP_NavEKF3: carry optical flow quality to the fusion time horizon
45419b5541  AP_OpticalFlow: report SIM_FLOW_QUAL as the SITL surface quality
010e0127de  SITL: add SIM_FLOW_QUAL optical flow surface quality
2cd07923d5  autotest: cover optical flow single-axis lockout recovery
b5493936b2  AP_NavEKF3: recover velocity from a single-axis optical flow lockout
2e02161d1a  AP_OpticalFlow: apply SIM_FLOW_OFS offset to the SITL flow rate
9d8e218d67  SITL: add SIM_FLOW_OFS optical flow rate offset for fault injection
```

## Autotest note

`EK3_FlowAxisLockoutRecovery` provokes the lockout with `SIM_FLOW_OFS_X`
rather than an accel bias. The accel bias reaches that state only indirectly,
via drift, and was genuinely flaky - it passed one run and failed the next with
no change to the test. `XKF5.NI` shows the same rejection in both halves while
`XKF7.FVC` counts a reset only with the option set, so the negative half is not
vacuous.
