# Brief: build experiment subject S4 "ssdfw" (synthetic LEGACY SSD controller firmware, C)

Purpose: a realistic, NEVER-PUBLISHED legacy SSD firmware used to test "AI-driven redevelopment". Other AI agents will
(a) analyze legacy code + materials to produce redevelopment data, (b) re-implement the firmware from that data WITHOUT
seeing hidden/. A hidden black-box harness then measures behavioral fidelity. Legacy behavior must be deterministic and
thoroughly exercised by hidden tests; tribal knowledge must NOT leak into legacy code or materials.

Work ONLY under $SP/samples/s4_ssdfw/ (SP=/tmp/claude-0/-home-user-Restructuring/9155ba45-e573-59a1-b70d-b72c0c21626d/scratchpad).
legacy/ (code a company hands over), materials/ (documents, Korean), hidden/ (never shown). Never touch /home/user/Restructuring.
Tools: gcc/clang, make, python3 (python-docx, openpyxl available).

## Shape of the firmware (C99, ~5,000–7,000 lines incl. headers; written by several engineers 2016–2019)
Directory sketch (adapt as you like, keep it firmware-like):
  config/      fw_config.h (build-time #defines with DEV defaults), nand_profile.h (geometry per NAND type)
  hal/         hal_nand.h (NAND driver interface the FW calls), hal_timer.h, hal_temp.h (temperature sensor)
  platform/asic/  register-level HAL for the real controller (memory-mapped registers, DMA descriptors, ISR) —
               realistic but NOT buildable on the host (it is analyzed, never run)
  platform/sim/   host simulation HAL used by the dev team on PCs: NAND model (page data + spare/OOB area, erase,
               bad blocks, bit-error injection), timer, temp sensor, image save/load, power-loss injection
  host/        command layer: NVMe-like admin + IO commands, completion status codes, queue handling simplified
  cache/       DRAM write cache (write-back, flush policy, FUA handling)
  ftl/         mapping (4 KiB mapping unit over 16 KiB NAND pages), allocation, GC, wear leveling, bad block mgmt,
               read retry, read-disturb refresh, metadata persistence (map checkpoints + journal), boot/recovery
  smart/       SMART/health log + counters persisted in metadata
  thermal/     throttling levels from temperature
  util/        crc32, bit ops, ring buffer, logging macros
  tools/       host test CLI used by developers (drives the sim build)
  Makefile     builds the sim target (libssdfw.a + tools); the asic target is referenced but not buildable here.

## External contracts (what the hidden harness uses; keep them small and stable)
1. `fw_api.h` — host-facing C API of the firmware (sim build):
   `int fw_init(void)` (power-on: mount/recover from NAND), `void fw_submit(const nvme_cmd_t*, void* buf, nvme_cpl_t*)`
   (synchronous for the sim: executes a command, fills completion), `void fw_shutdown(int clean)` (clean = normal
   shutdown notification; flushes cache, writes clean-shutdown mark), `void fw_tick(uint32_t ms)` (background work:
   idle GC, refresh, thermal sampling). nvme_cmd_t / nvme_cpl_t: opcode, nsid, slba, nlb, cdw10..15, status (SCT/SC),
   cdw0 result — define them as plain C structs.
2. `hal/hal_nand.h` — NAND interface the firmware calls (implemented by platform/sim and by the hidden harness's own
   simulator): geometry query, `hal_nand_read(blk, page, data, spare, *corrected_bits)` returning OK/ECC_FAIL with a
   read-retry level parameter, `hal_nand_program(blk, page, data, spare)`, `hal_nand_erase(blk)`, `hal_nand_is_bad(blk)`
   (factory mark), plus `hal_temp_read()` and `hal_timer_ms()`. Keep it synchronous.
3. On-NAND format: everything persisted (map checkpoints, journal, block info/erase counts, SMART counters,
   clean-shutdown mark, superblock with magic/version) — existing drives in the field must mount with new firmware
   and vice versa.

## Behavior to implement (deterministic; exact rules matter)
- Commands: READ, WRITE (+FUA bit), FLUSH, DSM-deallocate (TRIM), IDENTIFY (controller: model/serial/fw rev/vendor
  fields subset; namespace: size/capacity/LBA format 4096B), GET LOG PAGE (0x02 SMART/health: critical warning, composite
  temperature (Kelvin), available spare %, spare threshold, percentage used, data units read/written, host read/write
  commands, power cycles, power-on hours, unsafe shutdowns, media errors, error log entries), SET/GET FEATURES (volatile
  write cache enable 0x06, temperature threshold 0x04, power management 0x02), FORMAT NVM (user data erase), vendor
  commands 0xC0 (dump internal counters: GC count, WL count, bad block count, read-retry count, refresh count),
  0xC1 (set debug verbosity). Unsupported opcodes → Invalid Opcode; LBA out of range → LBA Out of Range; etc.
- Write cache: N entries of 4 KiB; when full or on FLUSH/FUA/shutdown it destages; reads hit the cache first; when
  volatile write cache is disabled (feature 0x06), writes are written through.
- FTL: page-level map (LBA 4K → physical (blk, page, slot)), over-provisioning from config, open block per stream
  (host vs GC), GC trigger when free blocks < threshold (greedy victim = min valid count; tie → lowest erase count →
  lowest block id), static wear leveling when (max_ec - min_ec) > WL_THRESHOLD every K GCs, bad block handling (factory
  bad skipped; program/erase failure → retire block, relocate valid data, increment counters, reduce available spare),
  read retry: on ECC_FAIL retry with levels 1..RR_MAX from a per-NAND-type table; success at level ≥ RR_REFRESH_LEVEL
  schedules refresh (relocation) of that block; final failure → Unrecovered Read Error status + media error counter.
  Read-disturb: per-block read counter; above READ_DISTURB_LIMIT → refresh in fw_tick.
- Metadata: map checkpoint every CKPT_INTERVAL writes + journal pages in between; on fw_init without clean mark →
  replay journal, unsafe_shutdowns++. Superblock with magic + format version.
- SMART: percentage used = avg erase count * 100 / PE_LIMIT(NAND type) (QUIRK: legacy caps at 255, not 100, and uses
  integer division); data units = ceil? (QUIRK: legacy uses floor division by 1000 of 512-byte units — deliberately
  differs from the NVMe spec rounding; comment claims "spec compliant"); temperature in Kelvin = °C + 273.
- Thermal: levels by thresholds (e.g. ≥ 70°C level1, ≥ 80°C level2, ≥ 85°C level3) delaying GC/limiting cache;
  temperature threshold feature sets critical warning bit.
- Build variants via #if: CFG_NAND_TYPE (TLC/QLC → geometry, PE_LIMIT, RR table), CFG_OP_PERCENT (over-provisioning →
  reported namespace capacity), CFG_GC_POLICY (GREEDY/COST_BENEFIT; cost-benefit code exists), CFG_WL_ENABLE.
  config/fw_config.h has DEV defaults: CFG_NAND_TYPE=QLC, CFG_OP_PERCENT=7, CFG_GC_POLICY=GREEDY, CFG_WL_ENABLE=1.
  **TRAP BUILD (tribal):** production firmware is built with `-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12` from the
  release build server (Makefile.release is NOT in the repo). Hidden tests expect PRODUCTION behavior.
