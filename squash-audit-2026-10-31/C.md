# Squash audit, slice C: Copter, rate-thread and system PRs (2026-10-31)

Logs searched:
- SFD-O4 logs 66-71 on `ea8cef60`;
- logs 54-65 on `0e2c9772`, `6d754361`, `59386e92` and `52b1d36f`;
- the Q25 on `0cb49e7d` (three logs), `308a7e73` and `5b70a271`, and Q25v1 on `0e2c9772`.

Build carriage is by subject, with patch-ids checked for the commits that matter. Every 10-30 fix below has been in every flown build since `52b1d36f` (SFD-O4 logs 61-65, 2026-10-30), byte-identical. Two exceptions differ only by stack conflict resolution: #34210's `84f977c110` and #34696's `c7e372ac6e`.

Across all of those logs there are:
- no motor tests;
- no Throw (ModeNum 18);
- no land failsafe (`LAND_FS_OPTIONS` 0 on every airframe);
- no temperature-calibration learning (`INS_TCAL1_ENABLE` 1 everywhere, apply only).

## Corrections to earlier claims

- **The ESC.Err boot window says nothing about #31274.** `FLIGHT_VALIDATION.md` (2026-10-31, 0b) and `31274/README.md` contrast today's 0.7 s at boot with log65's 3 s. But log65's build (`52b1d36f`) carries the same #31274 commits as today's.
  - Builds without the 10-30 DShot fixes (log57 on `6d754361`, log59 on `59386e92`) show today's 0.7 s window (4.96-5.64 s).
  - The 3 s window belongs to `52b1d36f`'s boot, where ESC telemetry starts 2 s later (6.99 s against 4.96 s).
  - This fits the 0c result (`ESC_CALIBRATION 9` recovers 2 s) and is likely #32238's 10-30 rework. That part is not checked.
- **#29000's 0a "it was twice" is confirmed by A/B.** Builds without `fcc3339b2b` print "rate set to 2007Hz" twice at boot (log57 `6d754361`, log59 `59386e92`); builds with it print it once (log65 `52b1d36f`, log66 `ea8cef60`).

## #29000

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| fcc3339b2b | leave the fast rates unset until the rate thread is enabled | 4cc85b68cf | Flown. On a normal boot it drops the second "rate set to 2007Hz": twice on log57/59, once on logs 61-71. The tcal-park part needs learning, which has never run. | Fold into 4cc85b68cf |
| (base) 4cc85b68cf | switch off fast rate while doing temperature calibration | - | Not run: it acts only while tcal learns, and `INS_TCAL1_ENABLE` is 1 on SFD-O4 and Q25v1. Unflown. | Takes the fix |

After: `Copter: switch off fast rate while doing temperature calibration` (4cc85b68cf + fcc3339b2b), then `autotest: check the rate thread is off during temperature calibration` (fbf9c380f9).

## #31274

