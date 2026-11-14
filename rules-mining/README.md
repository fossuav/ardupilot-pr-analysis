# Mining architectural rules from human review comments

State at 2026-11-14, written so the work can be picked up again.

The aim is a set of general architectural rules that maintainers hold but
rarely write down, so a change can be checked against them before review
rather than after a flight. Each rule is confirmed by the user before it
becomes a standard; the process is in the root playbook (`aap`, "Subsystem
Playbooks" -> "Architectural rules") and candidates wait in `aap`'s
`RULES_PROPOSED.md`, which is never installed. Rules true only on the
SmallFastDrone branches go in that repository's
`Tools/SFD/ARCHITECTURE_RULES.md` (none so far).

## Where it stands

Confirmed into `aap`'s playbooks (1.7.71): 26 architectural rules, 12
style rules, 6 logging and GCS rules and 4 replay rules, each with a page
under `aap/rules/`. Nothing is waiting in `RULES_PROPOSED.md`.

| rule | from |
|---|---|
| ARCH-1 Shared state is a contract between subsystems | the #32514/#34696 interaction on Q25v1, 2026-10-13 |
| ARCH-2 Test for what you need, not for something that usually comes with it | the same |
| ARCH-3 Lower layers detect, higher layers decide | mined: respect_layering_use_abstractions, logic_belongs_in_owning_class, generic_features_in_shared_libraries, library_detects_vehicle_acts, hal_abstraction, fix_root_cause_not_symptom (44 PRs) |
| ARCH-3, third bullet: a layer reports the structure its users configure | the user's position on #34543, 2026-10-16; folded into ARCH-3 2026-11-14 |
| ARCH-4 A feature costs nothing to the users who do not use it (merged into "Compile-Time Dependency Analysis") | mined: feature_guards_compile_out_cleanly, new_features_default_off, state_flash_cpu_ram_cost, minimal_boards_no_new_features (52 PRs) |
| ARCH-5 Safety logic is judged by what it does when it is wrong | mined: failsafe_and_safety_design (18 PRs); second draft, scoped to what the current flight depends on, against rmackay9's "regardless of sources" view of #32514 (see `../32514/README.md`, 2026-10-14) |
| ARCH-6 Do not break what users already have | mined: backward_compat_existing_users (15 PRs) |
| ARCH-7 Prefer the simplest design that does the job | mined: avoid_unneeded_complexity, avoid_extra_state (23 PRs) |
| ARCH-8 Reuse before you write | mined: reuse_existing_code_dont_duplicate (21 PRs) |
| ARCH-9 The main loop never waits (merged into "Scheduler Integration") | mined: no_blocking_in_main_thread, scheduler_and_periodic_cpu, shared_state_thread_safety (36 PRs) |
| ARCH-10 Nothing from outside is trusted | mined: bounds_null_and_input_validation (19 PRs) |
| ARCH-11 A pre-arm check catches what would silently go wrong, says what, and changes nothing | mined: prearm_checks_design, arming_side_effects (12 PRs); parked 2026-10-16, confirmed 2026-11-14 on a wording that leaves out checks for unusual settings |
| ARCH-12 Memory is paid for only where it is used (in "Memory") | mined: memory_allocation_and_init_safety (15 PRs), 2026-10-16 |
| ARCH-13 A driver change holds for every variant and failure it can meet | mined: sensor_driver_care (11 PRs), 2026-10-16 |
| ARCH-14 Do not add code before it is used, and remove what your change leaves unused | mined: remove_dead_code (11 PRs), 2026-10-16 |
| ARCH-15 internal_error is for the impossible, not the unexpected | mined: internal_error_usage (6 PRs), 2026-10-16 |
| ARCH-16 Use the weakest spatial reference the job needs, and name the one you use | mined: home_vs_origin (4 PRs), second draft with the user's Copter/Plane and position/location points, 2026-10-16 |
| ARCH-17 Libraries carry no vehicle-specific code; the vehicle moderates them | #34292's Rover floor, second draft with the user's scope, 2026-10-16 |
| ARCH-18 Data crosses from a driver's thread to the main loop only at the frontend's copy | #33484's race and the user's backend/frontend point, 2026-10-16; led to #34783 |
| ARCH-19 New behaviour is opt-in, and lands as the last and smallest commits of a PR | from the user, 2026-10-16 |
| ARCH-20 A flag a mode holds true must still be true when the mode ends | a Replayed flow landing, 2026-10-22; confirmed 2026-11-14 |
| ARCH-21 A state kept out of a filter update keeps its covariance consistent | #33498's flow mask, 2026-10-29; confirmed 2026-11-14, in the EKF3 playbook |
| ARCH-22 A parameter index any released build used is never given to another parameter | a fork's renumbered parameter, 2026-10-31 |
| ARCH-23 A new parameter has to earn its flash, and a feature costing 1 KB or more sits behind its own define | #34543's OSD items, 2026-11-02; mined: dont_add_parameters_needlessly (10 PRs) |
| ARCH-24 A threshold in flight code has a reason a reviewer can check | peterbarker on #34457, 2026-11-05 |
| ARCH-25 A feed-forward term models the vehicle, not a setting that shapes the command | #33318, 2026-11-06; lthall's review of it makes the same point; confirmed 2026-11-14 |
| ARCH-26 An estimate fused into another filter is not an independent measurement | #33478's AGL KF velocity fusion, 2026-11-06; confirmed 2026-11-14, in the EKF3 playbook |
| STYLE-1 to STYLE-12, in the root playbook's Code Style | mined: every style theme, 2026-11-14, without examples |
| REPLAY-1 to REPLAY-4, in the EKF3 playbook's DAL and Replay section | from the user, with rmackay9's #35077 and #35105 (replay messages grown at the end, with explicit padding) and tridge's RISJ ask on #32399 (mined principle 980), 2026-11-14 |
| LOG-1 to LOG-6, in the root playbook's Logging and GCS Messages | mined: every logging_gcs theme (log_field_design, gcs_text_volume, libraries_own_their_logging, log_bandwidth_cost, log_timestamp_semantics, informative_user_errors), 2026-11-14, without examples |

Rejected drafts and the reasons are kept in `RULES_PROPOSED.md`: the first
drafts of ARCH-1 and SFD-1 were too specific (the user: a rule must make
sense to a maintainer who has never heard of the incident), and ARCH-5's
first draft carried rmackay9's #32514 trigger unscoped.

## The 2026-11-14 rescan

The collection was re-run from scratch (887 PRs). Since 2026-10-14 those
PRs drew 58 human comments and 212 from AP-Review, which the mining drops
by design, so the human signal is now a few dozen comments a month. 35
passed the filters and gave 26 principles (ids 1000-1025), sorted into the
existing themes rather than re-clustered, so the theme keys and the rules
drawn from them stay put. The ranking barely moved: comment_quality passed
names_say_what_things_are, and one theme is new, vehicle_lead_approval (a
vehicle behaviour change needs its lead's approval before it merges;
rmackay9, lthall and peterbarker on #34208 and #34456). Most of the rest
restate rules confirmed since: ARCH-24 (rmackay9 on an "arbitrary" 10x
limit in #33585), ARCH-25 (lthall on #33318) and STYLE-2.

## What is next

Themes no rule has used yet, from `data/ranked.txt`, with their PR counts:

1. **Parameters**, partly covered: dont_modify_user_params (7),
   default_value_changes (6), options_bitmask_parameters (6),
   dont_change_param_meaning (4), param_conversion_needed (4), param_naming
   (4). param_doc_metadata_complete (10) is the playbook's Parameter
   Documentation already.
2. **Architecture**: explicit_state_machines (9) and vehicle_modes_hooks
   (7) are uncovered. hwdef_conventions (18) and
   hwdef_hal_changes_test_all_boards (6) belong to the hwdef playbook,
   scripting_api_design (5) to the AP_Scripting one.
3. **Testing and process**, mostly in the playbooks already. The gaps are
   test_on_real_hardware (17), test_on_all_affected_vehicles (8),
   release_and_backport_hygiene (11) and the new vehicle_lead_approval (2).
4. **Tier C backlog.** 786 longer comments from reviewers outside the top
   four were chunked on 2026-10-14 but never extracted; they add
   repetition counts more than new weight. `data/chunks/` is not kept, so
   `chunk_comments.py` without `--since` rebuilds them.

Parameter rules fit none of the ARCH, STYLE, LOG and REPLAY prefixes well; the
user decides which they take before they are drafted.

## Method, and how to re-run it

Every step but 3 and 5 is a script here; 3 and 5 are one agent per input,
with the brief in this directory. The user asked that repeated feedback
count most, with Randy and Peter weighted highest.

1. `python3 collect_reviews.py` - every issue comment, review and inline
   comment by a human on the author's PRs (887 PRs on 2026-11-14, about
   2600 API calls, 30 minutes) into `data/comments.jsonl` (not
   committed). It resumes by skipping PRs already in the file, so new
   comments on an old PR are fetched only if the file is deleted first.
   Comments carrying AP-Review's markers ("AI-generated", the verdict and
   head lines) are tagged `ai`: tridge's /reviewprs posted as tridge
   before the AP-Review account existed (121 of his 1167 comments), and
   AP-Review's own are tagged too. Long structured tridge comments without
   a marker are tagged `ai_suspect` (none were).
2. `python3 chunk_comments.py` - drops `ai`, bots, short and approval-only
   comments, and splits the rest into tiers: A rmackay9 and peterbarker
   (1184 comments, 4 chunks), B lthall and tridge (720, 2), C everyone
   else at 200+ characters (786, 4).
3. One extraction agent per chunk (sonnet was enough) with
   `extract_brief.md`, writing `data/extract/<chunk>.jsonl`: one line per
   general principle, with the PR, reviewer, url, a quote and whether the
   reviewer meant it generally. The 2026-10-14 run over A1-A4, B1-B2 gave
   1000 principles.
4. `python3 merge_principles.py` - numbers them into
   `data/principles_all.json` (committed) and a compact list for step 5.
5. One clustering agent with `cluster_brief.md`, writing
   `data/clusters.json` (committed): 85 themes, each id in exactly one.
6. `python3 score.py [kind]` - per theme, distinct PRs, reviewers, and a
   weighted score (each reviewer and PR pair counts 3 for rmackay9 or
   peterbarker, 2 for lthall or tridge, 1 otherwise). `data/ranked.txt` is
   the 2026-11-14 output.
7. Draft rules in `aap`'s `RULES_PROPOSED.md` in its format (a general
   principle, the incident only as its example, a check, the repetition
   count) and bring them to the user in batches of five to ten.

