# TRAPS - S4 "ssdfw"

Every trap planted in legacy/ + materials/, where the truth lives, and which hidden checks it breaks.
All numbers below were measured with `run_hidden_tests.py` (178 checks; expected values = legacy_ref
built with `-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12`). Variants are scratch copies of legacy_ref with
one change each, built by the harness exactly like a candidate (plain `make libssdfw.a`, no -D flags).

## T1 - production build flags (tribal knowledge, the main trap)

* Truth: release server `Makefile.release` (not in the repo) builds with `-DCFG_NAND_TYPE=TLC -DCFG_OP_PERCENT=12`.
  Repo defaults in `config/fw_config.h` are the DEV-EVB values `QLC` / `7`. Only `oracle_knowledge.md` §1 and
  `provided_on_request/Makefile.release` say so. Code comments only say "DEV defaults"; materials never give the values.
* A candidate must make TLC + OP 12% its **default** (the harness passes no -D flags).
* What each flag controls:
  * `CFG_NAND_TYPE` (TLC vs QLC): PE limit 3000/1000 (SMART percentage used), read-retry table order and
    length (1..7 vs 2,4,6,...), refresh level 4/6, read-disturb limit 20000/8000, model number "SRK S4T/S4Q",
    serial prefix "S4T/S4Q", superblock `nand_type` (a QLC build refuses to mount a TLC drive: fw_init -> -4,
    so every image-compat check fails in both directions).
  * `CFG_OP_PERCENT` (12 vs 7): namespace size 14528 vs 15352 LBAs (on the 96x48 TLC geometry), LBA-range
    boundary, spare-block budget (initial spare 10 vs 6 blocks -> available spare % for every bad-block
    count), GC/WL activity, capacity written into the superblock at format.
* Measured: DEV defaults fail **46/178**; TLC-only (OP still 7) fails 17; OP12-only (still QLC) fails 31.

## T2 - vendor 0xC0 is big-endian (code is truth, comment/doc are wrong)

* `host/nvme_vendor.c` header comment and the design doc (§9) say "little-endian"; the code packs every
  u32 with `put_be32` (`VS_PUT`). The factory station `s4ft` parses big-endian and cannot be changed
  (oracle §2, `provided_on_request/factory_tool_0xC0_protocol.txt`).
* The harness decodes 0xC0 as big-endian everywhere (it is the only window into GC/WL/RR/refresh/thermal
  counters), so "fixing" the byte order breaks **41/178** checks (vendor raw bytes, every GC/WL, bad-block,
  read-retry, read-disturb and thermal counter check).

## T3 - SMART data units: floor, not the spec's round-up

* `smart/smart.c du_conv()` = raw512 / 1000 (floor), comment claims "NVMe spec 준수 (spec compliant)";
  design doc says "NVMe spec 에 따름". Customer fleet monitoring baselines depend on it (oracle §3,
  `fleet_monitoring_note.txt`).
* Round-up variant fails **7/178**: smart_du_floor (252 LBAs -> 2, spec 3), smart_du_boundary, smart_after_2_clean,
  and the compat counter-continuity checks (a drive written by one FW and read by the other shows a jump).

## T4 - SMART percentage used saturates at 255 (doc says capped at 100)

* `smart_percent_used()` = (integer avg EC) * 100 / PE limit, saturate 255. Design doc §7 says "100 에서 상한"
  (outdated). Keep (oracle §3).
* Cap-at-100 variant fails **1/178** (`smart_aged_percentage_saturate`: aged image EC 9000 -> 300% -> 255,
  critical warning bit2 set). With the wrong PE limit (QLC) both aged checks fail.

## T5 - outdated materials (no tribal knowledge needed, code is right)

| item | material says | code (truth) | detected by |
|---|---|---|---|
| Available Spare Threshold | xlsx SMART_Log: 5% | 10% (`SPARE_THRESHOLD_PCT`) | variant `spare_threshold_5`: 1 fail (`smart_initial`) |
| 0xC1 debug command | xlsx Vendor sheet: missing | implemented | not required: `c1_debug_or_dropped` accepts Invalid Opcode (oracle: unused in production, may drop) - variant `drop_c1` = 178/178 |
| GC victim tie-break | doc §4.4: "가장 오래된 block" | lowest erase count, then lowest block id | variant `gc_tiebreak_oldest` = 178/178 (within GC/WL tolerances; informational) |
| background work | doc §3: runs in timer ISR | main loop `fw_tick()` since 2018.10 | no behavioural effect |
| 0xC0 byte order | doc §9 + comment: LE | BE | T2 |

## T6 - legacy quirks a "clean" rewrite might drop (each pinned by an exact check)

