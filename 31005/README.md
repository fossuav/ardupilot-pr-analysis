# #31005 Copter: don't fall out of the sky at zero throttle on min alt fences

### 2026-11-06: AP-Review fix on `r1106/31005-fix` (`943b540cef`, `5554038196`, `806fd8d2cf` on `957228a8e4`, not pushed)

AP-Review (2026-09-30, REQUEST CHANGES): skipping the disarm entered RTL
with auto_armed already cleared by zero throttle in STABILIZE, so RTL held
ground idle and the copter still fell. `943b540cef` sets auto_armed in
fence_check()'s else branch, gated on `motors->get_interlock()`: a SITL heli
in a manual autorotation was otherwise flown by RTL on an undriven rotor,
fell below critical rotor speed and was disarmed by the land detector at
38 m; with the gate it autorotates as on the PR head. A max alt breach at
zero throttle takes the same path (not tested separately).

`5554038196` adds MinAltFenceZeroThrottle (80 m, 65 m floor, STABILIZE at
zero throttle): PR head enters RTL and hits the ground at 17.1 m/s; with the
fix the lowest point is 52.7 m, it climbs back and lands at 0.5 m/s.
`806fd8d2cf` pops its nested context in a finally, after a Codex cold read
found a failure also reported a context-count mismatch; the PR-head build
now fails with "Fell to 37.0m" alone. All 12 fence tests pass.

Open: ALT_MIN plus a polygon or circle breach still starts the 10 s manual
recovery window, as on master; no test covers the interlock gate (SITL heli
only).

Pushed 2026-11-06: `pr-min-alt-disarm` `957228a8e4..806fd8d2cf` (fast-forward). Reply posted: https://github.com/ArduPilot/ardupilot/pull/31005#issuecomment-6690424237

## 2026-11-07: squashed, nothing in it flown, pushed

`FENCE_ENABLE` is 0 on every SFD-O4 and Q25 log, so neither the min alt
change nor its fix has flown, and the fix folds into it. Pushed
`806fd8d2cf` -> `2a11dfad65` (force, 5 commits to 3, same tree; backup
`pre-squash/31005-1107`). `943b540cef` (auto_armed on the hand-over)
folds into `3027988a2b`, now `51bbd04ec9`, whose message now says what
the skipped disarm does and carries the fix's SITL figures. The
nested-context fixup `806fd8d2cf` folds into the test `5554038196`, now
`2a11dfad65`. The AC_Fence commit is unchanged apart from its parent
(`0473515e97`).
