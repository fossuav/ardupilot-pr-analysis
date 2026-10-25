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
