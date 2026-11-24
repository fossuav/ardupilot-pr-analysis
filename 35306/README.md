# PR #35306 - Replay reads range finder records logged by 4.1 to 4.6

Analysis archive for [ArduPilot/ardupilot#35306](https://github.com/ArduPilot/ardupilot/pull/35306).

Opened 2026-11-20 at `08580d258c`, branch `pr-replay-rangefinder-cm`, on
master. One commit in `Tools/Replay/LR_MsgHandler.cpp`.

## What it does

c681bb4934 (2024-10-11, first in 4.7.0) changed RRNH from "hhB"
(ground clearance and maximum distance as int16 centimetres) to "ffB"
(floats in metres), and RRNI's Dist from a uint16 in centimetres to a
float. Replay copies a log's bytes into the current structures, so a log
from 4.1 to 4.6 gives a garbage sensor count and the EKF sees no range
finder at all: XKF5.rng reads 0 and HAGL is the unmeasured
terrainState - pd while the vehicle's own cores fused the range. The
commit reads the old layout by field (MsgHandler's typed accessors) when
the log's FMT says "hhB" / "fffHBBB", and converts.

No other replay record changed layout between 4.6 and 4.7. #34491's
zero-fill covers appended fields only.

## How it was found

While replaying the fleet for #35307, a 4.6 flow log from a 2.5" quad
gave lockout resets scaled by a 2.0 m height while the logged range was
0.4-1.0 m. Instrumenting Replay showed the range age equal to the whole
flight: the EKF had never been given a range. The log's RRNH/RRNI FMTs
were the old layout.

## Evidence (tier 1b)

- That log through master: before, the replayed core's XKF5.rng is 0
  throughout; after, 0.83 m against the vehicle's 0.83 m and HAGL 0.81 m
  against 0.79 m in flight. On the 4.7-based SFD beta, median |replayed
  rng - logged rng| is 0.000 m over 2191 samples.
- Fleet of 423 logs: 175 have the old layout. With the fix 84 of them
  replay a range finder (none did before), 89 have no range finder, 2
  have no usable rows. 82 logs change, all of the old layout; no
  4.7-format log changes.

## What it overturned

Every SFD fleet replay before 2026-11-20 ran the 175 old logs as
flow-only vehicles. The flow averaging study's ARK 5" runaway (GPS p95
2.76 -> 72 m/s) was this artifact: with its DroneCAN range finder
replayed, averaging moves that log's p95 2.15 -> 2.19 m/s. Re-measured
fleet-wide with the fix, averaging narrows the flow innovation spread
(median ratio 0.867) and cuts the time the flow is 1 m/s out by 17%;
GPS p95 summed +6.1, one faithful outlier (an O4 log, core 1,
8.0 -> 25.2 m/s).

## Review

- Codex cold read: one finding, that the earlier "hhH" RRNH layout (with
  a sensor bitmask) is not handled. Refuted: "hhH" existed from
  e116b1ff0a (2020-11-06) to 73755e2d1f (2020-11-26), before the DAL
  first shipped in 4.1.0; no fleet log has it. The commit message was
  narrowed to "4.1 to 4.6".
- `replay_fleet.py compare` crashed once an old log started differing:
  some replayed XKF5 rows carry fewer than seven fields and
  `flow_time_over()` reads `x['HAGL']`. `x.get('HAGL', 0)` fixes it; owed
  in the aap repo.

## 2026-11-24: merged

AP-Review accepted `08580d258c` on 2026-11-23 with one optional wording
point: with the old layout the sensor count reads zero, not nonsense, as
`copy_message` zero-fills past the five logged bytes. peterbarker approved
and merged it on 2026-11-24 (`a6578b612d`), noting that the comment above
`LR_MsgHandler.cpp:238` belongs inside the code it describes. Both are
left for a follow-up if wanted. The SFD beta's locked head is
patch-identical to what merged.
