# PR #33543: AP_Param: publish actual loaded defaults count, not the pre-count

https://github.com/ArduPilot/ardupilot/pull/33543

## 2026-11-02: commit message reworded

AP-Review (2026-09-30, COMMENT at `c7152347c6`) found the code change fine but the commit message describing a bug that does not occur: both counting passes (`count_defaults_in_file()` and `count_param_defaults()`) skip unknown parameters with the same `find()` as the load passes, so unknown parameters never leave stale override slots. Checked against the source: confirmed, and a re-open failure in the load pass panics rather than leaving `idx` short. The only divergence is a defaults file changing between the two reads.

Recreated as `9fb1afdec1` on `sq/33543-1102` (same tree as `c7152347c6`), the body rewritten as defensive hardening. Not pushed.

## 2026-11-02: pushed

Pushed to `9fb1afdec1` (refresh12 `b1093230e6` locks it).

## 2026-11-02 (later): description to match, rebased onto master

AP-Review round 4 (COMMENT at `9fb1afdec1`): the code is ready; only the PR
description still told the old stale-slot story. A replacement (the commit
message's account, plus a line saying the earlier description was wrong) is
drafted. Rebased onto master `5fdd5da0d0` as `9f1b08db4e` on
`sq/33543-1102b` so the bot re-reads the PR; QuadPlane
HighServoFunctionDefault, which loads a defaults file and checks the purge,
passes there. Not pushed.

Pushed 2026-11-02 (afternoon) to andyp1per with a lease: `9fb1afdec1` -> `9f1b08db4e` (refresh12 `df341758a7` locks it). Description updated.
