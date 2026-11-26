# PR #32995 - RP2350 Port

Analysis archive for [ArduPilot/ardupilot#32995](https://github.com/ArduPilot/ardupilot/pull/32995).

**2026-11-26:** Rover on the motorless RPI_UAVFC testbed, see
[bench-2026-11-26-rover.md](bench-2026-11-26-rover.md). At Rover's 50 Hz
default core0 is 33-35% busy armed; at 400 Hz 74-90%, mostly XIP
fetches. `3715cf8ccd` places Rover's hot code in SRAM as `[ardurover]`
(255 functions, 29.9 KB; the 58 Plane EKF3 and AHRS entries Rover runs
become `[arduplane,ardurover]`): armed core0 at 400 Hz 74-89% to
50-64%, at 50 Hz 33-35% to 28-30%, `ahrs_update` down a third to a
half, 33.6 KB less free memory; Copter and Plane byte-identical. One
local commit on `b9db33af08`, not pushed. Rover's GCS tasks at the
board's 25 Hz saved under 1.5 points and were left out. The registry
scripts now carry the program markers (`af935a65c2`, `46d1e21896`): the
repair script checks marked entries for `--vehicle` and keeps their
markers, and the size annotator no longer strips them; the PC
profiler now matches registry entries (`3ec670ca66`), and
`./waf <vehicle> --rp2350-relocate` runs the repair from the build
(`6f6ce1a495`..`14f61e9355`). The testbed is
back on its Copter `031f2549` from the full-flash backup, parameters
matching.

**2026-11-25:** ArduPlane on RPI_UAVFC, see
[bench-2026-11-25-plane.md](bench-2026-11-25-plane.md). Pushed as PR
head `f4c65bc4f1`, ten commits on `5e97be2505`. Then squashed, reordered
and force-pushed as PR head `b9db33af08`, 93 commits on master: seven commits that leave STM32 output unchanged, then
the six that change it. They are Copter's 200 Hz loop rate as a hwdef
define, line-neutral in `AP_Scheduler.cpp` (`2e9128a39f`..`ea31077f81`);
a registry marker, `[arduplane]` or `[arducopter,arduplane]`, that limits
an entry to those programs' own code (`5c1eacaf48`, `53f9a958a2`), and
`--verify` honouring it (`4f20652cea`); and Plane's per-loop path,
navigation path, EKF3 and AHRS in SRAM (`815f847a85`). The elevons
follow Plane's mix exactly through to the pin, and Andy saw the servo
move. Andy's flight board runs `f4c65bc4`, the same code. Still owed:
see "Outstanding", 2026-11-25.

**2026-11-23, later:** the notch update without libm is on branch
`notch-fast-sincos`, not on the PR and not yet flown. See "2026-11-23: the
notch update without libm" below.

**2026-11-23:** PR head `5e97be2505`, 86 commits on master `321896137f`;
the alpha2 flight card flown on `031f2549`, see
[bench-2026-11-23.md](bench-2026-11-23.md).

**2026-11-18:** PR head `9f1dcc9985`, 76 commits on master
`321896137f`. "Status (one line)" is the
current state; the paragraphs directly below describe the branch as it
was in early October.

**2026-10-02:** the flight build failed - continuous reboots (PIO UART lock
deadlock) and GPS dropouts (UART RX DMA count after an abort). Both fixed,
squashed into the PR and measured; see "2026-10-02" below and
[bench-2026-10-02.md](bench-2026-10-02.md).

**Current state, 2026-10-01.** PR head `564e6c1c7d`, 53 commits on upstream
`26c7363f64`, on the davidbuzz remote. The narrative below runs in date
order and its opening paragraphs describe the branch as it was in
mid-September; the newest rounds are "2026-10-01: two review rounds" and
"2026-09-23 to 2026-09-29" further down.
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
- [bench-2026-10-01.md](bench-2026-10-01.md) - the lock-free microsecond
  clock A/B (per-call cost down by more than half, system load unchanged),
  core1 left in the bootrom after an SWD flash and only a power cycle
  clearing it, and both cores' VTORs read off the running board.
- [bench-2026-10-02.md](bench-2026-10-02.md) - the flight build that
  rebooted and lost its GPS: the PIO UART lock deadlock caught on core0, an
  aborted DMA channel reading `TRANS_COUNT` as 0, and a CPU load A/B
  showing the fixed head costs nothing over the head before 2026-10-01.
- [bench-2026-10-28.md](bench-2026-10-28.md) - the PIO UART half-duplex
  echo fix on RPI_UAVFC R4 with a SmartAudio VTX: the late-reader A/B (276
  bytes out and none back without it, one request and its reply with it),
  fifteen SmartAudio regression runs across the builds, and the review
  findings accepted and rejected, the port-lock timeout among them. The
  board turned out to be a modified R3, not R4 (2026-10-29).
- [bench-2026-10-29.md](bench-2026-10-29.md) - the current input on
  modified R3 boards: a TBS ESC's 5.03 mV/A arrives in full and drifts
  1.35 mV/degC against the old boards' 28.4, while the quad's BLITZ E55
  gives 2-3 mV/A on a zero that moves as much; the first flights of
  `e45dae01b1` on the quad; a GPS failure chased as a firmware regression
  that was the receiver recovering; and the passthrough and
  `LOG_DISARMED` gotchas found on the way.
- [bench-2026-10-30.md](bench-2026-10-30.md) - four release-testing logs
  on `1f8685e9`: flight 2's three Acro EKF failsafes and lean traced to
  the compass under motor current (compensation about 1/24 of what the
  refit applies) and a GSF yaw reset taken mid-flip; the port clean
  throughout; the current input on this quad tracking load at 3.4 mV/A on
  a zero drifting 2-3 mV/degC; and the clean Acro flight after the rescale
  and compass refit.
- [bench-2026-10-31.md](bench-2026-10-31.md) - two more release-testing
  logs on `1f8685e9`: the port clean, the EKF yaw right throughout, but
  the compass's coupling to battery current down by a third overnight so
  the refit over-compensates (40 deg and more at high throttle); the
  current zero's temperature drift seen on the compass in flight; the GSF
  16-35 deg wrong in Loiter at 0.4 deg of spread; and a Loiter yaw tool
  that reads drag in a turn.
- [bench-2026-11-23.md](bench-2026-11-23.md) - the alpha2 flight card on
  `031f2549`: three clean low-throttle flights with the hard leg not
  flown, core1 at 64-65% armed, LED_roll's in-flight cost, and the first
  in-flight PC profile of both cores, with `__ieee754_rem_pio2f` the one
  real placement miss on core1. Log 15, later the same day, flew the hard
  leg in Acro at 30 m/s and 37 A, with the port still clean.
- [bench-2026-11-25-plane.md](bench-2026-11-25-plane.md) - ArduPlane on
  RPI_UAVFC without a rate thread, on `5e97be25`: core1 15-18% busy in
  every condition, core0 56% in armed FBWA at 200 Hz with EKF3 and 79% at
  400 Hz, where the scheduler starts deferring tasks; two thirds of
  core0's busy time is XIP fetches, and the registries hold none of
  Plane's own path. At Plane's own 50 Hz default core0 is 35.5% busy;
  the board's `defaults.parm` had set 200 for every vehicle, and
  `2e9128a39f`..`ea31077f81` move Copter's 200 into a hwdef define
  instead. Plane's per-loop path in SRAM (14.4 KB) takes armed FBWA at
  200 Hz from 57.6% to 51.3% of core0, and its navigation path (4.6 KB)
  about half a point more in CRUISE and LOITER. Its EKF3 and AHRS
  (17.3 KB, Plane's copies only) take FBWA and AUTO from 52% to 46%.
  All three are `815f847a85`, under the `[arduplane]` marker of
  `5c1eacaf48`..`4f20652cea`; the elevons follow Plane's mix to the
  pins.

## Status (one line)

2026-11-25: Plane on RPI_UAVFC has no rate thread, so core1 idles at
15-18% and core0 carries everything. Armed in FBWA at 200 Hz with EKF3,
core0 went from 57.6% to 45.8% busy with Plane's per-loop path, its
navigation path and its EKF3 and AHRS in SRAM (36.3 KB of functions,
39.8 KB of SRAM with veneers, `[arduplane]`, Copter
byte-identical). At 50 Hz, Plane's own default and now its default on
these boards, core0 was 35.5% busy before any of them. PR head
`b9db33af08`, 93 commits, the STM32-neutral ones first (first pushed
as `f4c65bc4f1`).

2026-11-23, latest: the notch change has left this PR for its own, #35358,
now at `bd5a581d84` from `andyp1per:pr-notch-sinf-cosf`, as
`calculate_sinf_cosf()` with Cephes' published constants, references and
documented error. On the bench core1 goes from 67.3% to 59.8%. Moving only
libm's range reduction to SRAM gave 64.8% from 67.0%, so about a third of
the saving is the flash penalty and the rest is arithmetic. This branch
needs a RAM registry line for the helper when it takes that commit.
Attenuation still needs a flight, and on by default needs a maintainer's
agreement (see [bench-2026-11-23.md](bench-2026-11-23.md), section 16).

2026-11-23: `notch-fast-sincos` A/B on the bench with injected
motor RPM, eight boots: core1 67.2% to 59.6%, no overlap between builds.
Attenuation is untested, so `NOTCH_CARD.md` is still owed. The unexplained
97% load `PEAK` is a start-up artefact of the measurement, with a fix on
local branch `pr33366-load-peak-settle` (`68e90044c2`, not pushed). PR head
unchanged (see [bench-2026-11-23.md](bench-2026-11-23.md), sections 13-15).

2026-11-23: the notch update's `sinf()` and `cosf()` replaced by an
inlined polynomial on branch `notch-fast-sincos` (`727edd1929`). Host tests
and SITL only: the core1 saving, at most 7-8 points, is not measured. The
next step is `Tools/RP2350/flight-test/NOTCH_CARD.md` on that branch, on
the computer with the quad. PR head unchanged.

2026-11-23: log 15 flew the hard leg on `031f2549`, Acro with flips
at 0.54 throttle, 37 A and 30 m/s. Port clean: worst rate-loop gap 0.94 ms,
no long loops or log drops. Core1 rises about 3 points with motor speed and
peaked at 68.3%; notch coefficient updates are 25.1% of its busy time. PR
head unchanged (see [bench-2026-11-23.md](bench-2026-11-23.md)).

2026-11-23: the alpha2 flight card flown on `031f2549` (#32995 at
`5e97be2505` with the follow-ups and profiling commits). Port clean on
three flights, but all at low throttle: the hard leg was not flown. Core1
64-65% armed, 45% disarmed; LED_roll +5.8 points of core0, +0.4 of core1.
Notch coefficient updates are 23.6% of core1's busy time. PR head
unchanged (see [bench-2026-11-23.md](bench-2026-11-23.md)).

2026-11-20: DShot150 and DShot300 on the PIO, as Betaflight does
it, with Betaflight's end-of-cycle delay fix; the five STM32-neutral
commits (stack trims, DShot) moved ahead of the six STM32-changing ones.
PR head `5e97be2505`, 86 commits (see the DShot section).

2026-11-19: PR #34623's static stack analyser run on the RP2350
build; rate, OSD_c1 and c1_main stacks trimmed (2.7 KB) and pushed as a
fast-forward: PR head `b166a6c230`, 83 commits (see the stack section).

Before that: Lua scripting trialled on RPI_UAVFC (LED_roll on four
NeoPixels: ~4% of core0, no main-loop or core1 effect, 36 KB free armed)
and RP2350 scripting memory resized (50 KB heap, 10 KB stack, 64 KB log
buffer while scripting is on): 110 KB free armed. The three commits
were then moved into the STM32-neutral block: PR head `f5ea4699d9`, 81
commits. A recursing script overflows the scripting stack at either
size (see below).

Before that: the registry repair folded into the commits that
introduced each stale entry, and a Scratch Y overflow before the core1
hot-path commit fixed, so every commit builds RP2350 again. PR head
`0bfe6d9e02`, 78 commits, mergeable, tree identical to `18cd947273`.

Earlier the same day: ESC passthrough bench-tested by Andy on RPI_UAVFC
with AM32 ESCs (esc-configurator read, wrote settings and flashed), and
moved into the STM32-neutral block with the registry repair. Pushed by
Andy's grant over `9f1dcc9985` as PR head `18cd947273`, 78 commits,
mergeable; the description's feature table now lists BLHeli passthrough
as Yes, AM32 tested.

Earlier:

2026-11-19: ESC passthrough added on top, local tip `e7c026ed54`, 78
commits, unpushed: `c3133097d0` and `e7c026ed54`, reworked the same
day to read replies with the STM32 path's decoder and release the line
as Betaflight does. Builds pass, STM32 output unchanged but for three
`__AP_LINE__` values; not run on hardware.

Earlier:

2026-11-18: PR head `9f1dcc9985`, 76 commits on master `321896137f`,
pushed by Andy's grant the same day over `6a9e836fb0`. The rebase
failed the RAMFUNC2 check on five functions master removed; a new
script repaired the registries, and all three boards build with every
placed function in SRAM (`086a624f07`..`9f1dcc9985` on top of the 72).
Unprofiled, not run on a board. AP-Review round 35's two minors (the
`dshot_send_command` marker, the bootloaders after the repin) are still
open, and the pin is the blocker as before.

Earlier:

2026-11-07, later: Auto flown on the same build. Port clean, every
waypoint reached; RTL's landing came in fast from the quad's vertical
waypoint settings and GPS height, both configuration. The GPS failsafe,
commit 48 and the PIO OSD remain unflown.

Earlier:

2026-11-07: head `1fcec947c5`, 71 commits, tree identical to the
`f0f78b48ec` that alpha2 carries. First flights of the 200 MHz build: the
port clean in flight, scheduler load 29-41% against log 5's 54-69%, one
0.3 s logging drop on the ground after disarm, not explained. RTL flew;
commit 48 still unflown.

Earlier:

2026-10-31: head unchanged at `e45dae01b1`. Two more logs on `1f8685e9`:
the port clean, no failsafe, EKF yaw within 6 deg; the airframe's compass
coupling fell by a third, so `COMPASS_MOT` needs refitting once Andy says
what changed. Commit 48 still unflown.

Earlier:

2026-10-30: head unchanged at `e45dae01b1`. Four release-testing logs on
`1f8685e9`: the port clean on every flight (1600 Hz, worst armed gap 1.07
ms, nothing dropped); flight 2's failsafes were the airframe's compass,
and Acro flew clean after the rescale and refit. Commit 48 still unflown.

Earlier:

2026-10-28: head `e45dae01b1`, 55 commits. Commits 1-51 leave STM32
output unchanged (MatekH743 at 51 equals master) and 52-55 change it.
Round 29's GET_CRC should-fix and the Laurel beep are fixed; the
PIOUART half-duplex echo is fixed on the bench (48), not flown. Pico2
runs on real hardware with a clean pre-arm but for RC. Otherwise open
as on 2026-10-27.

Earlier:

2026-10-27: head `6cffb8ed11`, 51 commits, AP-Review rounds 21, 24 and 25's
fixes and the three fossuav/ardupilot-rp2350 doc corrections squashed in;
round 26 asks for nothing beyond the ChibiOS pin. STM32 output unchanged
commit for commit. Open as on 2026-10-23, plus the PIOUART half-duplex
echo; the AI-disclosure line is declined.

Earlier:

2026-10-23: head `be00cf53c3`, 51 commits on master `2f3644c90e`;
everything but four STM32-changing commits leaves STM32 output unchanged.
Open: ChibiOS#113 not merged; CHANGES_REQUESTED from tpwrules, Peter and
tridge with their comments answered; the 2026-10-22/23 changes are unflown.

Earlier:

2026-10-01: 53 commits; the first 45 leave STM32 output unchanged. Open:
the RPI_UAVFC README image (CI), ChibiOS#113 not merged, tridge's
CHANGES_REQUESTED. The automated reviews were answered in
issuecomment-5937448806.

Earlier:

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

**2026-10-27:** "Not yet run against a receiver" above is out of date: Buzz
has since run SBUS with a receiver (reported by Andy; board, receiver and
log not recorded here). See "2026-10-27" below.

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

2026-10-23: the AP_Param row is resolved. Laurel and RPI_UAVFC no longer
use @READONLY, the commit is out of the PR, and #34443 carries a newer
version of the fix upstream.

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
  safety under SMP was not checked; **2026-10-01: moot** - `2d147f576d` reads
  TIMER0's raw 64-bit count with no lock at all
  ([bench-2026-10-01.md](bench-2026-10-01.md) section 1); `PICO2.py` carries datasheet tables
  flattened into comments; `AP_HAL_Boards.h` still defines three
  `AP_RP2350_*` feature names
- Pushed 2026-09-14 at `fea5156687`. Replies posted the same evening: Peter's
  `flash.c:85` thread (discussion_r4009838869), tpwrules' `stm32_util.h`
  thread (discussion_r4009839843) and a status comment for tridge's review
  (issuecomment-5671163072). Andy's hardware test of the change set is
  planned for 2026-09-15, including whether the RP2350 fault-path save is
  safe

2026-11-26, the Rover commit `3715cf8ccd` and the registry tooling
`af935a65c2`..`14f61e9355` (six commits): not pushed, not reviewed by `/pr-review`,
and Rover has not driven on the placement. The PR description says
nothing of Rover either.

2026-11-25, the Plane commits (`2e9128a39f`..`815f847a85`):

- `/pr-review` has not run on them.
- The PR description is stale: it says 71 commits (now 93) and five
  that change STM32 output (now six), and says nothing of Plane.
- Plane has not flown on RPI_UAVFC. Once it has, or when a maintainer
  asks for the final squash, fold the loop-rate fix into the board
  and documentation commits it corrects and the marker into the
  generator, waf and Tools commits it extends (bench-2026-11-25-plane.md,
  "Reorder, marker spelling and an elevon check").

## 2026-11-23: the notch update without libm

Andy asked for the notch performance work after log 15. Branch
`notch-fast-sincos`, on alpha2 `031f2549`. **Not run on a board and not
flown**, so no CPU saving is measured here.

| commit | what |
|---|---|
| `c1c925b716` | Filter: test the coefficients through the impulse response against a double precision design. Passes on the existing code |
| `727edd1929` | Filter: sine and cosine from one inlined polynomial pair |
| `8b1271bf0d` | Tools: `NOTCH_CARD.md` and `HISTORY.md`. Not for upstream |

Where the time goes. The quad has 4 motors, 4 harmonics and a triple notch,
so 48 notches, re-centred at half the 3201 Hz gyro rate because
`INS_HNTCH_OPTS` 22 sets `LoopRateUpdate`. `AP_ESC_Telem::get_rpm()`
interpolates between ESC reports, so a centre differs at each update and
the unchanged check in `init_with_A_and_Q()` rarely fires (derived from the
source, not measured). The coefficient update is 25.09% of core1's busy
samples in log 15. Within that, `sinf`, `cosf` and their helpers are 12.32%
of core1's busy samples (`__ieee754_rem_pio2f` 5.34, `__kernel_cosf` 2.67,
`__kernel_sinf` 1.94, `cosf` 1.20, `sinf` 1.17), and 10.80% in flight 3.
That caps what this change can save at 7.1-8.2 points of core1 load, less
the polynomial's own cost.

The change. `sin_cos_0_to_pi()` reduces the angle to +-pi/4, using pi/2 and
pi in two parts, and evaluates a degree 7 sine and a degree 8 cosine. It is
forced inline, so it runs from SRAM inside the registered
`init_with_A_and_Q` and needs no registry change. No parameter changes.

| Check, on the host unless stated | Result |
|---|---|
| Every float angle from 1e-4 to pi (125,262,020) | max error sin 6.5-8.0e-8, cos 7.4-8.8e-8, with and without fused multiply-add; glibc 3.3e-8 |
| This quad's notch at 3201 Hz (A 0.1, Q 11.7), 30 Hz up | 89% of coefficient sets bit-identical; worst response difference 0.002 dB at the centre, 0.003 dB within +-8% |
| 1-8 kHz, 15-40 dB, Q 1-8, 30 Hz up | 90% bit-identical; worst 0.001 dB at the centre, 0.0033 dB within +-8% |
| Stability, 5 Hz up, 400 Hz-8 kHz, 10-60 dB, Q 0.7-20 | 0 unstable of 370,320 coefficient sets |
| `CoefficientsTest` | passes before and after; fails with a sign deliberately flipped |
| RPI_UAVFC build | +424 B flash, +208 B SRAM, no `sinf` or `cosf` call left in the Vector3f update, no warnings |
| MatekH743 build | +432 B flash, no warnings |

