# Phase: SURVEY — system-level understanding and analysis plan

You are the lead reverse-engineer of a legacy system. The kit specification is in `.rekit/prompts/kitspec.md` — read it first.

Inputs (read-only, NEVER modify):
- Legacy code roots: {{CODE_ROOTS}}
- Materials: converted text in `.rekit/materials_text/` (index: `.rekit/materials_text/index.json`); originals: {{MATERIAL_ROOTS}}.
  Open original PDFs/images with the Read tool when figures/tables matter.
- Inventory with LOC/token estimates: `.rekit/inventory.txt`
- Human intake notes (goals, constraints, environment): `.rekit/intake.md`

Do:
1. Read the materials and skim the code structure (build files, entry points, main flows, directory layout) to understand
   purpose, system boundary, external actors/interfaces and module structure. No deep analysis yet.
2. Write drafts: `kit/00_overview.md`, `kit/02_architecture.md`, `kit/01_glossary.md` (seed).
3. Write `.rekit/units.json` (valid JSON):
   {"units": [{"id": "GC", "title": "...", "files": ["<root>:<path>", ...], "focus": "what matters most here",
               "depends_on": ["MAP"], "group": "FTL"}],
    "groups": [{"id": "FTL", "title": "subsystem title"}],
    "excluded": [{"file": "<root>:<path>", "reason": "vendor|generated|build-output|irrelevant: ..."}],
    "contracts": [{"id": "IF-XXX-001", "title": "...", "kind": "api|file|db|protocol|ops|config|hw|media|message",
                   "where": ["<root>:<path>:<lines>"]}],
    "runnable": {"feasible": true, "how": "exact build/run commands and prerequisites", "needs": ["..."]}}
   Rules: every text file of the inventory is in exactly one unit OR in "excluded" (with reason). Each analysis unit
   is one AI session, and every session has a fixed overhead — so prefer FEW, LARGE, cohesive units: pack related files
   up to ~{{UNIT_TOKENS}} tokens of code per unit (if the whole system is below that, ONE unit is ideal); split only
   along real module boundaries when a module exceeds the limit. Unit ids are
   short UPPERCASE area codes (2–8 chars) reused as <AREA> in kit IDs. Order units bottom-up (dependencies first).
   Assign every unit to a subsystem "group" (3–12 groups for large systems; a single group is fine for small ones).
4. Write initial human questions to `.rekit/questions/survey.json` (JSON array, kitspec question format, ids
   `Q-SURVEY-NN`): only things a human must tell us about scope, production environment, compatibility requirements,
   missing materials. Do not ask what the code answers.
Reply with a 5-line summary.