Re-running steps 3-5 renumbers the ids and re-draws the themes, which
breaks the theme names the table above records. To add newer comments
without that, run incrementally (as on 2026-11-14):

1. Collect as in step 1.
2. `python3 chunk_comments.py --since YYYY-MM-DD` - only comments made on
   or after the date, into `data/chunks/{A,B,C}N_YYYYMMDD.txt`.
3. Extract as in step 3. A few dozen comments need no agent.
4. `python3 merge_principles.py --append` - adds them after the existing
   ids, skipping any already present, and lists only the new ones in
   `data/principles_new.txt`.
5. Sort them into the themes with `assign_brief.md` (one agent, or by hand
   for a small batch), writing `data/assign.json`. `python3 assign_new.py
   --check` validates it; without `--check` it adds the ids to
   `clusters.json`, creating any new themes it names.
6. `python3 score.py > data/ranked.txt`.

The committed `data/` is the 2026-10-14 run that produced ARCH-3 to
ARCH-10, plus the 2026-11-14 increment (ids 1000-1025, one new theme).

## Limits

- The miners' theme counts in their own reports were hand tallies; only
  `score.py`'s counts, computed from `clusters.json`, are used above.
- The clustering is one agent's judgement. Two themes that a reader would
  merge (feature guards and default-off, for example) were merged by hand
  when drafting the rules, as the table above records.
- `general` is the miner's opinion of whether the reviewer meant a rule.
- Only this author's PRs are covered, so the counts say what maintainers
  told this author, not what they tell everyone.

## Other open threads (recorded elsewhere)

- Review policy: a full `/pr-review` before a PR opens or before the first
  push to an unreviewed PR, `/pr-review --quick` for pushes that answer
  findings or fix a bug (`aap` 1.7.34).
- Per-PR open items live in each PR's README: #34380's short-reach band
  awaits a maintainer, #33585's timing-window retry is a follow-up,
  #33359's accel-bias sweep is owed, #32270 is parked for SFD tracking.
- The Q25v1 field test: T3 is to be re-flown on the beta at `26f507edf4` or
  later (the field plan in the SFD tree); the write-up is
  in `../analysis`.