The host baseline is glibc's `sinf` and `cosf`, not the newlib versions the
firmware links. Newlib itself was not compared.

SITL `DynamicRpmNotchesRateThread`, six alternating runs of each binary,
peak in dB:

| | Unchanged (4 valid runs) | Changed (6 runs) |
|---|---|---|
| No notch | 15.00, sd 2.45 | 16.00, sd 1.22 |
| Single dynamic notch | -21.60, sd 1.46 | -20.54, sd 0.70 |
| Notch per motor | -25.34, sd 0.60 | -25.24, sd 1.31 |

The no-notch row cannot be affected by the change, so its 1.0 dB difference
shows the noise of this test. Two runs of the **unchanged** binary failed,
one on a 47.7 Hz peak at -2.15 dB after the notch was added and one on a
`GLOBAL_POSITION_INT` timeout. That is the test's flakiness, and the six
clean runs of the changed binary are not evidence that it fixed anything.

Measured and rejected:

| Change | Argument for | Why not |
|---|---|---|
| Polynomials over 0 to pi/2 with one reflection | one branch fewer, no two-part constants | max error 1.7e-7 in sin and 2.1e-7 in cos, about five times glibc's. Reducing to +-pi/4 with a two-part pi gives 8.0e-8 and 8.8e-8 |
| Move only `__ieee754_rem_pio2f` to SRAM on the RP2350 | one registry line, no new maths, no change on any other board | core1 67.04% to 64.79%, against 59.71% with the helper (alpha2 `031f2549`, three bench boots each) |

Not tried: one out-of-line helper, which would save most of the flash now
spent on three inlined template copies but needs its own SRAM placement on
RP2350; and recurrences across harmonics, which clash with each notch's own
slew limit.

Owed: the flight in `Tools/RP2350/flight-test/NOTCH_CARD.md`, which needs
the quad's motors because stopped motors leave every centre below the 400
Hz where the old path turned expensive. It compares `RPLD.C1` by throttle
band with log 15's 64.8, 65.6, 66.8 and 67.8%, and the gyro attenuation
with log 15's -25 to -31 dB at 150-250 Hz, -37 to -41 dB at 250-400 Hz and
-42 to -44 dB at 400-1000 Hz (`batch_fft.py`, 205-330 s). `INS_HNTCH_OPTS`
18 against 22 remains the larger, separate lever.

Reproduce, from `tools/notch_sincos/`:

```sh
python3 fit_coeffs.py
gcc -std=gnu11 -O2 -mfma -ffp-contract=fast accuracy2.c -lm -o <scratch>/a2 && <scratch>/a2
gcc -std=gnu11 -O2 -mfma -ffp-contract=fast accuracy3.c -lm -o <scratch>/a3 && <scratch>/a3 40 10 40
./verify_source.sh <checkout of notch-fast-sincos> <scratch>
```

### Superseded 2026-11-23 by the bench A/B

"Not run on a board" and "no CPU saving is measured" no longer hold. On the
motorless RPI_UAVFC bench, with the quad's notch set and injected motor RPM
putting 66% of harmonic centres above 400 Hz (log 15: 64%), eight
alternating boots took core1 from 67.19% to 59.63% busy by PC sampling. The
trig calls went from 10.48 points to none, and the worst armed rate-loop
gap from 0.91-0.92 ms to 0.83-0.89 ms. Log 15's trig cost is lower than the
bench's, so expect 6-8 points in flight. Attenuation needs the flight in
`NOTCH_CARD.md`. Details in section 14 of
[bench-2026-11-23.md](bench-2026-11-23.md).

## 2026-11-23: the alpha2 flight card

Logs 12, 13 and 14 from the quad on `031f2549`, with both cores' PC
profiles from flight 3. Measurements, tools and the open list are in
[bench-2026-11-23.md](bench-2026-11-23.md).

- No failsafe, internal error, long loop, log drop or ESC telemetry error.
  Worst rate-loop gap in flight 0.92-0.96 ms.
- The hard-flying leg was not flown: `CTUN.ThO` peaked at 0.17 and reported
  current at 6 A, against 0.70 and 50 A in log 8. Load under real throttle
  on this build is not measured.
- Core1 is 64-65% armed and 45% after disarm. LED_roll costs core0 5.8
  points and core1 0.4, with the rate loop unchanged.
- Core1 is 7.6% in flash, almost all `__ieee754_rem_pio2f` (4.44%, which
  the registry records as not profiling) and `__udivmoddi4` (2.13%, largely
  the idle-load measurement itself; derived from the disassembly, not A/B
  tested). Core0's table filled, so its placement cannot be judged.

Later the same day, log 15 flew the hard leg on the profile build: Acro
with flips, 0.54 throttle, 37.1 A reported and 30.3 m/s.

- The port stayed clean. Worst rate-loop gap in flight 0.94 ms, no long
  loops, log drops or ESC telemetry errors.
- Core1 goes from 64.8% below 0.15 throttle to 67.8% at 0.30-0.45, and
  peaked at 68.3%. Core0 follows the mode: 48.6% in Acro, 56.0% in Loiter.
- `__ieee754_rem_pio2f` rose to 5.34% of core1's busy time with motor speed.
- A new compass calibration and `COMPASS_MOT`. The measured coupling is 5.9
  mG/A, under a third of log 8's, and EKF yaw stayed within about 6 deg of
  true through the Acro.
- First card flight with a reply on the DisplayPort. Logs 12-14 received
  nothing on SERIAL1.

The compass difference is hardware: Andy fitted a new GPS/compass module
between logs 9 and 12. `COMPASS_DEV_ID` goes from a QMC5883L to an IST8310,
so compass figures from log 9 and earlier are not comparable with logs
12-15.

## 2026-11-19: ESC passthrough on the PIO DShot outputs

AP_BLHeli's passthrough (ESC configuration and flashing over the signal
wire, one-wire 19200 baud) had no RP2350 implementation: the HAL's
`serial_*()` calls fell back to the AP_HAL stubs, though AP_BLHeli itself
was already built in (39 symbols in the RPI_UAVFC ELF). Three commits on
`9f1dcc9985`, local, unpushed, at Andy's choice added to #32995 rather
than a stacked branch, and rewritten from Ben La Monica's
`benlamonica/pr/rp2350-esc-passthrough-alpha2` (`7770a03624`, on alpha2
`f0f78b48ec`) with credit rather than cherry-picked:

| commit | what |
|---|---|
| `358584a8a9` | AP_HAL: EdgeSerial and its 13 host tests, Ben's code, astyle-formatted; Ben is the author |
| `9704086a2d` | AP_HAL_ChibiOS: the RP2350 implementation, `RCOutput_pico` pause and resume, the STM32 blocks excluded in place, DEVELOPMENT.md; Co-authored-by Ben |
| `f5d840282c` | hwdef: on for RPI_UAVFC and Laurel by dropping their explicit `HAL_SERIAL_ESC_COMM_ENABLED 0`; READMEs |

Prior art. Ben's version read and flashed four Bluejay 0.19 ESCs through
esc-configurator on an RP2354A board (his commit message, not checked
here). Betaflight's PICO platform (`142ed9ad2`, surveyed 2026-11-19)
stops the DShot state machine, gives the pin to SIO and runs the generic
4-way bit-bang against `micros()` with no interrupts masked; that works
there because it is single core with nothing else running during
passthrough, and it releases the line at the start of the last stop bit.

Measured and rejected, or rejected from the source:

| alternative | argument for | why not |
|---|---|---|
| Ben's `chSysLock()` around each byte | exact bit timing, hardware-tested | holds the SMP kernel spinlock about 520 us a byte, so core1's kernel operations wait on every byte; core0-local BASEPRI masking gives the same timing without it |
| Betaflight's unmasked bit-bang | simplest, merged upstream | ArduPilot runs other threads on core0 that would preempt a bit; an edge late by half a bit corrupts the byte |
| the PIO UART `uart_tx` program on PIO2 | no CPU timing at all | it holds the stop bit to its end, and Bluejay can answer from its middle, so the two would drive the wire against each other for up to half a bit |
| `in_soft_serial()` as the core1 gate, as on STM32 | reuses the existing mechanism | adds a load and branch to `dshot_send_groups()` and `dshot_send()`, which run from Scratch Y with 8 bytes free; Ben's channel-mask test already gates `write_frame()` and `read_telemetry()` |
| Ben's new `AP_RP2350_ESC_PASSTHROUGH_ENABLED` | separate from the STM32 code | `HAL_SERIAL_ESC_COMM_ENABLED` already means this, defaults to 1, and the RP2350 hwdefs only had it at 0 |

Changes from Ben's version besides those: release, the early-start check
and the end of the last byte happen inside one masked window, so a
preemption cannot delay the release; the 2 KB edge buffer is allocated per
session and an overflow ends the read (Ben's ring could overwrite
silently); barriers between the interrupt and the reader; the existing
`GPIO::_attach_interrupt()` instead of PAL calls; resume flushes the FIFOs
again for a frame core1 queued during the pause; counters in a global for
SWD rather than a new line in `RCOutput::timer_info()`, which would have
moved STM32 `__LINE__` values. Kept as Ben measured them: the 1 s settle
refusal, the line driven high at idle, release at mid stop bit.

Checked 2026-11-19 at `f5d840282c` (tree as built):

- RPI_UAVFC, Laurel, Pico2 copter build with no warnings; the placement
  check passes on RPI_UAVFC and Laurel; Pico2 keeps passthrough off.
- MatekH743 copter `--consistent-builds` `f1db94851b64` with and without
  the RCOutput.h/.cpp edits.
- RPI_UAVFC with passthrough off and on: 1173 of 1181 functions in SRAM
  or in RCOutput are instruction-identical with addresses masked, the other
  eight being the new ones; `.data`, `.ram4_init` and `.ram5_init` the same
  size (0x19620, 0xdd8, 0xed8).
- `test_edge_serial` 13 of 13 on SITL.

Known gaps, derived from the source and not measured: `SERVO_BLH_TEST`
retries at once and so fails within the 1 s settle on a first attempt; a
fast PIO UART such as CRSF can overrun its FIFO while bytes are sent; no
BLHeli_32 or AM32 ESC has been tried. Owed: a bench session on RPI_UAVFC
with its ESCs, through esc-configurator. Ben's AP_BLHeli fix
(`7ab6e3c5fd`, ack on a failed set-address) is generic and wants its own
upstream PR.

### Superseded 2026-11-19 by the rework at `c3133097d0`

Andy was not convinced by a new decoder, and on review it was not needed:
ArduPilot already has an edge-timed soft-serial reader, the STM32 path's
`serial_bit_irq()`, `serial_byte_timeout()` and `serial_read_byte()`, used
in the field with BLHeli_S, Bluejay, AM32 and BLHeli_32. The three commits
above (`358584a8a9`, `9704086a2d`, `f5d840282c`) were reset away, unpushed,
by Andy's grant, and replaced by:

| commit | what |
|---|---|
| `c3133097d0` | AP_HAL_ChibiOS: the STM32 reader built for RP2350 too; RP2350 setup, transmit, release, end; `RCOutput_pico` pause and resume; DEVELOPMENT.md. Co-authored-by Ben for the pause |
| `e7c026ed54` | hwdef: on for RPI_UAVFC and Laurel; READMEs say untested |

What changed from the version above: no EdgeSerial; the line is released
at the start of the last stop bit and left to the pad's pull-up, as
Betaflight does, rather than driven to its middle; `serial_bit_irq()` is
attached before the last byte and the edges that byte latches are cleared
in `IO_BANK0` INTR at release, inside its masked window (a latched edge
reaching the reader first would read as a 0x00 byte); no settle refusal.
Kept: Ben's pause and resume, core0-local masking per byte, the driven idle
line between commands. The numbers above belong to the replaced commits and
are left as measured.

Checked 2026-11-19 on the tree committed as `e7c026ed54`:

- RPI_UAVFC, Laurel, Pico2 copter build with no warnings; the placement
  check passes on RPI_UAVFC and Laurel.
- MatekH743 copter `--consistent-builds` `f1db94851b64` with and without the
  RCOutput.h/.cpp edits, disassembly identical. That option fixes
  `__AP_LINE__` at 17, so it cannot see line shifts: in a normal build the
  three `WITH_SEMAPHORE()` calls after the serial block (2833, 3011, 3107 at
  `9f1dcc9985`) record lines six higher, and nothing else changes.
- RPI_UAVFC passthrough off against on: 1173 of 1186 functions in SRAM or
  in RCOutput instruction-identical with addresses masked, the other
  thirteen the passthrough functions and the shared reader; `.data`,
  `.ram4_init`, `.ram5_init` the same size.

Added to the rejected table's argument, not measured: EdgeSerial (for: it
handles a reply begun before release and resynchronises on every edge, and
was host-tested; against: a second decoder beside a field-proven one, and
the early-start case does not arise when the line is released at the start
of the stop bit). The 1 s settle (for: Ben measured Bluejay answering after
0.37 s and up to 2.7 s when written to early; against: neither Betaflight
nor the STM32 path waits, and the configurator retries). Open, for the
bench: Ben's commit says a pull-up loses to an ESC input with a pull-down,
which Betaflight's release-to-pull-up would contradict in the field.

### Bench test, attribution and the reorder, 2026-11-19

Andy flashed the `e7c026ed54` build to the bench RPI_UAVFC. The first
upload stopped at 78%: over SWD the app area matched the `.bin` up to
offset `0x10EA00` and was erased from `0x10EB00`, its first words
unwritten, so the bootloader stayed in its loop (`SCRATCH[5]`
`0xB001101F`) and the board looked dead. Re-run from Windows Python on a
free COM15 it programmed and verified, and the app sent heartbeats. What
interrupted the first upload is not known; Mission Planner and a Python
process were running.

Andy then ran esc-configurator through it on AM32 ESCs: read, wrote
settings and flashed firmware, all working (reported by Andy, no log).
That settles the open pull-up question for AM32 at least: releasing to the
pad's pull-up at the start of the stop bit works there. BLHeli_S, Bluejay
and BLHeli_32 are untried.

