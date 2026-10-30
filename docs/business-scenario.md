# The scenario in one page

**The team.** A small team keeps a blogging API (Node, Express, Prisma, Postgres: the RealWorld example app). They use AI coding
agents, and every agent session starts with no memory of the last one. The team's working rules (how long a comment can be edited,
how errors are shaped, how migrations are done) live in short Markdown notes that one person, the Maintainer, keeps up to date.

**The work.** Over one sprint three features go in: comment editing, a cap on how many articles one request can return, and soft
delete for comments. Each feature is planned by one session, built by another and reviewed by a third. Nobody carries information
between sessions except through the channels the team provides.

**The problem.** Rules change in the middle of the sprint. The edit window becomes longer. The error response shape is replaced and an
older runbook still describes the old one. A session that builds to the old rule creates rework, and a reviewer that checks against
the old rule waves the wrong code through. The team also keeps some private review findings that must never leak into answers about
the team's rules, and wants an honest signal when the memory service itself is down instead of a confident "there is no such rule".

**The question this demo asks.** When the rule source is Okto Neuron, how often does the work that comes out of the sessions use the
rule that is current when the work is made, compared with sessions that have no rule source and sessions that are handed the current
notes in their prompt? The answer is a number per arm with its spread over repeated runs (`docs/METRIC.md`), not a story.

**Who is who.**

| Person or session | Does |
|---|---|
| Maintainer | Edits the notes; changes two rules mid-sprint |
| Planner session | Gathers rules for a feature and writes a short spec |
| Builder session | Writes the migration, endpoint and tests from the spec and the rules |
| Reviewer session | Checks the diff against the current rules, keeps private findings |

**What counts as success.** The sessions' code, tests and verdicts follow the current rule after each change; every Neuron answer can be
traced to cited bytes; a model outage is reported as an outage. What counts as a result is only what a recorded run shows. At the time
of writing, no comparison run has been recorded.
