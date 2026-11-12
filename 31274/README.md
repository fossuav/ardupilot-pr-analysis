# PR #31274 - Motortest error rate

Analysis archive for [ArduPilot/ardupilot#31274](https://github.com/ArduPilot/ardupilot/pull/31274).
Branch `andyp1per/pr-motortest-error-rate`. Record started 2026-10-30.

## 2026-10-30: AP-Review at 4ef30eefe0, both blockers fixed

The bot's two blockers were both real. RpmData.error_rate means a
percentage for bidirectional DShot, IOMCU and FETtec, the cumulative
DSDL error_count for DroneCAN (Status.error_count "resets when the motor
restarts"), and 0 for BLHeli serial, KDECAN, PiccoloCAN, Torqeedo, QURT,
AP_RPM and SITL. AP_Periph complicates it: it relays its own DShot
percentage in the DroneCAN error_count field, while the HobbyWing and
APD periph drivers send counts. A throwaway gtest against PR head's
AP_ESC_Telem showed a DroneCAN count of 2 blocking are_motors_running()
at 1%, and a BLHeli 0 after a 5% DShot rate passing it with ESC.Err
reading 0. Both were fixed after 5beef05d5c.

Design: drivers pass error_rate_is_pct to update_rpm() (default false),
and an update without a percentage does not overwrite one already
reported for that ESC. The flag fits in RpmData's padding. Other values
are still stored, so ESC.Err and the AP_Periph relay are unchanged.
Converting the DroneCAN count was rejected: it needs a window per ESC
and a rate the DSDL does not define, and would mangle AP_Periph's
relayed percentage. Dropping the count from DroneCAN would change
ESC.Err for every DroneCAN user (peterbarker added it in 1d57ada441).

The motor test indexed ESC telemetry by test order. On "+" a four-motor
test at SIM_ESC_ERR_RATE=5 warned for motors 1, 2, 3 and nothing for the
fourth (head plus the SITL hook, arducopter md5 700dc8c3). After
7477db0924 it warns for 3, 1, 4, 2 (md5 75dd7402). The mapping is
AP_MotorsMatrix's own _test_order, factored into
get_test_seq_motor_mask() and exposed as get_test_seq_output_mask();
non-matrix frames return 0 and get no warning.

Commits on r1030/31274 (on 4ef30eefe0):
- 89beac93b0 SITL: add SIM_ESC_ERR_RATE
- fd0c7ea3cf AP_ESC_Telem: report SIM_ESC_ERR_RATE from the SITL backend
- 5beef05d5c AP_ESC_Telem: only check error rates that are a percentage
- 1f2cfbba08, d930e0e7a7, ce8e7c3956: DShot, IOMCU and FETtec opt in
- 670df11d41 Copter: motor test warns only on a percentage
- ace86c2c92 AP_Motors: add get_test_seq_output_mask()
- 7477db0924 Copter: name the ESC the motor test spins
- 05ddd48130, e1621a406e: TKOFF_RPM_MIN and Q_TKOFF_RPM_MIN docs
- 75ff6bc98c Copter: return after cancel, label the #endif
- 90f7f1d5c4 autotest: error rate takeoff block and motor test warning

Tests at 90f7f1d5c4: Copter MotorTestErrorRate, TakeoffCheck, MotorTest
and QuadPlane TakeoffCheck, MotorTest all pass. MotorTestErrorRate fails
before the fix as above. The new TakeoffCheck subtest fails with the 1%
limit removed from AP_Vehicle, so it measures the gate. In SITL the
warning reports 0 rpm because SITL only simulates motor RPM when
SIM_VIB_MOT_MAX or SIM_ESC_ARM_RPM is set; that explains the bot's
"at 0.0 rpm" note.

Builds: SITL copter after each code change, plane, sub and heli after
the AP_Motors change, and CubeOrange-bdshot copter at 90f7f1d5c4, which
compiles the DShot, IOMCU and FETtec changes. Flash on CubeOrange-bdshot
copter: text 1656892 at 4ef30eefe0 and 1657124 at 90f7f1d5c4, +232 bytes
for these fixes.

Left open: the 5 s bdshot counter reset (one bad frame just after a
reset reads high) needs a minimum frame count in RCOutput, which is new
state, so it was not done. The Copter commit body sentence the bot
flagged needs a history rewrite and was left. 1f2cfbba08's subject is
73 characters; the gate notes it.

## 2026-10-30: quick review of the fixes, fixed in place

Andy chose to fix in place. The quick review closed the five original
findings and raised five more against the new mechanism; all five held
up against the code, except that Q_TKOFF_RPM_MIN already said zero
disables Q_TKOFF_RPM_MAX.

The sticky error_rate_is_pct flag had no freshness of its own: with
DShot silent and BLHeli serial still updating the RPM, the gate kept
using the last percentage. A throwaway gtest against 90f7f1d5c4 showed
a 0.5% rate still passing 400 ms after DShot stopped, and the raw error
rate (ESC.Err, AP_Periph's relay) returning the kept 5% after a BLHeli
update where master returns 0. a0308c713f restores error_rate to
master's latest-driver value and keeps the percentage in error_rate_pct
with its own timestamp, valid for ESC_RPM_CHECK_TIMEOUT_US (210 ms). An
ESC that reported a percentage and went quiet now fails the takeoff
check, since bidirectional DShot only reports on a good frame. The probe
passes 6/6 after it. ESC.Err now logs exactly what master logs. RAM is
8 bytes more per ESC slot.

FETtec: tx_err_count minus its baseline was done in int, so a wrapped
16-bit counter gave a negative rate (baseline 65530, count 5, 1000
commands: -6552.5% before, 1.1% after 04b048c540). A lost reply in the
first _esc_count commands after _fast_throttle_cmd_count wrapped kept
the previous window's baseline; e9c36f8c69 clears a per-ESC flag at the
wrap and baselines from the next reply. The SITL FETtec sim cannot
inject errors, so neither has a SITL test; FETtecESC still passes.

Bidirectional DShot: a missing reply (RECV_FAILED) was counted against
erpm_errors[curr_telem_chan], a group-local slot that the DMA callback
has already advanced, not the output. f7795d2363 uses
group.chan[prev_telem_chan] as the decode path does. Needs a hardware
check; SITL does not run it.

The motor test updated its once-a-second timestamp inside the loop, so
only the first faulty output of a motor was named. With motor 1 on
outputs 5 and 6 (SIM_VIB_MOT_MASK gives them SITL ESC telemetry) the
warnings named [5] before df98b72b3c and both after. Setting up the
test showed that SERVO1 only carries motor 1 as a runtime default, so a
reboot with motor 1 on SERVO5 leaves SERVO1 unassigned; the subtest
uses outputs 5 and 6 and reboots after restoring them.

f2cc80f6bd adds "(which also disables TKOFF_RPM_MAX)" to TKOFF_RPM_MIN.

Commits: a0308c713f, 04b048c540, e9c36f8c69, f7795d2363, f2cc80f6bd,
df98b72b3c, 26b5d5351f. a0308c713f (74) and e9c36f8c69 (75) have
subjects over the gate's 72 characters; reword at squash.

Tests at 26b5d5351f: Copter MotorTestErrorRate, TakeoffCheck, MotorTest
and FETtecESC, and QuadPlane TakeoffCheck and MotorTest all pass.
Builds: SITL copter, plane and heli, and CubeOrange-bdshot copter, which
compiles the DShot, IOMCU and FETtec changes. CubeOrange-bdshot copter
text is 1657268, +376 bytes on 4ef30eefe0 (it was +232 at 90f7f1d5c4).
The gate raises only subject-length notes; branch conventions pass.

Follow-ups, not done: the Lua binding of update_rpm() cannot pass the
percentage flag, so scripted backends are not checked; tri, single,
coax and tailsitter frames give no motor test warning; the bdshot
post-reset small-sample noise.

## 2026-10-30: gate narrowed to bidirectional DShot, r1030/31274b

Andy narrowed the takeoff gate to ChibiOS bidirectional DShot. The
round-2 cold reads found more driver-level problems, so the series was
rebuilt by cherry-pick from 4ef30eefe0 as r1030/31274b, head
d2283c9410; r1030/31274 is left as it was at 26b5d5351f.

Dropped: the IOMCU and FETtec percentage opt-ins and the two FETtec
fixes (d930e0e7a7, ce8e7c3956, 04b048c540, e9c36f8c69). Their rates
stay unflagged and log as on master. The FETtec wrap (a uint16 delta
done in int goes negative when the ESC's error counter wraps) and the
late re-baseline (which under-reports, dividing errors since a late
baseline by all commands since the wrap) are pre-existing logging bugs
for a separate PR. Kept commits were reworded where their subject was
over 72 characters or their body named IOMCU or FETtec.

New on the branch:
- ed0f6a879a AP_HAL_ChibiOS: ESCs do not answer DShot commands, and the
  empty receive window after one counted as an error. Each pulse now
  records whether it sent a command to the channel in the telemetry
  slot. The edit also stripped trailing spaces from the neighbouring
  #endif in RCOutput_serial.cpp; restore at squash if wanted.
- 7dd747e7f5 AP_HAL_ChibiOS: a missing reply now goes through the same
  5 s statistics reset as a failed decode, so a silent ESC's counters
  cannot wrap.
- e8f50bee92, fee4c3a7d6: TKOFF_RPM_MIN and Q_TKOFF_RPM_MIN say only
  bidirectional DShot on flight controller outputs is checked, and that
  an ESC that has never reported a rate is not.
- 2d8fae19b7: TKOFF_RPM_MAX says it needs TKOFF_RPM_MIN.
- 3c07d10af8: the motor test names one faulty output a second, taking a
  motor's outputs in turn, as "Motor Test: motor %u errors %.1f%% at
  %.0f rpm" (47 characters at most, one STATUSTEXT; the queue holds 10
  on HAL_MEM_CLASS_192 boards).
- b04b2dfc95, d2283c9410: autotest regex for the new text, and the
  redundant reboot after context_pop() removed (reboot_sitl() inside a
  context already makes the pop reboot).

Never-received: nothing in AP_HAL says which outputs run bidirectional
DShot (only set_bidir_dshot_mask() exists, and ChibiOS keeps
_bdshot.mask private), and BLHeli's BDMASK includes IOMCU outputs that
no longer report a percentage. So an ESC that has never reported is not
checked; documented in the parameters and the description. A
get_bidir_dshot_mask() on AP_HAL::RCOutput, returning the FMU mask
shifted by chan_offset, would close it.

Results at d2283c9410: Copter MotorTestErrorRate, TakeoffCheck,
MotorTest and FETtecESC, and QuadPlane TakeoffCheck and MotorTest all
pass. Every warning is now one STATUSTEXT, and outputs 5 and 6 are named
one a second. The stale-percentage gtest passes 6/6. Builds: SITL
copter, plane and heli; CubeOrange-bdshot copter (text 1657272, +380
bytes on 4ef30eefe0); iomcu-f103-dshot iofirmware, which compiles the
changed RCOutput files. The gate notes only a9ae4cdc82's subject; branch
conventions pass. The DShot fixes need a hardware check.

Andy's decisions: fix the first cold-review blockers in place, then, when a
second round found more driver-level problems, narrow the takeoff gate to
flight-controller bidirectional DShot only (the FETtec and IOMCU opt-ins
dropped; the FETtec counter wrap left for a separate PR). The pushed head
is r1030/31274c, which is r1030/31274b with an unrelated trailing-
whitespace strip on an #endif in RCOutput_serial.cpp undone. The three
bidirectional DShot statistics fixes need a hardware check.

Pushed 2026-10-30 to andyp1per with a lease on the old head: `4ef30eefe0`
-> `db7371c4d8`.

## 2026-10-31: SFD-O4 logs 66-71

SFD refresh12 topup3, firmware `ea8cef60` (the flight card commit, same code as `f93bd10a`). No motor test was logged: with `LOG_DISARMED 2`, bench boots on USB
leave no log. Armed, ESC.Err stayed at or below 0.9% on every motor except
in log70's hard acro, where motors 1, 3 and 4 reached 1.85, 1.54 and 1.82%
at 340-370 s.

At boot every motor reads 75-99% from 4.9 to 5.6 s, the same on all four
and in every log. On `52b1d36f` (log65) the same window read 97-99% for 3 s,
to 10.1 s. The takeoff gate reads ESC.Err only while armed, so this never
bound, and no motor stands out.

### Superseded 2026-10-31 by the squash audit

The boot comparison above says nothing about #31274. log65's build
(`52b1d36f`) carries the same #31274 commits as `ea8cef60`, and builds
without the 10-30 DShot fixes (log57 on `6d754361`, log59 on `59386e92`)
show the same 0.7 s window, 4.96-5.64 s. log65's 3 s comes from its ESC
telemetry starting 2 s later (6.99 s against 4.96 s); why it started later
was not checked. The boot window is left above as measured. No log shows the
four DShot commits changing ESC.Err (`squash-audit-2026-10-31/C.md`).

## 2026-10-31: AP-Review's blocker at db7371c4d8 fixed

The bot's round at `db7371c4d8` (REQUEST CHANGES) had one blocker: right
after the 5 s stats restart a fresh percentage could read 0% and clear the
takeoff block for good. It is real. Each pulse republishes every ESC's
cached eRPM with the current rate (`RCOutput.cpp`, the loop after
`bdshot_prepare_for_next_pulse()`), and a missed reply never replaces the
cache (only a corrupt one does), so a reset left the next republish at
`0/(1+0+0)`. Its should-fix, 1 bad + 1 clean reading 33%, is the same
mechanism.

Fixed on refresh12 and ported as `r1031/31274g`, two commits:
`f0d19ac649` (AP_HAL_ChibiOS) and `d228911760` (AP_ESC_Telem comment).
Pushed 2026-10-31: `db7371c4d8` -> `d228911760` (fast-forward).
- Keep the rate of the last window that counted 250 frames; while the new
  window has fewer, report the larger of that and its own rate, or 100%
  before any full window. A window is closed before the reply that ends it
  is counted, and one with fewer than 250 frames gives no rate.
- Divide by the frames counted (3 errors in 299 read 1.00%, under the
  limit, with one added).
- The rate is computed in the RCOutput thread at each counted reply and
  published as one `volatile float`, starting at 100% in `init()`, so the
  IOMCU firmware's `telem_update()` cannot read counts torn by a restart.

It took five review rounds. Codex's cold reads found three real faults in
earlier versions: a window closing with a handful of frames (telemetry
starting after 5 s uptime, as log65's did at 6.5-7 s) cached its one-frame
rate; reporting the last window alone hid a failure starting just after a
restart for up to 249 frames (worse than the PR: 119 frames passing against
8); and the reply that ended a window was counted into it, so after a pause
249 good frames and one late reply replaced a 5% floor with 0%. Each was
reproduced in the extracted-code probe before it was fixed.

Extracted-code probe (SITL cannot run `RCOutput_bdshot`), good frames in
55 s reading 1% or under, PR against the fix:

| ESC | Case | PR | Fix |
|---|---|---|---|
| failing 50% | telemetry from 4.5 s | 11 | 0 |
| failing 50% | telemetry from 6.5 s | 13 | 0 |
| failing 50% | a 10 s pause | 10 | 0 |
| failing 5% | 500 / 100 replies a second | 277 / 240 | 0 / 0 |
| failing 50% | from 20 ms after a restart | 8 | 0 |
| failing 20% | from 50 ms after a restart | 20 | 3 |
| healthy | | all | all but the first 250 after start |

Deterministic boundary cases: a missed reply ending a clean window reads
100%; 249 good replies, a 6 s pause and one more keep a 5% floor. The
minimum of 250 was chosen over 100 because at 100 a 5% ESC still read under
1% on 22 frames at 500 replies a second.

Not changed: a failure that begins late in a full window is diluted by the
window's earlier clean frames (after 2000 clean frames a 50% failure needs
about 21 misses to pass 1%). That is the gate's 1%-over-a-5-s-window
design, not the restart artefact; a shorter or sliding window would change
it, and is a decision for the PR, not this fix. Codex also read the
republish comment as wrong; it is right (the cached slot is decoded every
pulse; the INVALID check is the corrupt-reply case).

Builds, no warnings: CubeOrange-bdshot and CubeOrange copter and the
iomcu-dshot firmware on the PR alone; SmallFastDronev1 on refresh12 costs
256 bytes of flash and 128 of RAM. Not flown.

## 2026-10-31: description and replies posted

Description replaced with the 10-30 draft, updated: the restart handling in the summary and detail, the flight (ESC.Err armed at or below 0.9%, 1.5-1.9% in hard acro), the extracted-code table, the corrected republish account, and the in-window dilution as a known limit. The original body is kept in that session's scratchpad only; the PR history shows it.
Reply posted: https://github.com/ArduPilot/ardupilot/pull/31274#issuecomment-6548809608 (the blocker fixed in f0d19ac649; IOMCU and FETtec left unchecked on purpose).

## 2026-10-31: squashed after the flight audit

Pushed `d228911760` -> `820f2550b0` (force, 30 commits to 13, same tree; backup `pre-squash/31274-1031`). What folded and what stays on top, and why: `squash-audit-2026-10-31/squash_C.md`.

## 2026-10-31: the 5 s window kept

Andy's decision: keep the gate on the 5 s stats window. A failure that starts late in a window is diluted by its earlier good replies (after 2000, a 50% ESC takes about 21 misses to read over 1%); the description lists it under "Not covered". Telemetry flows while disarmed, so an ESC already failing shows before spool-up, and only a failure starting in the spool-up seconds is slow. Revisit with flight data; the options were a short recent window alongside it or a 1 s stats window.

## 2026-11-02: AP-Review at the squashed head

COMMENT at `820f2550b0` (round 6, 2026-10-31 23:33), down from REQUEST CHANGES; nothing blocks. One minor left, and it is real: `bdshot_error_rate()` (RCOutput_bdshot.cpp:256) takes max(short-window rate, last window), a floor with no ceiling, so one missed reply in the first 99 frames after a 5 s restart reads 100%, then 50%, 33%, and stays over 1% until the 99th clean reply (about 0.5 s). Takeoff is only delayed, but the motor-test warning (error_rate_pct > 1) can name a healthy ESC.

Correction: the 2026-10-31 reply said "the 33% case goes with it". It does not; the bot's probe shows 1 bad + 1 clean reading 50% and the next clean 33%. Candidate fix, not yet made or measured: divide the short window's errors by the full window length rather than by the frames so far, keeping the max with the last window, so a short window can read no higher than the full one would if the rest of it came back clean (a dead ESC still reads over 1% from its third missed frame).

## 2026-11-02: the post-reset spike fixed

`bdshot_error_rate()` now divides a short window's errors by no fewer than the 250 frames a window needs to stand alone (`MAX(frames, 250)`) instead of by the frames so far, still floored by the last full window's rate, or 100% before there is one; the BDSHOT_ERROR_RATE_MIN_FRAMES comment says it is now also that divisor. On refresh12 as `bed4134fb4` (branch `r1102/31274-r12c`) and on the PR as `eea919627c` on `sq/31274-1102b` over `820f2550b0`, its own commit on top: unflown. RCOutput_bdshot.cpp is byte-identical in the two. Superseded local drafts, same behaviour: `r1102/31274-r12` `92fe4fb5f7`, `r1102/31274-r12b` `39b04921c1`, `sq/31274-1102` `c7e9135887` (errors times 0.4 below 250 frames; reworded and simplified after the cold read).

A/B with the driver's own `bdshot_error_rate()` and reply-counting block extracted verbatim into a host probe (scratchpad r1102/31274: extract.py, probe.cpp, probe_desc.cpp), 200 replies/s unless stated:

| Scenario | before (820f2550b0) | after |
|---|---|---|
| healthy ESC, one miss in a window's first 300 frames (worst k) | 100% peak, over 1% for 99 replies (495 ms) | 0.4% peak, never over 1% |
| dead from a restart, replies until over 1% | 1 | 3 (15 ms) |
| failing 50/5/2% from boot, good replies read 1% or under | 0/0/0 | 0/0/0 |
| failing 50/5/2% from 15 ms before a restart | 2/8/8 | 4/53/64 |
| dead from 10 s, replies after 16 s read 1% or under | 0 of 8800 | 0 of 8800 |
| healthy missing 0.1/0.2/0.4%, motor test warnings in 114 s | 3/8/9 | 0/3/3 |
| description row: failing 50% from 20 ms after a restart (500/s) | 0 | 3 |

A mutant with the floor removed reads 716 of 11266 good replies of a 5% ESC and 16 of 8800 dead replies at 1% or under, so the floor rows can go the wrong way. At 1000 replies/s the shape is the same. The warnings left at 0.2 and 0.4% come from windows just past 250 frames holding three misses, which read over 1% on their own count: the 250-frame resolution, not the restart. The price of the fix is two more misses before a failure starting at a restart shows; the description gains a "Not covered" line for it and its onset row changes from 0 to 3.

Builds at the port head, all rc=0 with no warnings: CubeOrange-bdshot copter, iomcu-dshot iofirmware, SITL copter and plane; SmallFastDronev1 copter at the r12 head. Copter.TakeoffCheck, Copter.MotorTestErrorRate and QuadPlane.TakeoffCheck pass (SITL does not run the DShot driver, so these guard the rest of the PR only). Mechanical gate and check_branch_conventions.py clean.

Quick review: Codex unavailable for the cold read (usage limit until 2026-11-04 08:31; the audit task finished first and called the spike CLOSED, and so does a hand audit at the new head), cold read by Claude on `c7e9135887`. No functional bug. Taken: the message's "a dead one passes no more often" was wrong for an ESC dying at a restart, and the takeoff check is where the two extra misses land, as a missed reply leaves the last good RPM in place (now said); 53 vs 8 was one seeded run, now the expected 57 vs 19; the message now says the 5 s counts are what restarts; the comment no longer hard-codes 0.4% or describes the old code; the MIN_FRAMES comment names its second use; one `MAX(frames, 250)` formula for both branches. The probe gives identical numbers on the reworked code, and the mutant without the floor still fails. Not taken: a per-channel low-pass instead of the window, a redesign against the 2026-10-31 decision to keep the 5 s window. Raised outside the commit, from `988f8abb9e`: a channel getting under about 50 replies/s never fills a 250-frame window, so its floor stays 100% (not checked here).

## 2026-11-02: pushed

Pushed to `eea919627c` (refresh12 `b1093230e6` locks it). Reply posted: https://github.com/ArduPilot/ardupilot/pull/31274#issuecomment-6576454593. Description updated with the onset row (0 to 3), the restart paragraph and a Not covered line.

## 2026-11-02 (later): the stored percentage latched stale

AP-Review round 7 (COMMENT at `eea919627c`, nothing blocks) raised two
minors. The first is real and checked in the code: `get_error_rate_pct()`
judged freshness only by `timeout_expired()` on the 32-bit
`error_rate_pct_us`, so with every DShot reply failing to decode while
BLHeli serial telemetry keeps the rpm fresh, the old percentage reads
recent again for 210 ms when micros() wraps 71.6 min later. Zeroing the
timestamp would not do, as `error_rate_pct_us != 0` is how
`are_motors_running()` tells a percentage-reporting ESC from a DroneCAN
one; a separate `error_rate_pct_valid`, set by `update_rpm()` and cleared
by `update()` once 210 ms old, follows `data_valid`.

Host probe (`stale_probe.cpp`, the freshness code copied, micros()
simulated; replies stop at 10 s, serial telemetry continues, 400 Hz
checks for 75 min): before, 84 of 1795879 checks pass, all within 210 ms
at 71.77 min; after, 0. Every check while the replies were good passes
both ways (4000/4000).

refresh12 `78cf55708f`, port `b723c6a05f` on `sq/31274-1102c` (same
change; the files differ only by base). CubeOrange-bdshot copter and
SITL copter/plane build with no warnings; Copter.TakeoffCheck,
Copter.MotorTestErrorRate and QuadPlane.TakeoffCheck pass. Self-reviewed
only (no Codex; no independent cold read in this pass). The race with
update() is the one `data_valid` has: it fails closed and the next pulse
repairs it.

The second minor is a note on the last reply: "ESCs failing 2% ... still
never pass" holds only for evenly spaced misses; with random 2% loss a
full window can read 1% or under. The draft reply corrects it.

Pushed 2026-11-02 (afternoon) to andyp1per with a lease: `eea919627c` -> `05edaf83de` (refresh12 `df341758a7` locks it). Reply: https://github.com/ArduPilot/ardupilot/pull/31274#issuecomment-6580087118. Description updated.

## 2026-11-02 (evening): squashed after the Q25 flights

The Q25 indoor logs on c46a09ec flew 988f8abb9e ("keep a DShot error rate
from a full window after a reset"): ESC.Err read exactly 100% on all four
outputs from 5.02 s to 10.50 s, then at most 1% (squash-audit-2026-10-31/
Q25-2026-11-02.md). Folded into "report the bdshot error rate as a
percentage" on `sq/31274-1102e` (head `2b31e43213`, 14 commits, tree
identical to `05edaf83de`; backup `pre-squash/31274-1102`). Not pushed.

### Superseded 2026-11-04 by a reread of the same logs

ESC.Err read 100% only to 6.02 s. From 6.06 s it read the first stats
window's own rate: 32%, rising to 44% at 6.18 s, falling to 6.5% at
10.0 s, held there to 10.5 s, then 1% or under. Same on all six Q25
boots on `c46a09ec56` and `722d77b5de` (below). The paragraph above took
every reading over 1% for 100%, and the squash-audit addendum
(`squash-audit-2026-10-31/Q25-2026-11-02.md`) has the same wording. Left
as written; the 100% branch did run, for the first second.

## 2026-11-04: the boot reading, the reply-rate floor, and a unit test

From tridge's dev call questions (comment 6625045530: why 100% at
startup). Local branch `r1104/31274-rate` on the PR head `2b31e43213`,
not pushed. `722d77b5de`'s RCOutput_bdshot.cpp is byte-identical to the
PR head's; `c46a09ec56`'s differs only in dividing a short window by its
frames, which no reading below reaches.

### Why ESC.Err reads high for 5.5 s after boot (tier 1, model tier 2)

Q25, MicoAir743v2, SERVO_DSHOT_RATE 2, SCHED_LOOP_RATE 200,
SERVO_DSHOT_ESC 3, four DShot600 outputs on one timer, TKOFF_RPM_MIN 0.
The worst of the four outputs:

| Log | first ESC | 100% to | then peak | at or under 1% from |
|---|---|---|---|---|
| c46a09e Indoor Loiter 1 of 2 | 5.02 | 6.02 | 43.7% | 10.54 |
| c46a09e Indoor Loiter 2 of 2 | 5.02 | 6.02 | 44.3% | 10.54 |
| c46a09e Inside house brown floor | 5.02 | 6.02 | 43.9% | 10.54 |
| c46a09e Loiter good then failsafes ... dim auto bay | 5.03 | 6.03 | 44.2% | 10.55 |
| 722d77b VALT Test 1 of 2 | 5.02 | 6.02 | 43.8% | 10.54 |
| 722d77b VALT Test 2 of 2 | 5.11 | 6.07 | 46.8% | 10.55 |
| 0cb49e7 Test new code seemed fine (master's formula) | 6.44 | - | 79.3% | 11.32 |

The traces repeat to the count across boots days and builds apart. A
model of the PR's counting fits each within 0.2 to 0.4% rms
(`boot_model.py` in that session's scratch): the first counted reply
restarts the window, since the counters start at uptime zero; DShot
starts at about 5.0 s, when the firmware finishes initialising; about
194 counted replies a second per output until the rate thread starts at
5.86 s (the driver's 800 Hz floor over four outputs), 449 to 477 after
(2 kHz); the ESCs miss their first 57 to 85 replies and every reply in a
0.15 to 0.2 s gap at 6.0 to 6.2 s, about 140 in all. The gap follows the
rate thread's DShot rate change by about 0.13 s on every boot. Its cause
is not found; DShot commands are not it, as their reply slots are not
counted.

So of the 5.5 s, about 1 s is the PR's 100% before 250 replies, about
4 s is those misses held in a window anchored to uptime, and 0.5 s is
that window's rate held as the floor until the next one counts 250.
Master counts the same misses: `0cb49e7` (master's errors/(1+frames)
with the PR's miss counting) read 79% at 6.44 s and was not under 1%
until 11.3 s. SFD-O4's 0.7 s (2026-10-31 above) fits: misses that land
before the first restart at 5 s are thrown away with it.

Effect: within about 10.5 s of boot a motor test warns on every motor,
and with TKOFF_RPM_MIN set a takeoff is held until then. The Q25 armed
at 17 s or later and has TKOFF_RPM_MIN 0, so none of this bound.

### The 50 replies a second

A window that never counts 250 replies never sets a rate, so a channel
counting fewer than 50 a second reads 100% for good. Confirmed in the
source and pinned by the test below (47.6 a second reads 100% for a
minute, 50 a second reports). No stock FMU configuration is near it:
set_dshot_rate() never pulses below 800 Hz (the 1 kHz timer at low loop
rates), and a timer captures one reply per pulse from at most four
outputs, so at least 200 a second. The Q25 counts 194 before its rate
thread and 449 to 477 after, so about a tenth of pulses go uncounted
there; a channel would need three quarters uncounted. It binds a
shorter window: a 1 s window with the same 250 needs 250 a second,
which the Q25 does not get before its rate thread (derived from the
source).

### IOMCU

`iomcu-f103-dshot` defines HAL_WITH_BIDIR_DSHOT and compiles
RCOutput_bdshot.cpp; `iomcu-dshot` does not. The PR does not touch
Tools/IO_Firmware, so IOMCU ESC.Err does not change until the binaries
are rebuilt, normally for a release. Then it reads as the FMU outputs do
(100% before 250 replies, the miss counting, the 250 divisor). AP_IOMCU
passes it on without the percentage flag, so the takeoff check and the
motor test ignore it either way. The current description's "ESC.Err
logs exactly what it did before" for IOMCU holds only until that
rebuild.

### Unit test, and the refactor it needs

SITL does not run the DShot driver (its ESC backend reports
SIM_ESC_ERR_RATE directly), so the counting moved, unchanged, into a
header the host build can test:
- `d9f71c7a59` AP_HAL: `BDShotErrorRate<N>` in
  `AP_HAL/utility/BDShotErrorRate.h`, the driver's arrays, mask and
  code, members in the same order and types.
- `df901690db` AP_HAL_ChibiOS: the driver uses it. The reply is decoded
  before it is counted, which reads nothing the restart writes.
- `2eb366d50a` AP_HAL: `tests/test_bdshot_error_rate`, 9 cases: no reply
  yet; healthy from boot (100% to the 250th reply); start-up misses held
  for their window (80 misses at 200 a second: over 1% for 6.25 s); the
  50 a second floor; dead after a restart (over 1% from the third miss);
  dead late in a window (the tenth miss after 900 good); one miss after
  a restart (0.4%); an ESC that restarts (over 1% for 5.25 s after it
  answers again); a pause (keeps the last window's rate).

Checks: all 9 pass. Three mutants of the header (no 100% default,
divide by the frames so far, no floor) fail 4, 3 and 7 cases. A host
probe feeding the PR head's code, copied, and the new class the same 80
million replies over 200 random streams (pauses, loss changes, the
millis() wrap) published identical rates to the bit. CubeOrange-bdshot
copter builds 4 bytes smaller in flash and RAM, iomcu-f103-dshot
iofirmware the same size, no warnings; check_branch_conventions.py
passes. Whether the refactor goes on the PR is Andy's call.

### Fix options, not made (derived from the fitted model, not run)

Neither half alone shortens the Q25's boot reading; both together do:
- Skip misses before an output's first good reply: the gap's misses then
  fall in the first 250 frames, read 30% at 6.16 s and are held to
  10.8 s, worse than now.
- Skip the gap alone: the 57 start-up misses read 23% at about 6.2 s and
  hold to about 10.5 s.
- Both: 100% to about 6.3 s, then 0%.
The gap's cause has to be found first; a bench boot log at
SERVO_DSHOT_RATE 0 against 2 would show whether it follows the rate
change. Shortening the window instead raises the reply-rate floor in
proportion (above).

## 2026-11-06: SFD-O4 log78, four takeoffs in one boot

Beta topup11 `52ec3c77`, TKOFF_RPM_MIN 1000: four takeoffs in one boot,
none held ("Takeoff blocked" or "ESC RPM or errors out of range" never
sent), `ESC.Err` at most 0.02-0.03% on every motor in flight. The boot
reading is as in October (99.7% decaying to 10.7% over 5.5 s), so neither
`4697e3f3f6` (the 250-frame window) nor `2b31e43213` (the stale latch) is
shown to have acted. Both stay on top.

## 2026-11-07: the 250-frame window flown, squashed and pushed

`4697e3f3f6` divides a short DShot window's errors by at least 250
frames. It ran armed with the motors spinning: only that division gives
exactly 0.400% for one error in a window under 250 frames, and three
flights read it (tier 1). SFD-O4 log80, 60.12-60.16 s at 11,200 rpm:
ESC0 0.400%, ESC2 0.800%. log82, 60.11-60.15 s: ESC2 0.400%. The Q25 on
topup9 (`a8487f0`), flight 01, 380.19-380.63 s through a spool-up from 0
to 2,700 rpm: ESC1 0.400% for 0.44 s, then one error over the frames.
Divided by the frames so far, as before, that spool-up would have read
over 1% for about the first 100 frames (derived from the source, not
measured). No takeoff decision was shown to change: the Q25 flies
`TKOFF_RPM_MIN` 0, and there was no motor test.

Pushed `2b31e43213` -> `0f9555fb6f` (force, 14 commits to 13, same tree;
backup `pre-squash/31274-1107`). It folds into "report the bdshot error
rate as a percentage" (`493b335397`), now `31c0cbe292`. The stale latch
(`0f9555fb6f`, was `2b31e43213`) stays on top: it needs serial ESC
telemetry alongside DShot, or a log longer than the 71.6 min micros()
wrap, and neither airframe has flown either.

## 2026-11-07 (evening): AP-Review at `0f9555fb6f`, the ESC.Err doc, pushed

AP-Review (COMMENT, nothing blocking) found the description saying ESC.Err
and AP_Periph's relayed DroneCAN error_count were unchanged, when on
bidirectional DShot outputs of a flight controller or AP_Periph they now
read the 250-frame percentage, 100 until an output has counted 250
replies. `c922349b3c` says so in the ESC.Err field doc, and the
description's sentence now says ESC.Err carries what each driver reports.

Pushed 2026-11-07: `pr-motortest-error-rate` `0f9555fb6f..c922349b3c`
(fast-forward). Description updated.

## 2026-11-12: SFD-O4 logs 89-90 (tier 1)

ESC.Err read 84-92% on every output from 1.9 s after power-up, at 0 rpm
while disarmed, falling below 1% by 6.8 s, on log89 (3408138/707,
`56d1905e`) and log90 (3408138/711, refresh15 `c42bd1fb`) alike: the ESCs
starting up (mechanism not checked). By the first arm it had settled
(log89 read 0.05% at 292.9 s). Armed, at most 0.33% (log89, ESC instance
3) and 0.27% (log90). The card's motor test is still owed.
