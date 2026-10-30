# What each EKF change must be replayed against

Every PR here that changes EKF3 estimator code should name the real flight
that exposed the problem, and any change to that code gets replayed against
that flight before it is believed. The rule is in [CLAUDE.md](CLAUDE.md)
under "Replay against the flight that exposed it"; this file is the record
it refers to.

Replay re-runs the estimator on the sensor stream the flight actually
recorded, so for an estimator change it is the closest thing to re-flying.
Its limits are in CLAUDE.md's evidence cascade and matter here: it cannot
show a vehicle-code fix working, and it cannot show anything the DAL did not
record.

## Resolving a log

Logs are never renamed, but they move between machines, and the names are not
unique - there are 24 files called `log7.bin` on the primary machine. So a log
is identified by name plus a fingerprint read out of the log itself, and
`find_log.py` resolves it:

```sh
export AP_LOG_ROOTS=<log-root>:<support-root>   # wherever they live here
./find_log.py log7.bin --acc-id 3408138 --bootcnt 517 --replayable
```

The fingerprints are private - several of these are customer logs whose file
names identify the customer and the fault they reported - and live in
`../analysis/logs/REPLAY_INDEX.md`. The ids below are the ones each PR's own
record already uses.

## The record

"Replay status" is what has actually been run against the *current* head of
that PR, not what could be.

