# Mining architectural rules from human review comments

State at 2026-10-14, written so the work can be picked up again.

The aim is a set of general architectural rules that maintainers hold but
rarely write down, so a change can be checked against them before review
rather than after a flight. Each rule is confirmed by the user before it
becomes a standard; the process is in the root playbook (`aap`, "Subsystem
Playbooks" -> "Architectural rules") and candidates wait in `aap`'s
`RULES_PROPOSED.md`, which is never installed. Rules true only on the
SmallFastDrone branches go in that repository's
`Tools/SFD/ARCHITECTURE_RULES.md` (none so far).

## Where it stands

Confirmed into the root playbook's Architectural Principles (`aap` 1.7.39):

| rule | from |
|---|---|
| ARCH-1 Shared state is a contract between subsystems | the #32514/#34696 interaction on TD25, 2026-10-13 |
| ARCH-2 Test for what you need, not for something that usually comes with it | the same |
| ARCH-3 Lower layers detect, higher layers decide | mined: respect_layering_use_abstractions, logic_belongs_in_owning_class, generic_features_in_shared_libraries, library_detects_vehicle_acts, hal_abstraction, fix_root_cause_not_symptom (44 PRs) |
| ARCH-4 A feature costs nothing to the users who do not use it (merged into "Compile-Time Dependency Analysis") | mined: feature_guards_compile_out_cleanly, new_features_default_off, state_flash_cpu_ram_cost, minimal_boards_no_new_features (52 PRs) |
| ARCH-5 Safety logic is judged by what it does when it is wrong | mined: failsafe_and_safety_design (18 PRs); second draft, scoped to what the current flight depends on, against rmackay9's "regardless of sources" view of #32514 (see `../32514/README.md`, 2026-10-14) |
| ARCH-6 Do not break what users already have | mined: backward_compat_existing_users (15 PRs) |
| ARCH-7 Prefer the simplest design that does the job | mined: avoid_unneeded_complexity, avoid_extra_state (23 PRs) |
| ARCH-8 Reuse before you write | mined: reuse_existing_code_dont_duplicate (21 PRs) |
| ARCH-9 The main loop never waits (merged into "Scheduler Integration") | mined: no_blocking_in_main_thread, scheduler_and_periodic_cpu, shared_state_thread_safety (36 PRs) |
| ARCH-10 Nothing from outside is trusted | mined: bounds_null_and_input_validation (19 PRs) |

Rejected drafts and the reasons are kept in `RULES_PROPOSED.md`: the first
drafts of ARCH-1 and SFD-1 were too specific (the user: a rule must make
sense to a maintainer who has never heard of the incident), and ARCH-5's
first draft carried rmackay9's #32514 trigger unscoped.

## What is next

1. **Architecture themes not yet used**, from `data/ranked.txt`. Several
   overlap the playbook already; check each against it first.
   ekf_ahrs_changes_need_scrutiny (10 PRs, overlaps the EKF3 playbook),
   memory_allocation_and_init_safety (15, partly in "Memory"),
   control_and_filter_changes_need_evidence (13), sensor_driver_care (11),
   remove_dead_code (11), prearm_checks_design (10),
   explicit_state_machines (9), vehicle_modes_hooks (7),
   hwdef_hal_changes_test_all_boards (6), internal_error_usage (6),
   scripting_api_design (5), protocol_parsing_robustness (5),
   home_vs_origin (4), singleton_and_instance_design (4, overlaps the
   singleton rule), third_party_code (4, overlaps the submodule rule).
2. **A second batch outside architecture.** The leading themes, by
   weighted score: names_say_what_things_are (30 PRs), comment_quality
   (28), test_quality (20), pr_description_and_testing_statement (21),
   types_and_units (17), test_on_real_hardware (16),
   evidence_and_repro_for_fixes (15), gcs_text_volume (11),
   log_field_design (13), split_unrelated_changes (11),
   param_doc_metadata_complete (10), dont_add_parameters_needlessly (9).
   Much of this is already in the root, autotest and writing-for-reviewers
   sections; expect fewer new rules than the first batch gave.
3. **Tier C not mined.** Comments from reviewers other than rmackay9,
   peterbarker, lthall and tridge (786 comments of 200+ characters, 65k
   words, 4 chunks) were collected and chunked but not extracted. Run step
   3 below on `data/chunks/C*.txt`; they add repetition counts more than
   new weight.

## Method, and how to re-run it

Every step but 3 and 5 is a script here; 3 and 5 are one agent per input,
with the brief in this directory. The user asked that repeated feedback
count most, with Randy and Peter weighted highest.

1. `python3 collect_reviews.py` - every issue comment, review and inline
   comment by a human on the author's PRs (870 PRs, about 2600 API calls,
   30 minutes, resumable) into `data/comments.jsonl` (4.3 MB, not
   committed). Comments carrying AP-Review's markers ("AI-generated",
   the verdict and head lines) are tagged `ai`: tridge's /reviewprs posted
   as tridge before the AP-Review account existed (121 of his 1167
   comments), and AP-Review's own are tagged too. Long structured tridge
   comments without a marker are tagged `ai_suspect` (none were).
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
   the 2026-10-14 output.
7. Draft rules in `aap`'s `RULES_PROPOSED.md` in its format (a general
   principle, the incident only as its example, a check, the repetition
   count) and bring them to the user in batches of five to ten.

Re-running steps 3-5 renumbers the ids and re-draws the themes; the
committed `data/` is the 2026-10-14 run that produced ARCH-3 to ARCH-10.

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
- The TD25 field test: T3 is to be re-flown on the beta at `26f507edf4` or
  later (`Tools/SFD/TD_FIELD_PLAN.md` in smallfastdrone); the write-up is
  in `../analysis`.
