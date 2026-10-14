/*
 * ftl.h - FTL internal interface
 *
 * page-level mapping: 4KiB LBA -> (blk, page, slot), 4 slots per 16KiB page
 * two write streams: HOST (cache destage / write-through) and GC
 * (GC stream is also used by wear-leveling, refresh and bad block relocation)
 *
 *  2016.05 jhkim   initial
 *  2017.03 jhkim   hybrid mapping 제거, page mapping 으로 전환
 *  2017.11 sypark  read retry / refresh
 *  2018.04 dykang  bad block relocation (retire queue)
 */
#ifndef FTL_H
#define FTL_H

#include "fw_types.h"
#include "fw_config.h"
#include "nand_profile.h"
#include "meta_format.h"

#define FTL_MAX_SPARE           256

#define STREAM_HOST             0
#define STREAM_GC               1
#define NUM_STREAMS             2

/* block runtime flags */
#define BF_REFRESH_Q            0x01
#define BF_RETIRE_Q             0x02

/* refresh reasons */
#define RQ_RR                   1       /* read retry success at high level */
#define RQ_RD                   2       /* read disturb */

/* bad block reasons (journal value) */
#define BAD_PROG_FAIL           1
#define BAD_ERASE_FAIL          2

/* GC reasons */
#define GC_FOREGROUND           0
#define GC_IDLE                 1

/* ftl_read_lba() */
#define FTL_OK                  0
#define FTL_ERR_UNC             (-1)
#define FTL_ERR_NOSPACE         (-2)

typedef struct {
    uint32_t ec;
    uint32_t rd_cnt;            /* reads since erase (RAM only) */
    uint32_t last_seq;          /* for cost-benefit age */
    uint16_t valid;             /* valid 4K units */
    uint8_t  state;             /* BI_xxx */
    uint8_t  flags;             /* BF_xxx */
} blk_t;

typedef struct {
    uint32_t open_blk;          /* BLK_NONE if no open block */
    uint32_t wp;                /* next page to program */
    uint32_t nslot;             /* filled slots in page buffer */
    uint32_t lba[SLOTS_PER_PAGE];
    uint8_t *buf;
} stream_t;

typedef struct {
    /* geometry (from HAL) */
    uint32_t nblk;
    uint32_t ppb;
    uint32_t page_size;
    uint32_t spare_size;
    uint32_t slots_per_blk;
    uint32_t pool_start;
    uint32_t pool_blocks;
    /* capacity (from superblock) */
    uint32_t capacity;
    uint32_t user_blocks;
    uint32_t spare_total;
    char     serial[20];
    /* runtime */
    uint32_t free_cnt;
    uint32_t map_used;
    uint32_t writes_since_ckpt;
    uint32_t jrnl_pages_since_ckpt;
    stream_t st[NUM_STREAMS];
    /* meta ring */
    uint32_t meta_cur;          /* ring index */
    uint32_t meta_wp;           /* next page in current meta block */
    uint32_t meta_seq;          /* last used meta seq */
    uint32_t ckpt_base;         /* seq of part0 of latest checkpoint */
    uint32_t jrnl_nent;
    uint32_t jrnl_map_dirty;    /* LBA entries pending in journal buffer */
    uint8_t  meta_bad[META_BLOCKS];
    int      in_gc;
} ftl_t;

extern ftl_t        g_ftl;
extern blk_t        g_blk[FTL_MAX_BLOCKS];
extern uint32_t     g_map[FTL_MAX_LBAS];
extern fw_persist_t g_cnt;

/* ftl_core.c */
int      ftl_geometry_setup(void);
uint32_t ftl_calc_capacity(uint32_t pool_blocks, uint32_t slots_per_blk);
void     ftl_calc_spare(void);
void     ftl_ram_reset(void);
int      ftl_read_lba(uint32_t lba, uint8_t *out);
int      ftl_write_lba(int st, uint32_t lba, const uint8_t *data);
int      ftl_flush_stream(int st);
void     ftl_trim_lba(uint32_t lba);
void     ftl_map_set(uint32_t lba, uint32_t ppa);
int      ftl_format(int ses);
void     ftl_ec_stats(uint32_t *min, uint32_t *max, uint32_t *avg);
uint32_t ftl_bad_total(void);
uint32_t ftl_avail_spare_pct(void);
int      ftl_is_open(uint32_t blk);

/* ftl_alloc.c */
uint32_t ftl_alloc_block(int st);
int      ftl_erase_block(uint32_t blk);
void     ftl_close_stream(int st);
void     ftl_check_free(uint32_t blk);
int      ftl_program_stream_page(int st);

/* ftl_gc.c */
uint32_t gc_select_victim(void);
int      ftl_relocate_block(uint32_t blk);
int      gc_run_one(int reason);
void     wl_check(void);
void     gc_idle_step(uint32_t idle_ms, uint32_t therm_level);

/* ftl_bbm.c */
void     bbm_retire(uint32_t blk, uint32_t reason);
void     bbm_queue(uint32_t blk);
void     bbm_service(void);
void     bbm_reset(void);

/* ftl_rr.c */
int      ftl_read_page_rr(uint32_t blk, uint32_t page, uint8_t *data, uint8_t *spare);
void     refresh_reset(void);
void     refresh_enqueue(uint32_t blk, uint32_t reason);
void     refresh_service(void);
void     refresh_cancel(uint32_t blk);

/* ftl_meta.c */
void     jrnl_reset(void);
void     jrnl_add(uint32_t key, uint32_t val);
int      jrnl_commit(int force, uint8_t flags);
int      ckpt_write(uint8_t flags);
int      sb_write_all(const sb_t *sb);
void     ftl_meta_after_cmd(void);
uint32_t meta_blk(uint32_t ring_idx);
void     spare_build(spare_hdr_t *sp, uint8_t type, uint8_t flags, uint32_t seq);
void     spare_seal(spare_hdr_t *sp);
int      spare_check(const spare_hdr_t *sp);

/* ftl_mount.c */
int      ftl_mount(void);

/* ftl_dbg.c (debug only) */
int      ftl_check_consistency(void);
void     ftl_dump_summary(void);

/* shared scratch buffers (ftl_core.c) */
extern uint8_t  g_ftl_rbuf[NAND_PAGE_SIZE];
extern uint8_t  g_ftl_mbuf[NAND_PAGE_SIZE];
extern uint8_t  g_ftl_spare[FTL_MAX_SPARE];

#endif /* FTL_H */
