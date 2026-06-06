# AC_Loiter drag/feed-forward fix: forensic validation against the reviewer's analysis

This is the write-up posted to PR #33318 in reply to Leonard's review. He agreed
the patch is a correct kinematic-consistency fix but argued (a) it "works because
the velocity PID's I-term absorbs the mismatch" and on optical flow "papers over
the actual bug", and (b) the real bug is the drag formula treating the EKF
observability cap (`gnd_speed_limit = MIN(LOIT_SPEED, ekfGndSpdLimit)`) as a
terminal velocity, so `drag_decel >> real_drag`. Both points are right; the data
shows the patch nonetheless reduces integrator load in the regime where the bug
lives. Reconstructed with `forensic_drag_analysis.py` from two real indoor flights
on the same airframe and params: log276 (before) and log278 (after).

---

Thanks for the detailed read. It's the right model, and it sent me back to the two
indoor logs to check it properly. Short version: I think you're right about the
root cause, and the data backs your drag-formula analysis. Sharing what I found.

Same airframe and params on both: log276 (before) and log278 (after).

One setup note that caught me out first: although `EK3_SRC1_POSXY/VELXY` are GPS
and the receiver held a 3D fix, the EKF never actually used GPS indoors.
`XKF4.SS` has horiz_pos_abs and using_gps clear with horiz_pos_rel set, and the
`XKF3` GPS innovations are all zero. So both flights are genuinely AID_RELATIVE
optical flow, which is exactly the regime your analysis describes.

On the root cause the logs agree with you:

- HAGL sat at 0.3 to 1.5 m, so `ekfGndSpdLimit = (FLOW_MAX-1)*HAGL` came out at
  0.15 to 2.26 m/s and bound `gnd_speed_limit` for the whole flight. LOIT_SPEED
  (5 m/s) never even entered the MIN.
- With that cap, `drag_decel = pilot_acc_max * v / gnd_speed_limit` reaches
  4.65 m/s^2 (0.82 of pilot_acc_max) at desired speeds of only ~0.5 m/s. That is
  nowhere near real airframe drag at half a metre per second. So
  drag_decel >> real_drag exactly as you say: the observability cap is being used
  as a terminal velocity.

The patch does not fix that. drag_decel is essentially unchanged after it (same
flow regime). All it changes is whether that drag term is consistent between the
velocity it shapes and the acceleration it feeds forward:

```
calc_desired_velocity(), each step, into AC_PosControl:

              desired velocity (plan)      feed-forward accel (push)
  before:     v -= (drag + brake)*dt       a -= brake            ->  a exceeds d(v)/dt by drag
  after:      v -= (drag + brake)*dt       a -= (brake + drag)   ->  a == d(v)/dt
```

On the I-term: I think your steady-state relation is the right lens, so I followed
it through both regimes. With the integrator settling at real_drag - drag_decel
before and real_drag after:

```
steady-state velocity-PID integrator (PIDN/PIDE I):

                     pre-fix               post-fix
  GPS, calibrated:   real_drag - drag ~ 0  real_drag            (drag ~ real_drag)
  flow, collapsed:   real_drag - drag      real_drag ~ 0
                     = -drag  (large)      (small)
```

You were reasoning about the GPS column, and there you're right: the patch moves a
little work into the integrator that the old code did not need. But the bug and
these logs live in the flow column, and there it was the old code leaning on the
integrator. It had to wind to about -drag to track, and it lagged in transients,
which is the overshoot. Pulling the logs confirms it: integrator magnitude P95
2.9 m/s^2 (peak 3.7) before, P95 0.16 (peak 0.19) after, with along-track position
error going from about +/-0.9 m to +/-0.1 m. So in this regime the patch takes load
off the I-term rather than adding it.

Where that leaves me: this is a narrow kinematic-consistency fix that clears the
overshoot in the collapsed-cap case and checks out on the vehicle (log278). It
doesn't touch the drag model. Your scaling approach, pulling pilot_acceleration_max
and gnd_speed_limit down together so the cap stays a real terminal velocity, is the
better general fix, and I'd be glad to help test it. It's a larger behaviour change
so it probably belongs as its own piece. Happy to go whichever way you think serves
the long-term model best.

---

## Reproduction notes (archive)

`forensic_drag_analysis.py <log.bin> <t0> <t1>` reconstructs `gnd_speed_limit`,
`drag_decel`, the position-controller feed-forward (PSCN/PSCE DAN/DAE) and the
velocity-PID integrator (PIDN/PIDE I) from the inputs `calc_desired_velocity`
uses, and prints the stats above. `--plot out.png before.bin bt0 bt1 after.bin
at0 at1` makes the before/after comparison figure.

The committed SITL plots (`plots/A_overshoot_before.png`,
`plots/B_overshoot_after.png`) show the same over-drive mechanism in the
`LoiterFlowBrakeOvershoot` autotest, which is public-data reproducible; the
integrator numbers above are from the real indoor flights, which are not
committed here.

## Follow-up: log279, and why it argues for your drag-model fix

Flew a third indoor flight (log279) with the patch, deliberately twitchy to stress
it. The consistency fix holds: over 175 s of flow Loiter the integrator stays at
P95 0.18 m/s^2 (peak 0.23) and along-track position error at P95 0.059 m, and
through a burst of 8 quick forward jabs it held within +/-0.07 m with no overshoot
and no backward lurch.

The interesting part is what's left. Each jab release produces a sharp 15-19 deg
rearward brake. It's correct - the vehicle decelerates and stops on target, no
overshoot - but it's much harder than it should be for a sub-1 m/s nudge. It's the
drag term: `drag_decel` hits ~5 m/s^2 (0.92 of pilot_acc_max) because
`gnd_speed_limit` is the collapsed flow cap (0.5-2.5 m/s). Exactly your point - the
cap is standing in for a terminal velocity, so the brake is sized for a 5 m/s
airframe, not a half-metre-per-second one.

Two aggravators at this height. The rangefinder is bottoming out (`RFND.Status` 2
/ OutOfRangeLow, `Dist` floored at 0, max 1.02 m) while the EKF `HAGL` drifts to
1.7 m, so the cap swings 0.5-2.5 m/s and the brake magnitude jumps jab to jab. And
because the patch puts drag in the feed-forward, that inflated, noisy drag now
shows up directly as attitude instead of being smoothed through the position loop.

So log279 reinforces both conclusions: the consistency fix is right and removes the
overshoot, and your scaling fix (pull pilot_acceleration_max down with the cap) is
what actually tames the magnitude. Worth a separate look too at the rangefinder
min-range dropout corrupting the cap below ~1 m.