- Vendor 0xC0 packs counters BIG-endian although the header comment says little-endian (**TRAP**: the factory tool
  depends on big-endian; code is truth; tribal knowledge says keep it).
- Legacy smells: globals, macros, magic numbers, Korean+English comments (some wrong/outdated), dead code (old
  hybrid-mapping remnants `#if 0`, unused cost-benefit tuning), copy-pasted code, a suspicious-but-intended quirk or two.

## Materials (Korean, partly outdated) in materials/
- `SSD_FW_아키텍처_설계서_v2.1.docx`: architecture, task model, FTL overview; outdated in places (e.g. says GC victim
  tie-break is "oldest block", says SMART percentage used is capped at 100).
- `NVMe_명령_지원_명세.xlsx`: supported commands/features/log fields (one vendor command missing, one field outdated).
- `NAND_프로파일.xlsx` or .txt: geometry and PE limits per NAND type, read-retry tables.
- `개발환경_가이드.md`: how to build sim target, run tools; must NOT reveal production build flags.

## Hidden (hidden/)
- `oracle_knowledge.md` (Korean): what a veteran FW engineer knows: production build flags (release server
  `Makefile.release`: TLC, OP 12%), big-endian 0xC0 must be kept (factory tool), SMART quirks must be kept (host fleet
  monitoring baselines), cost-benefit GC never shipped, asic platform register details if asked, which features are
  unused (0xC1 debug command unused in production → may drop), etc. Plus guidance to answer "모르겠습니다" otherwise.
- `provided_on_request/`: things a human could hand over if asked (e.g. a NAND datasheet excerpt, a factory tool
  protocol note for 0xC0) — must not contain the build flags unless asked specifically about release build settings
  (then they could hand over `Makefile.release`; include it there).
- A pristine copy of the legacy sources needed for reference builds: `hidden/legacy_ref/`.
- Hidden black-box harness `run_hidden_tests.py <impl_dir> [--out report.json]`:
  builds the implementation (contract: `make -C <impl_dir> libssdfw.a` producing a library that does NOT include a NAND
  simulator; headers `fw_api.h` and `hal/hal_nand.h` reachable via -I<impl_dir> (and -I<impl_dir>/include if present)),
  links hidden test programs + the harness's OWN NAND/timer/temp simulator implementing hal_*.h, runs scenarios, and
  compares with expected outputs generated from the LEGACY firmware built with PRODUCTION flags
  (-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12). The candidate is built with NO extra -D flags (production behavior must be
  the default of the new code).
  Check categories (aim ~120 checks): command semantics & status codes; IDENTIFY fields; data integrity under random
  workloads with cache on/off, FUA, flush, trim; SMART/health log exact values after scripted workloads (incl. quirks);
  vendor 0xC0 bytes; GC/WL metrics (erase-count spread, GC count within tolerance); bad block & program/erase failure
  handling; read retry & ECC failure behavior with injected bit errors; read-disturb refresh; power-loss at many points
  (data integrity of flushed data, unsafe shutdown counter, mount success); on-NAND image compatibility both directions
  (legacy writes → candidate mounts and vice versa, at least 4 checks); thermal throttling behavior; feature get/set.
  Report JSON: per check pass/fail + detail, per-category totals, overall.
- Verify: harness on legacy (built by the harness with production flags via a small wrapper Makefile in legacy_ref or
  a --legacy switch) = 100% twice (deterministic). Also run legacy built with DEV defaults and record which checks fail
  → `TRAPS.md` (proves the tribal traps bite), listing every trap and affected checks.

## Final report (your reply)
Paths, LOC, build instructions, contract summary, check categories & counts, harness results (prod flags / dev
defaults), caveats.
