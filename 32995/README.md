# PR #32995 - RP2350 Port

Analysis archive for [ArduPilot/ardupilot#32995](https://github.com/ArduPilot/ardupilot/pull/32995).
Buzz's PR, branch `rp2350-v5-squashed-and-cleaned-and-rebased` on the
**davidbuzz** remote, which andyp1per pushes to. Base `master`, merge-base
`b832113b10`. PR head `c1c8709823` as of 2026-09-14, 222 commits; 23 local
cleanup commits sit on top of it at `00d07c8f34`, **not pushed**. The
2026-09-11 session left head `27f3531d62` (198 commits); the work of
2026-09-12 and 2026-09-13 (`3326ce8af7`..`c1c8709823`: watchdog reset
detection, SD storage health, registry misses failing the build, bootloader
hex/UF2 address) was pushed without an entry here. Local safety refs
`backup/rp2350-pre-cleanup-20260911` (the original 179 at `164ac005d5`) and
`backup/rp2350-pre-gitmodules-drop`.

## Status (one line)

CI's six deterministic autotest failures are fixed and the conventions check
is down from seven failing categories to one; review cleanup reduced chip
conditionals outside the HAL from 26 to 3 and open review threads from 20 to
8. Remaining blockers are the ChibiOS submodule not being merged upstream,
three behaviour-changing chip checks awaiting a decision, and a handful of
unrelated changes that want spinning out as precursor PRs.

2026-09-14: the three chip checks are now board defines and there are no
`defined(RP2350)` checks left in vehicle or library code (only
`AP_HAL_ChibiOS`, `Tools/AP_Bootloader` and `Tools/CPUInfo` still have them);
shared-file churn is reverted to master text (excluding the submodule,
modified files 93 -> 86, lines deleted from master 694 -> 371). Unpushed.
The ChibiOS check is still the one red gate.

## Facts worth not re-deriving

Each of these cost real work to establish.

**The autotest failures were one line.** `ff0f01daa3 "AP_GPS: fix the ublox
detection baud test and re-probe"` changed the u-blox detection gate from
`_baudrates[dstate->current_baud]` to `dstate->probe_baud`. That single hunk
caused all six deterministic failures: Copter ProximitySensors (`ld06` 680 vs
1200), CommonOrigin, SIMCompare (`vel-err 3.7 m/s`), Replay,
GuidedWeatherVane (heading 84), and Plane GpsSensorPreArmEAHRS. Measured
mechanism: GPS 1 is detected at sim t=0.1 s with the hunk versus t=1.3 s
without, one full `GPS_BAUD_TIME_MS` (1200 ms) earlier, because `probe_baud`
holds the port's configured rate (230400 via `SERIAL3_BAUD`) while
`current_baud` is still index 0 (9600). Five failures are just the
deterministic SITL timeline moving under hard-coded expectations. The sixth
is different and unexplained: in the plane EAHRS test GPS 1 gets a fix and
both EKFs report "is using GPS", yet `SYS_STATUS` never sets the GPS health
bit for the full 30 s window. `AP_GPS::is_healthy()` gates on
`timing[].delayed_count` and `average_delta_ms`, which live outside the
`state[]` memset and survive re-detection - plausible but **not** pinned,
because the ~2600 ms `GPA.Delta` spike I suspected appears in the passing run
too. The commit is dropped from the branch. If it is ever resubmitted it
needs its own PR with those test expectations revisited and the plane health
question answered.

**A/B method that worked.** `git worktree add --detach <scratch>/base
<merge-base>`, build `bin/arducopter` there, then swap
`build/sitl/bin/arducopter` between baseline and branch binaries while
running the same test from the same clone. Per-hunk attribution came from
reverting one hunk at a time and re-running. Budget roughly one minute per
SITL build, a few seconds per short autotest.

**The conventions checker disagrees with our CLAUDE.md.**
`Tools/scripts/check_branch_conventions.py` + `allowed_subsystems.py` reject
`scripts:`, `debug:`, `CPUInfo:`, `environment_install:`, `gitignore:`,
`Agents:` and `ardupilotwaf:`. `Tools/{debug,scripts,CPUInfo,environment_install}`,
`.gitignore` and `AGENTS.md` all map to **`Tools`**; `Tools/ardupilotwaf` maps
to **`waf`**; `modules/ChibiOS` to **`modules`**. `debug` is also in
`BLACKLISTED_PREFIXES` (via `DEBUG`). We settled on compound prefixes -
`Tools: scripts: ...`, `waf: ardupilotwaf: ...` - which pass because the
checker only looks at the text before the first colon. Andy considers the
check wrong and intends a separate PR to change it. **The root CLAUDE.md
commit-prefix table still teaches the rejected forms and has not been
updated.**

**hwdef commits did not need splitting.** `hwdef/*` maps to *both* `hwdef`
and `AP_HAL_ChibiOS`, so for the four commits that touch hwdef plus
`AP_HAL_ChibiOS/*.cpp` the valid-prefix intersection is exactly
`AP_HAL_ChibiOS`. Renaming the prefix cleared the check with no split.
Splitting `220bb78f2a` ("enable SMP dual-core") would have left a
non-compiling intermediate commit.

**ChibiOS submodule: the only remaining red check, and it is not fixable
here.** `check_submodule_references_exist` requires the SHA to be reachable
from **master** in the canonical repo, accepting only compare status `behind`
or `identical`. `ArduPilot/ChibiOS/compare/master...e709d6823910` returns
**`ahead`** - so the RP2350 series sits cleanly on top of ArduPilot's ChibiOS
master with no divergence, but is not merged. Separately verified: the SHA
**is** fetchable from the canonical `https://github.com/ArduPilot/ChibiOS.git`
URL (tested with a real `git fetch --depth 1` into a throwaway repo, exit 0,
object type commit) because `andyp1per/ChibiOS` is a fork of
`ArduPilot/ChibiOS`, and `git submodule update --init` works on git 2.43.0
(same as CI) by falling back to fetching the explicit SHA. That is why
dropping the `.gitmodules` commit was safe. **Goes green only when the
RP2350 ChibiOS commits land in `ArduPilot/ChibiOS` master.** There are 20 of
them, from `9f37253c1b` to `e709d68239`.

2026-09-14: the pin has since moved to `63cd89e0f6` (ArduPilot/ChibiOS#113),
still `ahead` of ChibiOS master, so the check stays red on the same grounds.
That series now also adds 138 lines of optional write-path statistics to the
shared `hal_mmc_spi.c`; that belongs in the ChibiOS#113 review.

**The mock IMU backend and the inverted panic guard.** Master's
`AP_InertialSensor::start()` (around line 874) panics *when*
`AP_INERTIALSENSOR_ALLOW_NO_SENSORS` is set and the gyro count is zero. That
is why the port needed `AP_InertialSensor_NONE`: the flag suppressed the
`config_error` and then the guard panicked, so a substitute backend was added
to satisfy the count. Consequence: removing the mock while leaving the flag
set turns "boots with fake IMU" into "panics on boot" - **they have to go
together**, and both are now gone from Laurel and Pico2. The reason to
remove them is recorded in RPI_UAVFC's own `DEVELOPMENT.md`: on Laurel v1 a
failed probe silently substituted the mock, whose flat 0.01 per axis with no
gravity term "produced plausible-looking but wrong IMU data and cost a day of
chasing a phantom performance problem".

**Lazy `@SYS` generation bought nothing.** The defence was that returning
size 0 from `open()` is safe. But the size in the FTP open ack comes from
`GCS_FTP::OpenFileRO` calling `AP::FS().stat()`, and
`AP_Filesystem_Sys::stat()` has always returned a fixed placeholder ("too
expensive to read every file for a directory listing"). So generation at open
never fed the reported size; deferring it only moved an ENOMEM from `open()`
to the first `read()` and changed the error contract for every board. The
companion `ExpandingString::reserve()` argued against itself: `expand()` grows
`(5*buflen/4) + 512` via `mem_realloc`, which can extend in place, whereas one
upfront allocation of the whole buffer needs a single contiguous block -
harder on a fragmented heap, not easier. The "FATFS deadlock" in commit
`77a362d8de`'s subject has no body, and the generation path only calls
`hal.util` info functions and `AP::scheduler().task_info()`, none of which
touch the filesystem; `AP_Filesystem` holds no lock across the backend
`open()`. If there was a real deadlock its cause is unrecorded.

**Upstream bug found in passing, wants its own PR.** In
`GCS_serial_control.cpp` the blocking wait is dead code on master:
`packet.flags` is assigned `SERIAL_CONTROL_FLAG_REPLY` before
`if (packet.flags & SERIAL_CONTROL_FLAG_BLOCKING)` is evaluated, and REPLY is
1 against BLOCKING's 8, so `1 & 8 == 0` and a blocking SERIAL_CONTROL request
never waits for MAVLink TX space on any board. The port's `flags & BLOCKING`
fix is correct but was dropped from this PR as unrelated.

**Smaller measured facts.** Largest `group_info` table in the tree is 62
entries (`AP_OSD_Screen`), against a `uint8_t` wrap at 256 - the AP_Param
counter widening guarded an unreachable case, and would not have fixed it
anyway since `group_id()` still takes the index as `uint8_t`. `NOINLINE` is
referenced nowhere outside its own definition in `AP_Common.h`; ChibiOS
`os/common/ports/ARM-common/chtypes.h:91` defines it unguarded but the
`#ifndef` on our side is sufficient - Laurel and CubeOrange build with zero
redefinition warnings. `markdownlint-cli2@0.4.0` has **no `--fix` flag** (it
came later and is silently a no-op); use the separate `markdownlint-cli2-fix`
binary from the same package. Unconditional `#pragma GCC optimize("O2")` is
established house style - 20 files in master use it - so the pragma itself was
never the problem, only the chip conditional around it.

## What the 2026-09-11 session changed

Listed oldest first; all are on the PR head.

Failures and conventions:

- Dropped `ff0f01daa3` (AP_GPS) - fixes all six deterministic autotest failures
- Dropped `aa3f4210ad` and removed the deferred gyro-cal path from
  `85d7f9f6ff` where it was introduced, which also removed an unguarded
  `update()` call in `_init_gyro()` that the commit message never mentioned
- Collapsed the two EKF3 commits to one; dropped `ac03608275` whose only
  surviving content was two dead declarations
- Reworded 19 commit prefixes, split the ChibiOS `.gitmodules` commit out,
  then later dropped it entirely
- Fixed 256 markdownlint errors across 15 files and 20 RST `:ref:` roles
- Added the missing trailing newline to `SemaphoreRecursion.cpp`
- Corrected attribution: 11 commits where Buzz's work had been squashed under
  Andy's name got `Co-authored-by: David Buzz`, and one the other way

Review cleanup (`dd970772aa`..`27f3531d62`):

- New per-file optimisation registry
  (`hwdef/common/rp2350_optimize_registry.txt`, format `path|level`) plus a
  waf hook in `chibios.py`, replacing 13 chip-guarded pragmas. Verified:
  registry files get `-Os -Os -O2` (last wins), non-registry files on the same
  board get `-Os` only, CubeOrange gets `-Os` and zero warnings, and both
  miss paths warn loudly (nonexistent path, and exists-but-never-compiled).
  `AP_NavEKF3` and `AC_AttitudeControl` now have **no diff against master**
- Dropped the Invensensev3 bring-up scaffolding: eight `dbg_` members were
  plain members and four stores per sample in `accumulate_samples()` were
  unconditional, so every board with that IMU paid in the FIFO path at up to
  8 kHz for a report only RP2350 compiled
- `AP_Filesystem_Sys` PC sampler guards lost the redundant chip half
- Rate-loop gyro queue depth became a board-tunable define, default 8
- Log free-space check: first made a capability knob, then restored to
  master's behaviour on every board once the mechanism was understood. The
  port had removed the `start_new_log()` check for **all** boards; that is
  back
- Dropped the mock IMU substitute and both no-sensor flags
- Dropped the AP_Param counter widening, the GCS_serial_control changes, the
  lazy `@SYS` generation and `ExpandingString::reserve()`
- Dropped four churn items: a comment reindent, the `NOINLINE` commenting-out,
  a `1.8f` literal change, a `::printf` left in the BinarySem example

## What the 2026-09-14 session changed

Started from Peter's `flash.c:85` comment: the RP2350 change was buried in a
reindent of the whole file (+144/-41 against master; now +69/-0). Andy set
the scope as that file, the same churn in every shared file, and shared
behaviour changes the commit messages never mentioned. The rule: revert to
master unless RP2350 needs it; if it does, gate it behind a board define;
leave genuine generic fixes in for now and spin them out later. History: 23
commits on top of `c1c8709823` (`b9b143b1fc`..`00d07c8f34`), squashing per
subsystem deferred.

Chip checks that became board settings. Defaults live in the library's
`_config.h`; RP2350 values go in the `PICO2.py` `DEFINES` dict, which the
generator emits as `#ifndef` blocks into `hwdef.h`:

| define | default | RP2350 | was |
|---|---|---|---|
| `AP_AHRS_DCM_BACKUP_DECIMATION` | 1 | 16 | `defined(RP2350)` in `AP_AHRS.cpp` |
| `AP_SCHEDULER_FAST_TASK_MODULO` | 1 | 2 on Pico2 only | a const member tested every tick on every board |
| `AP_MAVLINK_FTP_THREAD_PRIORITY_BASE`/`_OFFSET` | `PRIORITY_IO`, 0 | `PRIORITY_UART`, 121 | chip check in `GCS_FTP.cpp` |
| `AP_MAVLINK_FTP_TXBUF_BACKPRESSURE_ENABLED` | 1 | 0 | chip check in `GCS_FTP.cpp` |
| `HAL_INS_RATE_LOOP`, `__FASTRAMFUNC__` | as master | set in `PICO2.py` | RP2350 branches in `board/chibios.h` and `AP_HAL_Boards.h` |
| `HAL_WITH_ESC_TELEM` | master | 1 in `PICO2.py` | RP2350 branch in `AP_ESC_Telem_config.h` |
| `AP_RP2350_DEBUG_REPORT_ENABLED` | 0 | 1 in Laurel and Pico2 `hwdef.dat` (RPI_UAVFC already set 0) | chip check in `AP_HAL_Boards.h` |

Reverted to master, or cut down to an RP2350-only block (tridge's items in
brackets):

- `AP_Scheduler::task_info()` allocated from the calling thread, racing the
  main loop, and changed the `TasksV2` header for all boards (F6)
- STM32 fault handlers and `save_fault_watchdog()`: master text. With the
  `STM32_HW` guard gone, RP2350 saves through the `watchdog.h` macro to
  `rp2350_watchdog_save()`; its handlers stay a separate block (ISSUE).
  Derived from the source, not exercised with a real fault
- `thread_info()` restored `realprio != 1`; the SMP core suffix is only
  compiled with `CH_CFG_SMP_MODE`
- GDB thread helpers in `Scheduler.cpp` (F9); `sdcard.cpp` honours the
  caller's `tries` again; the storage-thread comment corrected (note 1)
- `chconf.h` dropped the `CH_CFG_USE_TM` override (an RT 8 leftover), and
  `halconf.h`, `common.ld`, `usbcfg.h`, `usbcfg_dualcdc.c`, `hrt.h`,
  `AP_Vehicle.cpp` and `AP_HAL/board/chibios.h` are master copies
- `chibios_hwdef.py`: OTG1 default-serial emission, `#ifndef` wrappers
  around non-RP CRT0 defines, the bootloader `CH_CFG_USE_TM` and
  `HAL_UART_NUM_SERIAL_PORTS` changes; `HAL_HAVE_PIO_UARTS` is emitted for RP
  MCUs only
- `STM32_HW` is now defined once, in `board.h`, instead of in three
  headers with an `#undef` in `SoftSigReaderInt.cpp` (tpwrules'
  thread is narrower but not closed: it is still a name ChibiOS does not
  define for this chip)
- `-DHAL_ENABLE_THREAD_STATISTICS` out of Laurel's `chibios_board.mk`: it
  duplicated the hwdef define and caused 103 redefinition warnings
- Every `#warning` added to shared driver code (F7 FIFO, DMA, I2C, GPIO)
- `flash.c` and `watchdog.c` back to master layout with the RP2350 code in
  its own `#if` blocks; the watchdog comments that named the wrong file
  and claimed a stub were rewritten
- About 70 garbled comments rewritten across 20 shared files; five had lost
  words, restored from the commits that introduced them (`100de10e82`,
  `c70cf83cbb`). About 90 non-ASCII characters replaced in 20 RP2350 files

Kept as generic fixes, for precursor PRs: `FastRateBuffer` rate limit and
signal-after-unlock, `AP_Logger_File` heartbeat, `@READONLY`, FATFS
`ENODEV`, UART `thread_init` priority boost, the `RCInput` counter, GPIO
`iomode_t`, `sdcard.cpp` bus lock, `io_size`, backoff and `f_mkdir`,
`GCS_FTP` semaphore wake, reply timeout and `ENOMEM` texts, and the Storage
SD reopen.

Verification, all measured on `00d07c8f34` or the commit named:

- After the `flash.c`, watchdog and `chconf.h` reverts, CubeOrange and
  MatekF405 `arducopter.bin` were byte-identical before and after. The
  later reverts changed STM32 objects only where intended: `system.o` back
  to master, `thread_info()`, and `__LINE__` constants
- Generator: `hwdef.h` output from master's and the branch's
  `chibios_hwdef.py` identical for all 870 non-RP2350 `hwdef.dat` and
  `hwdef-bl.dat` files
- 22 files whose change was meant to be comment-only compared equal after
  `gcc -fpreprocessed -dD -E -P` comment stripping
- CubeOrange objects, and then MatekF405 preprocessed sources, compared
  between the branch and a worktree holding master copies of every shared
  file. That audit is what found the undisclosed changes above; what
  remains is the generic-fix list
- Zero warnings building copter for CubeOrange, MatekF405, RPI_UAVFC, Pico2
  and Laurel, AP_Periph for f103-GPS, and the CubeOrange, RPI_UAVFC, Pico2
  and Laurel bootloaders. ESC telemetry and the rate thread are present in
  the RPI_UAVFC and Pico2 ELFs, thread statistics in Laurel's
- Every one of the 23 commits builds copter for RPI_UAVFC and CubeOrange
  with zero warnings, and the Laurel bootloader builds clean at `257775aefb`
  (the chconf/halconf change) and at `00d07c8f34`
- **Nothing was booted or flown.** The RP2350 behaviour claims (DCM rate,
  FTP priority, the fast-task modulo) are the same settings as before, moved;
  that equivalence is derived from the source, not measured on hardware

Method notes:

- Audit with the ChibiOS-coupled headers (`halconf.h`, `mcuconf.h`,
  `spi_hook.h`) at branch versions, or the master copies fail to compile
  against the pinned submodule
- A preprocessing wrapper that passes `-E` through a compile line must also
  drop the joined `-oFILE` form; the first version overwrote about 30
  CubeOrange objects with preprocessed text
- MatekF405, not CubeOrange, for preprocessed audits: CubeOrange's include
  dirs go stale (`lib_scsi.h`) after a clean
- A CubeOrange bootloader build after a copter build fails on stale DroneCAN
  dsdlc headers until `build/CubeOrange` is removed, and then needs a
  configure before waf finds `common.ld`

**Rejected: folding the cleanup into the original commits.** Andy's first
choice. Two attempts, both abandoned on 2026-09-14:

- Forward application of tip-to-cleaned hunks onto every historical version
  of each file (plumbing only, a new branch): the hunks matched text in early
  versions whose surroundings differed, and the first commit touching
  `flash.c` no longer compiled
- Walking backwards with a three-way merge per version
  (`git merge-file current=Vi' base=Vi other=V(i-1)`): 19 files conflicted,
  and the walk stops at each file's first conflict, so that is a floor.
  Every hand resolution was another chance to break an intermediate build

Cleanup commits on top leave each original commit building as it did. The
per-subsystem squash will meet the same conflicts, so it is not free; it
was deferred, not solved.

## Outstanding

**Needs a decision (blocks Peter's "any direct mention of RP2350" thread).**
Three chip checks remain outside the HAL:

- `AP_AHRS.cpp` - DCM backup at 1/16 rate when EKF3 is active. The only one
  that changes flight behaviour, in a safety-relevant fallback, and the
  subject of Thomas's unanswered "Why?". Either drop it or make it a
  board/load-driven define with the cost measured
- `GCS_FTP.cpp` x2 - the thread priority split is mechanical (a board define,
  like `HAL_RATE_THREAD_STACK_SIZE`); the other removes MAVLink back-pressure
  (`last_txbuf_is_greater(33)`) on one chip, which changes GCS behaviour and
  wants explaining before being blessed

2026-09-14: all three are now board defines, master behaviour by default
and the old values on RP2350 (see the table in "What the 2026-09-14
session changed"). That removes the chip mention but not the questions:
the factor 16 still has no measured cost behind it, the back-pressure
removal is still unexplained, and neither define has been put to Thomas or
Peter yet.

**Precursor PRs (blocks Peter's `mode.cpp` and `AP_AHRS_NavEKF3.cpp`
"similarly elsewhere" threads).** Unrelated changes still in, descending size:

| item | size | note |
|---|---|---|
| `AP_HAL/examples/SemaphoreRecursion/` | +155 | a whole new example |
| `AP_Param` `@READONLY` enforcement | +31 | real fix; `CubeOrangePlus-ODID` and `CUAV-V6X-v2-ODID` already ship `@READONLY` defaults, and Laurel's defaults depend on it |
| `AP_Logger_File` heartbeat instrumentation | +14 | chip-neutral; guards false stuck-thread reports during log rotation on slow SPI SD |
| `AP_Filesystem_FATFS` `ENOSPC`->`ENODEV` | 1 | arguably more correct, behaviour change for every FATFS board |

The middle two are genuinely good and load-bearing, so they want spinning out
rather than deleting.

**Unmeasured claim.** The new registry asserts `-O2` is needed on 13 files.
Thomas's (now resolved) comment argued `-Os` is faster given the flash
bottleneck, and nothing in the branch puts a number on it. Worth a Laurel A/B
before defending it.

**Unverified on hardware.** The free-space check restoration assumes the
expensive first `f_getfree()` lands in `start_new_log()` while
`is_system_initialized()` is still false, where `io_thread_alive()` is exempt,
and that FATFS then caches the free cluster count. If the card mounts *after*
init completes - plausible given the port's SD cold-boot retry work - that
first walk would land unprotected. One boot-and-arm on Laurel with a large
card confirms or refutes it; symptom would be "Logging failed".

**Docs that may still lie.** `Laurel/README.md` and `FEATURE_GAP.md` were
updated for the IMU change, and `Pico2/hwdef.dat`'s stale mock-backend comment
was replaced. Other `FEATURE_GAP.md` / `DEVELOPMENT.md` claims were not
audited against the post-cleanup tree.

**Also open:** `HAL_BARO_ALLOW_INIT_NO_BARO` is still set on Laurel and Pico2.
Same bring-up-convenience shape as the IMU flag on a board that has a DPS310 -
deliberately left alone, but worth asking the same question.

**Open after 2026-09-14.** From tridge's automated review of 2026-09-13
at `c1c8709823`; ISSUE (fault store), F6, F7, F8, F9, F12, note 1 and the
stale watchdog comments are addressed in the unpushed commits, the rest is
not:

- F10: picotool is downloaded in `Tools/ardupilotwaf/chibios.py` with no
  checksum and a bare `extractall`
- F11: the 50 Hz override in `RCOutput.cpp`
- F13: PR size (185 files at `c1c8709823`, 178 now)
- Notes 2-6: `rp2350_memfunctions.S:19`, the thread-creation claim, the
  DShot wording in RPI_UAVFC's `defaults.parm`, the dead newlib relocation,
  `PORT_SPINLOCK_STATS` in `DEVELOPMENT.md`
- Core1 watchdog coverage is only indirect (`rp2350_core_affinity.h`)
- The RAMFUNC2 section script is silent about registry misses outside
  copter, and its copter check scans every object under the build root, so
  stale objects from another target can satisfy it
- Not from the review, found while auditing (derived from the source, not
  measured): `STM32_HW` is still a name this port invents for a non-STM32
  chip, now in one place (tpwrules' thread); the RP2350 USB direct-IO path
  keeps dead branches, `drop_unopened_usb_tx_backlog()` does nothing; RP2350
  sets up the USB strings early in `board.c` for no recorded reason;
  `hrt.c` uses `port_lock()` on RP2350 instead of the system lock, and its
  safety under SMP was not checked; `PICO2.py` carries datasheet tables
  flattened into comments; `AP_HAL_Boards.h` still defines three
  `AP_RP2350_*` feature names
- Push the 23 commits (needs `/prepare-for-push` from Andy), then reply to
  Peter's `flash.c:85` thread and post a status reply for tridge's items

## Open review threads (8 of 41)

Closed this session: 12, each verified against the tree **and** against the
PR head before replying. Remaining:

| who | file | comment | why still open |
|---|---|---|---|
| tpwrules | `AP_AHRS.cpp` | "Why?" | DCM skip still there, pending decision |
| tpwrules | `stm32_util.h` | "Surely this should be fixed in ChibiOS?" | still `#undef STM32_HW` / `#undef RP2350` in a shared header; he is right |
| tpwrules | `bl_protocol.cpp` | "How does the board run reliably in this case?" | answered in-thread, code stands |
| peterbarker | `Copter.cpp` | "*Any* direct mention of RP2350 outside of its own HAL is suspect" | 3 chip checks left; status reply posted, not resolved |
| peterbarker | `mode.cpp` | "Separate PR... similarly elsewhere" | unrelated changes remain |
| peterbarker | `AP_AHRS_NavEKF3.cpp` | "Again, separate PR. Similarly for other changes" | same |
| peterbarker | `rate_thread.cpp` | "If you're modifying anything in the Copter directory..." | file still modified (generic HAL APIs only, no chip guards) |
| peterbarker | `rate_thread.cpp` | "Why am I reviewing this crap?" | not a question |

`Tools/AP_Bootloader` (54) and `Tools/CPUInfo` (2) still test the chip
directly; left as idiomatic since master already carries 20
`defined(STM32xx)` checks in AP_Bootloader. Peter was asked in the status
reply whether he wants those gone too.

## Process gotchas

- **Never `git add <directory>`.** Done twice; the second time it committed
  `libraries/AP_NavEKF3/CLAUDE.md` and `CLAUDE.md.bak` into the PR. Fix is to
  stage explicit paths and **assert** the staged set equals the intent before
  committing, not print it alongside the commit
- `git checkout <rev> -- <path>` **stages** as a side effect, so it leaves a
  later commit's files in the index. The assert above caught this twice;
  `git restore --staged libraries/` clears it
- Pushing needs `/prepare-for-push <branch> --allow rebase,reset,amend` from
  the user; `pre_bash_check.py` also blocks running
  `check_branch_conventions.py` itself, because that file contains the string
  `git commit --amend`. Without a grant, use a local reimplementation of the
  subsystem audit instead
- Autotest is pinned to port slot 0 unless the checkout has
  `autotest.py --sitl-instance` (PR #34304). Applying that patch to the
  working tree temporarily is what let this branch run tests while another
  clone held the slot