Betaflight attribution: a one-line thanks in the file header ("With
thanks to Betaflight, whose 4-way interface and RP2350 port the transmit
side follows"), in the style of AP_BLHeli.h, and "As in Betaflight" in
the commit message. A first version naming `suart_putc_()`,
`BL_SendBuf()` and `dshotReleaseMotorIO()` was too detailed for Andy.

Reordered at Andy's request (`rebase` grant, revoked after), from
`eafb004cb4`: the registry repair (`822ddda06f`..`de9740a4e3`), passthrough
`c8ee3fa271` and its hwdef `836a00eadc`, then the six STM32-changing
commits (`4924d92d2c`..`f693390096`). Backup
`backup/pre-passthrough-reorder-20261119` at `e7c026ed54`. Tree identical
to the pre-reorder tip; `range-diff` shows the ten moved commits unchanged,
messages included. Per-commit builds in a scratch worktree:

- MatekH743 `--consistent-builds` `29c14509aeab` at `eafb004cb4` and at
  every moved commit through `836a00eadc`, then changing with each
  STM32-changing commit to `f1db94851b64` at the tip, as before.
- RPI_UAVFC copter fails at `eafb004cb4` (stale registry, as since the
  rebase) and builds with no warnings at every commit from `822ddda06f` to
  the tip, so the six STM32-changing commits now build on RP2350 too.

Owed: fold the registry repair back into the commits that introduced the
removed entries, so commits 1-66 build RP2350 again.

The shortened thanks was folded into the passthrough commit by Andy's
own grant (my run of `grant_push.py` was refused by the session's
permission check): comments and message only, tree identical, the rest
unchanged by `range-diff`. Renumbered: passthrough `ed999253e3`, hwdef
`80d903433b`, the six STM32-changing commits `20ec3fa10c`..`18cd947273`;
the registry repair keeps `822ddda06f`..`de9740a4e3`. Tip `18cd947273`.

Pushed 2026-11-19 with `--force-with-lease` pinned to `9f1dcc9985` (+12/-10);
GitHub reports head `18cd947273`, 78 commits, mergeable; grant revoked
after. Not reviewed by `/pr-review` at this head. The description's
`| BLHeli passthrough | No | |` row became a Yes row beside the DShot
rows, AM32 read, configured and flashed on RPI_UAVFC; nothing else in
it changed (diffed against the read before the edit).

## 2026-11-20: scripting CPU profile, a Lua flight mode at 50 Hz

Andy asked for a scripting performance test at 50 Hz (a flight mode
calling a bunch of functions) and a proper profile. Scripts and tools are
in `tools/scripting_profile/`.

Workload `perf_mode.lua`: registers custom mode 101 and runs every 20 ms.
A run makes about 45 binding calls: mode, arming, AHRS
roll/pitch/yaw/gyro/velocity/health, INS accel, baro, battery, four RC
channels, four ESC RPMs, four motor PWMs and three Parameter gets. It
runs a three-axis angle and an altitude-rate PI controller in Lua, calls
`set_target_angle_and_climbrate` in GUIDED_NOGPS or the custom mode (the
climb rate is never positive), writes a 10-float `logger:write` and sends
a named float at 10 Hz. Five `micros()` points time its sections.
`perf_mode_cached.lua` is the same script with every binding method
looked up once into a local (`local ROLL = ahrs.get_roll_rad` ...
`ROLL(ahrs)`).

Method. The firmware is the PR head `5e97be2505` built with
`--enable-stats` (a worktree, RPI_UAVFC, OSD_TYPE 6, MOT_PWM_TYPE 6,
BDMASK 15, no motors fitted). On the SMP port ChibiOS times every thread
off the 1 MHz TIMER0, and `threads.txt` reports each thread's share of
its own core since the previous read. `mav.py window` reads the file once
to zero the counters, records for 32 s and reads it again. Inside that
window: 50k core0 PCSR samples (2,500/s, no halting), attributed by
object file from the link map (`attrib.py`), with `categ.py` grouping
the run-minus-baseline difference; XIP CTR_HIT/CTR_ACC over 3 x 1 s; and
the script's own section times.

| Condition | Scripting thread | core0 idle | ArduCopter thread | sched load | XIP hit, misses | free |
|---|---|---|---|---|---|---|
| A no script, disarmed | 0.2% | 62.1% | 23.7% | 24.2% | 85.8%, 0.83 M/s | 148 KB |
| B perf_mode, disarmed | 10.4% | 50.8% | 24.2% | 24.2% | 90.8%, 1.09 M/s | 97 KB |
| E perf_mode_cached, disarmed | 7.8% | 52.8% | 24.1% | 24.4% | 91.2%, 1.02 M/s | 91 KB |
| D no script, armed GUIDED_NOGPS | 0.3% | 44.5% | 31.1% | 31.7% | 86.9%, 1.15 M/s | 147 KB |
| C perf_mode, armed GUIDED_NOGPS | 11.6% | 32.7% | 31.2% | 32.0% | 90.2%, 1.39 M/s | 89 KB |

The Scripting thread (priority 2) takes core0's idle time and nothing
else. The main loop's thread load and the scheduler load do not move,
and no task slipped. Task overruns in the one 10 s `tasks.txt` window
went 68 -> 143 (B) and 183 (E) disarmed, and 204 -> 274 armed. They are
spread over many tasks at a few tens of us over budget, which fits main
loop code evicted from the XIP cache between iterations. E costs less
than B but overran more, so these counts are noise-level. XIP accesses
double while the script runs (5.8 -> 11.9 M/s) and misses rise by 0.24
to 0.26 M/s. The hit rate goes up because the VM loop hits well.

The script's own timing is wall time, so it includes preemption. Runs
came every 20.3-20.8 ms (48-49 Hz). B took 2.07 ms on average and 1.47
ms at best: sensors 1.18, control 0.34, output 0.20, log 0.30 ms. C took
3.7 ms on average (more preemption armed) but only 0.12 more CPU. E took
1.40 ms on average and 0.95 ms at best: sensors 0.54, log 0.19 ms. One
`micros():toint()` costs 20-25 us.

Where B's extra 11.8 points of core0 went (E in brackets, 9.25 points):

| Points | Share | Category |
|---|---|---|
| 4.17 (3.32) | 35% | Lua VM and API (luaV_execute, luaD_precall/poscall, index2addr, luaH_getshortstr) |
| 1.37 (1.37) | 12% (15%) | Lua GC: the full `lua_gc(L, LUA_GCCOLLECT, 0)` after every run, `lua_scripts.cpp:627` |
| 1.18 (0.07) | 10% | binding method lookup: generated `load_function` linear `strcmp` over the type's method names, every call |
| 0.72 (0.60) | 6% | binding glue |
| 0.49 (0.40) | 4% | heap alloc/free (Vector3f and uint32_t userdata) |
| 0.43 | 4% | AP_Logger for logger:write |
| 0.37 (0.39) | 3% | `luaG_traceexec`: the SCR_VM_I_COUNT count hook makes `vmfetch` call it on every instruction |
| rest | | ArduPilot code the bindings call, kernel, and EKF reset-loop noise |

Per call (`perf_bench.lua`, disarmed, best of 9 batches of 40, empty
closure call 2.6 us subtracted, hot cache; in the real run calls cost
about three times this):

| Call | us | Call | us |
|---|---|---|---|
| Lua arithmetic, 4 ops | 2.2 | baro:get_altitude | 6.0 |
| math.sin | 3.8 | arming:is_armed | 7.2 |
| string.format | 28.7 | ahrs:get_roll_rad | 14.4 |
| millis() | 12.7 | vehicle:get_mode | 14.8 |
| micros():toint() | 25.2 | ahrs:get_gyro (new Vector3f) | 28.7 |
| uint32 subtract + toint | 66.5 | ins:get_accel(0) | 21.1 |
| Parameter:get | 8.2 | Vector3f + Vector3f | 23.5 |
| param:get(name) | 56.2 | set_target_angle_and_climbrate | 26.0 |
| rc channel norm_input | 10.4 | logger:write, 4 floats | 128.6 |

Simple getters differ by where the name sits in the `strcmp` list:
baro's list is short (6 us), ahrs's and vehicle's are long (14-15 us).

What it points at (none of it RP2350-specific except the last):
- The method lookup is the cheapest win. Scripts can cache methods in
  locals (-25% here). The generator could do the same for every script
  on every board by caching a found function in the type's metatable or
  using a table `__index`, an upstream PR.
- The per-run full GC is 12-15% of a 50 Hz script's cost. Its comment
  says it "seems to resolve a memory leak", so replacing it with
  incremental steps needs the leak understood first. Upstream discussion.
- The count hook is inherent to SCR_VM_I_COUNT (3-4%).
- RP2350 only: about 7 KB of the hottest VM code (luaV_execute 4.4 KB,
  luaD_precall, propagatemark, luaG_traceexec, reallymarkobject ...)
  holds 5.4 of B's 8.4 Lua-attributable points. Moving it to SRAM would
  remove its XIP stalls but costs SRAM the scripting heap competes for.
  Not measured.

Bench restored afterwards: LED_roll.lua back on the SD card, SCR_ENABLE
0, BRD_IDLE_STATS 0, SCHED_OPTIONS 0, FS_THR_ENABLE 1, TKOFF_RPM_MIN
1000, DISARM_DELAY 10, OpenOCD detached with C_DEBUGEN cleared, bridge
stopped. The board still runs the `--enable-stats` build of `5e97be2505`.

Follow-up the same day: Andy asked for the method lookup cache. Branch
`pr-scripting-index-cache` off upstream/master `c69185e3ed` (worktree in
the scratchpad, uncommitted; `index_cache.patch` here). Each type's metatable `__index` becomes a
table that caches what the type's index function returns, with a shared
metatable whose `__index` calls that function on a miss and stores the
result. It is filled lazily and set up last, after `__index` and the
operators, so a failed allocation leaves the type working uncached. A new
`test_index()` in `scripting_test.lua` passes on master and with the
cache.

Same bench and script, firmware the only difference (PR head plus the
patch, `--enable-stats`):

| | old | index cache |
|---|---|---|
| Scripting thread | 10.3% | 8.5% |
| perf_mode_cached (locals) | 7.8% | 8.1% |
| run best / mean | 1.49 / 2.55 ms | 1.13 / 1.84 ms |
| name lookup (load_function + strcmp) | 1.20 points | 0.08 |
| Lua VM and API | 4.17 points | 3.65 |
| Lua GC | 1.36 points | 1.39 |
| Lua heap in use | 27,364 B | 28,965 B |
| vehicle:get_mode / ahrs:get_roll_rad | 14.8 / 14.4 us | 5.3 / 5.2 us |
| set_target_angle_and_climbrate | 26.0 us | 10.6 us |
| flash, MatekH743 and RPI_UAVFC copter | | +432 B (+436 B final) |

SITL (upstream master + patch): Rover Scripting's internal test,
ScriptingLocationBindings, ScriptingSteeringAndThrottle, Copter
ScriptingFlipMode, ScriptingFlyVelocity and ScriptingAHRSSource pass.
Rover.Scripting's MAVLink step and Copter.LuaParamLockdown fail here on
plain master too (`mavlink_msgs.lua:71`, `param-lockdown.lua:220`
payload_ofs nil): autotest generates the Lua MAVLink module with the
system pymavlink, older than master expects. Not the change. Upstream
master needed MAVLink `6d0a097b`, fetched into the worktree from
ArduPilot/mavlink.

Self-review (/pr-review, full, 2026-11-20): three Claude reviewers (each
commit, whole diff), Codex cold reads of each commit and the whole diff
(no correctness defects), Codex verification of every finding. Verdict
COMMENT: 0 must-fix, 3 should-fix, 2 notes, all fixed and folded in
(rebase grants from Andy). The test compared cache hits only and a
first-lookup failure could be masked by later passes, so it now checks
once, on names nothing else looks up, and adds the singleton pair,
ap_object and numeric-key cases. The cache comment states that an index
function's answer must depend on the name alone; the key is a non-const
`static char` (QURT builds with -fmerge-all-constants); a
`luaL_checkstring` on the miss path keeps a bad key's error naming
`__index` (checked in SITL); the messages give before/after CPU, heap
cost and the first-lookup allocation. Round two: Codex audit closed all
eight findings; the re-review found CI's Lua language-server check would
fail on `rc:get_channel()` maybe-nil, fixed with `assert`. A cache that
stores unknown names fails the new test once and keeps the autotest red.
Final heads 4cac649b36 (test), 2a61e3d551 (cache); `index_cache.patch`
here is the format-patch of both. Opened as #35311 (see
../35311/README.md).

## 2026-11-20: DShot150 and DShot300

Andy asked for regular DShot and DShot300 the way Betaflight does it.
Betaflight `beba09ad5` ("PICO: dshot enable 150 300", 2026-08-28) runs
both PIO programs at every rate by the clock divider (bit period / 40 or
/ 125 cycles), fixes the bidirectional end-of-cycle delay (`jmp !y` with
y=4 never looped: 0.4 us at DShot600; `jmp y--` gives 2/4/8 us), and
lowers its PID rate at slow rates. Betaflight offers no DShot1200.

Ported: `RCOutput_pico::init(bidir, bitrate)`, clock = bitrate x 40 or
125, eRPM samples-per-bit from that clock, built at init before `_bidir`
is set (the lazy init in read_telemetry removed); RCOutput.cpp accepts
150/300/600, keeps a config error for 1200 and adds one for DShot
outputs on different rates (one program and rate per PIO block). ArduPilot
needs no PID-rate change: `can_send_dshot_pulse()` paces sends at
`dshot_pulse_time_us + 50`.

Audit of the ArduPilot-only bdshot600 fixes at 300 and 150 (Andy asked
first): low-half frame, checksum from is_bidir_dshot_enabled(), pads,
write_frame() handover at pull/past complete with RX flush, stall restart,
frame_held(), MISSING vs NONE, decode table - none rate dependent, given
that pacing outlasts a send-and-listen cycle (~2.24 frame times + 30 us
turnaround): 90/133 us at 600, 150/187 at 300, 269/293 at 150.

Bench (RPI_UAVFC, AM32, no motors), CLKDIV and eRPM counters read over
SWD (rcoutDriver + 0x140 errors, + 0x180 clean; offsets from the
stack-analysis worktree's DWARF): bidirectional 600 600.6 kbit/s and 300
300.1 kbit/s, 0 errors; bidirectional 150 at 150.0 kbit/s got no replies
(SMs parked at wait 1/wait 0) - ESC firmware answers bidirectional only at
300/600, as ArduPilot's DShot docs say; plain 300 and 150 at their rates,
FDEBUG TXSTALL on all four (frames taken), ESC acceptance unobservable
without motors. After the delay fix the time at PC 28 doubled from 600
to 300 (0.20% -> 0.40%), and the ELF carries 0x1d9c. A 31% error reading
straight after boot (plain -> bidirectional switch) was gone in steady
state; not checked on an older build.

Andy asked for the commits split by STM32 effect. The RP2350 block in
RCOutput.cpp was rewritten to its original line count (12/12), as
WITH_SEMAPHORE line numbers otherwise move STM32 objects. Normal (not
consistent) MatekH743 builds, stripped `objdump -d`, differ from their
parent only in the version string and hash for all five commits above
`f5ea4699d9` (stack trims and DShot). Commits `64733b3435` (delay fix),
`f025ce1432` (rates), `5c8d9a94f7` (README) moved with the stack trims
(`4b5e27c782`, `423a85aed5`) ahead of the six STM32-changing commits
(rebase grant, revoked after; backup `backup/pre-dshot-reorder-20261120`).
Per-commit consistent builds: MatekH743 `29c14509aeab` through the five,
then `35c6fd2c91fd`, `93fdb36ecc37`, `55e9e86f8f24`, `953d0b73947e`,
`f1db94851b64` x2; RPI_UAVFC no warnings at all twelve. Force-pushed
over `b166a6c230` with the lease pinned (+11/-8): head `5e97be2505`, 86
commits. Not flown; not reviewed by `/pr-review` at this head. The PR
description's "DShot rates other than 600 | No" became a "DShot150 and
DShot300 | Yes" row and a "DShot1200 | No" row, read back unchanged
otherwise.
The flash-cost section's shared-code paragraph gained the AP_Logger_File
log-buffer cap (acts only under HAL_LOGGING_FILE_BUFSIZE_SCRIPTING, set
only by PICO2.py); read back, nothing else changed.

## 2026-11-19: stack sizes from PR #34623's static analyser

Andy asked to try ArduPilot/ardupilot#34623 (tridge's `--stack-analysis`,
`Tools/scripts/stack_analysis.py`) on the RP2350 build to see whether the
stacks can be trimmed. The PR merged cleanly onto `f5ea4699d9` in a
scratch worktree (both on master `321896137f`); RPI_UAVFC copter built
with `--stack-analysis` (GCC 10.2.1), all 1058 sources with .ci/.su.
Two local changes to the analyser, posted on #34623 (comment
7015394618): entry patterns for rate, Scripting, OSD, OSD_c1, led,
SmartAudio and c1_main, and following linker veneers (`__X_veneer` stubs
end in `bx ip`; treating them as calls to X took elf-indirect sites from
709 to 65, estimates up 16-84 B). The fatal config-error loop was cut
(`--cut AP_BoardConfig::throw_error...`), as it dominated the rate path.
Runtime use from the board's threads.txt.

With veneers followed (usable = total - 320 B context):

| Thread | usable | bench | static | margin |
|---|---|---|---|---|
| ArduCopter | 6848 | 2064 | 6072 | 776 (469 unresolved) |
| rate | 5024 | 760 | 1576 | 3448 |
| c1_main | 704 | 104 | 164 | 540 |
| OSD_c1 | 928 | 144 | 408 | 520 |
| UART_RX | 672 | 160 | 248 | 424 |
| FTP | 2464 | 1688 | 2180 | 284 |
| log_io | 1504 | 400 | 1408 | 96 |
| monitor / storage | 944 | 224 / 736 | 964 / 956 | -20 / -12 |
| OTG1, UART1 | 224 | 256 | 432 | -208 |
| led | 160 | 144 | 312 | -152 |
| SmartAudio | 672 | 672 | 1012 | -340 |
| OSD | 1184 | 664 | 1616 | -432 |
| rcin | 1008 | 368 | 1460 | -452 |

timer, io and the bus threads miss their registered callbacks, so their
margins are not evidence. The rate path is Turtle arming from
motors_output into pre-arm send_text; OSD and SmartAudio go over only
through GCS::send_textv() servicing statustext inline before
vehicle_initialised() (SmartAudio announces at its first reply, possibly
during boot); bench SmartAudio has 320 B free of 992.

Trimmed (Andy's choice): rate 5120 -> 3072 (three hwdefs), core1 PSP
0x400 -> 0x280 (common_rp2350_smp.ld), OSD_c1 1024 -> 768
(AP_OSD_pico.cpp). All three boards build with no warnings; RPI_UAVFC
after 60 s armed: rate 736/3296, c1_main 104/640, OSD_c1 144/992, peaks
as before. Commits `48c7f0f0a5` (hwdef) and `b166a6c230` (AP_OSD),
STM32-neutral (AP_OSD_pico compiles to an empty object on MatekH743), on
top; pushed as a fast-forward with Andy's grant. The over-budget threads
are not acted on; SmartAudio first if they are. Scratch: patched analyser
and full result in the session scratchpad (`stack_analysis_rp2350.patch`).

## 2026-11-19: scripting on RP2350, measured and resized

Andy asked to assess scripting's impact, starting with a snake script on
the four-LED NeoPixel; none exists in any tree here, so LED_roll.lua
(examples) at 4 LEDs and NeoPixel. Bench RPI_UAVFC, firmware `0bfe6d9e02`
flashed so the ELF matched; OSD_TYPE 0 throughout (the PIO OSD owns PIO1,
which the NeoPixel needs), SERVO5_FUNCTION 94 in every condition. Core
load from 60k (core0) and 20k (core1) PCSR samples over SWD without
halting, attributed by object file from the link map; free memory from
MEMINFO.freemem32. Bench noise is about +-1.5 points of core0 (the EKF
forced-reset loop, no GPS/compass).

| Scripting | State | core0 busy | script share | core1 | sched load | free |
|---|---|---|---|---|---|---|
| off | disarmed | 35.3% / 36.3% | - | 45.4% | 24.1% | 160 KB |
| LED_roll | disarmed | 41.2% | 3.9% | 44.7% | 24.8% | 41 KB |
| on, stopped | disarmed | 36.2% | - | 43.5% | 24.1% | 141 KB |
| off | armed | 50.8% | - | 49.4% | 26.8% | 154 KB |
| LED_roll | armed | 53.1% | 3.9% | 46.1% | 26.8% | 36 KB |
| on, stopped | armed | 50.5% | - | 50.1% | 26.5% | 141 KB |

The script share is 3.3% Lua VM (luaV_execute and the rest, all in XIP
flash) plus bindings, AP_SerialLED and the script heap. XIP counters
(CTR_HIT/CTR_ACC cleared over SWD, 12 x 2 s windows, same boot, armed,
stop/run/stop/run): hit 84.2% -> 87.6%, accesses 6.1 -> 8.9 M/s, misses
0.97 -> 1.10 M/s (+13%); repeated identically. Per run 1.07 ms median
wall time (p90 2.6 ms), 12.9 KB Lua memory, 316 B allocated a run.
Scripting thread priority 2, so it only takes core0's idle time.

Stack: LED_roll peaked at 3.2-3.9 KB of the 17.6 KB scripting stack. A
probe driving each C-recursion path to LUAI_MAXCCALLS (300 deep) crashed
the board: CFSR STKOF, PSP at PSPLIM of the `Scripting` thread (named
from ch0.rlist.current). Per-level cost, one case per boot at depths 10
and 30: parser 75-225 B, __index 130 B, pcall ~400 B, gsub callback
~850 B (its luaL_Buffer; overflowed 17 KB at depth 30). So 17 KB
overflows at ~34 pcall / ~16 gsub levels, 10 KB at ~15 / ~7. Lua's 200
limit protects neither; STM32 boards have the same 17 KB and no PSPLIM,
so upstream likely corrupts silently - a Lua stack-space check (script
error instead of a reboot) is a separate upstream PR, offered, not
started. tostring/coroutine/sort cases not measured (the gsub crash
ended the sweep).

Andy's choice: 50 KB heap, 10 KB stack, 64 KB log buffer while scripting
is enabled and LOG_FILE_BUFSIZE is unset. Commits, pushed as a
fast-forward with Andy's grant: `37c149557a` AP_Logger hook
(HAL_LOGGING_FILE_BUFSIZE_SCRIPTING; MatekH743 --consistent-builds
`f1db94851b64` unchanged), `16f9cc7173` PICO2.py defines, `d815876924`
DEVELOPMENT.md. Bench with the new build: SCR_HEAP_SIZE reads 51200,
stack 10464 with 3.0 KB used, scripting costs 47,192 B disarmed (63,560
expected without the cap, 47,176 with it), 110 KB free armed with
LED_roll. The user-set LOG_FILE_BUFSIZE path was not run on the board,
as a stored value cannot be unset over MAVLink. Not reviewed by
`/pr-review` at this head. All bench parameters restored; LED_roll.lua
left on the SD card (scripting off).

2026-11-20: the PR description's feature table gained a "Lua scripting
| Yes" row after Parameter storage: the 50 KB heap, 10 KB stack and
64 KB log buffer defaults, LED_roll's ~4% of core0 and 110 KB free
armed, and the pcall/gsub recursion depths that overflow the stack.
Read back from GitHub; nothing else in it changed.

Moved at Andy's request (rebase grant, revoked after) to follow
`ebb61de3af` (hwdef: enable ESC passthrough), ahead of the six
STM32-changing commits: `5f6aa98314` AP_Logger, `644a43ec2d` hwdef,
`81d4e1b65d` DEVELOPMENT.md, then `d72823312c`..`f5ea4699d9`. Tree
identical, `range-diff` all `=`. Per-commit builds in a scratch
worktree: MatekH743 --consistent-builds `29c14509aeab` from `ebb61de3af`
through `81d4e1b65d`, then `35c6fd2c91fd`, `93fdb36ecc37`,
`55e9e86f8f24`, `953d0b73947e`, `f1db94851b64`, `f1db94851b64` as
before; RPI_UAVFC builds with no warnings at all ten. Force-pushed
with the lease pinned to `d815876924`; backup branch
`backup/pre-scripting-reorder-20261119`.

## 2026-11-19: the registry repair folded in

At Andy's request ("do the fold"). The repair commit `822ddda06f` is gone;
each change it made is in the commit that introduced the line it fixes,
made by rewriting every commit's tree from its own (git plumbing, no
rebase), so the final tree is byte-identical to `18cd947273`:

- the EKF3 getters, `update_throttle_gain_boost` and Scratch Y's
  `AC_PID::get_ff` in the registry's first commit (was `094c0ef17c`);
- the `lib_a-memcmp.o` pick, and "newlib's memcmp" in the message, in the
  core0 hot-path commit;
- the Picolibc archive-pick note in DEVELOPMENT.md where the archive-pick
  bullet was written (was `9051b2f0c6`);
- "replaces the newlib versions" in the registry with the commit that
  rewrote the matching DEVELOPMENT.md paragraph for Picolibc (was `cbbbaf13ed`).

