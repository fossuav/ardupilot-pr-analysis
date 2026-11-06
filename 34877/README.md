# AP_HAL_SITL: main-thread BinarySemaphore waits, and SemaphoreRecursion

**Open as [#34877](https://github.com/ArduPilot/ardupilot/pull/34877)**,
opened 2026-10-25 from `andyp1per/semaphore-recursion-example` at
`ede19eaf75`, two commits on master `d969364f35`. Split out of #32995
(the RP2350 port), whose second commit carried the example.

## Why

The SemaphoreRecursion example came from the RP2350 port, where it checked
the port's recursive mutexes. Moved onto master to go up on its own, it
failed in SITL: the main thread's wait for the worker thread timed out,
and the next wait then took that stale signal.

Cause, in `libraries/AP_HAL_SITL/Semaphores.cpp`: BinarySemaphore::wait()
from the main thread (or with `semaphore_wait_hack_required()`, which is
also main-thread only) busy-waits so simulated time advances. It held
`mtx` for the whole loop, and signal() takes `mtx`; the only release was
inside a `pthread_cond_timedwait()` with a zero, already-expired timeout.
The loop also never looked at `pending`, so a signal that did get in was
missed and stayed pending for the next call. Ordinary Semaphore::take()
busy-waits without holding any lock. The code dates from tridge's
original SITL BinarySemaphore, `7059f980b8` (2023-12-30).

## The change

`7ceb70f3d1`: give `mtx` before each 10 us delay, take it back after, and
return when `pending` is set. `ede19eaf75`: the example, David Buzz as
author, with `hal.console->printf` in place of `::printf` (most HAL
examples use the console, and it works where stdout is not wired up).

## Measured

The example in SITL, run as `build/sitl/examples/SemaphoreRecursion`
(examples run without a simulator attached):

| | runs | PASS |
|---|---|---|
| without the fix (`::printf` version) | 20 | 13 |
| without the fix (final version) | 40 | 26 |
| with the fix (`::printf` version) | 20 | 20 |
| with the fix (final version) | 60 | 60 |

Builds for MatekH743. Mechanical gate clean.

## Reach

A search of master finds no vehicle code waiting on a binary semaphore
with a timeout from the main thread: AP_Canard_iface waits from the CAN
thread, FastRateBuffer and SIM_FlightAxis use wait_blocking(), and lwIP's
`sys_arch` waits come from its own threads. So the fix should not move
any autotest; none was run.

## AP-Review round 1 at `ede19eaf75`, 2026-10-25

COMMENT, not REQUEST CHANGES. The bot agrees the SITL fix is right and
lowers the lost-wakeup rate. CI was red only on "test blimp", green on
master, cause not confirmed by the bot.

- Should fix, not yet checked here: in SITL examples the clock advances
  only in the wait loop and never sleeps, so the example's 1 s worker
  timeout is about 1.4 ms of real time. A slow worker wake-up prints
  "worker completion: FAIL" and the late signal then satisfies the next
  attempt. The bot saw 1 in 30 fail under load on a fresh build;
  worker_done.wait_blocking() passed 30 of 30, at the cost of hanging
  rather than printing FAIL on a broken HAL.
- Minor: the class is only allocated with new, so the false and 0
  initialisers on lines 42, 45 and 46 can go (CLAUDE.md agrees); keep
  test_ok = true.

Nothing changed yet. The 60 in 60 here was on an idle machine.

2026-10-27: taken out of #32995's table of split-out PRs at Andy's
request; it is just an example, and the port does not depend on it.

## 2026-11-05: round 1 fixed (local `r1105/34877-fix3` at `9377f42416`, not pushed)

Worktree `r1105-34877`, three commits on `ede19eaf75`:

- `f4dffb085e` keeps the timed wait() but, in SITL, waits UINT32_MAX us,
  named WORKER_TIMEOUT_US; elsewhere it stays 1 s. Reproduced first: with
  48 busy processes on 24 cores, `ede19eaf75` failed 48 of 60 runs, every
  one on "worker completion" (in the run inspected all three waits timed
  out). At the head: 60 of 60 under the same load, 30 of 30 unloaded.
- `574bac606a` drops the zero initialisers. Checked first: every
  operator new in `AP_Common/c++.cpp` is calloc.
- `9377f42416`, from a Codex cold read: thread_create()'s result was
  ignored. A failed start is now reported ("worker thread started: FAIL")
  and the worker attempts skipped; forced in SITL, it prints FAIL at once.

Why a timed wait and not wait_blocking(): the example is the regression
test for `7ceb70f3d1`, which fixes BinarySemaphore::wait() from the main
thread. A wait_blocking() version (tried first, `733a3f5405` on
`r1105/34877-fix`) also passed 60 of 60 under load, but with the SITL fix
backed out it passed 20 of 20, so it no longer catches that bug. The
timed version with the fix backed out hangs in 17 runs of 60 (6, 4 and 7
of 20 on three builds whose SITL code differs only in line numbers), where
the 1 s original failed 14 of 40.

Measured timeouts, with a probe whose worker never signals: with the SITL
fix, three UINT32_MAX timeouts took 15.6 s of real time (5.2 s each,
about 830x simulated time); without it, three 100 s timeouts took 194 s
(1.5x), so one full timeout there is about 46 minutes. That is how the
example fails without the fix: it sits in the wait, its console output
buffered, and prints "worker completion: FAIL" after about 46 minutes.

Hardware: a second Codex read flagged that UINT32_MAX everywhere would
make a non-signalling worker cost 71 minutes per attempt on hardware (its
watchdog-reset claim does not hold: examples have no AP_BoardConfig, so
watchdog_enabled() returns the default, false). The long timeout is
therefore SITL-only. The SITL objects with and without that `#if` differ
only in the two WITH_SEMAPHORE line constants, so the SITL figures carry
over; the example builds for MatekH743. A third cold read of all three
commits was clean.

CI "test blimp": unrelated. SIMCompare fails with the same distance,
4.03239913609426 m, on at least eight unrelated PRs' runs between 3 and
5 November (vehicleinfo_test, NAV_CONTROLLER_PROGRESS,
waf_c_optimization, fix/puya-py25q128ha-littlefs and others).

Gate and branch conventions clean. Reply and a description edit drafted,
not posted.

## 2026-11-06: pushed

`semaphore-recursion-example` `ede19eaf75..9377f42416` (fast-forward, the
round-1 fixes). Reply and description edit still drafted, not posted.

## 2026-11-06: reply posted

https://github.com/ArduPilot/ardupilot/pull/34877#issuecomment-6684181139

Description updated (the SITL timeout and the loaded-machine runs).