| quirk (all in code, intended per oracle §4) | check(s) |
|---|---|
| NUSE counts only LBAs already destaged to NAND (cached writes not counted) | identify/ns_nuse_cached |
| abrupt shutdown (fw_shutdown(0)) flushes data but still counts as unsafe at next boot | powerloss/pl_abrupt_shutdown, smart/smart_after_abrupt |
| SMART temperature = last 1 s sample (stale until fw_tick) | smart/smart_temp_stale, thermal/th_poll_timing |
| critical warning bit1 uses `>=` threshold; bit2 = percentage used >= 100 | smart/smart_cw_temp_threshold, smart/smart_aged_percentage_saturate |
| every failed command increments error-log entries; host read/write command counters count validated commands only, data units only successful ones | cmd/error_log_count, cmd/host_cmd_counting, readretry/rr_l9_smart |
| throttle event counted again when booting hot (sample at fw_init) | thermal/th_boot_level |
| read-retry counter = number of retry reads (level >= 1), table order per NAND type | readretry/rr_l2..rr_l9, rr_totals |
| write-through at thermal level 3 / VWC off (durable at completion) | thermal/th_l3_writethrough, features/feat_vwc_off_durable |
| cache limited to 32 entries at thermal level 2 (destage 16 oldest) | thermal/th_cache_limit |
| serial number generated at factory format ("S4" + type + crc(geometry,bad list) + nblk) | identify/id_sn, compat/*_meta |

## Measured runs
| run | score | failing checks |
|---|---|---|
| legacy, repo DEV defaults (QLC, OP 7%)  `--legacy-dev` | 132/178 | **identify** (3): id_sn, id_mn, ns_size_capacity; **smart** (3): smart_initial, smart_aged_percentage_used, smart_aged_percentage_saturate; **gcwl** (8): gc_count, gc_avg_ec, gc_ec_spread, gc_nand_programs, gc_idle, wl_count, wl_gc_count, wl_avg_ec; **badblock** (5): bb_factory_counts, bb_pf_spare, bb_pf_persist, bb_ef_spare, bb_spare9; **readretry** (7): rr_l2, rr_l3, rr_l4, rr_l6, rr_l9, rr_l9_smart, rr_totals; **readdisturb** (1): rd_at_limit; **compat** (19): r2c_clean_mount_data, r2c_clean_counters, r2c_clean_meta, r2c_cut_mount_data, r2c_cut_counters, r2c_cut_meta, r2c_pf_mount_data, r2c_pf_counters, r2c_pf_meta, c2r_clean_mount_data, c2r_clean_counters, c2r_clean_meta, c2r_cut_mount_data, c2r_cut_counters, c2r_cut_meta, rt2_mount_data, rt2_counters, rt2_meta, aged_mount |
| legacy, production flags  `--legacy-prod` (run 1 / run 2 identical) | 178/178 | - |
| variant `prod_defaults` (defaults changed to TLC/12, no -D) | 178/178 | - |
| variant `tlc_only` (TLC, OP 7%) | 161/178 | **identify** (1): ns_size_capacity; **smart** (1): smart_initial; **gcwl** (8): gc_count, gc_avg_ec, gc_ec_spread, gc_nand_programs, gc_idle, wl_count, wl_gc_count, wl_avg_ec; **badblock** (5): bb_factory_counts, bb_pf_spare, bb_pf_persist, bb_ef_spare, bb_spare9; **compat** (2): c2r_clean_meta, c2r_cut_meta |
| variant `op12_only` (QLC, OP 12%) | 147/178 | **identify** (2): id_sn, id_mn; **smart** (2): smart_aged_percentage_used, smart_aged_percentage_saturate; **readretry** (7): rr_l2, rr_l3, rr_l4, rr_l6, rr_l9, rr_l9_smart, rr_totals; **readdisturb** (1): rd_at_limit; **compat** (19): r2c_clean_mount_data, r2c_clean_counters, r2c_clean_meta, r2c_cut_mount_data, r2c_cut_counters, r2c_cut_meta, r2c_pf_mount_data, r2c_pf_counters, r2c_pf_meta, c2r_clean_mount_data, c2r_clean_counters, c2r_clean_meta, c2r_cut_mount_data, c2r_cut_counters, c2r_cut_meta, rt2_mount_data, rt2_counters, rt2_meta, aged_mount |
| variant `c0_little_endian` (prod defaults + 0xC0 packed LE as the comment says) | 137/178 | **vendor** (7): c0_sig_raw, c0_bad_raw, c0_raw_prefix, c0_free_ec, c0_dirty, c0_format_dirty, c0_nand_programs; **gcwl** (10): gc_count, gc_avg_ec, gc_ec_spread, gc_nand_programs, gc_idle, gc_idle_thermal, wl_count, wl_gc_count, wl_ec_spread, wl_avg_ec; **badblock** (4): bb_factory_counts, bb_pf_counts, bb_pf_persist, bb_ef_counts; **readretry** (6): rr_l2, rr_l3, rr_l4, rr_l6, rr_l9, rr_totals; **readdisturb** (2): rd_over_limit, rd_second; **compat** (3): r2c_clean_meta, r2c_cut_meta, r2c_pf_meta; **thermal** (9): th_l1, th_l2, th_l3, th_hold, th_hysteresis, th_drop_all, th_cache_limit, th_boot_level, th_events_persist |
| variant `smart_du_round_up` (prod defaults + data units rounded up per NVMe spec) | 171/178 | **smart** (3): smart_du_floor, smart_du_boundary, smart_after_2_clean; **compat** (4): r2c_clean_counters, r2c_pf_counters, c2r_clean_counters, rt2_counters |
| variant `smart_pct_cap100` (prod defaults + percentage used capped at 100 per design doc) | 177/178 | **smart** (1): smart_aged_percentage_saturate |
| variant `spare_threshold_5` (prod defaults + spare threshold 5% per command spec xlsx) | 177/178 | **smart** (1): smart_initial |
| variant `gc_tiebreak_oldest` (prod defaults + GC tie-break "oldest block" per design doc) | 178/178 | - |
| variant `drop_c1` (prod defaults + vendor 0xC1 removed) | 178/178 | - |
