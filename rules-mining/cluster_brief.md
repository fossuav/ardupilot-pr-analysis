You are clustering design principles mined from human code-review comments on ArduPilot pull requests, to find the rules maintainers repeat.

Input: data/principles_compact.txt. Each line is `id|reviewer|pr|principle` (a trailing "(generalised)" means the miner generalised from a specific remark). Read every line.

Group the principles into themes, so that each theme is ONE rule a maintainer would state, not a broad topic. Aim for roughly 50-90 themes; split a topic like "parameters" into its distinct rules (e.g. "don't add a parameter where a constant or default will do", "never change the meaning of an existing parameter", "parameter changes need a conversion", "doc metadata complete"...). Put principles that fit no repeated theme into a theme with key "misc".

For each theme give:
- "key": short snake_case id
- "rule": the rule in one plain sentence, general enough that a maintainer would agree with it without knowing the PR
- "kind": one of "architecture" (where code lives, layering, ownership, interfaces, shared state, coupling, threading/blocking, safety/failsafe design, feature gating and flash cost, backwards compatibility of behaviour), "parameters", "testing", "process" (PR/commit scope, descriptions, release hygiene), "style" (naming, comments, C++ idioms), "logging_gcs"
- "ids": every principle id in it

Every id must appear in exactly one theme. Write the result as JSON (a list of theme objects) to data/clusters.json, then re-read it and confirm all ids appear exactly once.
