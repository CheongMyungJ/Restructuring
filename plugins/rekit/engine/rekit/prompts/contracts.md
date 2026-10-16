# Phase: CONTRACT BOUNDARY CHECK — exact form of every boundary another party depends on

Read `.rekit/prompts/kitspec.md`, `.rekit/intake.md` (what the owners said must stay), `kit/02_constraints.md`,
`kit/08_decisions.md`, every `kit/03_interfaces/IF-*.md` and `kit/04_data/DM-*.md`, `.rekit/units.json` ("contracts").
Legacy code roots (read-only): {{CODE_ROOTS}}.

The spec layer is legacy-neutral, but a boundary that SOMEONE ELSE implements, calls, includes, parses or stores is not
legacy structure — it is a contract, and its exact form must survive the redesign. Typical cases: a host/public API
header, a hardware-abstraction (HAL/driver/platform) interface implemented by platform code or test harnesses, plugin
or callback interfaces, a run script and its arguments, environment variables, config files maintained by operators,
DB schemas/DDL owned by a DBA, file/message/on-media formats, protocol/command layouts, log lines parsed by others.

1. For each such boundary, decide: contract (default) or internal. It is internal only if nothing outside the system
   depends on it, or a human decision (DEC) allows changing it. An IF must never say "name/form is free in the new
   design" for a boundary another party depends on unless a DEC says so; fix such statements.
2. Make every contract IF exact in its code-level form: verbatim prototypes/signatures with parameter and return types,
   constants and their values, struct/record layouts (field order, types, sizes, offsets, packing), header/file names
   and include paths, script names and arguments.
3. Copy, verbatim, ONLY the boundary files that a party outside the system compiles against, implements or invokes
   (e.g. the public/host API header, HAL/driver interface headers, a DBA-owned DDL, the run script of the operations
   contract) into `kit/03_interfaces/files/<original relative path>` — `cp` them, do not retype — and reference each
   from its IF ("원문: files/…"). Do NOT copy internal headers or files even if a boundary file includes them or the
   legacy build uses them (configuration/build-flag headers, profile/constant tables, logging, utility/type headers,
   internal on-media structure headers, Makefiles, simulators): copying them hands the legacy decomposition to the
   implementer. Instead state in the IF exactly what the outside needs from them (a type's definition, a constant's
   value, a persisted layout field by field). Never copy implementation (.c/.java/…) files.
4. When you are not sure whether a boundary may change, keep it exact and add a question to
   `.rekit/questions/contracts.json` (JSON array, kitspec format).
Write `.rekit/contracts_report.json`: [{"if": "IF-…", "boundary": "...", "decision": "contract|internal",
"why": "...", "changes": "...", "files": ["files/…"]}].
Reply with a 3-line summary.
