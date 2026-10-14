# Task: redevelop a legacy NAND flash translation layer (SSD/embedded firmware storage core)

{{AVAILABLE}}

Produce a modern, clean, maintainable **C11** re-implementation in `./new/`.

Hard requirements:
1. **Public API & driver interface unchanged**: same function names, signatures, types, constants and error codes as
   the existing public headers `nfl/map.h`, `nfl/nand.h`, `nfl/error.h`, so existing callers and existing NAND drivers
   compile and link unchanged. Headers must be includable as `"nfl/map.h"` etc. with `-I./new`.
2. `make -C new libnfl.a` builds a static library with the implementation. The NAND driver functions (`nfl_nand_*`)
   are NOT part of the library; they are provided by the platform integrator.
3. **Field-upgrade compatibility**: the on-flash format and the power-loss/recovery semantics must be 100% compatible
   with the existing firmware — devices written by the old firmware must resume and continue working with the new
   firmware, and vice versa. Capacity reporting must be identical.
4. Same robustness behavior on bad blocks / failing blocks as the existing firmware.
5. Write your own tests (with your own NAND simulator) under `./new/tests/` and make them pass (`make -C new test`).

Work fully autonomously until done; do not ask questions. Record important decisions/assumptions in `new/NOTES.md`.
Only use files inside the current directory as information sources.
