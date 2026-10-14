/*
 * fw_config.h - S4 컨트롤러 펌웨어 빌드 설정
 *
 *  2016.03  jhkim   initial (S3 코드베이스에서 분리)
 *  2017.08  sypark  QLC 지원, OP 설정 분리
 *  2018.02  hwchoi  write cache 파라미터 정리
 *  2018.11  mjlee   thermal throttling 파라미터 추가
 *  2019.04  jhkim   WL threshold 조정 (field issue #2231)
 *
 * NOTE: 아래 값들은 개발(DEV) 기본값임. 빌드 시 -D 로 override 가능.
 *       (default values below are for the dev board; override with -D)
 */
#ifndef FW_CONFIG_H
#define FW_CONFIG_H

/* ---- selector tokens (used as -DCFG_xxx=<token>) ---- */
#define TLC             1
#define QLC             2

#define GREEDY          1
#define COST_BENEFIT    2

/* ---- build variants ---- */
#ifndef CFG_NAND_TYPE
#define CFG_NAND_TYPE   QLC         /* dev board 는 QLC 샘플 장착 */
#endif

#ifndef CFG_OP_PERCENT
#define CFG_OP_PERCENT  7           /* over-provisioning, % of user pool */
#endif

#ifndef CFG_GC_POLICY
#define CFG_GC_POLICY   GREEDY
#endif

#ifndef CFG_WL_ENABLE
#define CFG_WL_ENABLE   1
#endif

#if (CFG_OP_PERCENT < 3) || (CFG_OP_PERCENT > 50)
#error "CFG_OP_PERCENT out of range (3..50)"
#endif

/* ---- identity ---- */
#define FW_PCI_VID              0x1F7A
#define FW_PCI_SSVID            0x1F7A
#define FW_REVISION             "S4FW4219"      /* 8 chars, IDENTIFY FR */
#define FW_MODEL_PREFIX         "SRK S4"
#define FW_MODEL_SUFFIX         " NVMe SSD"
#define FW_IEEE_OUI0            0x9E
#define FW_IEEE_OUI1            0xB1
#define FW_IEEE_OUI2            0x38
#define FW_SPEC_VERSION         0x00010300      /* NVMe 1.3 */

/* ---- host interface ---- */
#define LBA_SIZE                4096
#define LBA_SHIFT               12
#define MDTS_SHIFT              8               /* 2^8 * 4K = 1MiB */
#define MDTS_LBAS               (1u << MDTS_SHIFT)
#define FW_NPSS                 2               /* power states 0..2 */
#define SECTORS_PER_LBA         (LBA_SIZE / 512)

/* ---- write cache (DRAM) ---- */
#define CACHE_ENTRIES           64              /* 4KiB entries = 256KiB */
#define CACHE_DESTAGE_BATCH     16              /* entries per destage when full */

/* ---- FTL limits (static array sizing) ---- */
#define FTL_MAX_BLOCKS          256
#define FTL_MAX_PPB             128
#define FTL_MAX_LBAS            32768
#define SLOTS_PER_PAGE          4               /* 16KiB page / 4KiB unit */

/* ---- system area layout (block index) ---- */
#define SB_BLOCK0               0
#define SB_BLOCK1               1
#define META_START              2
#define META_BLOCKS             8
#define SYS_BLOCKS              (META_START + META_BLOCKS)

/* ---- GC / WL ---- */
#define GC_FG_THRESHOLD         4       /* free blk < this -> foreground GC */
#define GC_FG_MAX_LOOP          16      /* max GC per allocation when free >= 2 */
#define IDLE_GC_FREE_TARGET     8       /* idle GC while free blk < this */
#define IDLE_GC_DELAY_MS        2000    /* host idle time before idle GC */
#define WL_THRESHOLD            20      /* max_ec - min_ec */
#define WL_CHECK_INTERVAL       8       /* check WL every N GCs */

/* ---- metadata ---- */
#define CKPT_INTERVAL           4096    /* host LBA writes between checkpoints */
#define JRNL_MAX_PAGES          24      /* journal pages before forced ckpt */

/* ---- refresh / retire queues ---- */
#define REFRESH_Q_DEPTH         32
#define RETIRE_Q_DEPTH          8

/* ---- thermal ---- */
#define THERMAL_POLL_MS         1000
#define THERM_L1_C              70
#define THERM_L2_C              80
#define THERM_L3_C              85
#define THERM_HYST_C            3
#define TEMP_THRESH_DEF_K       358     /* 85C */
#define TEMP_WCTEMP_K           343     /* identify WCTEMP (70C) */
#define TEMP_CCTEMP_K           358     /* identify CCTEMP (85C) */

/* ---- SMART ---- */
#define SPARE_THRESHOLD_PCT     10

/* ---- debug ---- */
#define FW_DBG_DEFAULT          1       /* 0:off 1:err 2:warn 3:info 4:trace */
#define FW_DBG_MAX              4

#endif /* FW_CONFIG_H */
