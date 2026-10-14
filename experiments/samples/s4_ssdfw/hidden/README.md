# S4 "ssdfw" - hidden material (never shown to the redevelopment agents)

| path | purpose |
|---|---|
| `run_hidden_tests.py` | black-box harness (see usage below) |
| `harness/hsim.c,h` | harness-owned HAL simulator: TLC production geometry 96x48x16KiB+64B, signature-based fault injection, power cut, image save/load, checkpoint "aging" patch |
| `harness/t_common.*, t_ssd.c, t_ssd2.c` | scenario program linked against a candidate `libssdfw.a`; prints `R <key> <value>` |
| `expected/expected.json` | expected values generated from `legacy_ref` built with production flags |
| `legacy_ref/` | pristine copy of `legacy/` (reference build) |
| `oracle_knowledge.md` | what a veteran FW engineer knows (Korean); answer only what is asked, else "모르겠습니다" |
| `provided_on_request/` | files a human could hand over when asked specifically (see its README) |
| `TRAPS.md` | every trap + which checks it breaks (with measured runs) |
| `tools/trap_variants.py` | rebuilds the one-change trap variants of legacy_ref and runs the harness on each (reproduces TRAPS.md) |
| `tools/gen_docx.py`, `tools/gen_xlsx.py` | generators of the Korean materials (docx / xlsx) |

## Usage

```
python3 run_hidden_tests.py <impl_dir> [--out report.json] [-j N] [--keep]
python3 run_hidden_tests.py --legacy-prod   # candidate = legacy_ref + production flags   -> must be 100%
python3 run_hidden_tests.py --legacy-dev    # candidate = legacy_ref + repo defaults       -> traps bite
python3 run_hidden_tests.py --gen-expected  # regenerate expected/expected.json
```

Candidate contract: `make -C <impl_dir> libssdfw.a` (no NAND simulator inside, no extra -D flags);
`fw_api.h` and `hal/hal_nand.h` reachable via `-I<impl_dir>` (or `-I<impl_dir>/include`);
the on-NAND format of `legacy/ftl/meta_format.h` (fmt 3.1) for the compat checks.
The harness also builds `legacy_ref` with `-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12` (through the
legacy Makefile's `EXTRA_CFLAGS`, same as `Makefile.release sim-release`) as the partner build for the
image-compatibility chains (legacy writes -> candidate mounts, candidate writes -> legacy mounts).

Runtime: ~30-40 s on 4 cores; temporary NAND images (~70 MB each, ~10 of them) in `$TMPDIR`.

## Notes for operators

* Fault injection is keyed by data signatures (bytes 16..31 of a 4 KiB block = `"@INJ" type param id`),
  so it does not depend on where a candidate places data. RR = page needs read-retry level >= param,
  PF = first program of a page containing that id fails.
* Power cuts are injected in-process (longjmp out of the HAL); `fw_init()` must fully re-initialize RAM
  state (power-on semantics). Compat chains use image files and separate processes.
* GC/WL metrics use tolerances (gc count/avg EC +-10 %, EC spread <= legacy+3/+6, WL count +-50 % or +-10);
  all other checks are exact. `c1_debug_or_dropped` accepts either legacy behaviour or Invalid Opcode
  (0xC1 is unused in production and may be dropped).
* `nand_protocol` = no program to a non-erased page / out-of-order program / program or erase of a factory
  bad block, summed over all scenarios.
