# Squash audit B: the flow and AGL KF stack (2026-10-31)

Which commits still on top have now flown, from SFD-O4 logs 66-71 (`ea8cef60`),
logs 61/63/65 (`52b1d36f`) and the Q25 on `0cb49e7d` (`q25-0cb4`, `-ft3`, `-run`).
Every on-top code commit below was in all three of those builds (subject match).

Evidence comes from two places. The first is the logs. The second is a Replay A/B with
the change removed, built in `tfix-ab-32473plat` (outputs in `sq/replay/`):

- at the beta `a82986c8bd` for the SFD-O4 logs. Its base is identical to
  `Replay-beta` on log69, and that Replay matches today's flights to 1e-7.
  For log65 its core 1 leaves the flight at 7.4 s, so log65 is not used for core 1;
- at `0cb49e7dfb` for the Q25. That base follows `ft3` to 138.6 s and `run` to
  141.3 s. It leaves `q25-0cb4` at 14.7 s, so that log is not used.

| Variant | Change removed | Result |
|---|---|---|
| v1 | #33484 other-axis gate (`otherAxisPassed` forced true) | identical on every SFD-O4 log, including today's three resets; Q25 `ft3` differs from 130.22 s (below) |
| v2 | #34380 `4c3f1a7724` (beta `d3a5a35307`) | log69 core 1 HAGL/TOfs from 150.8 s, log70 from 274.8 s; all else identical |
| v3 | #34457 floor hold when the range reads too low (beta `21be728c9d`) | identical on all 12 logs: never engaged |
| v4 | #34292 one-second rest-reading clear (beta `393931390d`) | identical on all 12 logs: never acted |

## Corrections to the record

- **Lockout resets did fire today.** "No lockout reset fired in logs 66-71 (no
  'flow vel reset' message)" (`../ardupilot-pr-analysis/34630/README.md`, the
  2026-10-31 section) is wrong. `EK3_OPTIONS 94` sets bit 6, which quiets those
  messages. `XKF7.FVC` counts three resets on core 1: log68 at 77.57 s, log69 at
  181.27 s and log70 at 287.57 s. FLIGHT_VALIDATION's "no reset" at log70's
  228.24 s deferral still holds.
- **log65's floor hold was not this commit.** The 2026-10-30 log65 note credits
  #34457 with holding both cores on the 0.05 m floor for 23 s after landing. v3
  shows the range-reads-too-low hold never engaged there or anywhere, so another
  #34457 commit did that work (the floor clear `42de1d07f1` or the coast stop
  `d3df572550`).

## #33484

| Commit | Subject | Fixes | Flown | Verdict |
|---|---|---|---|---|
| `fab41a7cf9` | reset a flow lockout only on a sample the other axis passed | `020cdcdced` (base recovery, flown and squashed 10-16) | **Yes, once.** Q25 `ft3` at 130.22 s on the flown code. The flight's 5th reset is taken on a later sample than it would be without the gate: core 0 speed 0.66 against 0.31 m/s at 130.5 s, the same by 131.5 s, 0.10 m position at most. Today's three SFD-O4 resets and log65's are identical with or without it (the other axis passed each time). | Can squash into `020cdcdced`, with its test `dc8b045265` into `235e2dd016`. The evidence is that the gate acted as designed, not that the result was better: no GPS on the Q25. Andy's call. |
| `e0e4a38f57` | order the flow latch stores against the sensor bus thread | the latch in `020cdcdced` | **Cannot fly here.** The reorder only matters for a PX4Flow on its bus thread under multi-core Linux. SFD-O4 is DroneCAN flow (`FLOW_TYPE 6`), the Q25 is MAVLink (5), both ChibiOS. The disarm clear of `flowQualRecoverStart_ms` is a no-op on one thread: nothing reads the field until the latch sets again, and the latch zeroes it first. | Stays on top. |

After the squash, 9 commits become 7: the four shared SIM_FLOW_OFS/QUAL commits
unchanged, `020cdcdced`+`fab41a7cf9`, `235e2dd016`+`dc8b045265`, then `e0e4a38f57`.
**Stacking:** #34630 is built on this head, so it has to be rebuilt on the new one.

