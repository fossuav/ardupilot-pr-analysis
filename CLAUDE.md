# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

Each directory here is the standing record of one PR: what was measured,
what was tried and rejected, and what a reviewer or a future self needs to
know before touching that branch again.

## The evidence cascade

| Tier | Evidence | Overturned by |
|---|---|---|
| 1 | Real flight (a log, a vehicle, an operator report) | Another real flight, or Replay of the original log |
| 1b | Replay of a real flight log through the changed code | Another real flight |
| 2 | SITL run (an A/B, an autotest) | A better SITL run, a Replay, or a real flight |
| 3 | Inspection (source reading, derivation, arithmetic) | Any of the above, or better inspection |

Replay sits where it does because its input **is** the real flight: the
sensor stream that produced the finding, pushed through the new code. Its
limit is that it re-runs the estimator, not the vehicle. It cannot say what
the aircraft or the pilot would have done differently, so a change that
alters the trajectory (a control law, a mode, anything the pilot reacts to)
is outside what Replay can settle, and it only ever sees what the DAL
recorded. For an estimator change on recorded sensor data it is exact.

## Two different questions

Keep these apart. They have different answers.

- **"May I edit this note?"** The cascade, strictly. See "Editing the
  record".
- **"May I change the code this note motivated?"** A more permissive rule.
  See "Changing code the record motivated". A finding being tier 1 does not
  freeze the code forever; it sets the bar for what has to be shown.

## Editing the record

A tier-1 finding is not edited, narrowed, softened or deleted. It is
**superseded in place**: the original stays exactly as written, and the new
evidence goes underneath it.

```markdown
## <original heading, unchanged>

<original text, unchanged>

### Superseded 2026-09-05 by <what>

<what beat it, with the evidence: log name, commit, Replay run, numbers>.
The finding above is left in place because <what it still explains, or
what has to be true for it to be right>.
```

Not politeness to the past: if the superseding conclusion is itself wrong,
the original text is the only route back, and by then nobody remembers what
the flight looked like.

The numbers most of all. Never adjust a measured value so it agrees with
current code. If the code has moved, record which code the number was taken
on and leave the number alone.

A tier-2 claim may be replaced outright, on one condition: the thing
replacing it is another run, not another argument. This is the failure the
repo has actually suffered. `92326be` "32471: withdraw the cb5026417f
revert, and record why" was reverted by `0e1c449`: a review pass misread
which direction a commit went and edited the archive to match its own
error, against measured numbers that were right all along.

## Changing code the record motivated

Most changes conflict with nothing measured. Those need only their own
evidence - a SITL A/B or an autotest that would fail if the change were
wrong - and the numbers added to the PR's README. No ceremony, and a
tier-1 finding elsewhere in the directory is not a reason to hesitate.

The rule below is for a change that **contradicts a real-flight
conclusion**. In descending order of what will do:

1. **Replay the original log** through the changed code and show the
   flight's own data no longer produces the failure. Best available short
   of re-flying, because the input is the real measurement. Estimator-path
   changes only; see the limit above.
2. **A SITL test that reproduces the original failure**, then shows the
   change fixing it. You must demonstrate the repro actually reproduces.
   A test that behaves identically on the good code, the bad code and the
   fix discriminates nothing. That trap is recorded in
   `../analysis/topics/aglkf_altitude_rng_use_hgt.md`.
3. **A SITL A/B alone**, with an explicit note of what the SITL model does
   not capture about the original flight. Weakest of the three; say so.

Inspection alone never clears this bar, however good the argument. The code
argument for `cb5026417f` is the best one in this repo and it is still
wrong; `32473/README.md` says what to do instead: "Do not re-derive it;
re-run `../32471/data/ab-2026-09-04/harness.py`."

Whichever route you take, the original finding stays where it is,
superseded in place. The code moves; the record accumulates.

## The "Measured and rejected" table is the point

Most PR READMEs here carry a table of changes that look right from source
and measured worse. It is the most valuable thing in the directory and the
easiest to lose.

- Add rows. Never prune one because it looks obsolete.
- Every row keeps its argument-for as well as its number, because the
  argument is what makes the change keep coming back.
- If a rejected change is later cleared by the ladder above, supersede the
  row with what cleared it. Do not delete it.
- A PR whose README has this table should open with the "Read this before
  changing the code" banner pointing at it.

## Update the record when the PR moves

The record is only worth reading if it describes the branch as it is now, and
a note that has gone stale reads exactly like one that is current. Update the
PR's directory in the same session as the change, not "later", whenever:

- commits are pushed, including a rebase or force-push that renumbers them;
- a review arrives - maintainer or automated - and is answered, whether the
  answer was a code change or a rebuttal;
- CI changes what is known: a new failure, or a red gate going green;
- the PR description is edited.

At minimum refresh the head commit and the date. Then re-read the sections
that describe mechanism, because a design that moved makes the prose wrong
rather than merely old, and prose describing code that no longer exists is
worse than no prose. #34292 carried a "How the value reaches the EKF" section
naming the wrong DAL record for a day after the record changed.

Numbers still follow "Editing the record": a measurement taken at an earlier
head keeps its value and gains the commit it was taken on. Re-run and add; do
not re-run and overwrite. If the test itself was rewritten, the new numbers
are a different measurement, so say so rather than presenting them as a
correction.

**Record the review findings that were rejected, with the reason.** This is
the same value as the "Measured and rejected" table. A reviewer's plausible
suggestion comes back - from the next reviewer, or from a later automated
pass - and next time the answer is already written down. Include findings from
automated reviews that turned out to be wrong: unrebutted, they get repeated.

## Changing code can invalidate an archived number

Before applying a change to a PR branch, check which archived runs it would
move. A baseline measured with a behaviour still in it stops being a
baseline once that behaviour is gated. Say so in the README, and either
re-measure or mark the affected rows with the code state they belong to.
Leaving a stale number beside new code is the same error as editing one.

## Repo conventions

- One directory per PR, named by number. `README.md` first: summary,
  conclusion, key findings, file map, reproduction steps.
- `plots/` holds PNGs plus a `make_plots.py` that regenerates them from
  `data/`. Keep it runnable.
- `data/` holds **SITL logs only**. This repo is public. Real-flight logs
  must never be committed; quote their numbers inline and name the log.
  SITL BINs are identifiable by their hundreds of `SIM_*` parameters and
  the CMAC default home (-35.36, 149.16).
- Record the branch head commit and the date any set of numbers was taken
  at. A number without its commit cannot be reproduced.
- A commit that exists on two branches (the `cb5026417f` / `361da5d064`
  pattern) gets a note in both PR directories, each pointing at the other.
- Update the PR's row in the root `README.md` table when its state changes.
- The `Reproduce` section is a promise. If a change breaks it, fix it in
  the same commit.

## Inspection-only claims must say so

Tier 3 is the only tier you may correct by thinking. In exchange it must be
**labelled**: write "derived from the source, not measured" in the text. An
unlabelled claim reads as measured, and three reviews later nobody
re-checks it. Cross-reference the root ArduPilot playbook's "A claim marked
checked is a hypothesis to the next reader."

## Writing rules

- Absolute dates, never "last week" or "recently".
- Cite the artifact: log name, commit hash, parameter values, test name.
- Separate hypothesis from conclusion. "Mechanism only" and "not measured"
  are useful phrases; use them.
- ASCII punctuation. No em-dashes, arrows or smart quotes.
- Wrap prose to about 75 columns to match the existing files.

`../analysis` holds the flight-log side of the same material, under the
same rules.