The base `cb66e83fde` and `3684d45ce3` have been in every flown build since log54. The takeoff check ran at every SFD-O4 takeoff (`TKOFF_RPM_MIN 1000`, and log66's "Takeoff blocked" shows the check active). ESC.Err was at or below 0.9% armed before takeoff, so it never blocked: it ran, and its decision never changed. Its fixes have exactly the same standing. `a9ae4cdc82` (the motor test) has never run.

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| 6fe73f3735 | SITL: add SIM_ESC_ERR_RATE | - | SITL only | Stays separate (fault injection) |
| 00d3d50182 | AP_ESC_Telem: report SIM_ESC_ERR_RATE from the SITL ESC backend | - | SITL only | Stays separate, after 6fe73f3735 |
| 0d7ac89ec9 | AP_ESC_Telem: only check error rates that are a percentage | cb66e83fde | Ran at every takeoff on logs 61-71, as the base did; never blocked | Fold into cb66e83fde: both have the same standing |
| 5db531fdc2 | AP_ESC_Telem: give the error rate percentage its own timestamp | cb66e83fde | As above | Fold into cb66e83fde |
| ed05baf35f | AP_HAL_ChibiOS: report the bdshot error rate as a percentage | - (no ChibiOS base) | Runs on every bidirectional DShot frame (SFD-O4 BDMASK 15, logs 61-71). No log signature against log57/59: armed Err of 0.0-0.9% before and after | May fold with the other three into one commit. Hold until the AP-Review blocker fix (in 715c381342's reset) is written |
| 2e53a6400b | AP_HAL_ChibiOS: count a failed DShot telemetry reply against its output | - | As above | As above |
| e2187aa2b1 | AP_HAL_ChibiOS: don't count the missing reply to a DShot command | - | Runs at boot (`SERVO_BLH_RVMASK 5` sends commands); boot Err is the same with and without (see corrections) | As above |
| 715c381342 | AP_HAL_ChibiOS: reset the DShot telemetry stats after a lost reply too | - | Runs on lost replies; the open AP-Review blocker is here (a dead ESC reads 0% after the reset) | As above; the blocker fix stays on top as unflown |
| eccb30a3c6 | AP_Motors: add get_test_seq_output_mask() | - | Motor test only, never run | Stays separate (helper). Move it before a9ae4cdc82, or the motor test fold will not build |
| 9efaf7eb79 | Copter: only warn in motor test about an error rate that is a percentage | a9ae4cdc82 | Not run: no motor test in any log | Fold into a9ae4cdc82 |
| 5f27cedfe2 | Copter: name the ESC that the motor test spins in its error rate warning | a9ae4cdc82 | Not run | Fold into a9ae4cdc82 (needs eccb30a3c6 first) |
| 4c00536edd | Copter: stop the motor test error rate check once the test is cancelled | a9ae4cdc82 | Not run | Fold into a9ae4cdc82 |
| 77f46482c4 | Copter: name every faulty output of a motor in the motor test warning | a9ae4cdc82 | Not run | Fold into a9ae4cdc82 |
| c11583c917 | Copter: bound the motor test error rate warning to one a second | a9ae4cdc82 | Not run | Fold into a9ae4cdc82 |
| 535181712d | Copter: document the ESC error rate check in TKOFF_RPM_MIN | - | Documentation | One Copter doc commit with the three below |
| 732a25b539 | Copter: say that TKOFF_RPM_MIN at zero also disables TKOFF_RPM_MAX | 535181712d | Documentation | Fold |
| c736ba44e9 | Copter: say which ESCs TKOFF_RPM_MIN checks for errors | 535181712d | Documentation | Fold |
| 4ae2a316c1 | Copter: say that TKOFF_RPM_MAX needs TKOFF_RPM_MIN set | 535181712d | Documentation | Fold |
| a0cd91585c | Plane: document the ESC error rate check in Q_TKOFF_RPM_MIN | - | Documentation | One Plane doc commit |
| d5c7a7697d | Plane: say which ESCs Q_TKOFF_RPM_MIN checks for errors | a0cd91585c | Documentation | Fold |
| defda06bc8 | autotest: test the ESC error rate takeoff check and motor test warning | - | Test | Takes the three below |
| a1d434498e | autotest: check the motor test names every output of a motor | defda06bc8 | Test | Fold |
| 40518bd547 | autotest: match the shorter motor test error rate warning | defda06bc8 | Test | Fold |
| db7371c4d8 | autotest: drop a reboot that context_pop() already does | defda06bc8 | Test | Fold |

After the squash:
1. AP_ESC_Telem: add an error rate limit to are_motors_running() (cb66e83fde + 0d7ac89ec9 + 5db531fdc2)
2. AP_Vehicle: fail the ESC takeoff check on a high ESC error rate (3684d45ce3)
3. AP_Motors: add get_test_seq_output_mask() (eccb30a3c6, moved up)
4. Copter: output error rate and rpm in motor test (a9ae4cdc82 + 9efaf7eb79 + 5f27cedfe2 + 4c00536edd + 77f46482c4 + c11583c917), reworded for the bot's body nit
5. Copter: document the ESC error rate check in TKOFF_RPM_MIN (535181712d + 732a25b539 + c736ba44e9 + 4ae2a316c1)
6. Plane: the same in Q_TKOFF_RPM_MIN (a0cd91585c + d5c7a7697d)
7. AP_HAL_ChibiOS x4 (ed05baf35f, 2e53a6400b, e2187aa2b1, 715c381342): as they are until the blocker fix, then optionally one commit
8. SITL: SIM_ESC_ERR_RATE (6fe73f3735), then AP_ESC_Telem: SITL report (00d3d50182)
9. autotest: changed takeoff blocked message (4ef30eefe0)
10. autotest: ESC error rate takeoff check and motor test (defda06bc8 + a1d434498e + 40518bd547 + db7371c4d8)

## #34210

`LAND_FS_OPTIONS` is 0 on every flown airframe (SFD-O4 logs 54-71, the Q25 and Q25v1), so the advanced land failsafe has never been active. Every commit is unflown.

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| bc5a6362d3 | wind the land failsafe ceiling down at any land speed | 84f977c110 | Not run (feature off everywhere) | Fold into 84f977c110 |
| aa2cf2ddcf | say what engages LAND_FS_OPTIONS | 84f977c110 | Documentation | Fold into 84f977c110 |
| 5be30dcfff | autotest: run LandFailsafeRunaway at the top of the land speed range | 93dcf216c0 | Test | Fold into 93dcf216c0 |

After: AP_Logger events (b649cfdd8c); Copter: add advanced land failsafe (84f977c110 + bc5a6362d3 + aa2cf2ddcf); autotest (93dcf216c0 + 5be30dcfff). The open should-fix (saturation feedback) can fold into the Copter commit too while the feature stays unflown.

## #34696

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| 571df9bdff | hold the EKF failsafe restore until there is a position | c7e372ac6e | Not shown. On the Q25 (`0cb49e7d`, `FS_OPTIONS 64`, `FS_EKF_ACTION 4`), the failsafe changed PosHold to VALT at 227.08 s and cleared at 249.68 s. The restore was pending until the pilot's switch at 282.72 s, but `hands_off` was false throughout: pitch rests at 1525 against `RC2_TRIM 1500`, `RC2_DZ 20`. `position_ok()` was true from 249 s, so the position gate decided nothing | Stays on top |
| 89a96878eb | autotest: cover the restore on a source set with no position | 0b02b0f800 | Test of 571df9bdff | Stays after 571df9bdff |

`c7e372ac6e` has flown: it set the restore pending and evaluated it (Q25 227-282 s), and cancelled it at touchdown (log54). It has never restored a mode in flight.

Finding: on the Q25 as set up, the restore can never fire, because its pitch centre sits 25 us off trim with a 20 us deadzone. That is a calibration point, but it also means a hands-off test that compares the stick against `RCn_TRIM` is fragile.

Nothing to squash.

## #32514

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| 32b818463e | hold the EKF failsafe count while the motors spool down after landing | 5eeb6356fa | Not run. All of the Q25's EKF failsafes on `0cb49e7d` (8 in q25-0cb4, 11 in -run, 9 in -ft3) began airborne, between the takeoff event and the landing. None began while landed or spooling down; each cleared about 1 s after disarm. SFD-O4 logs 66-71 had none | Stays on top |
| f272495d31 | autotest: a position lost as the motors spool down does not trip | 2de6865b39 | Test of 32b818463e | Stays after it |

Nothing to squash.

## #32270

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| ee9dc05040 | VALT snaps the full position target and scales its blend | bad5da6436 (blend) / b6f407d3dd (snap) | Half flown, as before. The loop-rate scaling of the blend ran in every Q25 VALT flight at `SCHED_LOOP_RATE 200` with `VALT_POS_EXPO 3` (`5b70a271`, `308a7e73`, `0cb49e7d`: VALT for most of each sortie). The offset snap has never run: no script offset, and `SURFTRAK_MODE 0` | Stays on top. To squash the flown half, split it: the scaling into bad5da6436, and the snap stays with 16e20eba19 |
| 16e20eba19 | held-offset test | - | Test of the snap | Stays after the snap |

Also flown (a base commit, nothing to squash): `74dc62ce7b`'s `FS_EKF_ACTION 4`, "EKF Failsafe: changed to VALT Hold Mode" at 227.08 s in q25-0cb4.

## #32475

The nine base commits (c2783234ce..f7a5aeb84f) were flown across about 30 drops on six airframes, before the 2026-09-04 rebuild. Nothing since: no Throw in any log searched. So the 18 Copter fixes of 10-30 are unflown fixes on flown commits and stay on top. The 25 test commits may fold among themselves, kept after the fixes; the README's pairs are c6e6484b22+041de0484b, 978b3999af+c2e8e0e66a and 1911cf40be+3904522d78. They must not fold into c8059d2ef1, which comes before the fixes they test. The AP-Review blocker (staying in THROW never starts horizontal control) is open, and its fix will be unflown too. Target is by topic.

| Commit | Subject | Target | Flown evidence | Verdict |
|---|---|---|---|---|
| 53519af9a3 | Copter: bound the drop descent gate in throw uprighting | 460066a714 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 1262253363 | autotest: check a drop arrested short of its descent target recovers | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 749f59a354 | Copter: restart a drop confirmation window that has not confirmed | c2783234ce | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| f33ae89841 | Copter: confirm a drop by its velocity change in constant position mode | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 8366268092 | autotest: check a held spinning vehicle is not a drop until released | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 0a4342601c | Copter: require a position while throw holds one | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 54160d9f31 | autotest: check an EKF failsafe acts while a drop holds position | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| ff1d69a53c | Copter: settle the throw source set before the next mode takes over | abcbfddb1e | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 0e31ea40ec | autotest: check the throw source set is settled at completion | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c856d6a1fd | autotest: make the throw spin tests check the vehicle recovers | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 14347eaea9 | Copter: restart the drop confirmation window across a navigation gap | c2783234ce | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 69aa9bab17 | Copter: start each throw afresh when it is armed again in throw | 2ca41b4091 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 182df1f14f | autotest: check a second throw armed without leaving throw starts afresh | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 23db59003d | Copter: keep plain GPS-free drop confirmation on the timer | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 9ea3911509 | autotest: tighten the held spinning drop test | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| e9eb61db8f | Copter: hold throw level on a position loss before a GPS-free mode | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| f52bc67df3 | autotest: check throw's EKF failsafe follows the next mode | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| b882070af5 | Copter: bound and announce the throw handoff's wait for a position | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 6c59cce12c | autotest: check the throw handoff's wait for a position | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 249d924c23 | Copter: name the throw uprighting timeout and document it for drops | 460066a714 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | behaviour-neutral (3000 stays 3000; comments): keep as one commit, or fold into 53519af9a3 |
| e46becb2f1 | autotest: check the throw spin tests are still spinning at detection | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 34ae6a25ad | Copter: decide throw's next-mode position need by mode number | 42f675ccd9 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| a58de9ac3f | autotest: check a stale AUTO submode can't skip the throw handoff wait | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 7283b680dc | Copter: let a new throw source set reach the EKF before the handoff | abcbfddb1e | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 5a29491c81 | Copter: set up each throw as entry does when it is disarmed | 2ca41b4091 | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| d24c031045 | autotest: check a re-armed throw is back on its throw source set | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c174d165e9 | Copter: make the throw comments say what the drop code does | c2783234ce | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | behaviour-neutral (3000 stays 3000; comments): keep as one commit, or fold into 53519af9a3 |
| d63c8868c5 | autotest: tighten the throw held-spin and EKF failsafe checks | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 5e6c1af447 | autotest: check held-spin detection before the held state it assumes | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 1154bffa6c | Copter: reset throw's direction state even while the throw set is kept | 5927d6c92c | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 1911cf40be | autotest: check an aborted throw leaves no yaw target for the next | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c6e6484b22 | autotest: check the stale-AUTO handoff wait came from this throw | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 978b3999af | autotest: recheck the held spinner for a detection after its checks | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| f65c724730 | Copter: reset throw's direction integrator when a spool-up aborts | 5927d6c92c | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 041de0484b | autotest: check the stale-AUTO handoff by its logged reason | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c2e8e0e66a | autotest: cover the whole held-spin hold from the vehicle's log | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 3904522d78 | autotest: narrow the aborted-throw leg to what it can see | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 9de2b82fbe | Copter: clear the throw yaw target along with the direction integrator | 5927d6c92c | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | stays on top (unflown fix on a flown base) |
| 60cee67154 | autotest: check the aborted throw had a yaw target to leak | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| d0b22fb813 | autotest: let the aborted throw's yaw target reach the log | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c57f083d21 | autotest: wait for the EKF itself to lose the re-armed throw's position | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| c38b657b8c | autotest: check the stale-AUTO handoff where no position comes | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |
| 3d634e4a5f | autotest: let the throw LOITER handoffs take over without a wait | tests (c8059d2ef1) | not run: no Throw (ModeNum 18) in any log since; logs 61-71, Q25 0cb4 x3 searched | fold with the other test fixups into one or a few test commits kept after the fixes |

After: the nine base commits as they are, then the 16 Copter fixes as they are, then the naming/comment pair as one commit (or folded into 53519af9a3), then the tests folded into a few commits.

## #32401

Flown today: "Arm pending" in log67 and log68, and "Arm pending: EKF bootstrap reset" in log67 at 29.87 s. It also flew on the Q25 (q25-0cb4 at 14.68 s, `ARMING_PEND_TIM 2`). The three commits are in three subsystems (AP_Arming, RC_Channel, Copter), so there is nothing to squash.

Finding: the bootstrap reset is this PR's (`4bc594f1c6` calls `reset_configured_backend()`).
- It fires on any pending-arm timeout, including while the EKF is only waiting for GPS. In log67 the GPS checks were passing, and the reset restarted EKF convergence, so GPS came 24 s late.
- It is not a DAL event, so Replay diverges at it.

## Nothing to do

- **#34209:** base and test only. Its path ran on the Q25, in unaided stretches after "stopped aiding" at 148.0, 226.2 and 308.6 s in q25-0cb4.
- **#34208, #34583, #34584:** feature commits, no fixups. #34584 contains #34583's three. Flown with the rate thread: `FSTRATE_ENABLE` 2 on SFD-O4, 1 on the Q25.
- **#34678, #34642** (SITL), **#30841, #31005, #32391, #32398, #33318, #33543, #33879:** no fixup commits.
- **#32398 and #33318:** each commit is in a different subsystem.
- **#34251:** its own two commits (Copter, Plane), already reworded. The branch's other 611 commits are its 4.7 base.

## Other people / bench only, noted

- **#31216 (iFlight Borg H7):** `2f220cecef` (hwdef: CAN1 silent GPIO) is a fixup of `dd1a670d95`. Both are bench-only, so it could fold. That's the board owner's call; no rewrite planned here.
- **#31770 (DFU bootloader, Andy's):** 11 commits. Five AP_Bootloader commits (b3603bea1e, ce51b26564, aa2f6f3ac0, 09d675fb6a, 9b6ecff7b3) read as iterations on 0a066350e3/d2b62c63b3. The bootloader never runs in a flight, so they may fold freely, if wanted.
- **#32238:** not in this slice (rishabsingh3003's), and not planned.
