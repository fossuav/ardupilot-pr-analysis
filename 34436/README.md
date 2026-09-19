# PR #34436 - Copter: honour the harmonic notch loop rate option in the rate thread

[ArduPilot/ardupilot#34436](https://github.com/ArduPilot/ardupilot/pull/34436),
branch `andyp1per/pr-rate-thread-notch-loop-rate`, opened 2026-09-19 at
`92e9caf784` on master `368dc0c428`. Two commits: `cc414b32dc` (Copter,
`rate_thread.cpp`) and `92e9caf784` (Filter, the `INS_HNTCH_OPTS`
description).

## What it does

With the rate thread running, `rate_controller_filter_update()` re-centres
every harmonic notch and updates the backend filters at `filter_rate`, the
rate loop rate capped at half the gyro rate, whatever `INS_HNTCH_OPTS` says.
The "Update at loop rate" option did nothing. Now, if any enabled notch sets
the option, the rate is as before; otherwise it is the scheduler loop rate.
The option is `@RebootRequired`, so reading it once in
`rate_controller_set_rates()` is enough.

It came out of #32995's bench work: on RPI_UAVFC, 36 per-motor notch
coefficient sets at 1608 Hz. The same patches are `caebec43a7` and
`982b41d3fe` on the RP2350 branch (`d9652ca650` and `706f76e33f` since its
2026-09-19 rebase onto `368dc0c428`). Measurements in
[../32995/bench-2026-09-19.md](../32995/bench-2026-09-19.md).

## Evidence

- RP2350 bench, props off, the notch leaf already in SRAM: armed core1 66% ->
  56.5% at zero throttle and 72% -> 61% at spin min with the option cleared;
  the notch update chain ~10% -> ~1.4% of core1. That was measured on the
  first version of the change; the final version is identical for option-clear
  and restores the old rate for option-set.
- Copter.DynamicRpmNotchesRateThread passes at `d53e33a7c2` (-19.4/-25.7 dB
  against a -10 dB limit; -20.2/-24.8 dB at the earlier `8ed8f80553`). The
  final commit changes only the option-set path, which this test never
  takes, and was built but not re-run. Weak coverage: SITL's gyro is 1 kHz,
  so the default only moves 500 Hz -> 333 Hz, and no autotest sets the option
  with the rate thread on.
- Tracking cost modelled from log52's ESC telemetry (in the #32995 note): at
  200 Hz the notch trails the motor by 1.7 Hz at p99 and 11.7 Hz on the worst
  transient, 7% and 50% of the single notch's half-bandwidth.
- **Owed:** a flight comparing notch attenuation through throttle punches with
  the option off.

## Design decisions, and what was rejected

| Proposal | Why not |
|---|---|
| Just clear `LoopRateUpdate` in the params | the rate thread never read it; that was the bug |
| Default to a fixed 200 Hz, as the option's docs said | Andy: the default is the scheduler loop rate |
| With the option, run on every rate-loop iteration (`filter_rate = 1`) | tried; the final review found `FSTRATE_DIV` defaults to 1, so option users would pay twice today's cost for updates the telemetry cannot feed. Capped at half the gyro rate again, so the PR only ever reduces cost |
| Let the main loop's notch task run when no notch sets the option | Andy: the notch is driven by motor telemetry and belongs with the fast loop; in the main loop it contends with everything else |
| A fixed cap on the filter rate (a 100 Hz cap was on the RP2350 branch in June) | ignores the option; the June cap was taken out while removing RP2350 code from Copter, not for a measured reason |

## Review findings answered

- Mixed notches (one with the option, one without) all update fast: known and
  unchanged, as they all did before; in the PR body. Rated must-fix by one
  Codex pass, left as documented.
- Stale design comments at `rate_thread.cpp` 6b and line 204: fixed.
- `INS_HNTCH_OPTS` docs described only the non-rate-thread path: the Filter
  commit.
- "Filter update now always lands on the same iteration as the full servo
  push, so the worst iteration grows": rejected. Before the change the filter
  update ran on every iteration, push included, so the worst case is unchanged.