## #34380

| Commit | Subject | Fixes | Flown | Verdict |
|---|---|---|---|---|
| `4c3f1a7724` | time a flat-ground return on fused range readings | #33585's `0b7027979e` (the flat-ground return; its lines, flown and squashed 10-08) | **Yes, and verified.** log69 core 1, 150.8-162 s, range out of range high (over 15 m) at 15-30 m altitude. As flown, TOfs returned to flat ground and HAGL read 24-27 m, then 12.3 m when the range came good at 161.5 s (14.4 m). Without it, TOfs held -17 m, HAGL read 11.8 m, then 0.05-0.3 m at 159-161 s at 17 m altitude and 27 m/s, and 0.8 m against the 14.4 m reading. log70 at 274.8 s: the return came 0.5 s sooner. | Can squash. Its home is #33585's `0b7027979e`, which means rewriting #33585 and restacking #34380, which then drops it. Folding it into #34380's own `92d80cc32f` would mix code that isn't that commit's. Otherwise leave it as its own commit. |
| `801b551d56` | cover range readings the terrain gate rejects | test for `4c3f1a7724` | test | Goes with `4c3f1a7724`: into #33585's test `7f5f8ffe85` if moved down, otherwise stays with it. |
| `d1f9ef8d72` | note that a position reset leaves the ground location | comment in `updateFlatGroundAssumed()` | comment only | Squashes freely into the commit that holds that code (`4c3f1a7724`, or `0b7027979e` if moved). |

The shared #33585 commits (`4c036f5be8`, `0e008302ec`) stay unchanged.

## #34292

| Commit | Subject | Fixes | Flown | Verdict |
|---|---|---|---|---|
| `19b9e2bd9a` | clear the flow rest reading once no sample is stored | rest reading (flown, squashed 10-08) | **No.** v4 identical on all 12 logs, and no disarmed flow gap over 1 s in any of them. | Stays on top, with its test `8cd64105c4`. |
| `244d608769` | keep the focus floor off flow at a declared sensor height | floor | **No.** Rover only (`FLOW_HGT_OVR`), and `b43ace7296` removes it. | Squash with `b43ace7296`: both unflown, and the net change is "the floor is out of Rover builds". |
| `b43ace7296` | leave the flow focus floor out of Rover builds | floor | **No.** Compiled out of Rover only; Copter unchanged. | Takes `244d608769`. Stays off the flown floor commits. |
| `a0e43dce3e` | say Rover does not use FLOW_HGT_MIN | `358e199373` parameter | parameter doc | Squashes freely (into `358e199373`, or with `b43ace7296`). |
| `3917ef38f2` | replay a Rover log without the flow focus floor | floor, Replay-only | **No.** Vehicle builds compile it as true; Copter logs replay the same. | Stays, or folds into `b43ace7296` (both unflown). Optional; the ARCH-17 Replay gate reads more clearly on its own. |
| `a0ab050ad6` | SITL flow from a sensor mounted above the ground | SITL | n/a | Stays unchanged (separable SITL commit). |
| `c0498ea0d5`, `b582cc7fe7` | Rover tests | tests | n/a | `b582cc7fe7` folds into `c0498ea0d5`. |