The sweep then found a second break the tip never showed: every commit
before the core1 hot-path commit overflowed Scratch Y by 56 B on RPI_UAVFC
and Laurel (Pico2 fitted). The Scratch Y registry is unchanged from its
first commit to the tip; the overflow is veneers. Scratch Y is out of a
branch's reach of flash, so each flash callee costs a 16 B veneer in the
bank: nine before the core1 commit, five after it, as that commit moves
the callees into SRAM. `rp2350_ramfunc2_update.py --build`, run at the last
failing commit, moved `HarmonicNotchFilter<Vector3<float>>::apply` (94 B)
to main SRAM. It is folded in from the registry's first commit through the
core1 commit, and a new commit after that one returns it ("return
HarmonicNotchFilter::apply to RP2350 Scratch Y"), so the core1 commit's
patch and every tree from the new commit on are unchanged.

Per-commit RP2350 copter builds in a scratch worktree, no warnings: Pico2
from the commit that adds it, Laurel from its own, RPI_UAVFC at every
commit from `hwdef: add RPI_UAVFC`, all three at the commit before the
core1 one. Scratch Y on RPI_UAVFC 4056 B with nine veneers before the core1
commit, 3992 B with five at it, 4088 of 4096 at the return. Later trees are
those the earlier sweeps built. STM32 output cannot change: only
`chibios.py`'s RP2350 path reads the registries, and the fold touches only
them and DEVELOPMENT.md. `range-diff` against `18cd947273`: the registry's
first commit, the core0 hot-path commit, the DEVELOPMENT.md commit and the
repair-script docs commit change as above, the core1 commit only in
context lines, the new commit added, the repair dropped, 62 identical.

Pushed with Andy's `reset,push` grant (`--force-with-lease` pinned to
`18cd947273`), revoked after: PR head `0bfe6d9e02`, 78 commits, mergeable.
Not reviewed by `/pr-review` at this head.

The worktree setup used on 11-19 for the passthrough sweep had written
the main checkout's submodule URLs (shared `.git/config`) to its own
`modules/` paths, which would have stopped `git submodule update` fetching
anything new there. Restored to the `.gitmodules` URLs; the fold sweep
passed local URLs only as `-c` overrides and left the config untouched.

## 2026-11-18: rebased onto master, and the build it breaks

Andy ran `git pull --rebase upstream master` at 14:59 UTC, moving the
series from `aea9a1b5d4` to `321896137f`, 154 upstream commits on. Local
tip `b957211b71`, 72 commits, not pushed. `git range-diff` against
`6a9e836fb0` shows all 72 commits unchanged, messages included, so the
rebase met no conflict and lost no `#` line this time. The ChibiOS pin
is unchanged at `39ed91cb626f`.

It does not build. RPI_UAVFC copter at `b957211b71` (built 2026-11-18 in
this checkout) stops at the strict RAMFUNC2 check, "5 registry entries
matched no symbol", all from master removing the functions:

| registry entry | removed upstream by |
|---|---|
| `NavEKF3::getEulerAngles`, `NavEKF3_core::getEulerAngles` | `dae5cea337` "AP_NavEKF3: remove getEulerAngles; derive logged eulers from quaternion" |
| `NavEKF3::getRotationBodyToNED`, `NavEKF3_core::getRotationBodyToNED` | `28b9bae3c8` "AP_NavEKF3: derive getQuaternionBodyToNED directly from the quaternion" |
| `AC_AttitudeControl_Multi::update_throttle_gain_boost` | `b02ee1b10f` "AC_AttitudeControl: apply throttle-gain boost once per loop" (Andy's) |

All five lines blame to `094c0ef17c` "AP_HAL_ChibiOS: add the shared
RP2350 support files". Laurel copter runs the same strict check and
should fail the same way; not built. Whatever replaces those functions
on the hot path is not yet placed, so the core0 profile wants a look
before the entries are simply deleted.

Also arriving with the rebase, read from the log and not yet exercised
on the board:

- Picolibc for libc, with the toolchain's newlib libm kept (`8747cddda9`,
  `cd99148514`, `c3bb9d8b1b`, 2026-11-17). The registry's libm picks
  (`lib_a-ef_atan2.o` and the rest) should be unaffected. The libc pick
  `(archive)|lib_a-memcmp.o` names a newlib libc member that may no
  longer be linked, which a linker-script pick would skip in silence.
  The build failed before the link, so this is open.
  `rp2350_memfunctions.S`'s `memcpy`/`memset` replacements need the same
  check.
- `edd2107456` "AP_HAL_ChibiOS: charge bdshot receive failures to the
  sampled ESC", which meets the port's `bdshot_count_reply()` counting.
- `8fa1a51051` (heap-backed ring buffer construction guarded),
  `33d04a44f1` (AP_HAL includes), `db16079ac9` (INS instance-count
  macros moved).

### The registries repaired by script

At Andy's request the repair was written as a tool rather than done by
hand, so the next rebase is one command:
`Tools/scripts/rp2350_ramfunc2_update.py --board <board> --build`
(`1c61a954e5`). It needs only git, waf and the cross
binutils. For an entry that matches nothing it finds the commit that
removed the function (`git log -S` on the entry's source file, the
registries excluded, since they name it too), and places what that
commit added in the same class or file plus the callers that took over
its code, up to the bytes the old entry held. A dead toolchain archive
pick goes to the build's own object. On a scratch-bank overflow it moves
the smallest entry that covers it to main SRAM and links again. Once the
build links it checks that every registered function, and every
`.ramtext` function, is in SRAM. Each change is marked `ramfunc2-update:`
in the registry for the profiling pass still owed.

What it did at `b957211b71`:

| out | B | in | B |
|---|---|---|---|
| `AC_AttitudeControl_Multi::update_throttle_gain_boost` | 140 | `get_throttle_pd_boost`, `rate_controller_target_reset` (new in `b02ee1b10f`) | 52 + 52 |
| `NavEKF3::getRotationBodyToNED`, `NavEKF3_core::getRotationBodyToNED` | 20 + 56 | `NavEKF3::getQuaternionBodyToNED` (its caller, which took the code) | 62 |
| `NavEKF3::getEulerAngles`, `NavEKF3_core::getEulerAngles` | 20 + 44 | nothing: the one caller left, `Log_Write_XKF1`, is 424 B | 0 |
| `(archive)|lib_a-memcmp.o` (toolchain newlib, no longer linked) | 32 | Picolibc's `memcmp` | 32 |
| `AC_PID::get_ff`, out of Scratch Y | 14 | the same, into RAMFUNC2 | 14 |

The last row is the second failure the rebase hid behind the first: once
the names matched, Scratch Y overflowed by 8 B. The script added nothing
there; upstream growth in functions already in the bank did, about 16 B
in all, since the bank was at 4088 of 4096 B on 2026-10-23 with
`get_ff` in it and is at 4088 without it now. Which function grew is not
measured. Scratch X is at 3832 of 4096 B. The section sizes alone
account for only 4020 B of Scratch Y; the rest is alignment and the
long-branch veneers the linker adds, which is why the script takes the
overflow from the linker rather than estimating it.

The Picolibc question from above is settled at this head, from the ELF:
`memcpy` and `memset` are the port's `.ramtext` copies at `0x20000f40`
and `0x20000fdc`, although Picolibc defines both too; only link order
picks the port's, and the script's check would report the other.
`memcmp` is at `0x20015f08`, in SRAM. The `edd2107456` bidirectional
DShot change compiled in without moving anything out of SRAM.

Checked: RPI_UAVFC, Laurel and Pico2 copter build and pass the
placement check. The check was shown to fail on a function known to be
in flash (`NavEKF3_core::FuseVelPosNED`), and a second run on the
repaired tree changes nothing. Its first version flagged `Vector84` on
Laurel and Pico2, where the PIO OSD is not built and the name is
ChibiOS's zero-size weak default label in `vectors.S`; weak labels with
no size are now skipped. Not done: any profile of the new placements,
and no board has run this build. The same change adds a pointer to the
script in the "matched no symbol" and scratch-bank overflow messages,
and documents it in `rp2350/DEVELOPMENT.md`.

Committed 2026-11-18 on `b957211b71`, registry repair first so that
every new commit builds (the rebased head alone does not):

| commit | what |
|---|---|
| `086a624f07` | AP_HAL_ChibiOS: the registry changes above, and the Picolibc archive-pick note in DEVELOPMENT.md |
| `1c61a954e5` | Tools: `rp2350_ramfunc2_update.py` |
| `a0a545728b` | AP_HAL_ChibiOS: the script named in the failure messages, DEVELOPMENT.md on the script and on memcpy/memset under Picolibc |
| `9f1dcc9985` | AP_HAL_ChibiOS: the stale RPI_UAVFC image item out of DEVELOPMENT.md |

The first is a placement change nothing has profiled or flown, so it
stays a commit of its own on top rather than going into the flown
commits by blame. Prefixes checked against `allowed_subsystems.py`;
`check_branch_conventions.py` itself was not run, as the push hook
blocks it even with `amend` granted (its source also contains `git
rebase -i`, so it wants `rebase` too). Its rules were applied to the
four new commits by hand instead: no merges or fixups, subjects within
the limit, well-formed prefixes, no submodule or board ID change, no
RST markup, every file ending in a newline. The 72 rebased commits are
patch-identical to those CI checked at `6a9e836fb0`.

Pushed 2026-11-18 with `--force-with-lease` pinned to `6a9e836fb0`;
GitHub reports head `9f1dcc9985`, 76 commits, mergeable. The grant was
revoked after the push.

The RPI_UAVFC README image, still listed as open under 2026-10-01 and
in `rp2350/DEVELOPMENT.md`'s known issues, has been closed since
`1b8b7e68cf` (pushed 2026-10-25): its README references
`RPI_UAVFC_Top.jpg` and `RPI_UAVFC_Bottom.jpg`, which `be00cf53c3`
(2026-10-23) did not have. CI's `validate_board_list` passes at
`6a9e836fb0`. The DEVELOPMENT.md line is removed by `9f1dcc9985`; by
blame it belongs in `094c0ef17c`, and being documentation it may go
into that flown commit at the next squash.

## 2026-11-08 to 2026-11-11: AP-Review rounds 32 to 35, and master's UART line lock

Reconstructed on 2026-11-18 from the PR thread and `git range-diff`; the
round was not recorded here when it happened. Four heads:

| head | what changed | review |
|---|---|---|
| `1fcec947c5` (2026-11-07), 71 commits on `2f3644c90e` | the 200 MHz series flown in logs 8 and 9 | round 32, 2026-11-07 13:45 |
| `9dcfb68204` | documentation only: the RPI_UAVFC README and DEVELOPMENT.md flight notes from logs 8 and 9 | round 33, 2026-11-10 |
| `20c605405c` (2026-11-11) | rebased onto master `aea9a1b5d4`, 322 commits on | round 34, 2026-11-11 16:27 |
| `6a9e836fb0` (2026-11-11) | one new commit and two amended | round 35, 2026-11-11 19:51 |

Round 32 (report 32): REQUEST CHANGES. Besides the pin, now `39ed91cb626f`
(ChibiOS#113's head), a merge conflict with master's AnalogIn refactor
(`e15fae8738`, `4eb8b67684`) had skipped CI, so nothing at
`1fcec947c5` went through it. Minors: the committed bootloaders no
longer match the source, since the new `memcmp`/Vector40/Vector68
placements also apply to bootloader builds; a PIOUART numbering check;
the AI line.

Round 33 (report 33), at `9dcfb68204`: the conflict now also hit
`AP_HAL/board/chibios.h`, where master dropped `#define HAL_BOARD_NAME
"ChibiOS"`, and after a rebase PIORXDriver would not compile, as master's
`828560a87b` made `set_options()`, `set_stop_bits()` and
`configure_parity()` non-virtual wrappers over backend methods. Should
fix: `-DHAL_BOARD_NAME=\"$(HAL_BOARD_NAME)\"` in
`chibios_board_rp2350.mk` would pass an empty string, master no longer
setting the variable, giving an empty USB product string ("-BL" in the
bootloader). The fast-erase GET_CRC trade-off listed again, no change
asked.

The rebase to `20c605405c` changed commits 2, 6, 9, 12, 15 and 26
(`range-diff` between `1fcec947c5` and `6a9e836fb0`):

- 2 and 26: `HAL_BOARD_NAME` left to master, in `chibios.h` and the
  RP2350 board makefile.
- 15: the RP2350 temperature pin under master's `#ifdef HAL_ANALOG_PINS`;
  `Util.cpp` takes master's rename to `HAL_SHORT_BOARD_NAME`.
- 9 and 12: PIORXDriver and the SIO path override `_set_options()`,
  `_set_stop_bits()` and `_configure_parity()`. PIORXDriver's own
  `_stop_bits` is gone in favour of the base class's, which master's
  `a1a575d7f0`/`e9aee4cd4a` added. `sio_lcr_h()` and
  `sio_apply_framing()` take the parity and stop bits as arguments,
  because the base class records the parity only once the backend has
  applied it.

Round 34 (report 34), at `20c605405c`: the three rebase items confirmed
fixed. Should fix: the new SIO branches change parity and stop bits
without `_line_config_sem`, which master (`0aa8ee5a88`, 2026-11-03)
declares and takes only under `HAL_USE_SERIAL`, so the race master fixed
for STM32 UARTs stays open on RP2350. Minor: the rebase dropped the line
of commit 15's message that began `#ifndef default equal to master's
value`: a conflicted rebase drops message lines that start with `#`.
CI failures at `20c605405c` were runner DNS failures in apt (Andy,
issuecomment-6803970372).

`6a9e836fb0`:

- New, 72: "AP_HAL_ChibiOS: lock RP2350 UART line setting changes".
  `_line_config_sem` is declared for `HAL_USE_SIO` too and taken in the
  SIO branches of `_configure_parity()`, `_set_stop_bits()` and
  `_set_options()`. `sio_apply_framing()` takes `_write_mutex` inside it
  and nothing holds `_write_mutex` while changing line settings, so the
  two are always taken in the same order (derived from the source). The
  message claims the only STM32 change is the line number two later
  `WITH_SEMAPHORE()` calls record; the 2026-11-11 session noted MatekH743
  moving 2060 to 2062 and 2159 to 2163. A bench method was worked out the
  same day - a Lua script on a `SERIALn_PROTOCOL` 28 port stepping
  `configure_parity()`/`set_stop_bits()` while OpenOCD samples UART0
  `LCR_H` (`0x4007002c`) without halting - but no result is recorded
  here, and the race itself was not exercised.
- Amended, 6 (`f0797eaf8f`): `chibios_hwdef.py` errors when
  `SERIAL_ORDER` lists PIOUARTs out of order or with a gap, the rule
  DEVELOPMENT.md documented.
- Amended, 15 (`6599145a54`): the message reworded so no line starts
  with `#`.
- Replaced at `9dcfb68204`, 66: "note the Pico 2 has run the 200 MHz
  flash settings" became "record the 200 MHz flights and the Pico 2's
  bench run"; 59's message and 63's README now say the 200 MHz settings
  flew on 2026-11-07. Documentation only.

Status comment issuecomment-6803970372 (2026-11-11 18:27) answered round
34. Round 35 (report 35, issuecomment-6805756935): REQUEST CHANGES on
the pin alone, the lock, the numbering check and the message confirmed.
`check-merge-commits` now fails at "Check branch conventions" because 1
(`e8bdbce44d`) and 56 (`9b8f9f69aa`), the two ChibiOS bumps, reference
commits not on ChibiOS master. Minors, unanswered:

- `rp2350_ramfunc2_registry.txt:363`'s `dshot_send_command` entry has no
  DShot marker, so an RPI_UAVFC or Laurel copter build with
  `HAL_DSHOT_ENABLED 0` fails the strict check. `[needs
  HAL_DSHOT_ENABLED]`, as `restart_sm` carries, would answer it. Still
  unmarked at `b957211b71`.
- The committed bootloaders, to regenerate after the repin.
- The AI line, declined.

CI at `6a9e836fb0` (`/pr-checks`, 2026-11-18): 118 checks, 106 pass, 12
fail.

| failed | cause |
|---|---|
| `check-merge-commits` | the ChibiOS pin, as round 35 says |
| 9 autotest and size jobs (plane 1a, 1b, quadplane 1c, rover, copter 1b, 1c, MatekH743-bdshot, disco) | `Failed to CreateArtifact`, the artifact upload; no test failure found in their logs |
| copter tests2b | GPSGlitchLoiter: "Did not get good COMMAND_ACK within 10.000000s". Not compared with master |
| copter tests2c | no failure marker in the log; not opened |
| copter tests2d | job log not downloadable |

Review state on GitHub: CHANGES_REQUESTED, from the earlier human reviews.
ChibiOS#113 is open at `39ed91cb62`, last updated 2026-11-07, no review.

## 2026-11-07, later: an Auto mission

Log 9, the same quad and build an hour after log 8, on a fresh pack, with
`EK3_SRC1_POSZ` changed from baro to GPS. Takeoff to 25 m, ten spline
waypoints, RTL.

- The port was as clean as in log 8: worst rate-loop gap 0.93 ms in
  flight, load 34-41%, nothing dropped. Log 8's logging drop did not
  recur. The 13 mission items stored and read back.
- Every waypoint was reached, within 0.8-4.8 m. The quad flew at its 30
  deg lean limit for 94% of the mission, as `WP_ACC` 60, `WP_ACC_CNR` 80
  and `WP_JERK` 120 ask for more than 30 deg gives, and fell up to 17 m
  behind its target on the tight turns.
- RTL's landing never slowed to `LAND_SPD_MS` 0.5: the target was still
  5.9 m/s at 9 m and 2 m/s near the ground when the pilot took over. Two
  causes, both configuration. `WP_ACC_Z` 10 with `WP_SPD_DN` 10 starts the
  slowdown too late: SITL lands at 0.8 m/s with them, 0.5 m/s with either
  alone, and 0.5 m/s with `LAND_SPD_HIGH_MS` 2. And GPS height wandered 3 m
  on the ground against the baro's 0.3 m, so home was set low and the quad
  reached the ground believing it was about 1.5 m up.
- The compass's static offset moved about 100 mG between logs 8 and 9,
  measured both from the EKF's learned body field and from the fit; it
  coincides with the pack change. EKF yaw within 4 deg of true throughout.
- The cold board's current input read about half the eRPM model's
  current, and `CurrTot` went negative on the ground.

Details in [bench-2026-11-07.md](bench-2026-11-07.md), "Log 9".

## 2026-11-07: first flights at 200 MHz

PR head `1fcec947c5` (71 commits), whose tree is identical to
`f0f78b48ec`, the head the alpha2 branch was rebuilt on; only the history
was rewritten. Log 8 from the quad on `4d4220d9`, the alpha2 branch, with
log 5's parameters but for the gyro calibration, so against log 5 the
build is the only change. First flights of the 200 MHz clocks, 100 MHz
continuous-read flash, the new SRAM placement, external AHRS out, the
microSD at 25 MHz and the fractional PIO dividers.

- The port was clean in flight: rate loop 1600 Hz, worst gap 0.91 ms, 2.23
  ms at the arming instant (log 5: 6.51), no long loops anywhere, nothing
  dropped on any UART, DShot telemetry from all four ESCs with no errors.
- Scheduler load (`PM.Load`) 29-41% in flight and 31-33% disarmed, against
  54-69% and 57-58% in log 5. The bench measured an 11-point fall; the
  quad's is about 25. Not reconciled. Free heap is about 6 KB less.
- 281 log messages, 0.3 s of every stream, dropped 1.4 s after the last
  disarm, on the ground. Both loops ran on, so the writer stalled, about
  0.8 s from the buffer figures. A flash-write park would have stalled the
  loops; the card's latency and the new 25 MHz SPI clock are left. Logs
  2-7 dropped nothing.
- The board sat 15 minutes on the ground waiting for 7 satellites (first
  fix 147 s, origin 787 s, as logs 2 and 6). It warmed to 25 degC, the
  current pin read up to 7 A with the motors stopped, and `COMPASS_MOT`
  turned that into 110-176 mG: the rebuilt mag-field arming check matches
  the logged 151-162 > 150 and reads 76-78 without it, and the heading on
  the ground moved -8.5 deg cold and +20 deg warm.
- The compass's coupling to battery current is 20.5 mG/A, back within 10%
  of log 5's 22.7 from 13.8-15.4 on 2026-10-31, so what changed then did
  not stay changed; which pack flew is the likelier variable. EKF yaw
  within 6 deg of true throughout, no failsafe.
- Throttle (`CTUN.ThO`, what `COMPASS_MOTCT` 1 multiplies) explains the
  interference within a few mG of current in logs 5 and 8, and is zero on
  the ground. Not flown.
- RTL flew for the first time: home from 34 m at 20 m, a 3.4 m overshoot,
  held within 1 m, descent started; the pilot took over at about 11 m.

Details in [bench-2026-11-07.md](bench-2026-11-07.md).

### Superseded 2026-11-07 by the quad's `OSD_TYPE`

"First flights of ... the fractional PIO dividers" holds for bidirectional
DShot only. The quad runs `OSD_TYPE` 5 (MSP DisplayPort), and the PIO OSD
is type 6, so it never ran; it needs a board with analog video. Left in
place for DShot, which did fly on its divider.

## 2026-10-31: two more release-testing logs, the compass coupling moved

PR head unchanged at `e45dae01b1`. Logs 6 and 7 from the quad on
`1f8685e9`, with nothing changed since log 5 of 2026-10-30. No port runs
half duplex, so commit 48's echo window is still unflown.

- The port was clean: rate loop 1600 Hz with a worst in-flight gap of
  0.95-1.05 ms, main loop 200 Hz, nothing dropped. The 4.3-6.5 ms stall
  at the instant of arming is in 2026-10-30's logs too and was left out of
  that day's armed figure; superseded there.
- No EKF failsafe or emergency yaw reset, and the EKF yaw within 6 deg of
  true in every window, from the accelerometer against GPS acceleration.
- The compass is no longer compensated. In steady fast Acro it reads 25-43
  deg off the EKF's heading at 55k summed RPM and above, against 7 deg in
  log 5. Fitting each flight, the compass's coupling to battery current
  was 20-23 mG/A on 2026-10-30 (logs 3, 4, 5) and 13.8-15.4 on 2026-10-31,
  turned about 20 deg; the current reading's gain against the eRPM model
  moved 2-14%.
  Something between the battery current and the compass changed between
  the two days. Not known yet.
- The compass sees the current zero's temperature drift in flight, at
  60-75% of the pin's disarmed rate: 50-75 mG over today's 14-23 degC.
- In log 7's Loiter the GSF was 16-35 deg wrong while reporting 0.4-1.4
  deg of spread, the overconfidence behind flight 2's bad reset; upstream.
  `ft_loiter_yaw.py` read the same flight as a 30 deg EKF yaw error, most
  likely the drag term in a turn; the tool now carries the caveat.

Details in [bench-2026-10-31.md](bench-2026-10-31.md).

## 2026-10-30: release-testing flights, the compass under motor current

PR head unchanged at `e45dae01b1`. Four logs from the quad (board
`99F517D8`) on `1f8685e9`, the release branch carrying it. No port runs
half duplex, so commit 48's echo window is still unflown.

- The port was clean on every flight: rate loop 1600 Hz with a worst
  armed gap of 0.94-1.07 ms, main loop 200 Hz with no long loops, IMU to
  the EKF at 5.00 ms, no log or UART drops, all four ESCs reporting RPM.
  Disarmed, the rate thread stalls 1.2-9.8 ms at each parameter save, as
  the flash storage design expects.
- Flight 2's three Acro EKF failsafes came from the compass. Motor current
  left 120-480 mG of interference against a 150 mG horizontal field: the
  current input read 5.8 times low and the old `COMPASS_MOT` was 4.2 times
  smaller than the refit's, so the compensation was about 1/24 of what the
  refit applies per amp, and pointed 53 deg away from it. Copter's
  pre-failsafe yaw reset then took the GSF's yaw mid-flip, just as the GSF
  lost track, and the compass was locked out for the rest of the flight.
  That last part is upstream EKF3 and Copter behaviour, not the port.
- The current input on this quad tracks load at r 0.98-0.99 against the
  eRPM model and the pack's sag, at 3.2-3.7 mV/A in every flight, on a
  zero that drifts 1.9-2.9 mV/degC. The battery voltage input does not
  drift, which points at the leaky clamp R4 replaces.
- With `BATT_AMP_PERVLT` 295, `BATT_AMP_OFFSET` 0.035 and the compass
  refitted, log 5's Acro had no failsafe or yaw reset, and the compass
  stayed within 7-9 deg of the EKF's heading at every throttle (48-68
  before). It holds near the 11-19 degC board temperature it was
  calibrated at; each degC away is 15-20 mG of compass error.

