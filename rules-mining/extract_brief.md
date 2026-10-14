You are mining human code-review comments on ArduPilot pull requests for architectural and design principles that maintainers hold. The goal is a set of general rules a future contributor should follow; repeated feedback matters most.

Input: one chunk file of comments. Each entry is: `PR#N "title" [reviewer kind path] url`, then the comment body, then `----`. All the PRs were written by the same author.

For each comment that states or clearly implies a reusable design or architecture principle - something that would apply to other PRs, not only to this PR's particular line - write one JSON object per line to your output file with these keys:
- "pr": the PR number (int)
- "user": the reviewer login
- "url": the comment url
- "principle": the principle in one plain sentence, stated generally, the way a maintainer would say it (no PR specifics)
- "quote": the shortest verbatim excerpt that carries it, at most 200 characters
- "general": true if the reviewer clearly meant it as a general rule, false if you are generalising from a specific remark

Include things like: where code belongs (library vs vehicle vs HAL vs scripting), parameters (adding them at all, naming, units, defaults, ranges, conversion/migration, reboot), compile-time feature guards and flash size, singletons/ownership/coupling, shared state and interfaces, backwards compatibility and user-visible behaviour changes, logging and GCS messages, failsafe and safety design, simplicity and scope of a PR, testing expectations (autotests, what a test must prove), MAVLink behaviour, commit structure, naming, comments.

Skip: astyle/whitespace nits, typos, "please rebase", CI chatter, pure questions without a stance, scheduling, bugs that only concern this PR's code, thanks/approval.

One comment may give several principles. Be faithful to what was said; do not invent.

Write ALL output lines to the output file with the Write tool (JSONL, one object per line). When done, reply with: the number of lines written, and the 12 most frequent principle themes you saw, each with a count of distinct PRs.
