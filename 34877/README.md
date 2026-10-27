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
