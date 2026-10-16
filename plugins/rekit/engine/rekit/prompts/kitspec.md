# Redevelopment Kit specification v3 (shared by every rekit phase)

The **kit** is the complete, precise knowledge package that lets an implementing AI agent **redesign and re-implement**
the legacy system in a new stack while preserving every externally observable behavior that matters. It also records
human knowledge (decisions, production facts).

The kit has THREE layers. Keeping them apart is the core rule of this format: the implementer must get the full
**WHAT** (behavior, contracts) without being handed the legacy **HOW** (module structure, function decomposition,
internal names, code-shaped algorithms) as its template — otherwise the new system silently becomes a port of the old.

| layer | content | who reads it |
|---|---|---|
| **spec** (kit root, `00`–`09`) | legacy-NEUTRAL: what the system must do, observable through its contracts | implementer: always |
| **design/** | the TARGET design, made clean-room from the spec (never from legacy code) | implementer: always |
| **legacy_ref/** | how the legacy does it: structure, internal algorithms as pseudo-code, internal names, src refs | implementer: only to resolve a specific ambiguity; never as a structural template |

## Language
Prose in **{{LANG}}**. Contract identifiers and literals (API/ABI names, file/column/field names, byte layouts, SQL that
is part of a contract, messages, log strings consumed by others) stay verbatim.

## Layout
```
kit/
  README.md                 # entry point: the three layers and their reading rules, must-preserve contracts, tests, plan
  00_overview.md            # purpose, scope (in/out), system context (actors, external systems, hardware),
                            # capability list CAP-*, end-to-end flows FL-* (external viewpoint)
  01_glossary.md            # domain term | meaning | contract identifier (only if it is part of a contract)
  02_constraints.md         # what the OUTSIDE imposes: runtime/call model required by contracts (who calls what, when,
                            # threading/ISR constraints of the platform), production configuration values, build/variant
                            # facts that change behavior (production values!), compatibility requirements
  03_interfaces/IF-*.md     # one file per EXTERNAL contract, field/byte exact
  03_interfaces/files/      # verbatim copies of contract source files (public/HAL headers, DDL, run script, ...)
  04_data/DM-*.md           # persisted / shared data contracts (on-media formats, files, tables) + invariants
  05_behavior/CAP-*.md      # one file per CAPABILITY (not per legacy module): rules, invariants, observable states,
                            # errors, outcome-determining algorithms
  06_nfr.md                 # performance, memory/footprint, timing/real-time, reliability, security, operations
  07_tests/                 # README, vectors/CAP-*.md (TV-*), golden/ (executable characterization from running legacy)
  08_decisions.md           # DEC-*: human-confirmed facts and decisions, quirks to preserve, things to drop/fix
  09_open_questions.md      # generated from questions.json: open items + the assumption currently applied
  10_plan.md                # implementation tasks ordered by TARGET design components, with context packs
  design/
    architecture.md         # components C-*, responsibilities, dependency rules, runtime model, data ownership,
                            # contract boundary adapters
    decisions.md            # ADR-*: alternatives, choice, reason; how each legacy structural problem LP-* is avoided
    allocation.md           # every CAP/BR/INV/SM/ERR/ALG/IF/DM id -> exactly one owning component C-*
  legacy_ref/               # REFERENCE ONLY
    README.md               # usage rule: consult per ID via trace.json, do not mirror files/functions/names
    structure.md            # legacy modules, runtime model, dependency graph, legacy module -> CAP mapping
    structure_issues.md     # LP-*: structural problems of the legacy (global state, god modules, layer mixing, ...)
    modules/<UNIT>.md       # per legacy module: internal algorithms as faithful pseudo-code, internal data structures,
                            # constants, legacy identifiers, quirks, coverage table
  trace.json                # { "<ID>": {"file": "kit/...", "src": ["<root>:<path>:L1-L2", ...], "confidence": "..."} }
```

## IDs
Spec IDs are named after **capabilities/domain areas**, never after legacy modules or files:
`CAP-<AREA>` capability, `BR-<AREA>-NNN` rule, `INV-<AREA>-NNN` invariant, `SM-<AREA>-NNN` observable state machine,
`ERR-<AREA>-NNN` error behavior, `ALG-<AREA>-NNN` outcome-determining algorithm, `TV-<AREA>-NNN` test vector,
`IF-<AREA>-NNN` interface, `DM-<AREA>-NNN` data contract, `FL-NNN` flow, `NFR-NNN`, `DEC-NNN`, `Q-…` question,
`C-<NAME>` design component, `ADR-NNN` design decision, `LP-NNN` legacy structural problem, `T-NNN` task.
`<AREA>` is a short uppercase domain code (e.g. READ, WRITE, SMART, LOAD, JUDGE) chosen in the survey; it must differ
from the legacy unit ids. Legacy-ref items use `LR-<UNIT>-NNN`.
Every ID appears exactly once as a heading `### <ID> <title>` and once in trace.json.

## Tags
Confidence on every non-trivial statement: `[코드확인]` verified in code, `[실행확인]` verified by running legacy,
`[문서]` only from materials, `[사람확인]` confirmed by a human, `[추정]` inferred.
Source references: in **legacy_ref/** write `(src: path:line-line)` inline. In the **spec** and **design** do NOT write
source paths, legacy file names or line numbers; the source of a spec ID lives in `trace.json` only.
Everything in the spec must be preserved by default; an item a human allowed to change/drop is tagged
`[변경 허용: DEC-NNN]`.

## The neutrality rule (spec and design)
The spec describes behavior **as seen from outside the system boundary** (contracts, persisted data, observable
outputs, timing, counters), in domain terms.
- Do NOT mention legacy internal function/variable/type/macro/class/file names, legacy module or directory names,
  legacy call chains, or "module X calls Y". Use domain terms (e.g. "the block with the fewest valid pages",
  not `gc_select_victim()`; "the load step", not `TlogRecordReader`).
- Contract identifiers ARE allowed verbatim (they are part of 03_interfaces/04_data): API functions/structs of a
  contract header, file/column/table names, property/env names, command opcodes, on-media field names.
  A boundary that another party implements, calls, includes, parses or stores (host API, HAL/driver/platform
  interface implemented by platform code or test harnesses, plugin/callback interfaces, scripts, schemas, formats) is
  a CONTRACT, not legacy structure: keep its exact code-level form (prototypes with types, constants, struct layouts)
  unless a human decision (DEC) allows changing it; never declare such a boundary "free to change" on your own.
  Files that the outside world includes, invokes or edits (a public header such as the host API header, a run script,
  a configuration file the operators maintain) are contracts too: name them, with their path, in the IF that defines
  them — then they are allowed everywhere.
- Rules are `condition → observable outcome` (with precedence, boundaries `<`/`<=`, rounding, overflow, empty/null,
  duplicates, retries, idempotency/re-run, error paths), never "function f does …".
- **Algorithms** belong in the spec only when the exact procedure determines an observable result (bit-exact output,
  on-media placement, counter values, ordering of side effects that a contract exposes). Write them declaratively:
  inputs, selection criteria and tie-breaks, formulas with constants, ordering constraints, and state WHICH observable
  result depends on them (`결과 결정: …`). Do not transcribe the legacy control flow (loops, helper calls, flags) — that
  goes to legacy_ref. If the exact step order matters, list the observable steps and say why.
- Internal data structures, caches, helper decomposition, threading of the legacy implementation, logging that no one
  consumes, and dead code belong in legacy_ref, not in the spec.
- Apparent bugs and quirks that are observable ARE spec (flag them `quirk`, never silently fix): record them as rules.

## What "precise" means (checklist)
- **Interfaces**: exact names/signatures/types/units; for files & messages: encoding, line endings, record/field order,
  offsets & lengths in bytes, padding/alignment, number formats (implied decimals, sign), date/time formats & time zone,
  header/trailer rules, naming patterns, validation and rejection behavior; for DB: tables/columns/types/keys, the
  semantics of every read/write (filters, joins, ordering, locking, transaction boundaries, upsert/merge rules);
  for protocols/HW: commands, fields, status codes, register/bit semantics, timing; for ops: CLI args, env vars,
  config properties (+defaults and PRODUCTION values), exit codes, logs consumed by others.
- **Rules**: condition → outcome incl. precedence/ordering, tie-breaks, boundary values, rounding (mode & scale),
  overflow, empty/null handling, duplicates, retries, idempotency, error paths.
- **State**: observable state machines as tables (state, event, guard, action, next), persistence/recovery semantics
  (what survives a crash/power loss, what is replayed), concurrency guarantees visible from outside.
- **Hazards**: doc-vs-code conflicts, environment/config-dependent behavior (system properties, env vars, build flags,
  default timezone/locale/charset, DB/OS specifics), suspected bugs → recorded + question if a human must decide.
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
