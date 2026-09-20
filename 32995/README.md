# PR #32995 - RP2350 Port

Analysis archive for [ArduPilot/ardupilot#32995](https://github.com/ArduPilot/ardupilot/pull/32995).
Buzz's PR, branch `rp2350-v5-squashed-and-cleaned-and-rebased` on the
**davidbuzz** remote, which andyp1per pushes to. Base `master`, merge-base
`b832113b10` (rebased 2026-09-15 onto `bf08027404`, local tip `d0106975ee`,
not pushed - eighth round). PR head `638efaa5d0`, pushed by Andy 2026-09-15 13:18 UTC
(`fea5156687` on 2026-09-14 plus six commits: threads.txt, the stack sizes,
and the ChibiOS bump to `af493a7bd5`, which fixes the boot hang
`480f26b109` exposed - fifth round). ArduPilot/ChibiOS#113 head is
`af493a7bd5`, also pushed. The
2026-09-11 session left head `27f3531d62` (198 commits); the work of
2026-09-12 and 2026-09-13 (`3326ce8af7`..`c1c8709823`: watchdog reset
detection, SD storage health, registry misses failing the build, bootloader
hex/UF2 address) was pushed without an entry here. Local safety refs
`backup/rp2350-pre-cleanup-20260911` (the original 179 at `164ac005d5`) and
`backup/rp2350-pre-gitmodules-drop`.

Local tip is `4f982aea88` as of 2026-09-17, nine commits past the eighth-round
`d0106975ee`: the sampler entry-point declaration, the bootloader hex and UF2
address fixes (`b8ebd9fc66`..`bc30cce141`), the round-two field
instrumentation (`3729215583`..`35e92d8b2e`) and the round-three OSD work
(`5a937f35cf`..`4f982aea88`). None of it is pushed, and the pushed head
`638efaa5d0` is not an ancestor of it - the eighth-round rebase rewrote those
commits, so the next push is a force push.

2026-09-18: local tip `43b818a69c`, adding the relay-read fix `5fc3f9a1ff`
and a ChibiOS bump to `4723972c44`, which is on the local submodule branch
`rp2350-clean-v7-padmode` and not yet on `origin/rp2350-clean-v7` - it has
to be pushed there before this branch is, or CI cannot fetch the pin. Why,
in [field-test-2026-09-17-video.md](field-test-2026-09-17-video.md): the
video losses are camera reboots, and a relay read could float a regulator
enable.

Later on 2026-09-18 the branch was rebased onto master `9165d22419` (281
commits, local tip `49b1131ca0`): the relay fix is now `e3f489bc73` and the
bump `49b1131ca0`, pin still `4723972c44`, now fast-forwarded onto the local
`rp2350-clean-v7` (unpushed). The relay fix exists on two branches: it is
also `1b28d11595` on `pr-relay-read-no-pinmode`, cut from the same master
for its own PR, and this branch drops its copy once that merges.
**Superseded the same day:** that PR went through three `/pr-review` rounds
and was opened as [#34430](../34430/) at `31df8dcb47` with a different
design; the RP2350 branch now carries the identical patch as `6d2ba24fc3`
(bump replayed as `570a564a8e`, pin unchanged, 280 other commits unchanged
by `git range-diff`; backup `pre-relay-swap/rp2350-20260918-1321` at
`49b1131ca0`). Both pushed by Andy 2026-09-18: #32995 head `570a564a8e`,
ChibiOS#113 head `4723972c44`. The pad-mode fix also went to ChibiOS trunk
as [ChibiOS/ChibiOS#83](https://github.com/ChibiOS/ChibiOS/pull/83)
(`635c7d1b86` on trunk `fd2e59c34`, whose copy of the file was identical to
ours before the fix). The
ChibiOS fix stays a separate commit on #113 rather than folded into
`9f37253c1b`: that commit imports ChibiOS trunk's RP2350 support, and trunk
has the same OE release, while ArduPilot/ChibiOS master's RP2040 setter
never releases an output - so there is nothing to fix on master alone.

2026-09-19: local tip `5e55b17873`, seven commits past the pushed
`570a564a8e`, not pushed: the OSD standard re-detection (`b95f6d6ef7`,
`202f47e8bb`), the notch coefficient leaf in SRAM (`0d16573e5c`), the rate
thread honouring the notch loop-rate option and its docs (`caebec43a7`,
`982b41d3fe`, upstream as [#34436](../34436/)), float angle shaping
(`cc87a7b9c7`, upstream as [#34437](../34437/)) and the RC input chain in
SRAM (`5e55b17873`). Measured in [bench-2026-09-19.md](bench-2026-09-19.md).
Then the `threads.txt` fixes: `c86b75980c` (the SMP stats reset),
`d403dceaa5` and `b0a6e0ef94` (the worst-slice mark and run test, upstream as
[#34438](../34438/)); local tip `b0a6e0ef94`, still not pushed.

Later on 2026-09-19 Andy rebased the branch onto master `368dc0c428`, and
DCM was then built out of RP2350 to settle F8 (see "Open after
2026-09-14"): local tip `0ccbd15f2c`, 289 commits, not pushed, so the next
push is a force push. `920c2883a4` sets `AP_AHRS_DCM_ENABLED` 0 in
`PICO2.py` and drops the three DCM registry entries; `0ccbd15f2c` closes
the DCM notes in `RPI_UAVFC/DEVELOPMENT.md`. The four AP_AHRS decimation
commits are dropped (`f03b69ab06`, `e5ef0b425e`, `680244b7f3`,
`3470687bcb` before the rebase), so `git diff 368dc0c428 HEAD --
libraries/AP_AHRS` is empty: the PR no longer touches AP_AHRS. `git
range-diff` finds the other 287 commits unchanged. Backup
`pre-drop-dcm/rp2350-2056` at `4805b3343c` is the rebased branch with the
DCM commit, before the drop. Hashes cited above, renumbered:

| was | now | after the squash | commit |
|---|---|---|---|
| `6d2ba24fc3` | `33228ce5a8` | `b302c1d5b6` | relay read fix, also [#34430](../34430/) |
| `570a564a8e` | `1b00d4db8d` | `55d6a1bb97` | ChibiOS bump, pin `4723972c44` unchanged |
| `d94c26ee20` | `44f49e51c7` | `65edd9aeba` | notch coefficient-update chain in SRAM |
| `b95f6d6ef7` | `207f42afc1` | `3c6fe683ca` | OSD video standard re-detection |
| `202f47e8bb` | `e8147b7865` | `d972b92517` | OSD standard re-check while disarmed |
| `0d16573e5c` | `d7645ce123` | `b674e33251` | notch coefficient leaf in SRAM |
| `caebec43a7` | `d9652ca650` | `e77a6a1723` | notch loop-rate option, also [#34436](../34436/) |
| `982b41d3fe` | `706f76e33f` | `c3a72b85be` | its option docs |
| `cc87a7b9c7` | `b4651e30e4` | `aac2547869` | float angle shaping, also [#34437](../34437/) |
| `5e55b17873` | `49b4501ac1` | `aa7ca064ee` | RC input chain in SRAM |
| `c86b75980c` | `cd62494f12` | `c25b2a761f` | SMP thread stats reset |
| `d403dceaa5` | `4a4be74999` | `666f11f890` | worst-slice mark, also [#34438](../34438/) |
| `b0a6e0ef94` | `bdefe5d54d` | `841e7c8109` | run test, also [#34438](../34438/) |
| | `920c2883a4` | `fade5bccc1` | build RP2350 without DCM |
| | `0ccbd15f2c` | `d3a6c77e31` | DCM notes in `RPI_UAVFC/DEVELOPMENT.md` |

Numbers keep the hash of the build they were taken on. Andy pushed
`0ccbd15f2c` the same evening, replacing PR head `570a564a8e`.

Then squashed from 289 commits to 248, local tip `d3a6c77e31`, not pushed
(backup `pre-squash/rp2350-2140` at `0ccbd15f2c`); the tree is identical
to `0ccbd15f2c`. Dropped: eight add-then-revert pairs whose later commit
exactly reverses the earlier one (AP_AHRS pre-arm wording, AP_Baro DPS280,
the AP_NavEKF3 and AC_AttitudeControl `-O2` pragmas, AP_Common NOINLINE,
the AP_Vehicle XIP print, AP_Param uint16_t counters, AP_ESC_Telem bidir
DShot). No commit touches AP_AHRS, AP_Baro, AP_NavEKF3,
AC_AttitudeControl, AP_Vehicle or AP_ESC_Telem any more; AP_Common keeps
the `reserve()` pair and AP_Param the `@READONLY` change. Folded: 25
fixups into the commits whose own lines they change, two of which were
retitled because what was left changed ("GCS_MAVLink: wake the FTP worker
on a semaphore and report FTP failures", "AP_Logger: refresh the IO
heartbeat through start_new_log()"). Candidates came from blaming the
lines each commit changes; each was replayed through the whole branch with
exact-context patches, and rejected where it did not apply or where a
commit in between uses what it moves: `ExpandingString::reserve()` has
callers until the @SYS rework, the PC sampler `#if` by value would move
ahead of its default under `-Werror=undef`, and the blank-block report
reads a counter a later commit adds.

Compile checks at the rewritten commits: SITL copter at `7e9d452505`
(FTP) and Pico2 copter at `de4189c281`, `840efe0a9f` and `79e7ed494f`
(the last before `HAL_WITH_ESC_TELEM` is set, so the dropped ESC pair)
build with no warnings. Three positions cannot be checked by building,
because intermediate commits there were already broken before the squash:

- Every ChibiOS build, STM32 included, fails from `b8853475de` (#1) until
  `6440d223cb` (#115): #1 sets `_CHIBIOS_RT_CONF_VER_8_0_` in the shared
  `chconf.h` and the pinned ChibiOS wants 7.0. The bootloader fold into
  #9 was checked instead by finding every identifier it uses in that tree;
  the RPI_UAVFC fold into #83 configures.
- SITL copter fails from `b75fc95b04` (#42) until `390ace7cde` (#98) on
  an unused `last_c1_report_ms` in `rate_thread.cpp`. At the AP_Logger
  fold (#59) AP_Logger and AP_Param compile clean before that error.
  **Corrected 2026-09-19:** this was first written as ending at
  `ac5f627f31` (#144), the commit that deletes the variable. That was read
  off a `git log -S` of the name and never checked: #98 already guards the
  declaration with `AP_RP2350_DEBUG_REPORT_ENABLED`, and SITL builds from
  there.

Both windows are the same in the pushed `0ccbd15f2c`. Both, and the others
the every-commit builds then found, are fixed; see "Making every commit
build" below.

## Making every commit build

Andy's call on 2026-09-19, after the squash: fix the windows so the series
bisects. Applied 2026-09-20: local tip `37b8135640`, 247 commits, tree
byte-identical to the pushed `0ccbd15f2c`, not pushed, so the next push is
a force push. Backup `pre-buildfix/rp2350-0020` at `d3a6c77e31`, the
squashed branch before the fix. The hashes in the table above are now, in
order: `3f57678b16`, `c92f5623c7`, `61a347c028`, `698fa8ea2c`,
`021faafe76`, `d10b8c9af3`, `edeb986662`, `480cdfaa10`, `dbf7498fdf`,
`60e2ff415d`, `2cc60a071e`, `edd326d9c2`, `de7f738ccd`, `f43c0d691e` and
`37b8135640`.

Building every commit found three more causes on top of the two above. All
five were in shared code, and all had been fixed later in the series, so
each fix moves to the commit that introduced the defect rather than being
written fresh:

| what broke | window | where the fix comes from |
|---|---|---|
| `chconf.h` says `_CHIBIOS_RT_CONF_VER_8_0_`, the pinned ChibiOS wants 7.0 | every ChibiOS build, #1-#114 | #115, with `mem_available()`'s `chCoreGetStatusX()` and the `stm32_util.h` typedefs |
| `chibios_board.mk` compiles a `fatfs_diskio_ap.c` that exists in no tree | every ChibiOS build, #1-#17 | #18, with the `cpu_id_ptr` fix in `usbcfg_common.c` |
| two statements before a `/* Falls into */` comment in `usbcfg_dualcdc.c`, which that makefile compiled everywhere | every ChibiOS build, #2-#109 | #110 |
| `hal_icu_cfg` appended outside the ICU block: a stray backslash in every STM32 `hwdef.h` | every STM32 build once the above clear | #110's generator hunk |
| the crashdump SPI path's `STM32_SPI_USE_SPIn` tests are STM32-only | Pico2, #115-#126 | #127 |
| `sdcard.cpp`'s local `tries` shadows the parameter (`-Werror=shadow`) | RPI_UAVFC, #115-#126 | #127, as a tree transform over #1-#126 because #57 also edits those lines |
| the pinned ChibiOS calls `spiExchangeHook`, defined only later | RPI_UAVFC, #115 | #116 |
| `bin2uf2.py` not executable when waf starts calling it | Pico2 and RPI_UAVFC, #224 | created executable at #223, so #225 empties and drops: 248 commits to 247 |
| the ChibiOS `override` precedes the AP_HAL declaration it overrides | every ChibiOS build, #18-#22 | the AP_HAL commit moves ahead of it |
| unused `last_c1_report_ms` on non-RP2350 | SITL, #42-#97 | a guard at #42 that #98 then narrows |

Verification, 634 builds and no failures: sitl copter 69, CubeOrange copter
182, MatekF405 bootloader 137, Pico2 copter 122, RPI_UAVFC copter 124. Each
commit was built for every target its changed files can feed, and each
target's first and last commit always. The sweeps ran on the intermediate
chains; the last round changed only `sdcard.cpp` and `spi_hook.h`, so
#114-#119 was rebuilt on all four boards and CubeOrange spot-checked at
#1-#3 and #57-#60.

Method, in the session scratch: candidates from blaming the lines each
commit changes, then a replay of the whole series with exact-context
patches, which fails loudly rather than merging, and a final check that the
tree equals `0ccbd15f2c`. No branch was touched until the result was built.

Limits. Laurel is not verified, being the third RP2350 board. RP2350 boards
cannot build before #115 whatever is moved: the kernel pin lands at #15,
the RT 7 conversion of the SMP code at #115, the waf support in between.
Authors are preserved; only #1 grows, absorbing about 250 lines that later
commits used to make.

## Companion notes

- [field-test-osd-rcin.md](field-test-osd-rcin.md) - the profiling build for
  the tester chasing OSD and RC input problems on analog video: what the data
  has to separate, the overlay that builds it, and what to pull off the board
  before power-off.
- [field-test-2026-09-16-results.md](field-test-2026-09-16-results.md) - the
  first two flights with that build: core1 ~98% busy in flight, the XIP
  profiler itself ~13% of it, raw gyro logging dropping 76% of the log, and
  the counters the next build needs.
- [field-test-round2.md](field-test-round2.md) - the second field build
  (`35e92d8b2e`): OSD late-block and PIO UART error counters in the 10 s
  report, no XIP profiler, and what to fly.
- [bench-2026-09-16.md](bench-2026-09-16.md) - props-off bench runs on Andy's
  quad: arming takes core1 from 55% to 96% and blanks 95% of OSD blocks;
  best guess is per-motor notch updates at 1604 Hz plus logging from core1.
- [field-test-2026-09-17-video.md](field-test-2026-09-17-video.md) - the
  round-three build flying, measured out of the tester's two OSD videos
  because no log came back: about one late block per field left, the losses
  proved block-aligned, and the DCM decimation (F8) showing up as a pre-arm
  failure that grows to 33 deg while the aircraft sits still.
- [bench-2026-09-19.md](bench-2026-09-19.md) - props-off bench with SWD
  profiling of both cores: the OSD standard fix confirmed, armed core1 from
  82% to 56.5% (notch leaf in SRAM, then the loop-rate option), core0 in
  ALT_HOLD and LOITER with a fake GPS, and the RC input chain into SRAM
  (core0 88.5% to 85.4%); later the same day, what building DCM out costs
  and saves.

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
modified files 93 -> 86, lines deleted from master 694 -> 371). Pushed at `fea5156687`.
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

**SBUS is supported, and the feature table said otherwise until
2026-09-20.** The PIO UART has a dedicated 8E2 receive program, inverts the
pad through `INOVER`, assembles whole 25-byte frames and debounces the
failsafe flag; the PL011 path sets parity, stop bits and `INOVER` too. What
was missing is upstream: `AP_RCProtocol_SBUS::_process_byte` will not start
a frame unless the header arrives `HAL_SBUS_FRAME_GAP` (2 ms) after the
previous byte, and on a batched port those timestamps are service times, so
a service carrying two frames loses framing and master discards the buffer
rather than resyncing. ArduPilot/ardupilot#33057 fixes that and Andy measured
continuous frame drops without it, so treat it as required rather than
nice-to-have. Not yet run against a receiver on an RP2350 board; CRSF is
what has flown. The dedicated GPIO41 pad stays unbound for two independent
reasons, both worth not re-deriving: its only hardware-UART function is
`UART1_RX`, which the GPS owns on GPIO36/37, and the PIO UART instance
table hard-maps instances 0-1 to PIO0 (all four state machines) and 2-3 to
PIO1, which `pio1_claim(PIO1Owner::OSD)` takes on RPI_UAVFC - so a third
PIO UART costs the analog OSD. SBUS therefore goes to the RADIO pad,
SERIAL3, with `SERIAL3_OPTIONS` 1.

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

2026-09-19: `AP_AHRS_DCM_BACKUP_DECIMATION` no longer exists. RP2350
builds DCM out instead (`AP_AHRS_DCM_ENABLED` 0, `920c2883a4`), and
`AP_AHRS.cpp` is master's text.

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
  headers (see the third round below for what it still guards)
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

### Second round, 2026-09-14

Seven more commits (`ae1143446e`..`ebbc93f962`), for tridge's F10, F11 and
notes 2-6:

- F11 (`d948479ad1`): RP2350 forced every PWM group at or below 400 Hz to
  50 Hz with a 3 MHz counter, a workaround for the 375 MHz clock overflowing
  the divider's 8-bit integer part at 1 MHz. All three boards now run below
  256 MHz (a static assert checks it), so RP2350 takes master's 1 MHz path
  and SERVO_RATE/RC_SPEED are honoured. 3 MHz could not stay: `pwmcnt_t` is
  16 bits on RP, and SERVO_RATE 25 Hz needs a period of 120000 at 3 MHz.
  **Not run on hardware**
- F10 (`ebbc93f962`): the picotool tarball's SHA256 is pinned (it matches
  GitHub's published asset digest) and only plain files and directories
  under `picotool/` are extracted. That also stops the archive's top-level
  `.keep` landing in the source root, which is where the untracked `.keep`
  in the working tree came from
- Notes 2-6: comment and document corrections, plus removal of the newlib
  memcpy/memset picks from `common_rp2350_smp.ld`, which matched nothing
  since `rp2350_memfunctions.S` supplies both

Verification, measured:

- Notes 2, 3, 5 and 6 together: RPI_UAVFC, Pico2 and Laurel copter and
  bootloader binaries byte-identical before and after (same HEAD, working
  tree builds)
- F11: CubeOrange and MatekF405 differ only in `RCOutput.cpp.0.o`, and
  only in five `__LINE__` constants shifted by 7. The RPI_UAVFC
  `set_freq_group()` literal pool holds 1000000 where it held 3000000, and
  the `#50` load is gone. Zero warnings on all five boards
- F10: a scratch harness runs `ensure_picotool()` extracted from the source:
  good archive, already present, hash mismatch, path traversal and a
  symlink entry all behave. Each check was removed in turn and a test
  failed, including with the Python 3.12 `data` filter disabled, since
  that filter alone also stops the traversal and symlink cases
- The note 2 commit cannot fix `add88d684f`'s commit message, which makes
  the same "runs once" claim; that has to wait for the squash

### Third round, 2026-09-14: Thomas's ChibiOS question and STM32_HW

**Correction.** The open-threads table had tpwrules' `stm32_util.h` thread
("Surely this should be fixed in ChibiOS?") as an objection to the
`#undef STM32_HW` / `#undef RP2350` block, and called him right on that.
That was a misreading. His selection at `d2728d3ae2` is lines 21-28, the
`PAL_LINE` override; the `STM32_HW` block starts at line 29.

What he was pointing at, derived from the source: ArduPilot/ChibiOS master
(`9aebaf4a40`) defines the RP `PAL_LINE(port, pad)` as `((pad), (port))`.
The comma operator discards the pad and yields the port, and `IOPORT1` is 0,
so every `PAL_LINE(IOPORT1, n)` was line 0; the discarded pad is what raised
`-Wunused-value`. The port's override `((void)(port), (ioline_t)(pad))`
fixed the value as well as the warning, although its comment claimed the
opposite. Upstream ChibiOS fixed the macro on 2026-03-24 (`aaea5285ad`,
Eric Molitor, `(port << 5) | pad` for the RP2350B high bank), ChibiOS#113's
first commit `9f37253c1b` carries it, and the submodule already had it when
he reviewed. The override came in with `5fb4a96ab1` and went in
`7fd63d181b` (2026-05-15). So he was right, it is fixed in ChibiOS, and
only a reply is owed.

`STM32_HW`: ChibiOS has no generic STM32 define. A `-dM` macro dump of
CubeOrange, MatekF405, f103-GPS and RPI_UAVFC shows only per-port include
guards (`STM32_REGISTRY_H`, `STM32_RCC_H`, `STM32_TIM_H`) and per-family
clock limits common to the STM32 builds and absent on RP2350, none of them
an interface. The family defines (`STM32H7`, `STM32F4`, `RP2350`) come from
our generator. Andy kept `STM32_HW` for its meaning and had the dead and
redundant uses removed:

- `7891b761e4`: the guard inside `send_pulses_DMAR()` (already
  `!defined(RP2350)`), `SoftSigReader.cpp` (only built with `HAL_USE_ICU`,
  off on RP2350; the file is master's again, `#undef` and `#error`
  included), and the two `Scheduler.cpp` watchdog calls that `watchdog.h`
  already maps
- `fea5156687`: the DMA stats layout tests RP2350 first, so master's two
  STM32 cases are unchanged and its catch-all `#warning` is gone

16 uses remain, each over STM32-only registers or types (`stm32_tim_t`,
`rccEnableSPIn()`, GPIO and clock init, IWDG). Measured: CubeOrange,
MatekF405, revo-mini (which builds the ICU path), RPI_UAVFC, Pico2 and
Laurel objects are identical apart from three `__LINE__` constants in
`RCOutput.cpp`, shifted by 2. The `7891b761e4` message says object code is
unchanged, which overlooks those constants; fix it at the squash.

Found in passing, not changed: the RP2350 DMA stats layout says 12
channels, but `rp_registry.h` gives RP2350 16 (`RP_DMA_NUM_CHANNELS`), so
channels 12-15 would be shown as a second controller.

### Fourth round, 2026-09-14: threads.txt, stack sizes, tridge's review of fea5156687

Local commits on top of the pushed `fea5156687`, **not pushed**:
`78cdd18667` (threads.txt per-core load and stack sizes on SMP),
`a31dc4a69e` (default MSP on the RP2350 boards), `7af065f5b6` (default
timer/rcin/rcout stacks), `480f26b109` (c1_main sleeps, core1 PSP 1 KB),
`03a9d450a4` (overflow check covers core1's MSP).

Andy's `--enable-stats` run on RPI_UAVFC hardware showed loads summing to
~50% per core and `c1_main` with a negative stack size. Derived from the
source: every load was divided by the total over both cores, and the core1
main thread's context lives in its OS instance, below its stack.

**The RP2350 stack increases were a misreading.** `threads.txt` prints
`STACK=free/total`; commit `036e5e8972` and the Laurel/Pico2 hwdef comments
read the first number as used. Every step from 4 KB to 38 KB recorded a
gap of 130-370 bytes ("208 B free" on the MSP), which is the real usage.
Measured on Andy's stats build (bench run, not flight): MSP 208 bytes of
38912, rcin 344 of 22752, rcout 224 of 14560, timer 336 of 3296, c1_main
112 of 16384. Back at master defaults the heap base drops by 126992 bytes
on RPI_UAVFC and Laurel and 65536 on Pico2 (ELF symbols); CubeOrange
objects unchanged. rcout at 512 is the tightest and wants checking with
bidirectional DShot active.

**Pico2's core1 never joins ChibiOS** (derived from the source and ELF, not
run): its `c1_main.c` is the legacy FIFO dispatcher and never calls
`chInstanceObjectInit()`, while the hwdef enables SMP and pins rcout, the
rate thread and the SPI0 bus thread to `ch1`. Not changed.

tridge's automated review at `fea5156687` (issuecomment-5671665240, posted
2026-09-14 22:27 UTC) moved to **REQUEST CHANGES**:

- F8 is a correctness bug, not a trade-off. Confirmed from the source:
  `AP_AHRS_DCM::matrix_update()` rotates by the INS's latest delta angle,
  which `_publish_gyro()` replaces on every update, so at decimation 16 the
  backup DCM integrates ~1/16 of the rotation (his Codex harness: 0.320 rad
  in, 0.020 rad integrated). This overturns the "performance only" reading
  under which Andy kept it; decision pending
- Core1 faults still bypass `save_fault_watchdog()` (own SRAM handler)
- A second copy of the F7 `#warning` in `RCOutput_bdshot.cpp:374`
- STM32 bootloaders lost the `SCB_VTOR` write before jumping, and gained
  `bl_usb_tx_poll_drain()` after every `cout()`; both want RP2350 guards
- OneShot/OneShot125 accepted on RP2350 but cannot work (period 0 to TOP)
- PR no longer merges cleanly: `Tools/CPUInfo/CPUInfo.cpp`
- CI: no workflow has run at `fea5156687`; waiting for approval

### Fifth round, 2026-09-15: the stack changes on hardware

Andy flashed RPI_UAVFC (tier 1, bench, not flown):

| build | result |
|---|---|
| `78cdd18667` threads.txt fix | boots; per-core loads and stack sizes now make sense |
| `03a9d450a4` all five commits | **does not boot** |
| `7af065f5b6` MSP + thread stacks at master defaults | boots |
| `480f26b109` + c1_main sleeps + core1 PSP 1 KB | does not boot ("appears to start booting") |
| `psp-only`: `7af065f5b6` + core1 PSP 1 KB, heartbeat kept | does not boot |
| `samelayout-1k-psp`: 1 KB usable core1 PSP, RAM layout identical to `7af065f5b6` | USB and heartbeats, but core1 stuck (see below) |
| `waitfix-full`: `03a9d450a4` + volatile state wait in `c1_main` | **boots**; both cores doing normal work |
| `sleep-only`: `7af065f5b6` + c1_main sleeps, 16 KB PSP | not flashed |

So the MSP and rcin/rcout/timer reductions work on hardware and the core1
process stack cut is the breakage; the sleep itself is untested. What is
known about why, derived from the source and ELF, not measured:

- `_crt0_c1_entry` (disassembled) sets `PSP` and `PSPLIM` to the core1
  process stack, switches `CONTROL` to PSP, runs `__c1_cpu_init()` and
  `__c1_early_init()` (both trivial), fills the stacks with the canary and
  calls `c1_main`. So the 112 bytes the canary showed should be real
- ChibiOS saves and reloads `PSPLIM` per thread (`PORT_SAVE_PSPLIM`), and
  CRT0 sets `MSPLIM`/`PSPLIM` on both cores, so an overflow faults at once.
  A frame that moves SP far down but writes little would fault while the
  canary still looks intact
- A disassembly walk of `c1_main`'s calls (veneers followed) found under
  100 bytes of frames
- Between `7af065f5b6` and `psp-only` the only RAM difference is `.bss`,
  `.ram0` and the heap starting 15 KB lower (`objdump -h`); no fixed
  address found in that window yet
- Ruled out by reading: `chThdSleep(TIME_INFINITE)` has no halting check;
  the notify-before-insert order in `chSchReadyI()` is covered because
  PendSV's `__port_schedule_next()` takes the kernel spinlock

`samelayout-1k-psp` separates the two: if it boots, the 15 KB shift is the
problem; if not, something really uses more than 1 KB of core1's PSP, and
core1's fault record (`WD_SCRATCH2` = 0xC1FA0001, CFSR in `WD_SCRATCH3`,
PSP at fault in `c1_fault_info[5]`) read over SWD should name it.

**Root cause, found on the debug board over SWD (tier 1, bench) on
2026-09-15:** `chSysWaitSystemState()` in ChibiOS `chsys.c` is
`while (ch_system.state != state) {}` with `state` not volatile, and the
compiler loads it once and then compares the cached register forever
(`ldrb r3,[r3]` before the loop, `cmp r3,r0; bne` inside). On
`samelayout-1k-psp`, read without halting: `WD_SCRATCH1` = `0xBB000003`
(core1 entered `c1_main`, never past the wait), core1's PC in that loop
on every sample, `ch_system.state` in memory already `2`
(`ch_sys_running`), core0 sitting in idle with the main thread blocked.
USB and heartbeats still came up, which is the "appears to start booting".

The stack size only moved the timing (inference, not measured): core1's
CRT0 fills its whole PSP with the canary before calling `c1_main`, and 16 KB
took long enough that core0 had finished `chSysInit()` first. That is why
the same-layout build, which fills only 1 KB, hung too, and why the RAM
shift was a red herring. The race is live at 16 KB as well; anything that
slows core0's init can hang boot on current code.

Verified: `waitfix-full` (the whole failing series with `c1_main` polling
`*(volatile system_state_t *)&ch_system.state` instead) boots, heartbeats on
USB, `WD_SCRATCH1` = `0xBB000035`, core0 sampled in EKF3/AHRS, core1 in the
IMU FIFO read, notch and servo output. Canary headroom on that build after
about a minute on the bench, disarmed: core0 MSP 200/1536 used, core1 MSP
120/1536, core1 PSP 104/1024, main thread 1880/7168, rcin 312/1216, rcout
192/704, timer 296/1728 (sizes include the port context overhead). Not
flown, and rcout not checked with bidirectional DShot.

Andy chose to fix it in ChibiOS as part of #113. `af493a7bd5` "RT: re-read
the system state while waiting for it" on `rp2350-clean-v7` reads the state
through a volatile pointer; the ArduPilot branch bumps to it in `638efaa5d0`.
Built at `638efaa5d0` with no `c1_main.c` change: RPI_UAVFC and CubeOrange
0 warnings, `chSysWaitSystemState` now branches back to the `ldrb` each
pass. Flashed to the debug board (bench, 2026-09-15): heartbeats on USB,
`WD_SCRATCH1` = `0xBB000035`, core1 sampled in `Copter::rate_controller_thread`,
the notch, `RCOutput::dshot_send` and `RCOutput_pico::restart_sm`. Not
flown. Both pushed 2026-09-15. The same one-hunk fix is also offered on
its own against ArduPilot/ChibiOS master as
[ArduPilot/ChibiOS#114](https://github.com/ArduPilot/ChibiOS/pull/114)
(`04602a8a8c`, branch `pr-wait-system-state`), since master carries the
identical `chSysWaitSystemState()`.

Build and flash notes:

- The variant `.apj` files and `uploader.py` are in
  `C:\Users\uav\rp2350_bisect` (the scratchpad copies under `/tmp` do
  not survive a reboot). Flash from Windows python (pyserial 3.5):
  `py uploader.py --port COM9,COM10,COM11,COM12 <file>.apj`, with Mission
  Planner closed
- **waf does not track `hwdef/<board>/c1_main.c`.** Changing it without a
  change to anything waf does track leaves a stale `c1_main.o` in
  `libch.a`; the first `psp-only` build silently kept the sleep version.
  Remove `build/<board>/modules/ChibiOS` to force it. Worth a fix
- A scratch worktree under `/tmp` was used for the bisect; after a reboot
  run `git worktree prune`
- A stuck app ignores the uploader's MAVLink reboot; start the uploader
  first and power-cycle the board so it catches the bootloader
- OpenOCD from WSL: `cd /opt/openocd-0.12.0+dev-x64-win && ./openocd.exe -s
  "$(wslpath -w /opt/openocd-0.12.0+dev-x64-win/scripts)" -f
  interface/cmsis-dap.cfg -f target/rp2350.cfg -c "gdb port 50000" -c "tcl
  port 50001" -c "telnet port 50002" -c "adapter speed 5000"`; tcl
  `read_memory` and `rp2350.cmN read_memory 0xE000101C 32 1` (PC samples) do
  not halt. The scripts path has to be the Windows form or it cannot find its
  own configs, and without the speed line sampling runs at a few hundred Hz.
  Shut it down before any flash or reboot
- When the probe answers DPIDR but no AP enumerates and every memory read
  fails, suspect the WSL host side before the board: BOOTSEL cleared the
  firmware as a cause on 2026-09-19 and a host reboot fixed it

Still to decide before any push: F8 (tridge shows
the 1/16 decimation loses rotation), and tridge's other findings from the
fourth round. `Tools/bootloaders/RPI_UAVFC_bl.bin`/`.hex` are modified and
`RPI_UAVFC_bl.uf2` is new in Andy's checkout from his 2026-09-14 22:39
bootloader build; not staged.

### Seventh round, 2026-09-15: tridge's clear-cut findings

Local commits on top of the pushed `638efaa5d0`, **not pushed**:

- `7be8dbed47` F7 remainder: the `#warning` and `defined()` test in
  `RCOutput_bdshot.cpp` sat inside `!defined(RP2350)` already; master's line
  is back and MatekL431-bdshot AP_Periph builds with no FIFO warning
- `72e1aef733` the STM32 bootloader writes `SCB_VTOR` before jumping again;
  RP2350 unchanged
- `7e80b5ead1` `bl_usb_tx_poll_drain()` is RP2350-only; STM32 `cout()` is
  master's
- `3dd6650b42` OneShot/OneShot125 refused on RP2350, falling back to normal
  PWM with a setup error, as a DShot group without DMA does
- `45e954e317` waf tracks the board `chibios_board.mk` and, for RP2350, the
  `c1_main.c` in `RP2350_BOARD_DIR` as ChibiOS make inputs. Tested: no
  rebuild on an unchanged tree, `libch.a` rebuilt after editing `c1_main.c`

Measured from the objects: MatekF405 and CubeOrange bootloaders have the
VTOR write in `jump_to_app` (`str` to `0xE000E000 + 0xD08`) and no
`usbStartTransmitI` in `support.o`; RPI_UAVFC keeps the drain and has no
VTOR write. CubeOrange, MatekF405, Laurel and Pico2 copter, MatekL431-bdshot
AP_Periph and the three bootloaders build with 0 warnings. Not run on
hardware. Note the ChibiOS make step also does not track
`modules/ChibiOS/os/rt`, so a kernel change (like `af493a7bd5`) needs
`build/<board>/modules/ChibiOS` removed; that is master's behaviour and was
left alone.

Left for Andy, each a judgement call rather than a mechanical fix:

- F8, the 1/16 DCM decimation that loses rotation
- core1 faults bypass `save_fault_watchdog()` (core1's own SRAM handler);
  routing them there means running flash code from a core1 fault
- printing registry misses outside copter: rover alone has 47, so a line
  per miss would flood every non-copter and bootloader build; a one-line
  count is the quieter option
- the copter registry check scanning stale objects under the build root
- Pico2's core1 never joining ChibiOS while its hwdef pins threads there
- the `Tools/CPUInfo/CPUInfo.cpp` merge conflict with master, which needs a
  rebase
- core1 watchdog coverage being indirect; F13 PR size

### Eighth round, 2026-09-15: rebased onto master

The branch is rebased onto `upstream/master` `bf08027404` (55 commits past
the old merge-base `b832113b10`), tip `d0106975ee`, **not pushed**; the push
will be a force push. Safety ref `backup/rp2350-pre-rebase-20260915` at the
old tip `d421415240`.

The only conflict was `Tools/CPUInfo/CPUInfo.cpp`: master `4cbc74d8fa`
added `div1000_check()` and `test_div1000_structured()`, and PR commit
`98c5daa842` had replaced the TRNG loop with an xorshift PRNG and watchdog
pats. Resolved at that commit (now `d5500148de`) by running master's
structured test first in the `div1000_pass1` section and having the PRNG
loop call `div1000_check()`.

Verified: `git range-diff` shows 265 of 266 commits identical and only
`d5500148de` changed; the whole PR diff against its base is identical
outside `CPUInfo.cpp` after normalising hunk offsets; ChibiOS pointer
unchanged at `af493a7bd5` (master still pins `9aebaf4a40`). Built at the
tip with 0 warnings: RPI_UAVFC, Laurel, Pico2, CubeOrange and MatekF405
copter; CPUInfo for RPI_UAVFC, CubeOrange and SITL; the RPI_UAVFC
bootloader. The mechanical checks show only what they showed before the
rebase (printf false positives, four long subjects, diff size). The
rewritten commit was not built on its own: a build of it in the scratch
worktree failed on the symlinked ChibiOS submodule (missing
`fatfs-0.14b_patched.7z` extraction), which is the worktree setup, not the
code. Its `CPUInfo.cpp` differs from the tip only by the later `__ARM_FP`
guard `392686bc0f`, a no-op on ARM, so it compiles wherever the tip does
(inference from the diff).

Not tested: master's structured div1000 test runs about 220000 divisions
with no watchdog pat, which on RP2350 CPUInfo may come close to the
watchdog.

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

2026-09-19: the `AP_AHRS.cpp` one is gone. DCM is built out of RP2350
(`920c2883a4`) and the branch leaves `libraries/AP_AHRS` at master, so
two checks remain, both in `GCS_FTP.cpp`.

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
at `c1c8709823`; ISSUE (fault store), F6, F7, F9, F10, F11, F12, notes 1-6
and the stale watchdog comments are addressed in the commits pushed at `fea5156687`, the
rest is not:

- F8: deliberately not addressed. Andy's call on 2026-09-14: RPI_UAVFC keeps
  the 1/16 DCM backup rate until the performance is dug into. Superseded in
  part the same night: tridge's review of `fea5156687` shows the skipped
  updates lose rotation, confirmed from the source (see the fourth round). The define
  from `971182202a` leaves it at 16 on all three RP2350 boards; the RPI_UAVFC
  binary at `00d07c8f34` still skips DCM while the count is 15 or below.
  **2026-09-17: it is in the arming path in the field.** The tester's OSD
  video has the aircraft sitting still, reporting "PreArm: DCM Roll/Pitch
  inconsistent" at 3 deg and then 33 deg
  ([field-test-2026-09-17-video.md](field-test-2026-09-17-video.md)). The
  board has one IMU, so EKF3 runs one core, so `attitudes_consistent()`
  compares DCM against the primary rather than skipping the check. Settle it
  with a bench build at `AP_AHRS_DCM_BACKUP_DECIMATION 1` before deciding F8
  **2026-09-19: decided without that check - DCM is built out.** Andy's
  call: DCM gains this board nothing but CPU load. `920c2883a4` sets
  `AP_AHRS_DCM_ENABLED` 0 for all three RP2350 boards and the decimation
  commits are dropped, so AP_AHRS is master's. Copter forces
  `FLAG_ALWAYS_USE_EKF`, so DCM was only the attitude before EKF3 starts,
  the `filter_faults` fallback and the `attitudes_consistent()` pre-arm
  check. Without it `fallback_active_EKF_type()` returns EKF3, so a filter
  fault stays on EKF3, and the check that failed in the video is gone
  (derived from the source, not measured). What it cost at 1/16 and what
  building it out saves: [bench-2026-09-19.md](bench-2026-09-19.md)
  section 6. Not yet booted: the three boards build with no warnings and
  no DCM symbols.
  **2026-09-20: reversed, and the removal was wrong.** The automated review
  on the PR found it first (ISSUE 0): `COMPASS_CAL_ENABLED` is
  `AP_COMPASS_ENABLED && AP_AHRS_DCM_ENABLED`, because
  `CompassCalibrator::AttitudeSample::set_from_ahrs()` reads attitude through
  `AP_AHRS::get_DCM_rotation_body_to_ned()`, which lives inside
  `#if AP_AHRS_DCM_ENABLED`. Building DCM out therefore compiled out
  interactive compass calibration - the `MAG_CAL` command handling, the
  calibrator, its pre-arm check and the aux function - on a board with no
  compass of its own. Fixed-yaw calibration and `COMPASS_LEARN` do not touch
  that accessor and survived. DCM is back at full rate with its three
  functions in the SRAM registry; the decimation stays gone. The cost and
  what is still unmeasured: [bench-2026-09-19.md](bench-2026-09-19.md)
  section 6.
  **2026-09-20: measured on the board, and it closes F8.** Full-rate DCM is
  1.53% of core0 (460,000 PCSR samples, disarmed) and nothing at all on core1,
  where the margin is tight. The 2.0-2.7% carried above was the 1/16 figure
  scaled by 16 and it was too high: `get_results` never was decimated. More to
  the point, DCM now tracks the EKF3 primary to 0.02 deg in roll/pitch against
  the 10 deg pre-arm limit, with `_error_rp` around 0.001, where the video had
  it failing at 3 and then 33 deg. The decimation was the fault, not DCM.
  [bench-2026-09-19.md](bench-2026-09-19.md) section 7
- F13: PR size (185 files at `c1c8709823`, 178 now)
- Core1 watchdog coverage is only indirect (`rp2350_core_affinity.h`)
- The RAMFUNC2 section script is silent about registry misses outside
  copter, and its copter check scans every object under the build root, so
  stale objects from another target can satisfy it
- Not from the review, found while auditing (derived from the source, not
  measured): the RP2350 USB direct-IO path
  keeps dead branches, `drop_unopened_usb_tx_backlog()` does nothing; RP2350
  sets up the USB strings early in `board.c` for no recorded reason;
  `hrt.c` uses `port_lock()` on RP2350 instead of the system lock, and its
  safety under SMP was not checked; `PICO2.py` carries datasheet tables
  flattened into comments; `AP_HAL_Boards.h` still defines three
  `AP_RP2350_*` feature names
- Pushed 2026-09-14 at `fea5156687`. Replies posted the same evening: Peter's
  `flash.c:85` thread (discussion_r4009838869), tpwrules' `stm32_util.h`
  thread (discussion_r4009839843) and a status comment for tridge's review
  (issuecomment-5671163072). Andy's hardware test of the change set is
  planned for 2026-09-15, including whether the RP2350 fault-path save is
  safe

## The 2026-09-19 automated review, and 2026-09-20's answers

AP-Review's pass over the delta between the two pushed heads: 1 of 22 earlier
findings resolved, 21 untouched, six new. What was done, and what was refuted
so it is not raised again.

Acted on: ISSUE 0, the compass calibration that went with DCM - the strongest
finding of the round, and the DCM entry above has it. ISSUE 1 falls out of the
same change. NOTE 6, the split-out PRs missing from the table, was already
fixed that morning. Then, as commits on the branch:

- `d2ad05e614` the RAMFUNC2 size annotations. 38 of 207 were stale, not the six
  the review named; two were out by more than 10x. Refreshed from the RPI_UAVFC
  binary, which is what the heap-budget argument is made from.
- `80bdaddd00` FLASHING.md. Laurel's app offset is `0x10010000`, not RPI_UAVFC's
  `0x10020000`; and the parameter loss after a `_with_bl.hex` flash is the hex
  itself, measured at 65,536 bytes of `0xff` across `0x10010000-0x1001fff0` on
  the RPI_UAVFC image, not the firmware that was there before.
- `c1a04fe43a` the OSD publish: a block rendered while a late one went out was
  published anyway. Also the interrupt rate, which was still an eight-line
  block's.
- `ee5a400928` SBUS drop accounting, and `ecf9de3051` the footer whitelist -
  five accepted byte values, so a receiver outside the set loses every frame.
  Upstream took the same list out in #33057 for the same reason; that one was
  found here rather than by the review.
- `21f63a7f93` CPUInfo's fixed 375 MHz, against 225 on two of the three boards.
- `2b7826d011` AP_Relay. Behind the `Bitmask<256>` note is a real defect:
  `ensure_output()` took a `uint8_t` while the API takes `int16_t`, so a GPIO
  above 255 tested another pin's bit and then set the mode on the truncated
  number.
- `7c9ba203cb`, `0674c732aa`, `e546e8dfd3` the smaller notes.

Refuted, with what was checked:

- **`advance_to()` "early-returns on a blank block without draining".** The drop
  loop discards any queued block whose tag is not the current one. After a run
  of blank blocks the queue legitimately holds *future* blocks, so draining
  there would throw away work already rendered. The early return is right.
- **`PICO2.py:49`'s 375 MHz is not stale.** It is the live default, and Pico2
  generates `HAL_EXPECTED_SYSCLOCK 375000000` from it; RPI_UAVFC and Laurel
  override with `MCU_CLOCKRATE_MHZ 225`. Only CPUInfo's copy was wrong.
- **NOTE 3's "keying on `defined(RP2350)` alone would be safe either way" is
  wrong**, and would under-report by 225x on a non-SMP RP2350 build. Only the
  SMP RP2 port reads the 1 MHz TIMER0
  (`ARMv8-M-ML-ALT/smp/rp2/chcoresmp.h:202`); the non-SMP ARMv8-M port a
  single-core build would use takes DWT CYCCNT at the core clock
  (`ARMv8-M-ML-ALT/chcore.h:1330`). The review said it could not check this
  without the submodule checked out.
- **ISSUE 2, in its remedy rather than its observation.** It is right that
  `rate_controller_filter_update()` also calls `ins.update_backend_filters()`,
  so the gate covers more than the commit message says. But leaving that half
  at gyro/2 would hand back most of the saving: `update_gyro_filters()` calls
  `notch.update_params()` for every enabled notch, which is where the
  coefficients are recomputed. The 66% to 56.5% was measured with both gated,
  and the tracking table in the bench note is the combined effect. #34436's
  description now states it instead.

## The 2026-09-20 automated review at `ecf9de3051`

Re-reviewed after the DCM reversal: of 22 findings, 14 resolved, 5 dropped
("because you are right"), 6 open. All three previously admitted ChibiOS gaps
closed in our favour once `modules/ChibiOS` was checked out, including the
`THREAD_STATS_COUNTER_HZ` SMP test and the `chTMObjectInit()` reading.

Items 3-9 were done as eight commits. Item 1 (two commit prefixes) and item 2
(the six board-validation items that actually block CI: a missing
`RPI_UAVFC-SimOnHardWare/README.md`, nine `SERIALn_*` lines in `defaults.parm`
that `test_new_boards.py` wants as `define DEFAULT_SERIALn_*`, and Laurel's
unreferenced JPEGs) are deferred by Andy.

- `c493fb6e39` **Pico2 reported 375 MHz for a part running at 250.**
  `MCU_CLOCKRATE_MHZ` was absent, so `HAL_EXPECTED_SYSCLOCK` fell back to
  `PICO2.py`'s 375 MHz - a rate no board runs - and `@SYS/threads.txt` and
  CPUInfo divided by it. The fallback is now the stock 150 MHz.
- `57200be57d` and the structural half the review suggested: `RP_PLL_SYS_CLK`
  is a compile-time expression, so `system.cpp` can `static_assert` the
  declared rate against the PLL dividers the way it does for STM32. That
  turns this whole class of mistake into a build error.
- `da4dd16ddb` **the 8E2 SBUS program was selected on `OPTION_RXINV` alone**,
  so FPort - inverted but 8N1, and recommended with `SERIAL3_OPTIONS 15` in
  our own README - got a parity-skipping receiver. Gated on the same
  inverted-at-100000-baud test the byte assembler already used, which now
  reads one flag rather than repeating the test. The same commit answers the
  footer-whitelist finding: alignment is enforced with a 2 ms frame-gap test
  in the PIO layer, because that is the last layer that knows the wire timing.
  A batched port has none left by the time the bytes reach the decoder, which
  is exactly what #33057 is for, so the two are consistent rather than in
  tension.
- `87430fdc70` **the FTP semaphore leaked on every failed `init()`**, and a
  remote peer paced the retry: `handle_file_transfer_protocol()` calls
  `init()` per packet, so each one allocated another and dropped the pointer,
  in exactly the low-memory state that made `thread_create()` fail.
- `0b3402796a` `hrt_micros64()` and the ADC error callback took the ARMv8-M
  port lock inline without `__dbg_check_lock()`, so an asserts build halts in
  `chSysHalt()`. Release firmware was never affected, which is why it flies.
- `71a7ae3872` **`HAL_GPIO_INIT_LEVELS` only covered pins with a `GPIO()`
  number**, so an OUTPUT pin without one had its `HIGH`/`LOW` silently
  dropped - and `board_rp2350.c`'s leftover `palClearLine(BEC_9V_EN)` then ran
  *after* the table and undid the HIGH it had just applied. On RPI_UAVFC the
  9V rail only came up because RELAY3 raised it later. The table now takes the
  level from the pin's own qualifier, and only an explicit one, since
  `get_ODR_value()` defaults to HIGH. Laurel's 9V enable is declared LOW to
  match its own hwdef comment and README.
- `bbaf70a578` the doc figures: Laurel still said 375 MHz / VSEL 15 / CLKDIV 6
  in four files, Pico2 still said 150 MHz in three, and `DEVELOPMENT.md` still
  claimed `MAIN_STACK` had had to be raised, which was the free-stack misread
  and was reverted.

**Item 5 was answered with a sentence rather than a VSEL.** Pico2 runs a 1.67x
overclock with no `RP_VREG_VSEL`, so `rp2350_vreg_init()` is compiled out and
the core stays at 1.1 V, where Laurel and RPI_UAVFC raise it to 1.15 V for a
slower 225 MHz. Laurel's own record has a 300 MHz LOCKUP at 1.1 V. There is no
Pico2 on the bench, and raising the core voltage of a board nobody can test is
not better than disclosing that it is uncharacterised. The hwdef says so now,
and names VSEL as the first thing to try.

**ISSUE 2's remainder is answerable from the source and needs no code change.**
The review's worry is that gating `rate_controller_filter_update()` decimates
the backend coefficient push along with the re-centre, taking a 100->200 Hz
step from 7.0 ms to 35 ms. But `AP_InertialSensor::update()` calls every
backend's `update()` each main loop, and that reaches `update_gyro_filters()`
and the same `notch.update_params()` (`AP_InertialSensor_Backend.cpp:844`),
rate thread or not. So the push still happens every main loop, exactly as on a
vehicle with no rate thread; what is gated is the *extra* push the rate thread
was making on top. #34436's description now says this.

## The 2026-09-20 follow-up review at `bbaf70a578`

Two resolutions (the clock constant, checked across all seven RP2350
configurations including the three bootloaders; and the FTP semaphore), three
new findings, and the two commit prefixes still named as the entire CI
failure.

**The frame-gap test was broken in a way worth remembering.** `_service_irq()`
is the shared vector for both directions, and TXNFULL is true whenever the TX
FIFO has room, so timestamping every entry to `_service_rx_fifo()` refreshed
`last_byte_us` continuously while the port had anything to send. The 2 ms of
silence could then never be observed, no `0x0F` was ever accepted, and SBUS
would not have synced at all on a port that also transmits. The comment three
lines above the bug says TXNFULL "never stops firing"; the code was written
anyway. `6011171ede` takes the timestamp from a byte that actually arrived.

The same commit takes the reviewer's ISSUE: a discarded byte no longer
consumes the gap. All bytes in a batch share one timestamp, so any of them
could be the one that followed the silence, and letting a leading noise byte
spend it cost the real header behind it. The gap is now consumed only when a
frame actually starts.

### The commit prefixes, and the CI failure behind them

Fixed by rewording two commits, which is all the failing check ever wanted.
`Tools/scripts/allowed_subsystems.py` maps `Tools/ardupilotwaf/chibios.py` to
`waf` alone and `AGENTS.md` to `Tools` alone, so "ardupilotwaf: build a UF2 for
RP2350 firmware" became "waf: ardupilotwaf: ..." - matching four sibling
commits already on the branch - and "AGENTS.md: list RPI_UAVFC in the board
table" became "Tools: list RPI_UAVFC in the AGENTS.md board table". Master's
own history carries plenty of bare `ardupilotwaf:` and `AGENTS.md:` subjects;
the checker is newer than they are.

Done non-interactively, with `GIT_SEQUENCE_EDITOR` marking exactly those two
commits for reword and `GIT_EDITOR` rewriting a subject only when it matches
one of the two strings, so nothing else could be touched by accident. 47
commits replayed, the tree verified identical to a backup ref afterwards, and
all 270 branch commits now pass the mapping. Rewriting at depth 47 means the
next push of this branch is a force push.

### The 9V rail finding, and what the history actually says

Reported as "the 9V rail now comes up enabled at boot on RPI_UAVFC", from the
hwdef comment saying the rail is "held off until the power tree is validated".
Half right, and the half that matters was already settled here:

- **Polarity is active HIGH.** Each enable drives an MP4334 EN through a
  pull-down, so LOW or floating is off. The rail being observed on does *not*
  make it active-low, and DEVELOPMENT.md already says not to touch
  `RELAY3_INVERTED` on that basis.
- **Pin mapping on the supported final revision is PA18 = 5V, PA19 = 9V.** The
  earlier revision had them swapped, which is where every wrong mapping in the
  notes came from. The hwdef *labels* were right; its own comment and the
  bootloader hwdef were the ones disagreeing, so a reader had three mappings
  to choose from.
- **The rail was already being enabled.** `RELAY3_FUNCTION 1` with
  `RELAY3_DEFAULT 1` means `AP_Relay::init()` drives GPIO 82 ON
  (`AP_Relay.cpp:387-398`, `DefaultState::ON == 1`). Removing the leftover
  `palClearLine()` removed the brief low period between board init and relay
  init, not the enable. The stale text was the "held off" sentence, written
  when both relay defaults were 0.

So `8380799f31` corrects the comment and the bootloader labels and leaves the
level alone. Turning the rail off at boot would mean `RELAY3_DEFAULT 0` as
well, which is a behaviour change on a board whose VTX runs off that rail, and
is Andy's call rather than a reviewer's.

## Open review threads (8 of 41)

Closed this session: 12, each verified against the tree **and** against the
PR head before replying. Remaining:

| who | file | comment | why still open |
|---|---|---|---|
| tpwrules | `AP_AHRS.cpp` | "Why?" | DCM skip still there, pending decision. 2026-09-19: gone, the file is master's and RP2350 builds DCM out; reply owed at the next push |
| tpwrules | `stm32_util.h` | "Surely this should be fixed in ChibiOS?" | about the `PAL_LINE` override, not `STM32_HW` (corrected 2026-09-14, see the third round); fixed in ChibiOS#113, override gone since `7fd63d181b`; replied 2026-09-14, not resolved |
| tpwrules | `Laurel/images/*.jpg` | "These pictures can be scaled down, 1MB is large ... Do we need the board at all?" | new 2026-09-14, not answered |
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
