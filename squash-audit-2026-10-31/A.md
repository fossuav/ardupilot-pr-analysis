# Squash audit A: #34942, #32471, #32473, #34941 (2026-10-31)

Analysis only: nothing squashed, committed or pushed.

**Evidence**
- Today's SFD-O4 logs 66-71 (`ea8cef60`, the same code as `f93bd10a`).
- The Q25 logs on `0cb49e7d` (topup5). These carry none of #34942 or #34941, and none of #32471's v3.
- The 2026-10-30 audit, and each PR's record.

**Builds and dry-runs**
- Presence in each flown build is by subject plus stable patch-id: `presence.py` and `A_presence.txt`.
- The A/B Replays were built in `tfix-ab-34942b`: refresh12 `f93bd10a6f` with one change reverted uncommitted (`build_ab34942.sh`, outputs in `ab34942/`). Base matches the flight to 1e-7 (log68 checked).
- Fold feasibility was checked with `dryrun.py`: cumulative `cherry-pick -n` on a detached HEAD, then the final tree compared with the PR head, submodules ignored. No builds were run per group.

## #34942 (10 commits, all first flown today)

| commit | subject | fixes | flown | verdict |
|---|---|---|---|---|
| d6825422d5 | fix on-ground height innovation filter never updating | base | carried today; no fix on top | keep |
| f2b487cb55 | report a height error as the pre-arm reason | base | no refusal today, so the report never printed | keep |
| 4d0a453b5d | ground height test without a vertical velocity | base | 8 arms, none refused | keep |
| c7fc88ce75 | filter rejected height samples on the ground | base | not separately measured | keep |
| bf1ea90b4e | keep a shock from holding off the stillness check (5) | base | **Flown.** With it reverted, Replay differs on all six logs. Core 1 yaw moves 0.14-0.29 deg from 5.34 s, at every boot. log66 core 0 yaw moves 0.57 deg at 61.4 s, and core 1 yaw 3.1 deg and pitch 1.8 deg around 264-313 s (VD 0.019 m/s, PD 0.07 m). Nothing wrong was seen. | keep |
| 7cf54da6dd | skip the ground height test while falling | base | not run: no re-arm while falling | keep |
| 21a8e3a683 | reset an impossible velD on coming to rest (G) | base | not run: no reset at rest, as flown or with B reverted | target of B |
| 3da7a8cf2e | autotest | test | n/a | keep |
| dc76e048a6 | take the static yaw reference before it is first fused (A) | fixes 5 | **Not run.** Reverting it leaves all six logs identical on both cores, since SFD-O4 has a compass. It acts only with no yaw source (the Q25). | **stays on top**: 5 has flown and A has not |
| 2a52c965e2 | no velocity reset at rest while a measurement is fused (B) | fixes G | **Not run.** Reverting it leaves all six logs identical, since G never reached a reset. | **squash into G**: G is unflown |

Correction: bf1ea90b4e's message gives its SFD-O4 effect as "on three [of eight flights], each once on the ground, by at most 0.05 m/s and 0.3 m". That message does not mention the yaw shift at every boot: today it moved core 1's yaw by 0.14-0.29 deg from EKF start on all six logs, as the check now reads still from its first sample. The VD and PD figures still hold.

Proposed list, 9 commits:
1. d6825422d5
2. f2b487cb55
3. 4d0a453b5d
4. c7fc88ce75
5. bf1ea90b4e
6. 7cf54da6dd
7. 21a8e3a683 + 2a52c965e2, with the message extended
8. 3da7a8cf2e (test)
9. dc76e048a6, on top until a flight with no yaw source runs it

The dry-run applies, and the final tree equals `2a52c965e2`.

## #32471 (50 commits; last squash 2026-09-30, `b8ad09e9cb`)

All base commits are in every flown build since `0e2c9772` and earlier. The table lists only commits added after the 09-30 squash.

