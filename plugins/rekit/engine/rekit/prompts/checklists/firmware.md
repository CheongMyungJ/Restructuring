## Domain checklist: embedded / SSD firmware (C, C++, assembly)
Capture explicitly when present:
- **Execution model**: main loop vs RTOS tasks, ISRs (which vector, what runs in interrupt context), multi-core split
  (front-end/FTL/back-end cores), inter-core mailboxes/queues, scheduling order, priorities, polling vs interrupt.
- **Concurrency**: shared data, locks/spinlocks, interrupt masking, `volatile`, memory barriers, DMA ownership and cache
  maintenance (flush/invalidate before/after DMA), re-entrancy.
- **Hardware contracts**: register maps (address, bit fields, R/W semantics, write-1-to-clear), memory map & linker
  sections (fixed addresses of buffers/tables), DMA descriptors, NAND command sequences & timing, status polling and
  timeouts, ECC/LDPC engine use, error/retry handling (read retry tables, soft decoding), controller/NAND variants.
- **Data layout**: packed structs, bitfields (compiler-dependent order!), endianness, alignment, sizes — give exact
  byte offsets for anything persisted or shared with HW/host.
- **On-media formats**: metadata/mapping tables/journals/checkpoints/bad-block tables persisted on NAND or NOR:
  exact layout, versioning, magic numbers, CRC/ECC coverage, update ordering, power-loss atomicity and recovery scan.
- **FTL**: mapping granularity, address translation (logical→virtual→physical), allocation policy, over-provisioning,
  GC trigger thresholds/victim selection/copyback, wear leveling (static/dynamic, thresholds), bad block management
  (factory/grown, replacement), trim/unmap, flush/FUA semantics, read disturb/retention handling.
- **Host interface**: supported NVMe/SATA/UFS commands, admin vs IO, identify fields, log pages, features, vendor-unique
  commands, queue handling, completion status codes, error injection/debug commands, SMART/health counters.
- **Power/thermal**: power states, PLP (power-loss protection) behavior, throttling, watchdog, boot/init sequence,
  firmware update/activation, format/sanitize.
- **Build variants**: every `#if/#ifdef` dimension (customer, NAND type, capacity, debug) — which is the production
  configuration; constants derived from configuration (show the formulas and the resulting values).
- **Resource constraints**: SRAM/DRAM budgets, stack sizes, code size, latency/IOPS targets, real-time deadlines.
