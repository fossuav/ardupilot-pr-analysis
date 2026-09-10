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
| [33478](33478/) | log35, log38, log41 | velD fusion on a baro-only vehicle with no velZ source | validated, table in the record |
| [33484](33484/) | log A, log B, log C | the single-axis flow lockout the recovery is for | 500 ms threshold tuned on these |
| [33484](33484/) | log7 | the recovery misfiring at the flow tilt gate | re-run 2026-09-10 on the PR's own tree: the gate suppresses **nothing** there, 2 resets either way. The 3 -> 0 is on the beta branch with #33359 and #33478 stacked |
| [33507](33507/) | log311, log66 | accel-Z bias, PD drift over the hover | sweep in the record |
| [33585](33585/) | log308 | AltHold demotion at the rangefinder ceiling | validated pre-submission at an earlier head; force-pushed to `a4d8966c85` 2026-09-10 and **not re-run since** |
| [32972](32972/) | log7 | finding 6, the height floor blocking a correction in cruise | **owed** - not run |
| [34292](34292/) | log67 | the near-ground flow floor | partial; the record notes replay does not reproduce the disarm path |
| [34361](34361/) | log7 | getHAGL reporting nothing while the filter flies on a database AGL | **not applicable** - see below |
| [32553](32553/) | log200-log206 | terrain offset after ground effect clears | not established |
| [32768](32768/) | log3, log12, log21 | baro temperature drift across an arm | not established |
| [33498](33498/) | log53, log54, log56 | Z gyro bias with no yaw source | not run |
| [32471](32471/) | log197, log198 | the hover Z-bias measurement | the A/B harness ran without replay records |

## Where no flight log applies, and why

Recorded so nobody looks for one. "No log" here is a conclusion, not a gap.

| PR | why |
|---|---|
| [34360](34360/) | the sign error is 2 x the terrain height above the EKF origin, so it is exactly zero at a field where the origin sits on the ground - which is every flight in this archive. Only SITL over relief exposes it |
| [32232](32232/) | found by #33585's autotest, not in flight |
| [34305](34305/) | an uninitialised read, demonstrated with a poisoned struct |
| [34209](34209/) | autotest only; fails on master, passes fixed |
| [32473](32473/) | gates the same terms as #32471 and borrows its SITL A/B |
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
