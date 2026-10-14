# Task: redevelop a legacy SSD controller firmware

{{AVAILABLE}}

Produce a modern, clean, maintainable **C11** re-implementation of the firmware in `./new/` for the next-generation
controller.

Hard requirements:
1. Keep the **host-facing firmware API** (`fw_api.h`) and the **HAL interface headers** (`hal/*.h`: NAND, timer,
   temperature) unchanged — names, signatures, struct layouts, constants, status codes — so the existing host test
   infrastructure and existing HAL implementations work unchanged. Headers must be includable as `"fw_api.h"` and
   `"hal/hal_nand.h"` (etc.) with `-I./new`.
2. `make -C new libssdfw.a` builds a static library containing the firmware only — NO HAL implementation (NAND, timer,
   temperature sensor are provided by the platform).
3. The current **production behavior must be the default**: the release build server compiles your code WITHOUT any
   extra `-D` options.
4. **Field-upgrade compatibility**: drives written by the existing production firmware must mount and keep working with
   the new firmware, and vice versa (on-NAND format, metadata, persisted counters).
5. All host-visible behavior (command semantics, status codes, IDENTIFY/log page/feature data, vendor-specific
   commands, SMART/health counters) must stay identical to the current production firmware.
6. Write your own tests (with your own simulator) and make them pass.

Work fully autonomously until done; do not ask questions. Record important decisions/assumptions in `new/NOTES.md`.
Only use files inside the current directory as information sources.