Details in [bench-2026-10-30.md](bench-2026-10-30.md).

### Superseded 2026-10-30 by the bench note's own caveat

"The battery voltage input does not drift, which points at the leaky
clamp R4 replaces" says more than the measurements do. On the quad the
battery pin moved under 0.3 mV/degC (log 5, disarmed), but on 2026-10-29's
bench it drifted 1.70 mV/degC, so the current input's drift is not yet
shown to be the clamp's; R4 needs measuring before it is called fixed. The
line is left in place because the quad's own figure is as it says.

### Superseded 2026-10-31 by logs 6 and 7

"A worst armed gap of 0.94-1.07 ms" counts the flights. The window holding
the arming instant reads 4.29 ms in log 3 and 6.51 ms in log 5, on the
ground at spin-arm: the parameter-save stall, at arming.

"It holds near the 11-19 degC board temperature it was calibrated at; each
degC away is 15-20 mG of compass error": the 15-20 mG was derived, and
measured on the compass in flight it is 13.1 mG/degC in log 5 and 6.6-8.8
in logs 6 and 7. The refit stopped holding the next day mainly because the
compass's coupling to battery current fell from 22.7 to 13.8-15.4 mG per
reported amp, not because of temperature. The bullet is left in place
because log 5 held as it says.

## 2026-10-29: the current input, first flights of `e45dae01b1`, a GPS false alarm

PR head unchanged at `e45dae01b1`. The release branch at `1f8685e9`,
carrying it, flew twice on Andy's quad (board `99F517D8`, a modified R3):
rate loop 1600 Hz, worst gap 0.97 ms, no log drops. No port runs half
duplex there, so commit 48's echo window is still unflown.

- Raspberry Pi: the boards in hand are R3s with the current input's
  pull-down changed to 10k and the leaky clamp still fitted; R4 is due.
- A TBS 8S 4-in-1 on the bench gives 5.03 mV/A at the pin (static 5 A
  load, Betaflight and ArduPilot agreeing), and the zero drifts 1.35
  mV/degC against the old boards' 28.4. For that ESC: `BATT_AMP_PERVLT`
  200, `BATT_AMP_OFFSET` about 0.0165.
- The quad's BLITZ E55 gives about 2-3 mV/A on a 47-67 mV zero drifting
  about 4 mV/degC, so its analog current is unusable. Hypothesis, not
  measured: a high source impedance divided by the 10k pull-down, which
  R4 keeps.
- GPS never fixed in either flight; not the firmware. An indoor A/B of
  the receiver's own RF report showed `9347a457` and `1f8685e9`
  identical, and `1f8685e9` fixed at once later. Two conclusions made on
  the way, board then firmware, are withdrawn in the note.
- Upstream: GCS serial passthrough on USB leaves MAVLink unable to read
  USB until a reboot (the port's owner becomes the timer thread),
  reported as ArduPilot/ardupilot#34935.
- The release branch's two load measurement commits (`1eebac56d2`,
  `c03191be64`) are not for this PR after all. They fix an upstream bug
  (every other `threads.txt` read freezes LOAD and PEAK, on STM32 too),
  which #33366's `ca78096f50` also fixes for one core, and they change
  STM32 output, so they could not go into commits 1-51. They stay on the
  release branch until #33366 merges.

Details in [bench-2026-10-29.md](bench-2026-10-29.md).

## 2026-10-28: Pico2 hardware, the PIO UART fixes moved up

Two commits went on top of `6cffb8ed11` earlier in the day and were pushed
as `9a9765e128`: `7873a96aa0` ends the half-duplex echo window in the
interrupt, and `9a9765e128` bounds the five receive FIFO loops at 16
entries. Their messages carry the bench evidence (SmartAudio v2 on
RPI_UAVFC SERIAL4, with AP_SmartAudio changed for the test to skip its
flush and read 150 ms after each request: 276 bytes sent and none received
in the 35 s after boot, against one request and its 11 byte reply); it was
not re-measured here. Neither has flown.

The bench session that wrote them recorded its measurements, the code
state behind each, the SmartAudio regression runs before and after, and
the review findings it accepted and rejected in
[bench-2026-10-28.md](bench-2026-10-28.md). The VTX is SmartAudio v2, as
Andy confirmed.

Pico2 hardware arrived (a Pico 2 on COM16, a Debugprobe on COM10). On the
old head the board printed the `Perf:` report every 10 s and failed two
pre-arm checks besides RC, with a third behind them:

- "Logging failed": with no microSD or dataflash, MAVLink is the only
  backend compiled in, so it was the default (`LOG_BACKEND_TYPE` read 2)
  and it reports failed until a GCS streams it.
- "3D Accel calibration needed": the two simulated IMUs had zero offsets.
- Behind that, "Accels inconsistent", which the arming code holds for 10 s
  after boot until the accels have agreed that long. It clears by itself.

Fixed in `hwdef: add Pico2`: `AP_RP2350_DEBUG_REPORT_ENABLED 1` removed (the
default is 0), `HAL_LOGGING_BACKENDS_DEFAULT 0`, and `defaults.parm` gives
INS_ACC and INS_ACC2 offsets of 0.001 and scales of 1.001, as SITL's
`copter.parm` and CubeOrange-SimOnHardWare do. On the board the pre-arm
then reports only "RC not found". `LOG_BACKEND_TYPE` 2 and a reboot bring
the MAVLink backend back ("Logging failed" again with no GCS streaming);
the board was left at 0. A first attempt compiled logging out
(`HAL_LOGGING_ENABLED 0`, 77.6 KB less flash); Andy preferred keeping
MAVLink logging available. Laurel's debug report is off too. In
DEVELOPMENT.md the storage section said only RPI_UAVFC sets
`AP_STORAGE_NO_WRITE_WHILE_ARMED`, which has been wrong since round 24 set
it on Laurel and Pico2; it now says all three do.

The Pico2 commit message described an earlier design that its own hwdef no
longer matched (an RP2350B on a sensor carrier at 250 MHz, SMP off, three
PIO UARTs, SPI and I2C sensors). It was rewritten for the bare-module
Simulation-on-Hardware target.

One unexplained boot: with the logging-compiled-out build, the boot after
two back-to-back uploads raised internal error 0x8000 (`main_loop_stk`,
semaphore line 0): the main loop went 500 ms without patting the watchdog.
That latches until a reboot and blocks arming. It did not recur in 9
further boots of that build, a plain reflash and an old-to-new cross-flash
among them, nor in 2 boots of the old firmware. Not attributed to the
change; worth chasing if it comes back.

Squash 8 (backup `pre-squash8/rp2350-v5-20261028` at `260486bb05`):

- The four fixups folded into 11 (DEVELOPMENT.md), 27 (Pico2, with the new
  message) and 28 (Laurel). Pico2 never flies and Laurel has no flight on
  the current architecture.
- 52 and 53 moved unchanged to 48 and 49, ahead of the four STM32-changing
  commits, rather than folded by blame. Their hunks blame to 9 (the
  driver), 34 (the PIO program), 44 and 11. Split that way, commits 9 to 33
  would carry driver code waiting for an `irq` the program does not raise
  until 34, and the fix is unflown while 9, 34 and 44 have flown.

`git range-diff`: 50 commits identical, 11, 27 and 28 changed, the four
fixups gone. The tree is identical to `260486bb05`.
`check_branch_conventions.py` passes. MatekH743 copter with
`--consistent-builds`, in a scratch worktree whose submodules were cloned
from the main checkout: `78d37bd9006d` at the base `2f3644c90e` and at the
new 49, `5532a473c873` at the tip, both as recorded before. RPI_UAVFC and
Pico2 build at 48 and 49, Pico2 at 27 and Laurel at 28 (and both at the tip
in the main checkout), with no warnings. Pushed as `d5cb7ecb59`, 53
commits, matching GitHub's count.

Process: `pre_bash_check.py` matches guarded git commands anywhere in a
command line, so a grep for the string, or a comment naming the command,
is blocked as well. Running `check_branch_conventions.py` needs `amend` in
the grant for that reason.

### AP-Review round 29 at `9a9765e128`, and squash 9

REQUEST CHANGES on the ChibiOS#113 pin, with one should-fix: GET_CRC in
a session that uploaded nothing returned the CRC of an all-erased image,
so `uploader.py --verify-firmware-is` rejected a board running the
matching firmware. Reproduced on the Pico2: `0xacf138cb`, which is
exactly the CRC of 4,128,768 bytes of 0xFF. The round also repeated the
minor Laurel bootloader beep item and the documented fast-erase
trade-off.

GET_CRC now returns the XIP readback it already computed when
`prog_crc_len` is 0. On the Pico2 verify-only still failed, stably, at
`0x9a0ad77f`. A dump of the whole app area through the bootloader's
READ_MULTI (142 s for 4 MB) matched that CRC exactly and the image byte
for byte; the only difference was a 256-byte page of 0xEF at the top of
flash, the RP2350-E10 UF2 workaround block (addressed to `0x10ffff00`,
wrapping on a 4 MB part). Neither `bin2uf2.py` nor `picotool uf2
convert` 2.2.0 as waf runs it emits that block, so it came from some
earlier UF2. The fast erase skipped its block because the first 4 KB
page read erased. The readback was exact, which weakens the source
comment's claim that XIP readback after programming is unreliable on
Laurel; that may have been stale data too (not checked on a Laurel).

The RPI_UAVFC (back on COM15, picoprobe on COM10, running `f88a2e79`,
a build from outside this checkout) had a different stale area: 8 KB at
app offsets `0x3cc000`-`0x3cdfff`, mid-block, with that block's first
and last pages erased. Its whole app area was dumped first as a restore
copy. So the erase now skips a block only when its first and last pages
read erased, and CHIP_FULL_ERASE, which the RP2350 bootloader refused,
erases every block (`uploader.py --force-erase`). Bench on RPI_UAVFC
with the new bootloader written over SWD:

| step | result |
|---|---|
| verify-only, `f88a2e79` | fail, `0xfb428d21` = CRC of the dump |
| `--force-erase` upload, then verify-only | pass (upload 50 s) |
| 0xEF page planted at the top, normal upload, verify-only | pass |
| `@SYS/flash.bin` over MAVLink FTP | bootloader as programmed, then the AP_FlashStorage header at `0x10010000` |
| `f88a2e79` restored from the dump, verify-only | pass; rate loop at 1611 Hz on core1 |

`@SYS/flash.bin` had read from `0x08000000`, STM32's flash base, which
is not flash on RP2350; `AP_FILESYSTEM_SYS_FLASH_BASE` now defaults to
that and PICO2.py sets `0x10000000`. pymavlink stops at 100,000 bytes,
the fixed size `@SYS` stat reports, on any board.

The Laurel beep: Laurel's hwdef.dat names the GPIO5 buzzer as the
RDTE-4.000-3030-NS1, which Raltron lists as an externally driven
magnetic transducer, so `hwdef-bl.dat`'s "self-oscillating" was wrong
and the beep thread could only click. `HAL_BOOTLOADER_BEEP_GPIO` and the
thread are gone; no other board used them.

Squash 9 (backup `pre-squash9/rp2350-v5-20261028` at `ea2cf47daa`):
the bootloader changes into 24 with its message rewritten, the
binaries into 30, Laurel into 28, DEVELOPMENT.md into 11, and two new
commits for `flash.bin` at 50 and 51, ahead of the four STM32-changing
commits now at 52-55. Tree identical to `ea2cf47daa`; `range-diff`
shows 11, 24 and 28 changed, 30 equal as text (binary), 50 and 51 new.
MatekH743 copter `78d37bd9006d` at 51 and `5532a473c873` at the tip;
MatekF405 bootloader `70b7f05b0e12` at 24 and at the tip; RPI_UAVFC and
Pico2 build at 51, Pico2 at 27, Laurel at 28, no warnings;
`check_branch_conventions.py` passes. Pushed as `e45dae01b1`, 55
commits. The Pico2 still has the interim bootloader (GET_CRC only) and
its 0xEF page.

## 2026-10-27: SBUS run, garbled log names gone, and the release branch

Reported by Andy on 2026-10-27, not measured here:

- Buzz has run SBUS with a receiver. Board, receiver and log are not
  recorded here.
- The garbled log file names (`0000012B.IN` for `00000012.BIN`) are no
  longer seen. The fix was not isolated. The candidates are ChibiOS
  `773973509` (RP SPI abort and receive-overrun detection, 2026-09-07),
  although the 2026-09-08 measurements recorded on `rp2350-v6`
  (`c36765aa97`) found neither path taken in normal running, and
  ArduPilot/ChibiOS#115 with #34477 (one SPI exchange per block). #32995
  on its own carries the first and not the second.

fossuav/ardupilot-rp2350 now publishes the port for users. Its default
branch, `ArduPilot-4.8-rp2350`, is master `2f3644c90e`, then #32995 at
`1b8b7e68cf`, then the follow-up PRs, with a top-level README and release
tooling in `Tools/RP2350/`. `1b8b7e68cf` differs from the current head
`bf14656274` only by round 25's blank line in bin2uf2.py. Its ChibiOS pin is
`7e50cd016f`, #113 plus #115, the head of andyp1per/ChibiOS
`rp2350-flight-test` and on no ArduPilot/ChibiOS branch.
Later on 2026-10-27 it was pushed to a new fork, fossuav/ChibiOS, as branch
`rp2350-releases` and tag `rp2350-20261027`, so the release clones whatever
happens to `rp2350-flight-test`; `Tools/RP2350/build_release.sh` now refuses
to stage a release whose pin is not one of those refs. This does nothing
for #32995's `check-merge-commits` failure, which wants #113 merged to
ArduPilot/ChibiOS master.

Three commits on that branch correct the port's docs and are to be folded
into #32995 at its next update. All three are documentation only, so they
may go into flown commits:

- `342690e663` RPI_UAVFC README: enter BOOTSEL by holding BOOT while
  plugging in USB; SBUS no longer marked untested. Folds into `f412580afd`
  "hwdef: add RPI_UAVFC".
- `00f9f2579d` Laurel README: the same BOOT button route. Folds into
  `3d798ccd6f` "hwdef: add Laurel".
- `323fb63aee` DEVELOPMENT.md: the BOOT button, and the log names as above.
  Folds into `813cc4dca1` "AP_HAL_ChibiOS: add the shared RP2350 support
  files".

The hashes are those at `1b8b7e68cf`; round 25's squash renumbered commits 7
to 51 on `bf14656274`.

### AP-Review round 26 at `bf14656274`

REQUEST CHANGES on the ChibiOS#113 pin alone (2026-10-27 00:03, report
26.html). It confirms round 25's ruff fix and a green pre-commit job, and
asks for no change:

- PIOUART half-duplex echo: still open, as before.
- The AI-assistance line: declined by Andy on 2026-10-26, listed again.
- The bootloader's fast erase (support.cpp:231) judges a 64 KB block by
  its first 4 KB page. The bot calls it the documented trade-off, notes a
  failed upload recovers on retry, and asks for nothing.
- quadplane-tests1c also fails on master at the PR's base, so it is not
  this PR's (the bot's finding, not checked here).

No reply posted. #34877 was taken out of the description's split-out PR
table the same day at Andy's request: it is just an example.

The three doc commits from fossuav/ardupilot-rp2350 were then folded in,
each into the commit blame gives for its lines: the RPI_UAVFC README
change into "hwdef: add RPI_UAVFC", the Laurel README change into "hwdef:
add Laurel", and the DEVELOPMENT.md change into "AP_HAL_ChibiOS: add the
shared RP2350 support files". No message needed editing. The net change
is exactly the three diffs; every later commit differs only in those
files, so STM32 output and the RP2350 builds are as measured on
2026-10-25. markdownlint clean. Pushed as `6cffb8ed11` (backup
`pre-squash7/rp2350-v5-20261027` at `bf14656274`). The release branch
still carries its own copies, which drop out when it next rebases onto
the PR.

## 2026-10-25: AP-Review round 21 at `be00cf53c3`

The bot's review of `be00cf53c3` (2026-10-23 21:12, report 21.html) is
REQUEST CHANGES on the ChibiOS#113 pin alone, with two should-fix and nine
minor items. No human comments since the two Laurel header replies of
2026-10-23 (discussion_r4363878843 and r4363879192).

Ten additive commits on `be00cf53c3`, pushed as `26ffacadeb`, with a
status comment for the bot (issuecomment-6398918677):