The shared SIM_FLOW_OFS commits (`367ac1bd68`, `629245031e`, patch-identical to
#33484's) stay. After the squash: 27 commits become 24 or 23, with `19b9e2bd9a`
and its test still on top.

## #33359

The four gates (`0c2e335f61`, `3eeee55f04`, `b19254da42`, `4c332e6a20`), the
odometry gate `64ae3d5641`, and their tests. **Unchanged: stays.** The 2026-10-30
audit showed three of the gates changing flow decisions in flight, but
`0c2e335f61`, `3eeee55f04` and `4c332e6a20` also change the body odometry path,
and no flight has odometry (none today either). Splitting the odometry lines out
would let the flow parts squash.

Shared with #33478:
- `308cb9954c`/`771ba3a363` and `b6a25ee1a6`/`753c44a8a0` are patch-identical;
- `bd9c45c2bc`/`cece19aa78` are the same change adapted to each PR's options
  (#33478's also tests `AglKfVelForVelD`), so they will conflict when the second
  one merges.

## #34543

| Commit | Subject | Fixes | Flown | Verdict |
|---|---|---|---|---|
| `78aa029352` | take the AHRS semaphore for the EKF lane items | `cbda421ea8` (lane items, flown and verified 10-08) | **Yes, in the only sense a lock can.** It runs on every OSD frame in every flight since 10-16 (`OSD_TYPE 5`, `OSD1_EKF0/1_EN 1` on SFD-O4 today and on the Q25), with no stall: PM.MaxT 5.1-5.3 ms after boot, as before. | Can squash into `cbda421ea8`. |
| `edc6cb9dec` | show the flow sensor's signal strength on an EKF flow lane | new feature | ran every frame; what was drawn is unconfirmed | Not a fix: stays as its own commit, with its test `17f017fb8c`. |
| `a2f1de5edd` | keep the EKF3 lane status while DCM is active | `09f2c62741` (flown) | **No.** No DCM fallback in any log (the Q25's two "DCM" lines are pre-arm checks). | Stays on top, with its test `003ef442a9`. |
| `af50a66828`, `351aea9eaa` | test fixes (flash check, `SIM_TERRAIN 0`) | lane item tests | test only | Fold into the test commit each fixes (`92767a6d63` / `17f017fb8c`). |

Also reword the squashed-subject bodies of `d9e4277412` and `92767a6d63` (the
bot's minor). After the squash: 14 commits become 11.

## #34630

None of this PR's display commits has flown: what the OSD drew was never
confirmed. So its fixes fold freely into them:

- `17ead03a5e` and `7e63c513bf` (floor only with bit 3, and while latched) go into
  `623c5886fa`. Every flight had bit 3 set, so neither changed branch has run.
- `a7ac51780b` and `6b84dcfeb9` (descriptions) go into `a67dd5323c`, which wrote
  those lines.
- `057ca0f7d8` and `191ad8c36b` go into `d402ac272a`.
- `9a64b9bc5f` goes into `60b8bd1d79` (`git blame`: all 19 changed lines are
  `60b8bd1d79`'s).
- `f29c794577` (250 ms) goes into `afd12ac827`, and `32decd38b8` (its comment)
  into `e18433d773`.

The EKF side of the quiet option and the reset flag flew again today: three
silent resets with bit 6, as above.

If Andy did bench check 0d, ask whether `EK3_OPTIONS 86` showed no floor. If it
did, the floor display and `17ead03a5e` are verified together, and the squash
still holds. If only the 94 step was seen, keep `17ead03a5e` on top.

**Stacking:** this PR is built on #33484's `e0e4a38f57`, so it is rebuilt if
#33484 squashes. Its copies of #34543's commits predate #34543's rebase and do not
carry `a2f1de5edd` or the test fixes.

## #34457, #33507

Nothing on top. The hold commit `8ba98494bd` already carries the unflown
fused-reading arming (folded on 10-11, recorded on 10-13). v3 shows the hold has
still never engaged, so that commit's hold remains unflown. Nothing to squash.
#33507 is stacked on #34457 and has nothing on top of its own.

## #34456

Nothing on top, and it flew again today: selections armed and disarmed in logs
68-70 each reached their lane ("EKF3 lane switch" within 10 ms).
- `ff1223799d` (the AP_DAL standalone stub) is the build prerequisite for the
  EKF3 commit and changes no behaviour.
- `6f7bcbeb85` is patch-identical to #32471's `da4ec5479f` and stays as it is.

## Nothing to do

Each of these is its behaviour commit and test, with no fix on top:

- #33478 (the step hold `81f8ee534f` flew in log44 and is kept separate by
  design);
- #33585;
- #33568;
- #34851;
- #34933;
- #34362;
- #34363;
- #32553;
- #34783.
