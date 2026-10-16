# Phase: SURVEY — system-level understanding and analysis plan

You are the lead reverse-engineer of a legacy system. The kit specification is in `.rekit/prompts/kitspec.md` — read it
first (especially the three layers and the neutrality rule).

Inputs (read-only, NEVER modify):
- Legacy code roots: {{CODE_ROOTS}}
- Materials: converted text in `.rekit/materials_text/` (index: `.rekit/materials_text/index.json`); originals: {{MATERIAL_ROOTS}}.
  Open original PDFs/images with the Read tool when figures/tables matter.
- Inventory with LOC/token estimates: `.rekit/inventory.txt`
- Human intake notes (goals, target stack, architecture wishes, constraints, environment): `.rekit/intake.md`

Do:
1. Read the materials and skim the code structure (build files, entry points, main flows, directory layout) to understand
   purpose, system boundary, external actors/interfaces and module structure. No deep analysis yet.
2. Identify the system's **capabilities** from the OUTSIDE: what services it offers through its contracts (commands,
   jobs, APIs, files, persisted data, background duties visible through counters/outputs). A capability is a
   domain-level responsibility (e.g. "read data", "persist and recover state", "health reporting", "load test logs",
   "judge bins"), NOT a legacy module; one legacy module may serve several capabilities and vice versa.
   Choose 4–15 capabilities with short uppercase AREA codes that differ from the unit ids below.
3. Write drafts (spec layer, legacy-neutral): `kit/00_overview.md` (incl. the capability list `### CAP-<AREA> <title>`
   with a 2–4 line external description each), `kit/02_constraints.md`, `kit/01_glossary.md` (seed).
   Write `kit/legacy_ref/structure.md` (draft): legacy modules/directories, runtime model, dependency sketch,
   legacy module → capability mapping.
4. Write `.rekit/units.json` (valid JSON):
   {"units": [{"id": "GC", "title": "...", "files": ["<root>:<path>", ...], "focus": "what matters most here",
               "depends_on": ["MAP"], "group": "FTL", "capabilities": ["CAP-SPACE", "CAP-SMART"]}],
    "groups": [{"id": "FTL", "title": "subsystem title"}],
    "capabilities": [{"id": "CAP-SPACE", "area": "SPACE", "title": "...", "description": "external view",
                      "units": ["GC", "ALLOC"]}],
    "excluded": [{"file": "<root>:<path>", "reason": "vendor|generated|build-output|irrelevant: ..."}],
    "contracts": [{"id": "IF-XXX-001", "title": "...", "kind": "api|file|db|protocol|ops|config|hw|media|message",
                   "where": ["<root>:<path>:<lines>"]}],
    "runnable": {"feasible": true, "how": "exact build/run commands and prerequisites", "needs": ["..."]}}
   Rules: every text file of the inventory is in exactly one unit OR in "excluded" (with reason). Each analysis unit
   is one AI session that must read all of its code line by line; small, cohesive units give markedly more precise
   specifications (measured), so keep each unit at most ~{{UNIT_TOKENS}} tokens of code: split large modules by
   responsibility, group only tiny closely related files, never mix unrelated modules. Unit ids are
   short UPPERCASE codes (2–8 chars) used only inside legacy_ref. Order units bottom-up (dependencies first).
   Assign every unit to a subsystem "group" (3–12 groups for large systems; a single group is fine for small ones)
   and to the capabilities it contributes to. Every capability lists its contributing units.
5. Write initial human questions to `.rekit/questions/survey.json` (JSON array, kitspec question format, ids
   `Q-SURVEY-NN`): only things a human must tell us about scope, production environment, compatibility requirements,
   missing materials. Do not ask what the code answers.
Reply with a 5-line summary.
