You are sorting newly mined design principles into an existing set of themes, so that an incremental run of the review-comment mining keeps the themes, and the rules already drawn from them, stable.

Inputs:
- data/clusters.json: the existing themes, a list of {"key", "rule", "kind", "ids"}. Read every theme's key, rule and kind; ignore "ids".
- data/principles_new.txt: the new principles, one `id|reviewer|pr|principle` line each (a trailing "(generalised)" means the miner generalised from a specific remark). Read every line.

For each new principle, choose the existing theme whose rule it restates or directly supports. Be faithful: a principle joins a theme only if a maintainer would see it as the same rule, not merely the same topic. Where several new principles share a rule that no existing theme states, create a new theme for them, with:
- "key": short snake_case id, not one already used
- "rule": the rule in one plain sentence, general enough that a maintainer would agree with it without knowing the PR
- "kind": one of "architecture", "parameters", "testing", "process", "style", "logging_gcs" (as defined in cluster_brief.md)

A principle that fits nothing and shares a rule with no other new principle goes to the existing "misc" theme.

Write data/assign.json:

    {"assign": {"<id>": "<theme key>", ...},
     "new_themes": [{"key": "...", "rule": "...", "kind": "..."}, ...]}

Every new id must appear exactly once in "assign". Then run `python3 assign_new.py --check` from the rules-mining directory and fix anything it reports. When done, reply with: the number of principles sorted, how many went to existing themes, misc and new themes, and each new theme's key, rule and principle count.
