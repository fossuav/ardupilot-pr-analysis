# Squash audit, 2026-10-31

Which commits on top of Andy's PRs have flown, and so may be folded into the
commit they fix, after SFD-O4's refresh12 card (logs 66-71, firmware
`ea8cef60`) and the Q25's flights on `0cb49e7d` (refresh11 topup5). Rule:
fold a fix into its target only when the target is unflown, or both have
flown and been verified; shared and separable commits stay as they are.
Evidence is a message, event or log field only the path produces, or Replay
with the change removed against the as-flown build (refresh12 `f93bd10a6f`;
for the Q25, Replay rebuilt at `0cb49e7dfb`).

- `A.md`: #34942, #32471, #32473, #34941.
- `B.md`: the flow and AGL KF stack (#33484, #34630, #34543, #33359, #34292,
  #34380, #33585, #34457, #33507, #34933, #34851, #34456 and older ones).
- `C.md`: Copter, rate thread and system PRs (#29000, #31274, #34210, #34696,
  #32514, #32270, #32475, #32401 and the rest).
- Addenda: `Q25-2026-11-02.md` (the Q25 on `c46a09ec`) and
  `O4-2026-11-05.md` (SFD-O4 logs 73-78 on topup11 `52ec3c77`).

Analysis only: nothing was squashed. The scripts and A/B outputs they name
lived in that session's scratchpad and are not kept here; the tables carry
the numbers.
