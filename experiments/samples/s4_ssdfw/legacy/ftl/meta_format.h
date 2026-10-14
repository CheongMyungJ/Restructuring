/*
 * meta_format.h - ON-NAND FORMAT (superblock / spare / checkpoint / journal)
 *
 * !!! 필드 순서/크기 변경 금지 - 필드 드라이브 호환 (fmt 3.x) !!!
 * All multi-byte fields little-endian, structures packed.
 *
 *  2016.05 jhkim   fmt 1.0
 *  2017.03 jhkim   fmt 2.0 (journal 도입, hybrid map 제거)
 *  2018.09 sypark  fmt 3.0 (SMART 카운터를 persist 영역으로 이동)
 *  2019.02 mjlee   fmt 3.1 (thermal throttle_events 추가 - rsvd 사용)
 */
#ifndef META_FORMAT_H
#define META_FORMAT_H

#include "fw_types.h"

#define FMT_VERSION_MAJOR       3
#define FMT_VERSION_MINOR       1
#define FMT_VERSION             ((FMT_VERSION_MAJOR << 8) | FMT_VERSION_MINOR)

/* ------------------------------------------------------------------ */
/* map entry (physical page address of a 4K unit)                      */
/*   bit31..16 block, bit15..2 page, bit1..0 slot                      */
/* ------------------------------------------------------------------ */
#define MAP_UNMAPPED            0xFFFFFFFFu
#define MAP_UNC                 0xFFFFFFFEu     /* uncorrectable marker */
#define MAP_IS_PPA(m)           ((m) < MAP_UNC)
#define PPA_MAKE(b, p, s)       (((uint32_t)(b) << 16) | ((uint32_t)(p) << 2) | (uint32_t)(s))
#define PPA_BLK(m)              ((m) >> 16)
#define PPA_PAGE(m)             (((m) >> 2) & 0x3FFF)
#define PPA_SLOT(m)             ((m) & 0x3)

/* ------------------------------------------------------------------ */
/* spare (OOB) layout - first 28 bytes of the spare area               */
/* ------------------------------------------------------------------ */
#define SPARE_MAGIC             0xA55A
#define PG_TYPE_USER            0x01
#define PG_TYPE_SB              0x51
#define PG_TYPE_CKPT            0xC1
#define PG_TYPE_JRNL            0x71

#define SPF_CLEAN               0x01    /* ckpt: written by clean shutdown */
#define SPF_BOOT                0x02    /* jrnl: boot record */

typedef struct FW_PACKED {
    uint16_t magic;
    uint8_t  type;
    uint8_t  flags;
    uint32_t seq;               /* user: data seq, meta: meta seq */
    union {
        uint32_t lba[4];        /* user page: LBA per slot, 0xFFFFFFFF = pad */
        struct FW_PACKED {
            uint32_t base_seq;  /* ckpt: seq of part0, jrnl: seq of base ckpt part0 */
            uint16_t part;
            uint16_t nparts;
            uint32_t count;     /* jrnl: #entries, ckpt: capacity */
            uint32_t payload_crc;   /* crc32 of the full data page */
        } m;
    } u;
    uint32_t crc;               /* crc32 of bytes [0..23] */
} spare_hdr_t;

#define SPARE_HDR_CRC_LEN       24

/* ------------------------------------------------------------------ */
/* superblock - block 0 page 0, copy at block 1 page 0                 */
/* ------------------------------------------------------------------ */
#define SB_MAGIC0               0x57465353u     /* "SSFW" */
#define SB_MAGIC1               0x31304253u     /* "SB01" */

typedef struct FW_PACKED {
    uint32_t magic0;
    uint32_t magic1;
    uint16_t fmt_version;
    uint8_t  nand_type;
    uint8_t  op_percent;
    uint32_t num_blocks;
    uint32_t pages_per_block;
    uint32_t page_size;
    uint32_t spare_size;
    uint32_t sys_blocks;
    uint32_t meta_start;
    uint32_t meta_blocks;
    uint32_t capacity_lbas;
    char     serial[20];
    char     fw_rev[8];         /* fw revision that formatted the drive */
    uint32_t factory_bad;
    uint32_t rsvd[8];
    uint32_t crc;               /* crc32 of all preceding bytes */
} sb_t;

/* ------------------------------------------------------------------ */
/* persisted counters (ckpt part0 + every journal page)                */
/* ------------------------------------------------------------------ */
typedef struct FW_PACKED {
    uint64_t du_read_raw;       /* 512B units read  */
    uint64_t du_written_raw;    /* 512B units written */
    uint64_t host_read_cmds;
    uint64_t host_write_cmds;
    uint64_t power_cycles;
    uint64_t poweron_ms;
    uint64_t unsafe_shutdowns;
    uint64_t media_errors;
    uint64_t err_log_entries;
    uint32_t gc_count;
    uint32_t wl_count;
    uint32_t rr_count;
    uint32_t refresh_count;
    uint32_t rr_refresh_count;
    uint32_t rd_refresh_count;
    uint32_t prog_fail_count;
    uint32_t erase_fail_count;
    uint32_t grown_bad_count;
    uint32_t ckpt_count;
    uint32_t format_count;
    uint32_t throttle_events;   /* fmt 3.1 */
    uint64_t nand_data_programs;
    uint32_t user_seq;
    uint32_t rsvd[7];
} fw_persist_t;                 /* 160 bytes */

/* ------------------------------------------------------------------ */
/* checkpoint: part0 = header + persist + block table, part1..n = map  */
/* ------------------------------------------------------------------ */
#define CKPT_MAGIC              0x304B5043u     /* "CPK0" */
#define MAP_ENTRIES_PER_PAGE    4096            /* 16KiB / 4 */

#define BI_FREE                 0
#define BI_USED                 1
#define BI_BAD_FACTORY          2
#define BI_BAD_GROWN            3
#define BI_SYSTEM               4

typedef struct FW_PACKED {
    uint32_t ec;
    uint8_t  state;             /* BI_xxx */
    uint8_t  rsvd[3];
} ckpt_blk_t;

typedef struct FW_PACKED {
    uint32_t     magic;
    uint16_t     fmt_version;
    uint16_t     nparts;
    uint32_t     capacity;
    uint32_t     num_blocks;
    fw_persist_t p;
    /* ckpt_blk_t blk[num_blocks] follows */
} ckpt_hdr_t;

/* ------------------------------------------------------------------ */
/* journal page                                                         */
/* ------------------------------------------------------------------ */
#define JRNL_MAGIC              0x314E524Au     /* "JRN1" */

typedef struct FW_PACKED {
    uint32_t     magic;
    uint32_t     nent;
    fw_persist_t p;
    /* jrnl_ent_t ent[nent] follows */
} jrnl_hdr_t;

typedef struct FW_PACKED {
    uint32_t key;
    uint32_t val;
} jrnl_ent_t;

/* key < JK_SPECIAL : LBA -> val = map entry (ppa / UNMAPPED / UNC) */
#define JK_SPECIAL              0xF0000000u
#define JK_ERASE                0xF1000000u     /* | blk, val = new erase count */
#define JK_BAD                  0xF2000000u     /* | blk, val = reason          */
#define JK_TYPE_MASK            0xFF000000u
#define JK_BLK_MASK             0x00FFFFFFu

#define JRNL_MAX_ENTRIES(psz)   (((psz) - sizeof(jrnl_hdr_t)) / sizeof(jrnl_ent_t))

#endif /* META_FORMAT_H */