| PR | log | what it exposes | replay status |
|---|---|---|---|
| [33359](33359/) | log280 | indoor alt-hold divergence at the rangefinder height-source switch (std 1.14 / max 5.40 m) | validated pre-submission, and still valid after the 2026-09-10 head move to 640cd4a5fc (comments only); corrected 2026-09-10 - this row named log281, which is the flight flown *with* the fix, so replaying it would compare a fixed core against a fixed core |
| [33359](33359/) | log29 (3408138/567) | terrain step up: the switch re-engages on a stale terrain offset and the source-change reset pulls the height down (ground-to-ground -0.45/-0.46 m) | validated 2026-10-06 on the beta at this PR's head plus the logic of 5d98f8175f: +0.10/-0.35 m; regression set log30 (571), log31 (575), log35 (582), log280 (327), log281 (331) unchanged |
| [33478](33478/) | log35, log38, log41 | velD fusion on a baro-only vehicle with no velZ source | logs **resolved and fingerprinted 2026-09-10** under `support/bragg/TD-Matek-5Inch/`, all replayable. Re-run still owed, and subject to the same XKFA limit: `XKFA.VFuse` cannot be observed on these logs, so the fusion has to be judged from XKF1.VD instead |
| [33484](33484/) | log A, log B, log C | the single-axis flow lockout the recovery is for | 500 ms threshold tuned on these; re-run 2026-09-10 as a before/after over the review fixes, `bfb41f69a1` vs `c3db493b9a` (amended to `853f3f2177`, comment only) - B loses one reset to the unhealthy latch gate, A and C unchanged |
| [33484](33484/) | log7 | the recovery misfiring at the flow tilt gate | re-run 2026-09-10 on the PR's own tree: the gate suppresses **nothing** there, 2 resets either way. The 3 -> 0 is on the beta branch with #33359 and #33478 stacked. Re-run again at `c3db493b9a` (now `853f3f2177`): still 2 resets, but now **3 deferrals reported** where the tree was previously silent |
| [33507](33507/) | log311, log66 | accel-Z bias, PD drift over the hover | logs **resolved 2026-09-10** (see the private index); re-run **attempted and blocked** - Replay cannot emit XKFA when replaying these logs, so the bias state is unobservable. PD drift, the available proxy, does not separate: -0.0029 to +0.0005 m/s across pre-fix/fixed and Q 0.05/0.30 |
| [33507](33507/) | log19 | the bias state learning a start-up transient on the ground and freezing confident on the floor | **validated 2026-09-29** for `129d602eb6` on log19's own firmware with #34457's velocity clear removed: flow-lane worst height gap 4.63 -> 1.43 m, AGL KF level height error 0.61 -> 0.44 m. Supersedes the row above as the flight for the bias state: log19 logs XKFA, so the format-table block does not apply to it |
| [33507](33507/) | log22, log25 | the floor gate never closing because the range finder offset correction lifts the on-ground reading off the floor (log22 nose-up, log25 nose-down) | **validated 2026-10-02** for `06dd0ef90e`'s change on the beta (`0f669176` + the change): bias std at liftoff 0.016 -> 1.0 and 0.028 -> 1.0, flow lane worst height against the range finder over 18 s -1.38 -> +0.58 m and -0.68 -> -0.30 m. Supersedes log19 as the flight for the gate, which passed there only because nothing lifted its reading. **Replayed at `df974dddee` 2026-10-02, not shown:** both arms held the bias std at 1.0 on log22, log25 and log26, so the change could not be seen. The explanation first recorded here, that master discards an out-of-range-low reading on the ground, is **wrong**: master substitutes `rngOnGnd` while disarmed (`readRangeFinder()`'s `onGround` branch), and that branch does not set the new `onFloor` flag (a /pr-review finding the same day). Why neither arm fused on the ground is not established |
| [33585](33585/) | log308 | AltHold demotion at the rangefinder ceiling | validated pre-submission at an earlier head; force-pushed to `a4d8966c85` 2026-09-10, then `4fd131e6bf`, then `36f86f06eb` 2026-09-11 (terrain-database flow scale gated on `terrainAltUsable()`) and **still not re-run**. Two heads behind, and the new commit is on the flow scale path log308 exercises. Five commits behind by 2026-09-15 (`de33b1f5a4`, `76f3428d1a`, and three 2026-09-15 commits, pushed as `7050b23964`, `67caf21bc4`, `e18c7d6fc3`); log308 did not resolve under the log roots on the machine used, so still not re-run |
| [32972](32972/) | log7 | finding 6, the height floor blocking a correction in cruise | **owed** - not run |
| [pending-aglkf-floor](pending-aglkf-floor/) | log9 | the AGL KF velocity winding up on the ground, and the +2.21 m takeoff height step it causes | **validated 2026-09-21** at `8461433db6`: samples with the height on its floor and velocity below -1 m/s go 1313 -> 0 on core 0, worst floor velocity -9.25 -> -0.71 m/s, unexplained height step 2.17 -> 0.43 m, height error against the range finder over the first seven seconds of flight -0.93/-2.39 -> -0.40/-0.72 m. Replay cannot reach the ground-effect release half: it feeds the recorded `takeoff_expected` and never exercises that path |
| [34457](34457/) | log19 | the AGL KF bias fitted to the start-up transient and then frozen confident on the floor (std 0.20 -> 0.016), which sinks the flow-only core 1.0 m after a gentle takeoff | **validated 2026-09-29** at `5adc2ea0` + `d42f9dc86d`'s change: baseline reproduces the flown cores to 0.000 m; core 101 worst gap to core 100 -1.00 -> +0.28 m, AGL KF level height error 0.083 -> 0.037 m RMS. Checked against log18, 20, 21 (unchanged) and log5, log7 (ground velocity unchanged); log9 and log12 did not resolve on the machine used. The gate moved to #33507 before the push, as `129d602eb6`; #34457 is `5a086b2cd9` on top of it |
| [34457](34457/) | log27, log28 | the AGL KF coasting up off the ground after a landing with the range finder below its minimum, then going invalid; a touch-and-go re-initialising it | **validated 2026-10-02** for `7568122335`'s hold on the beta (`caafe615` + the identical hold): log27 landed height 1.61 -> 0.05 m, invalid samples 176 -> 0; log28 bias std one second into the second takeoff 0.977 -> 0.018; log22 in flight byte-identical, log25 AGL height within 0.07 m. **Validated at the head 2026-10-02** (`45852b4417` against `7505d332d9`, core 100/101 decoded by hand because the beta logs' XKFA format differs from master's): log27 second landing 1.52 -> 0.05 m, invalid 176 -> 0 of 209; log28 touch-and-go invalid on the ground 68 -> 0 of 97 and in the first 2 s of the second takeoff 5 -> 0 of 22; log22/25 AGL height mean within 0.03 m |
| [34457](34457/) | log27, log28 | the AGL KF coasting up after a landing, for the coast stop that replaced the landed hold | **validated 2026-10-02 at `18276345bf`** against `7505d332d9`: landed height while still valid 0.16-1.14 -> 0.06-0.17 m; in flight and every takeoff unchanged on log22, 25, 27, 28. Supersedes the row above, which measured the abandoned landed hold |
| [34292](34292/) | log12 | the focus floor holding and releasing, flown with FLOW_HGT_MIN at 2.0 m | **run 2026-09-21**, and it went against the inflated value: with `minHeight` cut to the ground clearance so the flow below 2 m is fused, the flow lane's velocity error against GPS improves from RMS 1.60 to 1.01 m/s through the climb window and 2.25 to 1.67 through the descent, above-floor windows unchanged. Discarding good flow costs accuracy - the parameter's own "no higher than the sensor's focus limit" measured. The churn guard itself is still unexercised: the pilot disarmed 0.7 s after touchdown |
| [34292](34292/) | log67 | the near-ground flow floor | partial; the record notes replay does not reproduce the disarm path. Head 337cf08df6 withholds the zeroed sample from the terrain estimator, which is inert on Copter (EK3_FLOW_USE=1) so log67 is unaffected, but a Plane log would be needed to exercise it. Head `2714d632d1` (2026-09-29) changes comments and default arguments only on the estimator side, so neither row is owed a re-run; the AGL KF alternative the dev call asked about was measured in SITL and rejected, see the README |
| [34361](34361/) | log7 | getHAGL reporting nothing while the filter flies on a database AGL | **not applicable** - see below |
| [32553](32553/) | log200-log206 | terrain offset after ground effect clears | not run; SITL A/B 2026-09-15 shows the reset needs the takeoff window held until above GNDEFF_ALT, which Replay cannot show because it re-feeds the recorded `takeoff_expected`. Superseded 2026-09-15 (later): the flown-config SITL rig puts the error in baroHgtOffset, not terrainState, and log200-log206 are not on the primary machine |
| [32553](32553/) | log224 (3408138/260) | post-landing 3 m height error in the flown configuration (EK3_RNG_USE_HGT 3) | **not replayable in the air**: the logger dropped 37% of DAL frames from arming (dropped counter 0 -> 72449), so Replay bifurcates within 80 ms of the rangefinder coming into range; the ground phase replays. Needs a new flight with LOG_REPLAY on and the high-rate PID/rate log bits off |
| [32768](32768/) | log3, log12, log21 | baro temperature drift across an arm | not established |
| [33498](33498/) | log53, log54, log56 | Z gyro bias with no yaw source | not run; the 2026-09-15 guard change (pushed squashed as `97661a3b2d`) owes a replay, log roots unavailable on the machine used |
| 34933 (issue #34932; no record directory yet) | T25 hand launch, 5b70a271 (2818322/36) | the flow Z gyro bias mask (#33498) leaving P indefinite at the first flow fusion, after which baro height fusion was refused | **validated 2026-10-29** at `60db78a7a0` (head now `47d399e569`, a comment and message amend) on master's EKF (refused fusions 2460 -> 0, P positive definite throughout) and at the beta port `407e331247` (now `c114af0f71`, same amend) (every baro height fusion accepted, height variance under 0.9 m^2, post-crash attitude level). The master replay's XKF1 does not parse, as the beta log's FMT is reused; XKV1 and the refusal counts are the evidence there |
| 34933 (issue #34932; no record directory yet) | T25 `308a7e73` (2818322/43); TD25 operational `0e2c9772` (2818322/165) | first flights with the fix; the old board's flight on the unfixed build | 2026-10-29: `308a7e73` flown, three ground take-offs, no refused update and P valid (the unfixed EKF on the same log: 341 indefinite steps in handling before the arm, no refusals). TD25 `0e2c9772`: the flown filter diverged while disarmed in handling before the first arm (height variance 4.6e5 m^2) and forced a reset; the unfixed beta EKF refuses 469 height updates there, none in flight; fixed, none |
| [32471](32471/) | log197, log198 | the hover Z-bias measurement | the A/B harness ran without replay records. The 2026-09-15 Replay inhibit fix (pushed as `18511cd9f2`) is a defect in what the flight writes: a log flown at `9b852c9464` with bit 2 already lacks the set event, so no existing log can show it; the Copter.Replay AccelBiasInhibit bit covers it. 2026-09-29 (`c9f68beab8`): the learner re-seed on arming and save-only-if-learnt are vehicle code, which Replay does not run; the `Pmut` change is a compile fix with no behaviour change. Nothing new owed. 2026-09-30 (`b8ad09e9cb`): the AHRS accel bias change is outside the EKF, which Replay does not re-run; the covariance change is zero unless bit 1 is set and armed, and log197/198 carry no replay records. Nothing new owed |
| [32473](32473/) | T25 `308a7e73` runaway (2818322/45) | the #32471 release restore firing on an acro exit and learning a 1.1 m/s velocity error as -0.8 m/s/s accel Z bias | **validated 2026-10-29** at the beta port of `0d693fa234` + `57efcebaec`: identical to the flight to 109.2 s, then the bias holds (0.17 to 0.13) where the flight jumped to -0.82 |
| [32473](32473/) | log7 (SFD-O4) | 134 s of ACRO on a build carrying the acro inhibit | **owed** - replay with the inhibit events suppressed; log root not reachable 2026-09-15. Supersedes this PR's entry under "no flight log applies" |
| [33568](33568/) | not named | the GPS-then-flow Loiter flight behind the PR body's scaler plot and "bit-identical" claim | **owed** - the flight is not named in this archive or the flight analyses; a SITL-log Replay A/B stands in (2026-09-15, see README). A second estimator change since, `02faf4127d` 2026-09-29 (`!gpsVelUsed` on the AID_ABSOLUTE -> AID_RELATIVE edge), is **not replayed** either; it only changes a flight fusing GPS, drag, airspeed or external velocity when position is lost, so the flight to replay it against is one of those, not the Loiter flight |
| [34456](34456/) | log11, log14 (SFD-O4) | a source set selection that reported success while the lane it named never flew | **owed** at `0b1f1fb7ff` (2026-09-29): setPosVelYawSourceSet now refuses, before the DAL event, a lane that does not exist or cannot follow while armed. log14 flew with `EK3_OPTIONS` 62 (bit 1 set) and every selection was accepted, so a replay should reproduce the flown cores unchanged; that is the check owed, not a demonstration of the refusal, which only SITL (EK3_SourceSetSelectsLane) shows |
| [34851](34851/) | log54 (SFD-O4, 3408138/624) | the ground offset, and the flow lane's relative position with it, dropping at the fall back to baro after a touchdown on range finder height; EKF failsafe 60 ms before land complete | **validated 2026-10-22** on the beta it flew (`0e2c97724d`) with the beta port of `da86aaa70f`'s change: replayed core 1 held relative position to disarm where the unfixed replay lost it at 371.085, the instant the flight did; XKF1 and XKF5 on both replayed cores identical to the unfixed replay in all 7956 records. Master's own EKF not replayed: the low hover on range finder height that set it up is beta-only. Not the same file as #33498's log54 |
| [34851](34851/) | log57, log58, log59 (SFD-O4, 3408138/629, 632, 633) | the same gap on landings flown without and with the beta port | **validated 2026-10-29**: without the change the flow lane loses position 0.78 s before land complete on log58 and 0.3 s before disarm on log59 (replay at `6d7543612b`); with it both hold (flown, `59386e92`). On log57, flown without it, the change removes five in-flight position blips and moves the touchdown loss 3.9 s later, still before a 7.75 s switch disarm |
| [34630](34630/) | none applies | output-only: the lane status read by the OSD, and an option gating a statustext | **not applicable** - no estimator state or fusion changes. With `EK3_OPTIONS` bit 6 set the reset statustext is gone, so a 33484 Replay sweep must run with bit 6 clear to keep its reset count |
| [32471](32471/) | log63 (SFD-O4, 3408138/643), flight 1 | applying the stored total with bit 2 clear double-counts the ground bias the EKF learned disarmed | **run 2026-10-30** on the beta `52b1d36f`'s EKF (Replay at smallfastdrone `0cb49e7dfb`), reproducing C=0/1 exactly, with the correction rewritten in RISK and bit 2 emulated by inserted REV3 events: height error rms over the first 20 s, core 0/1, as flown 0.14/1.10 m, none 0.12/0.65, total with bit 2 0.33/0.75, stored delta 0.11/0.54. A flight at 15 is owed |
| [33585](33585/) | log61 (SFD-O4, 3408138/639) | the SRTM flow scale height collapsing to `rngOnGnd` when looked up at a drifted flow lane's position | **run 2026-10-30** on the beta `52b1d36f`'s EKF: reproduces core 1 to 0.1 m/s through 256 s; core 1 at the Loiter switch (GPS 13.4 m/s) 0.9 as flown, 6.8 with bit 2 off, 28 with RTER stripped. No fix written |
| [34941](34941/) | log61 (3408138/639), log65 (3408138/646) | re-entering AID_RELATIVE after the 5 s flow timeout zeroing a velocity that was right | **run 2026-10-30** for `d2bebe7f32` (master branch `pr-ekf3-flow-reentry`) through a beta port: flow core speed error rms 9.5 -> 4.0 m/s (log61) and 9.2 -> 2.6 m/s (log65), worst position error 466 -> 313 m and 333 -> 95 m, aiding timeouts 4 -> 0 and 6 -> 0; log63 (643) identical. Master's own EKF not replayed (the beta logs' formats). log61's terrain path only partly tested: Replay re-feeds the terrain heights the flight looked up. **Re-run 2026-10-30** for v3 (`pr-ekf3-flow-reentry-v3` `8412571a33`, beta port): logs 61, 63 and 65 identical to v2's replay (0 EKF records differ), so the figures stand for v3 |
| [33484](33484/) | log65 (SFD-O4, 3408138/646) | the first lockout resets provoked in flight, each repairing a velocity zeroed by a re-entry | flown on `52b1d36f`; **not replayed**. A replay without the recovery would show what each reset saved |
| [32471](32471/) | SFD-O4 log26, 28, 29, 30 (two flights), 50, 54, 63 (3408138/562-643); TD25 T1F2, T1F3, T2F2, T2F3, T3F2, T4 (two flights), grass (2818322/115-132) | the stored hover Z-bias as a total against the motors-on delta, each predicted from the previous flight | **run 2026-10-30** on the beta `52b1d36f`'s EKF with RISK and RFRN patched: SFD-O4 flow core hover rms none 0.39, total 0.47, delta 0.30 m (total worse than none by >0.1 m on 3 of 8, delta on 0); TD25 cannot separate them (arms before learning a ground bias) and +0.02 applied was no better than none (0.64 against 0.61 m). The learner itself is vehicle code and not replayed; the delta branch is `pr-vrf-core-delta` `4464fa06e7`..`b4a8e0f7b0`, rewritten as `pr-vrf-core-delta-v2` (`9479937c24`..`0124a93a3d`) and `-v3` (`85dbca9896`..`04e501e13d`, same code) after review: v2 changes only what is learned with bit 2 set, and these flights flew `ACC_ZBIAS_LEARN` 8, 10 or 11 (bit 2 clear), so the sweep stands for it |
| [34942](34942/) | T25 `0cb49e7` vertical runaway (2818322/52); T25 `308a7e73` runaway (2818322/45) | arms after an in-air disarm and a clipped landing with the EKF still descending 1.1 to 4.3 m/s, which the dead on-ground height filter could not refuse | **validated 2026-10-30** on refresh12 `2e2936166d` with the head's (`a1fbfbcdc7`) EKF changes: all 5 such arms refused (3 on the height error, 2 realigning after a reset it triggered); before the change the filter read 0.00 at all 52 arms |
| [34942](34942/) | regression set: T25 2818322/36, 43, 49; TD25 2818322/165; SFD-O4 3408138/624, 628, 629, 632, 633, 639, 643, 646 | false refusals and forced resets on the ground | **run 2026-10-30**, same build: 9 of 27 other MicoAir arms refused (8 re-arms within 4 s of a disarm), 0 of 20 on SFD-O4, 7 forced resets on the ground on the MicoAir logs |

## Where no flight log applies, and why

Recorded so nobody looks for one. "No log" here is a conclusion, not a gap.

| PR | why |
|---|---|
| [34360](34360/) | the sign error is 2 x the terrain height above the EKF origin, so it is exactly zero at a field where the origin sits on the ground - which is every flight in this archive. Only SITL over relief exposes it |
| [32232](32232/) | found by #33585's autotest, not in flight. Still true at `8bec444e50` (2026-09-11); the autotest itself changed, see that README's sampling note |
| [34305](34305/) | an uninitialised read, demonstrated with a poisoned struct |
| [34209](34209/) | autotest only; fails on master, passes fixed |
| [32473](32473/) | gates the same terms as #32471 and borrows its SITL A/B. **Superseded 2026-09-15**: log7 (SFD-O4) flew 134 s of ACRO with LOG_REPLAY=1 on a build carrying the inhibit, so a log does apply - see the record above |
| [33338](33338/) | closed experiment |
| [33497](33497/) | needs a DroneCAN flow node, which SITL does not have |
| [34363](34363/) | logging only, no estimator behaviour |

Two entries above say "not applicable" rather than "no log", because a log
does exist and Replay still cannot answer:

- **[34361](34361/)** - `getHAGL()` has no consumer inside the EKF. Every
  caller is vehicle code, which Replay does not run, so a Replay computes the
  corrected height and reports nothing. log7 is still the flight that exposed
  it; SITL is what validates it.
- **[34362](34362/)** -
  Replay re-feeds the `takeoff_expected` and `touchdown_expected` bits the
  flight recorded, through `log_RFRN`, so a vehicle-side gate fix cannot
  appear in it. It can show what the EKF-side floor cost, which is #32972's
  outstanding item above.

## Keeping this current

A later flight usually covers a mechanism better than the one that first
exposed it - a cleaner configuration, a longer window, replay records the
first one lacked. When that happens **move the row and say what it
supersedes**, rather than adding a second row and leaving the next reader to
guess which to run:

```
| [33484](33484/) | log7 | ... | supersedes log A/B/C for the tilt-gate case |
```

The first flight stays named in the PR's own record - it is what the finding
was made on - but this file names what to check against *now*.

### Sweep of 2026-09-10

Reconciled every EKF PR's head against what its record claims. One real
divergence: **#33585 was force-pushed to `a4d8966c85`** and now carries eight
commits including #33478's three, so its "validated pre-submission" replay
status refers to a head that no longer exists.

The same sweep found the stack converging: **#34360, #34361 and #33585 all
modify the same four lines** of the SRTM block in `FuseOptFlow`, each
differently. `git merge-tree` confirms #34360 conflicts with both. #33585
also still carries its own copy of the sign fix, which #34360 now duplicates,
and a `terrain_srtm_alt_ms != 0` guard on `terrain_srtm_alt_valid` that
neither #34360 nor #34361 has - a master defect of the same class as the
sign, currently fixed only inside the option-bit PR.

Three things put a row out of date, and all three should be caught in the
same session that causes them:

- **A new flight** that exposes the same mechanism more directly.
- **A change to the code the log covers.** Re-run the Replay and update the
  status column; "validated pre-submission" is a claim about a head that has
  since moved.
- **A log that gains or loses replay records.** A flight flown without
  `LOG_REPLAY` cannot be used, however good the data is, and that is worth
  recording rather than rediscovering.

## Retired local branches (2026-09-10)

Two stale local branches were deleted after their content was confirmed
superseded by the pushed remotes. SHAs recorded here in case anything is
ever wanted back before gc reclaims them:

- `pr-rng-aglkf-terrain` at `66eb1ae2dc` (3 commits on a base 640 behind,
  missing the PR's 4th commit) - superseded by `andyp1per/pr-rng-aglkf-terrain`
  at `640cd4a5fc`.
- `pr-ekf3-aglkf-veld` at `cad74d9359` (2 commits, pre-rebase) - superseded by
  `andyp1per/pr-ekf3-aglkf-veld` at `e21558d163`.

Both were hazards rather than backups: publishing by that branch name
without checking would have sent the wrong tree to the remote.


## Replay cannot show the AGL KF on these logs (found 2026-09-10)

Replaying any of these flights against the upstream branches produces **no
XKFA at all**, so the AGL KF's own states - height, velocity, bias, and the
`VFuse` flag #33478 is judged by - are invisible in the output.

The cause is not the option bit and not the feature flag. Both were ruled
out:

- A control run proves `--parm` reaches the replayed EKF:
  `--parm EK3_ALT_M_NSE=50` moves the replayed core's `XKF4.SH` from 0.0777
  to 0.0170 while core 0 stays at 0.1437.
- A compile probe on `EK3_FEATURE_OPTFLOW_AGL_KF` reports enabled, and
  `AGL_ABIAS_P` is present in the Replay binary. (A `strings` check for
  "XKFA" returns nothing, but that is a false negative - the format name is
  not stored as a standalone string. Do not use `strings` for this.)
- `Log_Write_XKF5` runs for the replayed core (790 messages at C=100), and
  the XKFA block sits in the same function immediately after it.

What actually happens is that **Replay inherits the input log's format
table**. These logs were recorded on the fork, where the AGL KF is XKF6 at
message id 49; there is no XKFA slot to write into. Confirmed on two
independent logs (log66 and log311): both carry identical fork FMT tables
(`XKF0..XKF7, XKFD, XKFM, XKFR, XKFS`) and neither replay declares XKFA.

Consequences worth carrying:

- The Replay sweeps this archive cites for #33507 were necessarily taken on
  the **fork** build, where the message is XKF6. They are not reproducible
  against the upstream branch, and a maintainer following the record will
  get an empty result.
- Any future AGL KF replay evidence needs either a log recorded by firmware
  that already declares XKFA, or a metric that survives in XKF1/XKF5.
