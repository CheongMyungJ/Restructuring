# Redevelopment Kit specification (shared by every rekit phase)

The **kit** is the complete, precise knowledge package that lets an implementing AI agent re-implement the legacy system
in a new stack **without reading the legacy source**, while preserving every externally observable behavior that
matters. It is also the place where human knowledge (decisions, production facts) is recorded.

## Language
Prose in **{{LANG}}**. Identifiers, literals, file/column/field names, byte layouts, SQL, messages, log strings and code
snippets stay verbatim (original language/case/spaces).

## Layout
```
kit/
  README.md                 # entry point for the implementing AI: reading order, conventions, how to use tests/plan
  00_overview.md            # purpose, scope (in/out), system context (actors, external systems, hardware), features, key flows
  01_glossary.md            # term | code identifiers | meaning   (domain + technical)
  02_architecture.md        # components, execution/runtime model (tasks/threads/jobs/ISRs/main loop), dependencies,
                            # configuration/variants (build flags, profiles), legacy→suggested-new mapping
  03_interfaces/IF-*.md     # one file per EXTERNAL contract, field/byte exact (see below)
  04_data/DM-*.md           # persistent & core data structures/formats, invariants, lifecycle
  05_behavior/<unit>.md     # per module/feature: rules, algorithms, state machines, error handling, edge cases
  06_nfr.md                 # performance, memory/footprint, timing/real-time, reliability, security, operations
  07_tests/                 # acceptance scenarios & test vectors; executable characterization tests if available
  08_decisions.md           # DEC-*: human-confirmed facts and decisions, quirks to preserve, things to drop/fix
  09_open_questions.md      # generated from questions.json: open items + the assumption currently applied
  10_plan.md                # ordered implementation tasks with context packs and done criteria
  trace.json                # { "<ID>": {"file": "kit/...", "src": ["path:L1-L2", ...], "confidence": "..."} }
```

## IDs
`IF-<AREA>-NNN` interface, `DM-<AREA>-NNN` data, `BR-<AREA>-NNN` rule/behavior, `ALG-<AREA>-NNN` algorithm,
`SM-<AREA>-NNN` state machine, `ERR-<AREA>-NNN` error behavior, `NFR-NNN`, `TV-<AREA>-NNN` test vector, `DEC-NNN`
decision, `Q-NNN` question, `T-NNN` task. `<AREA>` is a short uppercase code of the module (e.g. GC, MAP, LOAD).
Every ID appears exactly once as a heading `### <ID> <title>` and once in trace.json.

## Tags (mandatory on every non-trivial statement / item)
`(src: path:line-line)` source reference(s) relative to the code root; confidence: `[코드확인]` verified in code,
`[실행확인]` verified by running legacy, `[문서]` only from materials, `[사람확인]` confirmed by a human, `[추정]` inferred.
Mark each interface/behavior item as `계약(유지 필수)` (must be preserved: externally observable / compatibility) or
`구현상세(변경 가능)` (internal; may be redesigned).

## What "precise" means (checklist)
- **Interfaces**: exact names/signatures/types/units; for files & messages: encoding, line endings, record/field order,
  offsets & lengths in bytes, padding/alignment, number formats (implied decimals, sign), date/time formats & time zone,
  header/trailer rules, naming patterns, validation and rejection behavior; for DB: tables/columns/types/keys,
  every SQL statement's semantics (filters, joins, ordering, locking, transaction boundaries, upsert/merge rules);
  for protocols/HW: commands, fields, status codes, register/bit semantics, timing; for ops: CLI args, env vars,
  config properties (+defaults), exit codes, logs consumed by others.
- **Rules**: condition → outcome, including precedence/ordering, tie-breaks, boundary values (<, <=), rounding
  (mode & scale), overflow, empty/null handling, duplicates, retries, idempotency/re-run behavior, error paths.
- **Algorithms**: pseudo-code faithful to legacy incl. constants, magic numbers, loop bounds, quirks, apparent bugs
  (flag them, do not silently fix), complexity guarantees.
- **State**: state machines as tables (state, event, guard, action, next), persistence/recovery semantics,
  concurrency (who runs when, shared data, locks, interrupt context).
- **Hazards**: doc-vs-code conflicts, environment/config-dependent behavior (system properties, env vars, build flags,
  default timezone/locale/charset, DB/OS specifics), dead code, suspected bugs → recorded + question if a human must decide.
- **Examples**: concrete input→output test vectors for every rule with edge cases.
Forbidden: vague phrases like "handles errors appropriately", "processes the data", "etc." without the exact list.

## Questions (questions.json entries)
{"id":"Q-<AREA>-NN","kind":"question|material_request","priority":"blocking|important|minor","area":"...",
 "question":"(in {{LANG}}, answerable by a domain expert/operator who does NOT read code)",
 "context":"what the code/doc shows, with src refs","why":"what changes in the new system depending on the answer",
 "options":["...","..."],"assumption":"what the kit currently assumes until answered","affects":["kit/..."]}
Ask about: production configuration/environment, intent behind quirks (keep vs fix), doc-vs-code conflicts,
compatibility requirements (formats, interfaces, on-media data), scope (unused features), missing materials
(samples, master data, specs, datasheets). Do NOT ask what the code already answers.

## Working style (all phases)
- Write output files incrementally: one file (or one section) per Write/Edit call, each call ≤ ~300 lines. For long
  specifications, create the file with the first sections and append the rest with further edits. Never try to compose
  the whole kit in a single response.
- Read code with the Read tool (or `cat -n` for line numbers) so that `(src: path:line)` references are exact.
- Never modify the legacy code roots or materials. Use `.rekit/sandbox/` for any build/run experiments.
- Do all work yourself in this session: do not delegate to sub-agents or start background jobs (they are disabled).
