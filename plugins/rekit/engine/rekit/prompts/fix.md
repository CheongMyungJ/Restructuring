# Phase: GAP FIXING

Read `.rekit/prompts/kitspec.md` and the gap list `.rekit/review/batch_{{BATCH}}.json` (found by an implementer who only
had the kit). Legacy code roots (read-only): {{CODE_ROOTS}}. Materials: `.rekit/materials_text/`.

For each gap: investigate the legacy code (and materials) and fix the kit precisely, following the three layers
and the neutrality rule of kitspec.md (spec: observable terms + confidence tags, sources into `kit/trace.json`;
legacy internals into `kit/legacy_ref/modules/`).
If only a human can resolve it (production configuration, intent, external facts), add a question to
`.rekit/questions/review_{{BATCH}}.json` (JSON array, kitspec format) and write the current assumption into the kit.
Write `.rekit/review/fixed_{{BATCH}}.json`: [{"gap": "<id>", "status": "fixed|question|invalid", "note": "..."}].
Reply with a 3-line summary.