| commit | subject | fixes | flown | verdict |
|---|---|---|---|---|
| a7fdc4d09b | applied hover Z-bias added to the accel bias AHRS removes | fixes f1b61c9cf8 | **Flown** by configuration: apply on and correction non-zero while armed, in log63 (10-30, -0.029/-0.035) and logs 67-71 (0.025-0.030). Verified by today's item 3. | **squash into f1b61c9cf8** |
| 7e0882eb10 | hover Z-bias taken off the covariance prediction | fixes f1b61c9cf8 | **Flown**, same flights; part of the RISK A/B that moved log68's core 1 from 0.59 to 0.42 m | **squash into f1b61c9cf8** |
| 9a9f3a8aed, 235e1c1c19, ae81b5886d | AHRS accel subtest, arm-event poll, re-indent | tests | n/a | squash together (unflown tests). Folding 235e1c1c19/ae81b5886d into the original test commits conflicts. |
| da4ec5479f | AP_DAL: say whether an EKF3 event was written | plumbing | n/a | **keep separate**: byte-identical to #34456's 6f7bcbeb85 |
| 19206748ae | log the accel bias inhibit until the DAL takes it | fixes 80ab66a2dd | **Not run.** It differs only when an event is refused or a log starts after the set. Every inhibit in logs 69-71 was written at once: log71 at boot (5.05 s) and arming, log69/70 at acro entry and exit. It changes only what reaches the log. | stays on top |
| 01227784b6 (+ test 1c14ca0a3e) | save only the hover Z-bias each IMU learnt this flight | fixes 2729bac582 | **Not run.** It needs one IMU that learnt nothing while another did. SFD-O4's two IMUs always learn or skip together: log70 learnt nothing on either and kept both values, which the old single flag also does. | stays on top |
| feddc0eea2 | AP_DAL: say whether DAL data is being logged | plumbing | n/a | keep separate (DAL plumbing) |
| 3973add04c (+ test d9e7d85f5c) | log the inhibit again in a restarted log | fixes 19206748ae | **Not run.** log71 is a boot log; no GCS erase was flown. | stays on top |
| 85dbca9896 | learn the hover Z-bias as the change since arming (v3) | redesigns 2729bac582 | **Flown and verified.** log66 saved end minus arming (item 2). The apply A/B took 0.13-0.17 m off core 1 (item 3). log71 learnt the whole bias with bit 2, AZ 0.00 at arming. | **cannot fold**: moving it below 01227784b6 (unflown) conflicts at 2729bac582. Stays its own commit. |
| 117508173e | INS doc: VRF Z bias as the motors-on change | doc for v3 | n/a | keep after v3. Folding it into an earlier INS commit applies (8659291d12), but would describe v3 before v3. |
| 04e501e13d, 54d41e98c1, 5afa8d69fb | v3 test, platform step-off, bit 2 flight reboot | tests | n/a | squash together. Folding 54d41e98c1 into e6b4378803, or 5afa8d69fb into f131b04087, conflicts. |

Proposed list, 44 commits. It is the current order with these changes, and every other commit unchanged:
- f1b61c9cf8 absorbs 7e0882eb10 and a7fdc4d09b, with its message extended to say AHRS and the covariance see the correction.
- 9a9f3a8aed + 235e1c1c19 + ae81b5886d become one autotest commit.
- 04e501e13d + 54d41e98c1 + 5afa8d69fb become one autotest commit.

The dry-run of all six moves together applies, and the final tree equals `5afa8d69fb`.

Still on top: 01227784b6 (+1c14ca0a3e), 19206748ae, 3973add04c (+d9e7d85f5c) and 85dbca9896 (+117508173e). da4ec5479f and feddc0eea2 stay as plumbing.

## #32473 (5 own commits, on #32471's `d9e7d85f5c`)

| commit | subject | fixes | flown | verdict |
|---|---|---|---|---|
| d3b5890246 | ACC_ZBIAS_LEARN bit 3: inhibit in acro | base | **Flown**: REV3 16 at acro entry while armed (log69 78.07 s, log70 155.07 and 255.07 s) | keep |
| 115050a65d | bit 3 test | test | n/a | keep |
| 968ea7d7e5 | keep the accel bias variance when an armed hold ends | base (#32473's only EKF commit) | **Flown.** Each armed acro exit (log69 265.07 s; log70 247.07 and 368.07 s) cleared the hold with XKV2.V15 kept at the 5e-8 floor. The disarmed release at log71's arming (38.28 s) restored it, 5e-8 to 3.9e-6, as designed. | keep: nothing in its subsystem to fold into |
| 3ca94847db | acro exit velocity error test | test | n/a | keep (a new test, not a fixup) |
| f945737262 | step off the accelerating platform before arming | test | n/a | **drops**: same added and removed lines as #32471's 54d41e98c1 |

#32473's head is stacked on #32471's d9e7d85f5c, from before v3. As a PR on its own it does not carry v3 (85dbca9896, 117508173e, 04e501e13d) or 5afa8d69fb. Only the SFD stack has both.

A restack onto 5afa8d69fb (or its squashed successor):
- conflicts in d3b5890246's ArduCopter/Parameters.cpp, the ACC_ZBIAS_LEARN description written by both v3 and bit 3. rerere holds refresh12's resolution and applied it.
- applies 115050a65d, 968ea7d7e5 and 3ca94847db cleanly.
- leaves f945737262 not applying, because its change is already there.

After the restack: d3b5890246, 115050a65d, 968ea7d7e5, 3ca94847db. No builds were run.

## #34941 (2 commits)

| commit | subject | flown | verdict |
|---|---|---|---|
| 8412571a33 | do not time out flow aiding while the tilt check withholds it | **Flown**: logs 69/70, 18 stretches over 45 deg for 5-31 s with flow on core 1, no "stopped aiding" or "started relative aiding" pair, core 1 never zeroed (log65 without it: six pairs). No A/B was run, since no squash decision depends on it. | keep |
| 247d0fb74e | autotest | n/a | keep |

Nothing to squash.
