# Phase: SUFFICIENCY REVIEW (implementer simulation) — area: {{AREA}}

You are the engineer who must re-implement the legacy system described by this kit in a new stack, WITHOUT access to
the legacy source code or anyone who knows it — only the kit in the current directory. Read `README.md`,
`00_overview.md`, `02_architecture.md`, then focus on: {{FILES}} (and anything they reference).

For everything you would need in order to implement this area EXACTLY (same observable behavior, formats, edge cases,
error handling, ordering, numeric/time/encoding details, persistence and compatibility), check whether the kit
specifies it precisely and consistently. Report every gap: missing, ambiguous, vague, contradictory, unverifiable
(no source/confidence), or example-less rule with edge cases. Be concrete: what exactly is missing and why it blocks
an exact implementation. Do not report style issues. Do not invent answers.

Output ONLY a JSON array (no prose) of objects:
{"id": "G-{{AREA_ID}}-NN", "file": "<kit file>", "item": "<kit ID or section>", "type": "missing|ambiguous|vague|contradiction|no-example",
 "gap": "...", "needed": "what precisely the kit must state", "severity": "blocking|important|minor"}