- `e6c8f1b17e`: the heap report reads padded `STACK= 416/1280` rows.
  Util.cpp pads with thread statistics on, so threads with under 1000
  bytes free dropped out.
- `4363f13f58`: `--apply` writes the timer, rcout, rcin, io and storage
  stack sizes as hwdef.dat defines. It used to rewrite Scheduler.h's
  shared #ifndef fallbacks for every ChibiOS board. Tested on scratch
  copies.
- `d4f1de215b`: MAIN_STACK is planned once, from the deeper of the two
  ISR rows (`__c1_main_stack_size__ = __main_stack_size__`).
- `d733d26892`: an `--hwdef` outside the checkout no longer raises
  ValueError.
- `2bbafa5c8c`: `rp2350_ramfunc2_sizes.py --update` keeps the markers;
  29/2/2/10 in, 29/2/2/10 out on RPI_UAVFC.
- `fb4fdd44c5`: ESC.Err counted one missed reply twice. The bot's fix in
  read_telemetry() overflowed Scratch Y by 8 bytes (4088/4096 used), so
  bdshot_count_reply(), in main SRAM, skips counting while write_frame()
  holds a frame back. Scratch Y unchanged. Not checked against a log.
- `de32d03d38`: found while testing the next one. The 2026-10-23
  HAL_UART_NODMA generator fix only saw `define HAL_UART_NODMA 1`; boards
  write it bare, which still failed with "too many initializers". It now
  tests whether the define is present. ZubaxGNSS's hwdef.h is identical.
- `8b30393db1`: `_device_initialised` is set after sioStart() in every
  build, so SBus output's framing change applies under HAL_UART_NODMA.
- `1d8fa05d9a`: the render_block() comment describes flush()'s copy.
- `26ffacadeb`: an SPI request SCR cannot reach takes the smallest even
  SSPCPSR that does, carried in bits 23:16 of the freq flag. 400 kHz runs
  at 399 kHz (SSPCPSR 4, SCR 140); every request from 440 kHz up keeps its
  divider. Not checked on hardware.

Builds: RPI_UAVFC (also with a bare HAL_UART_NODMA), Laurel and Pico2.
MatekH743 `5532a473c873` and CubeOrange `b1a4fb2cb76e` are identical at
`be00cf53c3` and at the tip with `--consistent-builds`.

Left open: the PIOUART half-duplex echo. The flag clears only from
available() or flush(); the PIO UART has no thread, and uart_tx raises
nothing at the end of the stop bit, so clearing it from the interrupt
needs an `irq` in the program (29 of 32 instructions used) and a
SmartAudio test.

PR description refreshed with the push: #34438 merged on 2026-09-28,
#34443 is no longer carried, and Laurel's watchdog is on through the
ChibiOS BRD_OPTIONS default rather than `@READONLY`.

Fourth squash, the same day, at Andy's request: each fix folded into the
commit that introduced the lines it changes, by blame, and pushed as
`485f751fe6` (backup `pre-squash4/rp2350-v5-20261025` at `26ffacadeb`;
follow-up comment issuecomment-6399250111). The five tool fixes went into
`c36860fa7e` (heap and RAMFUNC2 reports); frame_held() into `f28b021ebe`
(PIO drivers) and the count into `d97f16f57a` (RC in and out); the
generator into `d8e762586b`; the UART flag into `e419c7302c`; the SPI
prescaler into `f519aca5a9` with its DEVELOPMENT.md note in `41f5adabe0`.
The OSD comment blamed to the double-buffer commit but went into
`4cf04d0d1d`, which adds the copy it describes. Three messages changed:
the generator ("defines HAL_UART_NODMA"), SPI (the larger prescaler) and
the heap report (hwdef.dat defines).

Checks: the tree is identical to `26ffacadeb`. The generator's hwdef.h is
identical, old against new, for all 22 HAL_UART_NODMA configs (ZubaxGNSS
and the ten f103-periph boards, app and bootloader). MatekH743 and
CubeOrange with `--consistent-builds` hash to master's `78d37bd9006d` and
`220b8666965e` at commits 6 to 47, and commits 48 to 51 match the old
series hash for hash, ending at `5532a473c873` and `b1a4fb2cb76e`.
RPI_UAVFC builds at every commit from 29, Pico2 and Laurel where they are
added and at the tip.

Later the same day the SemaphoreRecursion example left the PR for
[#34877](../34877/), with a SITL fix it found. Commit 2 lost the two
example files and its paragraph about them; every later commit differs
from before only by those files, and examples are in no firmware build.
Pushed as `90e876b1b1` (backup `pre-dropex/rp2350-v5-20261025` at
`485f751fe6`), and the description's split-out table gained #34877.
`rp2350-flight-test` still carries the example until its next rebase.

### AP-Review round 24 at `90e876b1b1`

REQUEST CHANGES on the ChibiOS#113 pin alone; round 21's fixes all
confirmed. Eleven additive commits on `90e876b1b1`, local tip
`e8e24d00e2`, unpushed:

- `66e572d11e`: PIORXDriver inherited the base
  receive_time_constraint_us(), which returns now, so the FPort (2.5 ms),
  SRXL2 (2 ms) and GHST (1 ms) late-reply guards never fired. The RX
  interrupt now stamps arrivals. Scratch X +32 bytes, 304 free.
- `b89bdf1b31`: the GPIO RC reader (Laurel, Pico2) assumed edges
  alternate. The RP PAL handler clears a pin's latched events and calls
  back once, so two edges before service read as one and reverse every
  later pair. It now reads the level per edge and restarts the pair.
- `f9a8726b93`: LC_ALL=C in rp2350_ramfunc2_sections.sh. The bot's
  dropped-duplicate case was not reproduced (en_US.UTF-8 not installed);
  the sorted order is the link order, so locale moved the layout. Lists
  unchanged under C.UTF-8.
- `170a624a93`, `ba939782a4`: AP_STORAGE_NO_WRITE_WHILE_ARMED on Laurel
  and Pico2 (AP_Stats saves every 30 s), and Laurel's list loses it.
- `de3815f645`: one rp2350_ramfunc2_gen task per build. Each program had
  its own, all rewriting the same fragments; `--targets
  bin/arducopter,bin/arduplane` now runs it once. `./waf copter` builds
  only arducopter here, so the flight builds were not exposed.
- `ed2d149501`: AP_FLAKE8_CLEAN on bin2uf2.py and rp2350_ramfunc2_sizes.py.
- `8c8669b7c1`, `f84957b840`, `e8e24d00e2`: set_group_mode() stopped
  PWMD1, shared on RPI_UAVFC by output 5 and the buzzer, and restarted it
  at output 5's 1 MHz against the alarm's 1.5 MHz (4 kHz near 2.67 kHz).
  An LED group on RP2350 now leaves the slice alone. Not checked on
  hardware.
- `63d22c9b04`: start_sm() and restart_sm() set and clear PIO2 CTRL bits
  through the atomic aliases.

Still open: the PIOUART half-duplex echo. Builds: RPI_UAVFC, Laurel,
Pico2; MatekH743 `5532a473c873` and CubeOrange `b1a4fb2cb76e`, unchanged.
Two subjects run over 72 characters (73, 85); they go with the squash.

Squashed the same day at Andy's request (backup
`pre-squash5/rp2350-v5-20261025` at `e8e24d00e2`), by blame, to local
`1b8b7e68cf`, 51 commits: the PIO UART timestamp, the RC edge fix and
the CTRL aliases into the PIO drivers commit (9); LC_ALL and the
DEVELOPMENT.md notes into the shared support files (11); the generator
into "waf: build RP2350 boards" (8); the flake8 markers into 7 and 32;
the storage define into Pico2 (27) and Laurel (28); the README into
RPI_UAVFC (29); keep_slice into RC input and output (14). Messages of
8, 9 and 14 updated. The alias helpers moved from rp2350_pio.h, which
only appears at 34 ("assemble ... from source", whose message promises
unchanged state machine code), to file-static functions in
RCOutput_pico.cpp, their only user; that is the only tree difference
from `e8e24d00e2`. MatekH743 and CubeOrange hash to master's at 7 to 47
and match the old series at 48 to 51; RPI_UAVFC builds at every commit
from 29, Pico2 and Laurel where added and at the tip.
Pushed as `1b8b7e68cf`; status comment issuecomment-6401893031.

`rp2350-flight-test` followed both pushes: onto `485f751fe6` as
`1cc7a9a8c3` (backup `pre-rebase3/rp2350-flight-test-20261025`), then
onto `1b8b7e68cf` as `cfc250c56a` (backup
`pre-rebase4/rp2350-flight-test-20261025`), which also drops the
SemaphoreRecursion example. Each time the 20 extras applied cleanly and
range-diff showed them unchanged, the branch moved by exactly the PR's
own change, and RPI_UAVFC, Laurel and Pico2 built. Not flown; bench
checks owed: the buzzer pitch with a NeoPixel strip on output 5, DShot
start and recovery, the 399 kHz microSD init, and ESC.Err against a log.

### AP-Review round 25 at `1b8b7e68cf`, 2026-10-26

REQUEST CHANGES on the ChibiOS#113 pin alone; round 24's fixes all
confirmed. CI: `check-merge-commits` failed only on that pin ("exists in
ArduPilot/ChibiOS but is not yet merged to master"), every other check in
the job passing; `pre-commit` failed on ruff I001 in bin2uf2.py, fallout
from dropping `flake8: noqa` in round 24 (pyproject's isort has
lines-between-types = 1). One blank line fixes it; ruff 0.15.6 and flake8
pass, and pre-commit excludes hwdef/scripts, so chibios_hwdef.py's
BLE001 hits (on master too) do not count. Squashed into commit 7
(`a93818b7d5`, backup `pre-squash6/rp2350-v5-20261026`) and pushed as
`bf14656274`: commits 7 to 51 differ only by that line, and old and new
bin2uf2.py write an identical UF2, so nothing was rebuilt.

The bot also asked for the AGENTS.md section 8 line saying the PR was
AI-assisted. Andy declined for #32995 and #34877: "AI agents have no
agency, all code is human authored, AI is just a tool." Rejected; expect
the bot to keep listing it.

## 2026-10-23: rebased onto master, and the review commits squashed

Rebased onto master `3868711713`. Upstream gave 7160-7169 to Viima, so
the boards moved to 7180 (RPI_UAVFC), 7181 (Pico2) and 7182 (Laurel),
with the bootloaders rebuilt; the block is reserved separately in
#34857. `ALLOW_ARM_NO_COMPASS` is gone upstream (ineffective since
2019; the runtime equivalent is `ARMING_SKIPCHK` 4, the compass bit)
and was dropped from the Laurel and RPI_UAVFC
hwdefs. RP2350 has no EXTI, so the new interrupt storm crash trigger is
left out there.

Then the 34 review commits of 10-22/23 (thread core table, AP_ names,
docs, cheap fixes, core1 start) were folded into the commits they
belong to: 91 commits to 54, tree identical to the pre-squash head
`2b0c874cbf` (backup branch `pre-squash/rp2350-v5-20261023`), pushed as
`9ee03b3bc7`. 57 (Copter pinned rate thread) folded into 24: with
`thread_create()` back, its STM32 change vanishes. 40 (SMP API in SITL)
and 43 (Matt's `OSD.md`) emptied, since their files are gone. 47
(`AP_Param` @READONLY) moved after 52, so the no-change block is
unbroken. Stale-comment fixes went to the commit that made the comment
stale, not the one that wrote the line: the OSD back-frame comment to
Matt's double-buffer commit, the line-count comment to the scan-out
commit.

Method: each commit's tree computed directly. A file a recent commit
touched takes its final content from its placement commit on, with any
later commit's change reverse-applied in between; a failed
reverse-apply marks a hunk that belongs later. Two files needed
hunk-level splits (`AP_OSD_pico.h`, `PIOUART.h` placed whole at 36).

Verified with `--consistent-builds`, 253 builds, no failures:

| | MatekH743 copter | CubeOrange copter |
|---|---|---|
| master and new #1-#52 | `78d37bd9006d` | `220b8666965e` |
| 47 `AP_Param` | unchanged | `f1e161d0e88f` |
| 53 UART race | `45b3a11b597d` | `46acf6f804fc` |
| 54 RCOutput | `ac6421f0452b` | `6409f08852db` |
| 55 INS | `161e0ba321d2` | `a6fa35bbf140` |
| 56 SPI guard (tip) | `5532a473c873` | `2c91403ed7a3` |

All equal the old series at the same commits. MatekH743 alone misses
`AP_Param`: only CubeOrange shows it. SITL copter at every commit;
Pico2, Laurel and RPI_UAVFC copter from their board commits; MatekF405
bootloader `70b7f05b0e12`, equal to master, at the 8 commits touching
common or bootloader code. A bootloader built in the same build
directory as the app fails on missing DroneCAN headers, so use a board
nothing else builds.

Second squash the same day: the nine review fixes (Peter's five
comments, the bot's RAMFUNC2/NODMA/heap-report items, the docs) and the
RP2350 ESC.Err counting were folded the same way, 63 commits to 53,
pushed as `723e5723e7` (backup `pre-squash2/rp2350-v5-20261023` at
`17cf914775`). "AP_Scheduler: support the RP2350 task timing" emptied
and dropped. 102 builds: the folded no-change commits keep master's
hashes, the five STM32-changing ones keep the table above, and
RPI_UAVFC, Laurel and Pico2 build at every commit from their board
commits. Scratch Y is at 4088/4096 after ESC.Err, so the next addition
there needs something moved out.

### Later on 2026-10-23

Board IDs: #34857 merged as `2f3644c90e`, so the PR was rebased onto it and
its own AP_Bootloader commit dropped as already applied (head
`e32d68d42e`).

@READONLY and AP_Param: Laurel's five @READONLY defaults (AHRS_ORIENTATION
8, FS_THR_VALUE 925, BRD_OPTIONS 5, COMPASS_ENABLE 0, LOG_BACKEND_TYPE 1)
and RPI_UAVFC's LOG_BACKEND_TYPE 1 were removed. LOG_BACKEND_TYPE 1 is the
default on a board with microSD and no dataflash, the watchdog bit of
BRD_OPTIONS is the ChibiOS default, the rest belong to the airframe, and
COMPASS_ENABLE 0 also blocked the external compass the bot kept flagging.
With nothing in the port using @READONLY, "AP_Param: enforce @READONLY
defaults over stale stored values" was dropped from the PR (head
`0a6d594d80`, 53 commits). #34443 carries the fix upstream in a newer form:
`read_param_defaults_file()` saves the default over the stored value, with
an autotest. The dropped copy, kept locally as
`param-readonly-over-storage`, is the superseded 2026-09-20 version.
Without it, CubeOrange copter at the tip is `b1a4fb2cb76e` and MatekH743 is
still `5532a473c873`, and both equal master at the commit before the UART
race, so four STM32-changing commits remain. The table above was taken with
AP_Param in the series.

Betaflight headers: osd_tx.pio and uart.pio got the copyright and GPLv3
notice that dshot.pio has. The authors come from Betaflight's history:
mjs1441 is Matthew Selby (the same email addresses) and wrote osd_tx.pio
and uart_tx_program.c. osd_tx.pio is identical to Betaflight's current copy
apart from 259 lines of trailing whitespace, now stripped.
`rp2350_pioasm.py --check` with pioasm 2.2.0 passes, so the committed
.pio.h files match their sources, which the bot had listed as not reviewed.

Bootloaders: the committed RP2350 bootloaders rebuilt from `0a6d594d80`
differ only in the 16-byte embedded git hash (offsets 801-816).

Third squash: the @READONLY, notes and licence-header commits folded into
their board, support-file and PIO commits, 54 to 51, identical tree, pushed
as `be00cf53c3` on base `2f3644c90e`. Only RP2350 text changed, so the
check was each board at its own commit and all three at the tip, with no
@READONLY left in any embedded defaults. A first attempt parented the
rebuilt series on `upstream/master` by name, which had just been fetched
forward by three IndiH743 commits, so commit 1 would have reverted them;
the commit-prefix check caught it and the rebuild uses the explicit base.

### Review state at `be00cf53c3`

Answered in the thread on 2026-10-23: Peter's five comments of 2026-10-07,
and a status comment for AP-Review round 17 (issuecomment-6371628655). The
chconf.h `defined() &&` construct now has a default (fixed), the compass
list uses AP_COMPASS_I2C_BACKEND_DEFAULT_ENABLED (fixed) and the fast task
modulo is gone (fixed).

Rejected, with the reason, so they are not raised again:

- Peter, sysperf.c: `const auto &_load = *load;`. The file is C, so there
  are no references or auto; it stays a pointer.
- Peter, Laurel defaults.parm: use enumeration names.
  `AP_Param::parse_param_line()` reads the value with strtof(), so a name
  would load as 0.
- AP-Review, OSD flush() copying into the frame core1 may be reading: kept.
  The copy writes the frame being shown, and render_block() reads `front`
  once per 9-line block, so the worst case is half a character row mixing
  old and new text for one field; write() and clear() only touch the back
  frame. Derived from the source, not measured.

Unflown: the last flights recorded here are 2026-10-03's (log142, log144).
Nothing from 2026-10-22/23 is recorded as flown, and at Andy's request it
was folded into commits that have flown, against the rule in this repo's
CLAUDE.md: the thread core table, the core1 start under the kernel lock,
the OS instances and idle stacks in .bss, the per-core load rescale, the
ESC.Err counting and the Laurel default removals. On 2026-10-23 Andy ran it
on the bench (boots, not flown) as `rp2350-flight-test` rebased onto
`17cf914775`.

Open: ChibiOS#113 unmerged, with no review since 2026-09-24, the only
blocker. CHANGES_REQUESTED still stands from tpwrules (2026-05-10), Peter
(2026-09-11) and tridge (2026-10-07), with every review comment answered
except Peter's and tridge's 2026-10-07 threads on the removed Betaflight
config header (the pinout is now in Laurel/HARDWARE.md). PIOUART
half-duplex echo suppression needs a SmartAudio test; the ESC.Err counting
and the buzzer pitch with a NeoPixel on output 5 are unchecked on hardware.
The nine ways DEVELOPMENT.md says Laurel lags RPI_UAVFC all stand, among
them the frame, notch and GPS_DRV_OPTIONS in defaults.parm, no
AP_STORAGE_NO_WRITE_WHILE_ARMED, thread statistics on, HAL_OSD_TYPE_DEFAULT
1 with no SPI OSD and the 9V rail without a relay.

## 2026-10-03: logging capacity lost in the 09-23 split, and the 1.4 kHz tone

Andy's log142 (flight-test `e12f495c`) logged at about 145 KB/s with the
buffer full and about 108 messages/s dropped; log144 (rp2350-v7 `baa23b86`)
the same, about 120/s. log123 (`3d26814c`, 09-22) wrote 162 KB/s armed with
no drops and never less than 18.7 KB free. Same `LOG_BITMASK`, same
54 B/message. Cause: the 09-23 rebuild split the microSD work out and with
it RPI_UAVFC's `define AP_FATFS_MAX_IO_SIZE 32768`. FATFS `io_size` starts at
4 KB and only `set_io_size()` raises it; #34476 adds that call on the
MMC-SPI path but with `AP_FATFS_MAX_IO_SIZE`, which is 4 KB except on big H7
and boards that define it, so the board fell back to a sync every 4 KB
(119 KB/s against 265 KB/s in the original sweep, DEVELOPMENT.md). The
define is back in `hwdef: add RPI_UAVFC`, pushed 2026-10-03 as `1abd39c093`
(53 commits; RPI_UAVFC builds at every commit from that one). It only takes
effect with #34476. Not bench-measured before the push: the board was
unplugged, and Andy judged the evidence sufficient.

The audible resonance "slightly above hover" is not firmware: the same
noise on rp2350-v7, and Andy's recording shows fixed lines at about 1400 Hz
and 2200 Hz that light up as the rotor harmonics sweep through them, about
7x rotation at 12k rpm (14-pole motor electrical frequency). The IMU's
internal anti-alias filter (about 1 kHz at a 4 kHz ODR) removes it: log144's
pre-filter gyro reads 0.000 dps in 1300-1500 Hz in every batch block. Also
noted, unexplained: `INS_GYRO_RATE` 2 but the batch sampler reports
3216 Hz.

## 2026-10-02: the flight that failed

Andy flew `rp2350-flight-test` (`df0ee89f`, PR head `564e6c1c7d` plus 17
split-out commits) and it rebooted continuously; with the lock-free clock
backed out it stopped rebooting but the GPS kept dropping out. Neither was
the clock. Both bugs came from 2026-10-01 work, both found on the bench over
SWD: the PIO UART per-port lock deadlocked core0, and the UART RX DMA flush
read `TRANS_COUNT` after an abort, which RP2350 reports as 0. Fixed as
`fixup!`/`amend!` commits on the flight-test branch (`195e6a7ada`,
`ec2cf9be6c`, `c3c3439520`, the last the same read on the TX timeout path),
then squashed into the PR's own commits. A CPU load A/B (before 2026-10-01
against the fixed head) found no measurable cost. Details and numbers:
[bench-2026-10-02.md](bench-2026-10-02.md).

Pushed 2026-10-02 as `fc8a3009d9`, 53 commits on `26c7363f64`, final tree
identical to the measured build B. Every commit from `hwdef: add RPI_UAVFC`
on builds RPI_UAVFC, and MatekH743 copter hashes match the 2026-10-01 run
commit for commit (`55c6972d59e2` through the `@READONLY` commit,
`f55647ee7e54` from the Copter commit to the head). Correction posted as
issuecomment-5960369015.

## 2026-10-01: two review rounds, the tables into SRAM, ten pushes

PR head `564e6c1c7d`, 53 commits on upstream `26c7363f64`, pushed
2026-10-01 17:10 UTC. GitHub reports no failing checks; tridge's review is
still CHANGES_REQUESTED. Bench measurements of the day are in
[bench-2026-10-01.md](bench-2026-10-01.md).

| time (UTC) | head | commits | what |
|---|---|---|---|
| 10:42 | `2b8df6d7fc` -> `34838f941d` | 78 | review fixups squashed - **on a stale local master**, see below |
| 10:54 | -> `76d63ae655` | 38 | `rebase --onto 26c7363f64` back to the real base |
| 11:40 | -> `c4ec53c632` | 44 | pioasm sources, `rp2350_pioasm.py`, installers |
| 11:57 | -> `afd3275fb5` | 45 | first automated-review fixes |
| 12:43 | -> `5420869370` | 47 | commit 13 SPI repair, Peter's SITL request |
| 13:02 | -> `26bef29059` | 45 | no-change commits moved first, two folded |
| 13:32 | -> `306db74eb8` | 49 | Matt's OSD work, `OSD_TYPE` 5 |
| 14:42 | -> `805070fb5f` | 50 | lock-free microsecond clock (fast-forward) |
| 16:33 | -> `2d147f576d` | 52 | second automated-review fixes |
| 17:10 | -> `564e6c1c7d` | 53 | PIO UART cross-core lock (fast-forward) |

### tridge and Peter, 2026-09-30

Answered by Andy on 2026-10-01 with short replies; the fixes are in the
10:42 squash.

- `c1_main.c` ("this whole file is very odd"): cut to about 60 lines. Gone:
  the boot markers and scratch writes (they clobbered watchdog SCRATCH1, the
  bootloader handoff), `c1_fault_info`, the MPU disable and SHCSR enables.
  Kept: the NVIC clear (the boot ROM leaves IRQ47 enabled) and the XIP
  doorbell at minimum priority. The doorbell handler moved to
  `board_rp2350.c` as a raw `VectorA8` that dispatches on `SIO->CPUID` with
  no OSAL prologue, because core0 holds the kernel spinlock across the flash
  operation. A core1 fault now goes to `HardFault_Handler`. Kept in
  ArduPilot rather than pushed into ChibiOS.
- Vector tables: the first cut pointed core1 at core0's table in striped
  SRAM. Andy: "it needs to run from uncontended ram". Now `.c1_vectors` at
  `0x20081000` (SRAM9, filled by core0 in `rp2350_board_pre_hal_init()`) and,
  at his request, `.c0_vectors` at `0x20080000` (SRAM8). Hot code behind
  them: core1 3752 of 3808 B, core0 on Pico2 3464 of 3808 B.
  **Corrected 16:16:** Andy was told core1 used the SRAM9 table on the
  strength of the placement alone. `_crt0_c1_entry` stores the flash
  `_vectors` into VTOR before calling `__c1_cpu_init()`, so it did not;
  `__c1_cpu_init()` now sets VTOR under `CH_CFG_SMP_MODE`. The extern is
  inside the guard too, because an unguarded one broke the bootloader link
  with a duplicate `_unhandled_exception`. Confirmed on the board:
  [bench-2026-10-01.md](bench-2026-10-01.md) section 3.
- PIOUART globals and initialisers: the `AP_PIOUART_DEBUG_ENABLED` code is
  gone. IRQ timing kept as members, and the uarts.txt PIO line shortened to
  `IRQ=8us/s,max=15us` without `NE=0 FlowCtrl=0`.
- `RCOutput.cpp` `chTimeUS2I`: `RCOUT_US2I` and the `delay_microseconds`
  bypass reverted. The pinned ChibiOS has tridge's fix `d3f61cd949`; checked
  there are no 64-bit divides.
- `UARTDriver.cpp`: the SIO helpers moved to a top-level
  `UARTDriver_rp2350.cpp` (waf only globs the top directory and
  `utility/`).
- `SoftSigReaderInt.h` `defined()` guards reverted; `HAL_USE_EICU` is always
  defined. `AP_Filesystem_Sys.cpp`: `#endif` comments added.
- pioasm (tridge, `RCOutput_pico.cpp`): five of the seven embedded PIO
  programs had no working source, and `pico_pio_uart.pio` did not assemble.
  `rp2350/pio/` now has uart, dshot and ws2812 (from pico-examples) and
  osd_tx (Betaflight, attributed), with the generated `.pio.h` committed;
  all assemble to the words previously embedded. The loaders relocate JMP
  targets, so the firmware is not byte-identical to before.
  `Tools/scripts/rp2350_pioasm.py` regenerates, `--check`s and `--install`s
  pinned pico-sdk-tools 2.2.0 pioasm and picotool (Linux x86_64 and aarch64,
  mac; tested on x86_64 only). The Ubuntu and mac installers offer it as an
  optional step. waf no longer downloads picotool: upload wants it on PATH.
  Reply discussion_r4154969276 corrected an earlier claim that Betaflight
  already requires pioasm.
- Peter's SITL request (`Scheduler.h`): `HAL_SCHEDULER_SMP_ENABLED` in
  SITL's `board/sitl.h`, and Copter always creates the rate thread with
  `thread_create_pinned_to_core()`. `DynamicRpmNotchesRateThread` passes.
  MatekH743 differs by 21 B in `Copter::one_hz_loop()`, so that commit
  claims no "no change". Reply discussion_r4155650581.

### Automated review at `2b8df6d7fc` (comment 5901861096)

Fifteen findings. Andy: ignore 1, agree on 5, reject 9, document 12.

- Fixed: UART inversion on the wrong pad (`PAL_PAD` masks to 0-31) and
  wiped by `begin()` (new `sio_apply_inversion()`); PIO TX inversion at the
  RP2040 bits 9:8 instead of 13:12; OSD use-after-free on the 200 ms probe
  timeout (a small leak remains); UART RX count read before the DMA abort
  (**superseded 2026-10-02**: the re-read after the abort returns 0 on
  RP2350 and corrupted every partial flush - the GPS dropouts in Andy's
  flight; now counted from `WRITE_ADDR`, see
  [bench-2026-10-02.md](bench-2026-10-02.md) section 2);
  SPI DMA allocation failure, which was a hard fault (`acquire_bus()` now
  unwinds); GPIO RC pulse pairing anchored on a rising edge; a dead
  `.claude/` reference in Debugger.md; three stale facts in the PR
  description. The core1 fault record cleared at boot went with the
  `c1_main.c` cut.
- Rejected: SBUS out on a PIO UART. A parity request sends nothing and
  says so once; the commit message says 8E2 is receive-only.
- Documented limitations: the fast erase checks only the first 4 KiB page
  of each 64 KiB block - the full-scan fix was reverted because it stalls
  USB, and Andy: "it has never bitten us yet"; the bootloader's GET_CRC
  answers from the received bytes.
- Deferred: the RPI_UAVFC README image.

### Automated review at `306db74eb8` (comment 5934596981)

REQUEST CHANGES. All but the PIO UART item went into `2d147f576d`.

- `scripts:` prefix: reworded to `Tools:`. All 52 commits then pass
  `allowed_subsystems.py`.
- The OSD double buffer broke Lua overlays: a script's text landed in the
  frame that was never cleared, so 'DIST 9' over 'DIST 12345' showed
  'DIST 92345'. `flush()` now copies front into back after the swap.
- `clock_pulse()` had no timeout recovery on RP2350. `SPIDevice::abandon_transfer()`
  is shared by it and `do_transfer()`.
- The heap budget tool read free stack as used; now used = total - free.
- The optional RP2350 installer step under `set -e` ended the whole
  install on unsupported hosts; now non-fatal.
- Core1 VTOR: see above. `HARDWARE.md` `/home/buzz` paths removed.
- The PIO UART cross-core race: below.

Answered 2026-10-01 in one reply covering all three automated reviews
(issuecomment-5937448806), at head `564e6c1c7d`.

### The PIO UART cross-core race

The receive purges masked the PIO vector with `nvicDisableVector()`, which
reaches only the calling core's NVIC, so a FETtec purge from core1 cleared
the ring under a live interrupt on core0 and then enabled the vector on a
second core. `_write()` drained the TX ring under `chSysLock()`, the
interrupt drained it with no lock.

The first fix (`90230c88b0`, never pushed) put the interrupt and the purges
under the kernel lock. Andy objected: "we need to minimise cross core kernel
locking". In SMP the kernel lock is one hardware spinlock both cores contend
for, and RP2350-E2 is an erratum on those spinlocks. Pushed instead
(`564e6c1c7d`): a per-port `uint32_t` lock (`ldaex`/`strex`). The thread side
raises BASEPRI over `PIO_UART_IRQ_PRIO` before taking it, so the interrupt
can never spin on a lock held on its own core. `_end()` clears both of the
instance's INTE bits, which both cores see. No `chSysLock` is left in
PIOUART.

The lock helpers must be `always_inline`. Plain `inline` in the header still
left weak out-of-line copies in flash, and `_service_irq`, which runs from
Scratch X, called them through veneers. That was checked in objdump, not
assumed. On hardware: u-blox detection works on a PIO UART. The FETtec
cross-core case is not exercised.

#### Superseded 2026-10-02 by the failed flight

The lock deadlocked. BASEPRI over `PIO_UART_IRQ_PRIO` does not survive a
kernel interrupt: any that leaves through `chSysUnlockFromISR()` writes
BASEPRI 0, and the port's interrupt then spins on a lock its own core's
thread holds. Andy's flight build rebooted continuously; core0 was caught in
the spin with the holder stacked inside `_write()`. The thread side now
masks at `CORTEX_BASEPRI_KERNEL`. And the hardware check above proved
nothing: the u-blox is on hardware UART1, not a PIO UART. Evidence in
[bench-2026-10-02.md](bench-2026-10-02.md) section 1. The text above is left
as the reasoning that was wrong.

### Matt's OSD work (andyp1per/ardupilot#39)

Taken: the double-buffered character frame and the renderer-decides-blank
change (both Matt's, split by module under `AP_OSD:`, comments trimmed to
house length), and his OSD.md as an hwdef commit. Matt's `OSD_TYPE` 1 -> 6
became 5 (MSP DisplayPort) as its own hwdef commit, at Andy's call. The
`__DMB()` barrier commit was dropped: no LTO. The draw thread "OSD" runs on
core0, the scan-out "OSD_c1" on core1. #39 is still open on Andy's fork.

### Keeping STM32 output unchanged up front

Every commit built in its own worktree with `--consistent-builds`.
MatekH743 copter stays at `55c6972d59e2` through the first 45 commits. The
six that do change STM32 output follow, then the clock commit:
`AP_Param` `@READONLY`, the UART start-up race, RCOutput, INS signalling, the
SPI `clock_pulse` guard and Copter's pinned rate thread. Head copter is
`f55647ee7e54`, unchanged by the clock commit. The commits that were not
moved (38-41, 43, 46) went up behind the no-change block with the claim line
added. 42 (waf picotool) was folded into "waf: build RP2350 boards". 44 (the
docs) was split per board, and Pico2's "core1 runs a bare-metal dispatcher"
was corrected to "core1 is started but idles". The MatekH743 bootloader
hashed `f3d783624e6b` in two morning runs and `ef2fd554a9ca` from 12:24 on.
The two are not reproducible against each other, and the cause is not
understood.

### Two mistakes, both caught by checking

- The 10:42 squash rebased onto local `master`, 39 commits behind upstream.
  Those upstream commits were rewritten into the PR (GitHub showed 77) and
  pushed. Fixed by `rebase --onto 26c7363f64` twelve minutes later. Take
  the base from upstream and check the commit count against GitHub before
  pushing.
- `absorb.py` applied hunks with `--unidiff-zero`, and that put
  `return spi_started;` after `#endif` instead of inside `apply_config()`.
  The final tree was right, but commits 13-44 of `afd3275fb5` did not
  compile. Found by the per-commit build, fixed in `5420869370`. absorb now
  self-checks that each fixup's diff matches the hunk it was given.

### Still open

- RPI_UAVFC README image. It becomes the CI blocker once ChibiOS#113
  merges.
- `rp2350_pioasm.py --check` is not in CI.
- Not bench-tested: UART inversion, GPIO RC input, the SBUS-out refusal,
  the PIO programs from source, Matt's OSD changes, FETtec over PIO.
- The boot-to-boot two-state rate/load swing, and the core1 hang after SWD
  ([bench-2026-10-01.md](bench-2026-10-01.md) section 2).
- Bootloader hash non-reproducibility.

## 2026-09-23 to 2026-09-29: 330 commits to 40, and the split-outs

This week was not recorded here when it happened. It was reconstructed on
2026-10-01 from the session transcripts, and some heads were pushed by Andy
outside them (`12ebfaed5f`, `87e36198ce`, `2b8df6d7fc`), so the list of pushes
is incomplete.

- 2026-09-23: the FTP and logger work split out to #34474 and #34473 and the
  microSD work to ChibiOS#115, #34476, #34477 and #34478. The SD retry
  went back to 3 s (282-305 ms per failed probe on the bench). The AP_Relay
  change was dropped and #34430 closed with a reply to tridge. Rebuilt from
  `rp2350-rebuild2` as 36 commits, down from 330. All 90 per-commit builds
  pass, and shared code costs +312 B on MatekF405. Pushed as `4e957574bd`,
  reply issuecomment-5803428685.
- 2026-09-24, ten pushes (`60dd0c5cdd` .. `e4f935b225`):
  - the DShot-command memset and XIP-timeout fixes;
  - the UART split;
  - SMP hooks made neutral (29 of 38 commits byte-identical on STM32);
  - the pico OSD moved into AP_OSD as `AP_OSD_pico`, its AP_OSD fix split
    out to #34497;
  - `HAL_RATE_THREAD_CORE`.
- 2026-09-26/27: `03a36713a1`, the reorder `a7c50b6317`, `7e839c6677`.
  issuecomment-5858538406 reports ST boards byte-identical up to
  `67676b6493` (360 boards; PixFlamingo differs only through
  `__AP_LINE__`). #34518 opened for the size-compare fix.
- 2026-09-28: `2c61bc3fd9`, 40 commits. Laurel watchdog on,
  `RCOutput_bdshot.cpp` at `-O2`. RPI_UAVFC-SimOnHardWare removed; the same
  build now comes from `sitl-on-hw.py`, which also retires the 2026-09-22
  registry miss on that board.
- 2026-09-29: memory.txt under-reported free heap through `chHeapStatus`,
  filed as #34530 (`0a9f82f353`, branch `pr-meminfo-core-free`) and taken
  off this branch.
- Open from 2026-09-23: Peter asked for review from the original authors,
  and tpwrules asked for dual-core to be dropped.

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

## The round at `c29abfea7c`: two failures CI was hiding (2026-09-22)

All five previous findings closed and the gate removal held up under review
as new code - neither pass could find an ordering it broke, and the strongest
argument for it was one neither had made: `thread_rx_init()` was already
called unconditionally from the top of `_begin()` even with the gate in place,
so the gate only ever deferred the TX thread. It was internally inconsistent.

**REQUEST CHANGES, for two things not in the delta at all, both invisible in
CI.** The workflow steps are sequential with no `if: always()`, so the
`modules/ChibiOS` submodule gate going red first means everything after it -
the submodule update, the cross toolchain, and the board compiles - never
runs. The red tick we have been reading as "just the ChibiOS dependency" was
concealing both of these, and both surface the moment ChibiOS#113 lands, which
is the same moment the PR becomes mergeable.

1. **`RPI_UAVFC-SimOnHardWare` did not build.**
   `AP_RCProtocol_Backend::is_detected` is header defined and only gets an
   out-of-line copy where enough callers exist; that board compiles a reduced
   RC backend set - 24 `AP_RCProtocol` objects against 59 - and inlines it
   away, which the strict registry check correctly read as a miss. Dropped the
   entry: no define expresses "the compiler inlined it", so a `[needs ...]`
   marker would key on something unrelated, and it is 26 B. Six other
   header-defined entries in that registry could hit the same thing on a
   future reduced build.
2. **`test_new_boards.py` fails on the README image check** for both
   `RPI_UAVFC` and `RPI_UAVFC-SimOnHardWare`. Andy is photographing the board.
   One image referenced from both READMEs closes it, the variant's reference
   pointing at `../RPI_UAVFC/images/`.

### The DMA flag resurrection, and why the structural fix was right

Both directions recompute their DMA flag in `_begin()` from a bounce buffer
that is allocated once and never freed, so a flag cleared because no channel
could be had comes back true with nothing behind it. On TX that turns the null
dereference just fixed into a permanent silent stall, because the Shared_DMA
handle still records us as owner so `lock()` never re-runs the allocator. On RX
it stops receive outright.

The reviewer's structural point was the good one: RX allocated its channel
inside the one-shot `_device_initialised` guard while the flag is recomputed
every time, so a port that first came up without RX DMA - `OPTION_NODMA_RX`,
or a failed bounce buffer - could never get a channel afterwards, with no DMA
exhaustion involved at all. Hoisting the allocation fixes both.

Checking it turned up a detail neither of us had raised: `!was_initialised`
also gates *starting* the DMA, so allocating on a later `begin()` without
starting would leave a dead channel. Handled with an explicit "this call got
the channel" flag. Behaviour is unchanged wherever it already worked.

### Two corrections worth keeping

- **The reviewer retracted its own severity claim.** It had argued the DMA
  exhaustion was reachable because "all 12 RP2350 DMA channels" could be taken.
  RP2350 has **16**; 12 is the RP2040 figure. Peak simultaneous demand on
  RPI_UAVFC is 10, so the double-allocation failure cannot occur on any board
  in this PR. The fix is hardening, not a blocker.
- **My own comment was wrong in the safe direction.** It said
  `dmaChannelFreeI()` "asserts on null". These boards build without
  `HAL_CHIBIOS_ENABLE_ASSERTS`, so the `osalDbgCheck` is a no-op and a null
  channel would **fault**. The guard is worth more than the comment claimed,
  which is the better way round to be wrong but still wrong.

## The gate is gone, and the round at `3e2ec1b91d` (2026-09-22)

Nine of eleven findings closed. Two carried over, and the one that came back
was mine again.

**The `txdma` fix was a level too low.** Clearing `tx_dma_enabled` inside
`dma_tx_allocate()` does not help the caller that triggers it:
`write_pending_bytes()` picks the DMA path on the flag,
`write_pending_bytes_DMA()` takes the Shared_DMA lock, and *the lock is what
runs* `dma_tx_allocate()` - so the first failure clears the flag and then walks
straight into `dmaChannelDisableX(txdma)` with null. Only later calls were
diverted. Fixed by re-testing after the lock and handing the handle back, the
shape the contention branch above already used.

Chasing that turned up a second null-deref I would have shipped: `Shared_DMA`
records ownership even when the allocation failed, so the *next* user's
`lock_core()` calls our `dma_tx_deallocate()` with nothing to free, and
`dmaChannelFreeI()` opens with `osalDbgCheck(dmachp != NULL)`. The reviewer
warned about it in one clause and it would have bitten. Worth noting the
pattern: both halves of this were me fixing the place I was looking at rather
than following the call chain.

Also closed: the PIOUART drain lock (the reviewer *verified* the prerequisite
rather than asserting it - PIO IRQs are priority 5, `CORTEX_MAX_KERNEL_PRIORITY`
is 2 on the ARMv8-M-ML port, so `BASEPRI` really does mask them inside the lock
zone), `txspace()` reporting the ring's free space, the deferred-thread
ordering, and all four documentation findings.

### Removing the gate

Andy bench-tested the current code, then took the open question: delete the
RP2350-only `(sdef.is_usb || hal.scheduler->is_system_initialized())` gate on
`thread_init()`. That removed the gate, the three lazy retries and
`start_deferred_threads()` together - net 65 lines - and put
`Scheduler::set_system_initialized()` back to master's. One commit, so one
revert if the bench said no.

It did not. Bench evidence, all three UARTDriver ports:

| port | proven by |
|---|---|
| SERIAL0 | USB enumerates, GCS connects |
| SERIAL1 | OSD overlay up |
| SERIAL2 | GPS reports configured |

The GPS one is the useful trick when there is no debugger: `is_configured()`
only clears once the UBX config messages are **ACKed**, so it needs transmit,
and a port that cannot send sits on "GPS 1 still configuring this GPS"
(`AP_Arming.cpp:780`) forever. Satellite count and lock are irrelevant to the
question. SERIAL3 and SERIAL4 are PIOUARTs, a different driver class the change
does not touch.

**Still owed:** this was a boot-order race, so one boot cannot separate "fixed"
from "got lucky". Three or four power cycles confirming the overlay each time
is the evidence that matters, and it is free. The failure mode is at least loud
now - `thread_init()` panics rather than leaving a port silent.

**And the notes needed the same treatment.** Removing the mechanism made the
`DEVELOPMENT.md` description of it stale, which is yesterday's lesson exactly.
Grepping the tree for it this time turned up `OSD.md`, which already carried a
note from the NeoPixel work saying `is_system_initialized()` is the wrong gate
for anything that wants a parameter. The UART driver made the same mistake at
greater cost; the two are now cross-referenced.

## Review round at `5c7814430a`, and a pattern worth naming (2026-09-21)

Verdict COMMENT. Two new findings, both against yesterday's UART fix, both
correct; five carried, four of them mine.

- **The fix had a race I introduced.** `start_deferred_threads()` ran *after*
  `_initialized = true`, and every other caller of `thread_init()` is gated on
  that flag while `thread_init()`'s own null check is check-then-act. A writer
  could have created a second thread for one port. Moved above the flag.
- **The `txdma` null-deref is real and I had half-dismissed it.** Recording
  that `tx_dma_enabled` was 0 on the failing board was right, and closing the
  DisplayPort investigation did not close this: the RX path clears
  `rx_dma_enabled` when both allocations fail, the TX path had no such branch.
- **Two genuine PIOUART bugs**, neither from this PR's recent work:
  `_drain_tx_fifo()` reads a byte then writes it and runs from both `_write()`
  and the ISR, so an interrupt in that window reorders the wire; and
  `txspace()` returned a constant 512 whenever the hardware FIFO had a slot,
  against 511 actually accepted on an empty ring, which MAVLink reads as a
  promise.
- **Open by choice:** the RP2350 `thread_init()` gate itself. The reviewer is
  right that removing it would delete the bug class and the scaffolding around
  it, but `git log -S` puts it in the original port commit with no recorded
  rationale, and it changes when every non-USB port starts its thread. Bench
  it rather than guess.

### The pattern: I keep fixing the file instead of the claim

All four carried findings that were mine are the same mistake. Turning Pico2's
SMP off corrected two table rows and left the file header calling it "the
current SMP branch", the prose still saying SMP was re-enabled and the
dispatcher was "not the default", one table cell carrying both accounts at
once because the new sentence was prepended to the old, and `c1_main.c` still
calling SMP "the default" - on the board whose `c1_main.c` is the reason it is
off. Correcting the `SIM_RATE_HZ` claim in a README left the same claim in
`defaults.parm`, written by me two commits earlier.

These files state the same fact in several registers - status table, prose,
code comment, parameter file - so a half-corrected tree reads as
self-contradicting and costs a review round every time. Andy caught it before
the bot did. The rule now: after changing a stated fact, grep for the old
claim's distinctive words and for the define it rests on, and fix every hit
before committing.

## The MSP DisplayPort fault: the port was never transmitting (2026-09-21)

Diagnosed live over SWD on a running board, no halting, no instrumented build.
Root cause: SERIAL1 had no UART thread, so it had never transmitted a byte.
`UARTDriver.cpp:645` - RP2350-specific code in this PR - defers `thread_init()`
for a non-USB port whose `begin()` runs before the scheduler is initialised,
and SERIAL1 is opened early by MSP and OSD init. The three lazy retries meant
to catch that up all sit behind a write, and `msp.cpp:35` stops calling
`write()` once the buffer is full, so the retry inside `_write()` is
unreachable. Deadlock. Fixed by `start_deferred_threads()` from
`Scheduler::set_system_initialized()`.

Before: `uart_thread_ctx` NULL, thread name buffer empty (so `thread_init()`
was never entered at all), `_writebuf` pinned at 1022/1024 with `head` unmoved
over ten minutes, zero bytes transmitted against 3621 on the GPS port, and
every queued frame `$M>` cmd 182 with no replies. After: thread `UART0`,
298,466 bytes transmitted, ring cycling, DisplayPort frames plus `$M>` replies
to all eleven polled commands. Andy: "OSD is working again".

### What I got wrong on the way, and what the evidence actually said

- **I proposed the wrong fix first.** The peer polls a DJI-style telemetry set
  and never asks for `MSP_OSD_CANVAS`, `MSP_OSD_CONFIG` or `MSP_FC_VARIANT`,
  cold or warm, so I concluded it was not a DisplayPort peer and recommended
  `OSD_TYPE 3` / `SERIAL1_PROTOCOL 33`. It is a DisplayPort peer: it renders
  the pushed cmd 182 frames without ever requesting a canvas. Andy pushed back
  that it felt more fundamental than a mode mismatch, and he was right.
- **I also guessed it had pruned commands that went unanswered.** It polls the
  same eleven now that it is being answered, so that was never true.
- **Three "no gap" captures were worthless** because my windows expired before
  he reached the bench. The lesson is to run the capture until told to stop and
  timestamp it in wall clock, not to pick a duration and hope.
- **A claim of mine about the CPU cost of dropping #34436 was wrong** and he
  caught it: with `INS_HNTCH_OPTS` bit 2 set, which is how the board flies, the
  commit changes neither behaviour nor load.

### What it corrects in the board notes

The old section's central claim - "both directions of that connector work" -
was wrong. Only receive did. The `UART` log figure of 5378 B/s tx that it
rested on needs re-reading before it is cited again. The intermittency is
explained too: whether `begin()` lands before or after system init is a race,
so the overlay worked on some boots. Two of the probe steps in open item 8
would have misled - an idle TX pin on a scope reads as a mux or DMA fault, and
`tx_dma_enabled` was 0 so the `txdma` check was aimed through the wrong
mechanism.

### Method

Addresses from the ELF, since the build ships no DWARF types:
`AP_MSP::_singleton` and `UARTDriver::serial_drivers` for the objects, field
offsets from disassembling the functions that touch them -
`msp_parse_received_data()` gives `cmd_msp` at +210, `write_pending_bytes_NODMA()`
gives `_writebuf` at +0x6c, `thread_init()` gives `uart_thread_ctx` at +0x28.
Sampling `cmd_msp` at ~1.9 kHz recovers the peer's command stream; unplugging
the cable and watching the stream stop is what proved which device was talking;
diffing the stuck port's object against the working GPS port's is what found
the null thread pointer.

## #34436 dropped from the branch (2026-09-21)

Andy's call: carry only what the port needs to be tested. Of the five PRs he
named - #33055, #33056, #33057, #33058, #34436 - **four contributed nothing to
the diff already**. `git diff` against the merge-base touches neither
`libraries/AP_Baro` nor `libraries/AP_RCProtocol` at all, and #33056's `d_name`
memset is not there either, so the description's first table was accurate and
there was nothing to remove for them.

#34436 was the only one in the branch, as two adjacent commits at depth 39-40.
Dropped, and the resulting tree differs from the pre-drop tip by exactly those
two hunks: `rate_thread.cpp` back to
`calc_gyro_decimation(rate_decimation, gyro_rate/2)` and
`HarmonicNotchFilter.cpp` back to master's parameter text. What still differs in
`rate_thread.cpp` is the RP2350 `cores_are_independent()` work, which is the
port's own.

**A CPU claim of mine was wrong and Andy caught it.** I said removing it would
cost 9 points of core1, from 57% back to 66%. It does not:
`LoopRateUpdate` is `1<<2`, so `INS_HNTCH_OPTS 22` sets it, and with the bit set
#34436's loop finds a notch asking for loop rate and assigns exactly the
expression the unpatched code used unconditionally. The 66% to 57% was the
*option-cleared* case - a saving the commit makes available, not one it
delivers. At the setting this board flies, behaviour and load are identical
either way.

Where it does change something is Laurel, whose `defaults.parm` sets
`INS_HNTCH_OPTS 2` with no loop-rate bit: without #34436 that board re-centres
at gyro/2 rather than at the main loop rate. Laurel is not flying, so it is a
note rather than an objection.

Two consequences. The reviewer's open ISSUE 2 - the `filter_rate` gate covering
`update_backend_filters()` as well as the re-centre - leaves this PR with the
commits, and is now #34436's business alone. And the description's second table
lost a row: #34436 moved up to the split-out group, leaving four carried PRs.

## The 2026-09-21 review at `955a2b84b9`, and two boards that could not boot

Closed: the commit prefixes (273 commits, all passing), the nine `SERIALn_*`
lines - checked behaviourally rather than just moved - and the Laurel and Pico2
README images. The one red CI job is now the submodule gate, which is the
normal state for a PR carrying an unmerged ChibiOS change.

**Two findings in this round were the same shape: a board configured for
something it does not implement.** Both were raised before and neither could be
confirmed without checking the build.

- **Pico2 had SMP on with no `ch1`.** `CH_CFG_SMP_MODE TRUE` in the hwdef, but
  its own `c1_main.c` only implements the bare-metal FIFO dispatcher, where
  Laurel's and RPI_UAVFC's call `chInstanceObjectInit(&ch1, ...)`. Meanwhile
  `rp2350_core_affinity.h` pins RCOUT and SPI0 to core 1 for every RP2350 SMP
  board, and `Scheduler.cpp:140` and `:861` create those threads against
  `&ch1`. The instance is `.data`, so they would have been enqueued into a
  zeroed ready list. Andy's call was to declare the board non-SMP rather than
  port ~60 lines of boot code that nobody can test, so `CH_CFG_SMP_MODE` is
  FALSE and the hwdef now says what is needed before it goes back on. Three
  ChibiOS registry entries are only out-of-line under SMP and took the
  `[needs CH_CFG_SMP_MODE]` marker the strict check already understood.
- **Pico2's scratch RAM was never initialised.** `RP2350_CRT0_AREAS_NUMBER = 0`
  in its board makefile, justified by a comment saying the Pico2 linker script
  defines no extra RAM areas. It links the same `common_rp2350_smp.ld` as the
  other two, and its ELF carries 3432 B of `.ram4_init` and 1880 B of
  `.ram5_init` - `AP_Scheduler::run`, `attitude_controller_run_quat`,
  `NotchFilter::apply` and two interrupt vectors. At 0, `crt1.c` compiles
  `__init_ram_areas()` to a bare `bx lr`, which the disassembly confirms
  against Laurel's six-area loop, so none of it was copied from flash. The
  override is gone. **Watch the rebuild:** the ChibiOS library does not rebuild
  when only a board makefile changes, and the first build after the fix still
  had the `bx lr`. `build/<board>/modules/ChibiOS` has to be removed.

The lesson for the rest of the port: the previous round listed both of these as
"could not settle", and the answer to each was one `objdump` away. A claim about
what a build does is answerable from the build.

### Also this round

- **The SBUS failsafe debounce is gone.** It needed three consecutive flagged
  frames and any clean one reset the count, so an alternating receiver cycled
  1, 2, 0 forever and had its failsafe stripped indefinitely - the marginal
  link where the flag matters most. A HAL UART driver editing a protocol
  payload was the other half of the objection.
- **The SimOnHardWare README promised something it does not deliver.** It said
  the rate thread runs as it does in flight; `FSTRATE_ENABLE` compiles in as 0
  and only `RPI_UAVFC/defaults.parm` sets it, which a derived board does not
  inherit - the very mechanism the README explains three paragraphs later.
  Corrected rather than papered over, along with a one-directional claim about
  `SIM_RATE_HZ`.
- **The serial defines were trimmed** to those that differ from
  `AP_SerialManager`'s own defaults, per the hwdef playbook's rule against
  restating a default. Pico2's SERIAL1/2 MAVLink2 and SERIAL5 None were
  redundant; SERIAL3 and SERIAL4 still override the GPS default.

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

### The board-validation items

Five of the six cleared; the sixth is a decision rather than a fix.

- **The nine `SERIALn_*` lines** are now `DEFAULT_SERIALn_*` defines in the
  hwdefs. Worth doing on its own merits: both hwdefs were disabling ports that
  defaults.parm then enabled, so you had to read two files to know what a port
  did. Laurel's hwdef said SERIAL4 was off while its defaults.parm ran it at
  MAVLink2, and Pico2's said SERIAL1 and SERIAL2 were off while its
  defaults.parm ran both. The defines now carry the effective values, so
  nothing moves at runtime, and all three boards build with
  `AP_SERIALMANAGER_DEFAULTS_CHECKS_ENABLED`, which is what the script turns on.
  One loss: Laurel's `SERIAL2_BAUD 115 @READONLY` cannot stay read-only as a
  define. The default is unchanged, the lock is gone.
- **Laurel and Pico2 READMEs** now reference the images their directories were
  already carrying, and Laurel's two 3000x4000 photos went from 2.2 MB to
  591 KB, which is what tpwrules asked for on 2026-09-14.
- **`RPI_UAVFC-SimOnHardWare/README.md`** exists now. Master's own
  `*-SimOnHardWare` directories carry no README at all; they predate the check.
- **The image for RPI_UAVFC is not solved.** There is no photo of that board
  anywhere in the repo or any branch, so `check_new_board_readme()` fails for
  it and for the SimOnHardWare variant, which would reference the same file.
  Andy's call on 2026-09-20 was to leave it failing rather than substitute a
  generated diagram. One photo dropped into `RPI_UAVFC/images/` closes both.

Note that running the script locally is misleading unless the local `master`
ref is current: it takes the merge-base against `master`, so a stale ref pulls
in dozens of boards that came from upstream and reports their failures as
yours. `HCR-523` and `ModalAI-VOXL3` both fail this check in master today.

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

**Stale since 2026-09-22.** The 2026-09-30 tridge and Peter threads were
answered on 2026-10-01 (see that round); this table was not re-derived
from GitHub then.

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
- The PR base is upstream `master`, not local `master`. A squash onto a
  stale local master pushed 39 upstream commits into the PR on
  2026-10-01. Check the commit count against GitHub before every push
- Zero-context patches (`git apply --unidiff-zero`) can land a hunk at the
  wrong place and still give the right final tree. Build every commit
  after a squash, not just the tip: an STM32 board at every commit, an
  RP2350 board from its hwdef commit on, and the `--consistent-builds`
  hash again for every commit that claims no change. When a working-tree
  diff is split into fixups, check that the staged hunks plus the ones
  left out on purpose add up to the whole diff before committing; on
  2026-10-01 a staged 5+/2- where 4+/1- was expected went unread, and
  commits 13-44 did not compile
- Grants for this branch need `--remote davidbuzz`; the default is
  `origin`, which is andyp1per's fork and not the PR head, so a push there
  misses the PR without any error. Squashing fixups in wants `--force
  --allow push,rebase,amend`: `amend` only because the hook refuses to run
  `check_branch_conventions.py`, whose source contains that command. Check
  the result with `gh pr view 32995 --json headRepositoryOwner,headRefOid`
- Commit prefixes come from `Tools/scripts/allowed_subsystems.py`:
  `Tools/scripts/` is `Tools:` and `Tools/ardupilotwaf/` is `waf`, whatever
  the playbook says
- Per-commit builds need their own `./waf configure` at each commit (plain
  `./waf` does not regenerate `hwdef.h`), and the bootloader wants its own
  worktree, or stale DroneCAN headers break it
- After an SWD flash, power-cycle the board before measuring anything; see
  [bench-2026-10-01.md](bench-2026-10-01.md) section 2
- Boards on Windows COM ports are driven with Windows `python.exe` from
  WSL. On 2026-10-28 it had pyserial but no pymavlink; putting WSL's venv
  (`\\wsl.localhost\Ubuntu\home\andy\venv-ardupilot\lib\python3.12\site-packages`)
  on `sys.path` works without installing anything, and `uploader.py` and
  `.apj` files run straight from `\\wsl.localhost` paths. The uploader's
  raw MAVLink reboot needs no pymavlink, and its progress output is
  `\r`-separated, so write it to a file. That day: Pico2 on COM16,
  RPI_UAVFC on COM15, picoprobe on COM10.
- A board's flash can be read back without SWD through the AP bootloader:
  READ_MULTI (0x28, up to 252 bytes per request, streaming from offset 0)
  dumps a 4 MB app area in about 142 s. Take one before overwriting a
  board's firmware; it restores byte-exact as an `.apj`. A failed
  `--verify-firmware-is` leaves the board in the bootloader, and GET_SYNC
  then BOOT (`21 20`, `30 20`) starts the app.
- The RPI_UAVFC bootloader over SWD (`init; halt`,
  `program <board>_bl.bin 0x10000000 verify`, `reset run`) erased only
  `0x10000000`-`0x10004fff` and left core1 running, rate loop up (one run,
  2026-10-28). For BOOTSEL, copy the UF2 from `C:\temp` with PowerShell
  `Copy-Item`: a `\\wsl.localhost` path in a bash double-quoted string
  loses its backslashes.
- Earlier Windows bench notes (2026-09-23 to 2026-10-01). Windows
  `python.exe` is the route to a board on a Windows COM port; check these
  notes rather than ask. usbipd is no use: the device is not shared and
  binding needs admin. Files were staged under
  `C:\support\raspberrypi\rp2350v2\`, where the SD retry test left
  `bench\` helpers: `info.py` (board id, git, params), `setparam.py`,
  `dumpparams.py` and `esctelem.py` (EDT temperatures prove DShot commands
  reach the ESCs). Run `uploader.py` under `timeout 180`; the RP2350
  bootloader comes up on the same COM port with no replug (3/3,
  2026-09-23). After a MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN the traceback is
  the port going away. pymavlink's mavftp writes to a hard-coded `/tmp`,
  so `C:\tmp` has to exist. An idle Mission Planner did not hold the port
  (COM40); a connected one does
- With OpenOCD connected, do not use `uploader.py`: its reboot into the
  bootloader left core1 locked up (PC `0xeffffffe`) and the board off USB,
  2/2 on 2026-09-24. Flash over SWD instead, and shut OpenOCD down before
  a MAVLink reboot. `set USE_SMP 0` lets core1 be poked alone (for
  example masking its IRQ26 through NVIC_ICER0 `0xE000E180` to force the
  XIP lockout timeout), but a `reset run` from that config once left core1
  in the boot ROM and the board never came up; reset with the default SMP
  config (`init; reset run; shutdown`). Halting core1 stalls core0's
  MAVLink too, so a halt cannot be used to force a timeout. VTOR
  (`0xE000ED08`) and the DWT PCSR (`0xE000101C`) read per core without
  halting
- `pre_bash_check.py` matches guarded git commands anywhere in a command
  line, greps and comments included, and reads a heredoc's first line as
  the commit message. Write scripts and messages to files first.
