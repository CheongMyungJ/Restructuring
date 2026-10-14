/*
 * ftl_core.c - FTL core: geometry, map, read/write path, trim, format, stats
 *
 *  2016.05 jhkim   initial
 *  2017.03 jhkim   page mapping (4K unit) 로 전환
 *  2018.04 dykang  UNC marker 추가
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"
#include "crc32.h"

ftl_t        g_ftl;
blk_t        g_blk[FTL_MAX_BLOCKS];
uint32_t     g_map[FTL_MAX_LBAS];
fw_persist_t g_cnt;

uint8_t g_ftl_rbuf[NAND_PAGE_SIZE];     /* read scratch (host read / relocation) */
uint8_t g_ftl_mbuf[NAND_PAGE_SIZE];     /* metadata scratch */
uint8_t g_ftl_spare[FTL_MAX_SPARE];

static uint8_t s_stream_buf[NUM_STREAMS][NAND_PAGE_SIZE];

/*
 * HAL 에서 geometry 를 읽는다.  profile 과 다르면 경고만 출력 (EVB 에서
 * 다른 NAND 를 꽂아서 테스트하는 경우가 있음).
 */
int ftl_geometry_setup(void)
{
    hal_nand_geo_t geo;

    memset(&geo, 0, sizeof(geo));
    hal_nand_get_geometry(&geo);

    if (geo.page_size != NAND_PAGE_SIZE) {
        LOGE("ftl", "unsupported page size %u", geo.page_size);
        return -1;
    }
    if (geo.spare_size < sizeof(spare_hdr_t) || geo.spare_size > FTL_MAX_SPARE) {
        LOGE("ftl", "unsupported spare size %u", geo.spare_size);
        return -1;
    }
    if (geo.num_blocks < SYS_BLOCKS + 16 || geo.num_blocks > FTL_MAX_BLOCKS ||
        geo.pages_per_block < 8 || geo.pages_per_block > FTL_MAX_PPB) {
        LOGE("ftl", "unsupported geometry %ux%u", geo.num_blocks, geo.pages_per_block);
        return -1;
    }
    if (geo.num_blocks != NAND_BLOCKS || geo.pages_per_block != NAND_PAGES_PER_BLK)
        LOGW("ftl", "geometry %ux%u differs from %s profile (%ux%u)",
             geo.num_blocks, geo.pages_per_block, NAND_TYPE_NAME,
             NAND_BLOCKS, NAND_PAGES_PER_BLK);

    g_ftl.nblk          = geo.num_blocks;
    g_ftl.ppb           = geo.pages_per_block;
    g_ftl.page_size     = geo.page_size;
    g_ftl.spare_size    = geo.spare_size;
    g_ftl.slots_per_blk = geo.pages_per_block * SLOTS_PER_PAGE;
    g_ftl.pool_start    = SYS_BLOCKS;
    g_ftl.pool_blocks   = geo.num_blocks - SYS_BLOCKS;
    return 0;
}

/* user capacity (LBAs) = raw pool slots minus OP, 32KiB aligned */
uint32_t ftl_calc_capacity(uint32_t pool_blocks, uint32_t slots_per_blk)
{
    uint32_t raw = pool_blocks * slots_per_blk;
    uint32_t cap = (uint32_t)(((uint64_t)raw * (100 - CFG_OP_PERCENT)) / 100);

    cap &= ~7u;
    if (cap > FTL_MAX_LBAS)
        cap = FTL_MAX_LBAS;
    return cap;
}

void ftl_calc_spare(void)
{
    g_ftl.user_blocks = DIV_ROUND_UP(g_ftl.capacity, g_ftl.slots_per_blk);
    g_ftl.spare_total = (g_ftl.pool_blocks > g_ftl.user_blocks) ?
                        (g_ftl.pool_blocks - g_ftl.user_blocks) : 0;
}

void ftl_ram_reset(void)
{
    int i;

    memset(&g_ftl, 0, sizeof(g_ftl));
    memset(g_blk, 0, sizeof(g_blk));
    memset(g_map, 0xFF, sizeof(g_map));
    memset(&g_cnt, 0, sizeof(g_cnt));
    for (i = 0; i < NUM_STREAMS; i++) {
        g_ftl.st[i].open_blk = BLK_NONE;
        g_ftl.st[i].buf = s_stream_buf[i];
    }
    jrnl_reset();
    refresh_reset();
    bbm_reset();
}

int ftl_is_open(uint32_t blk)
{
    return (g_ftl.st[STREAM_HOST].open_blk == blk) || (g_ftl.st[STREAM_GC].open_blk == blk);
}

/*
 * map 갱신 - valid count / journal 처리 포함.  모든 map 변경은 여기를 거친다.
 */
void ftl_map_set(uint32_t lba, uint32_t ppa)
{
    uint32_t old = g_map[lba];
    uint32_t b;

    if (MAP_IS_PPA(old)) {
        b = PPA_BLK(old);
        if (g_blk[b].valid)
            g_blk[b].valid--;
        ftl_check_free(b);
    }
    if (old == MAP_UNMAPPED && ppa != MAP_UNMAPPED)
        g_ftl.map_used++;
    else if (old != MAP_UNMAPPED && ppa == MAP_UNMAPPED)
        g_ftl.map_used--;

    g_map[lba] = ppa;
    if (MAP_IS_PPA(ppa))
        g_blk[PPA_BLK(ppa)].valid++;
    jrnl_add(lba, ppa);
}

int ftl_read_lba(uint32_t lba, uint8_t *out)
{
    uint32_t m = g_map[lba];
    int rc;

    if (m == MAP_UNMAPPED) {
        memset(out, 0, LBA_SIZE);       /* deallocated -> zeros (DLFEAT=1) */
        return FTL_OK;
    }
    if (m == MAP_UNC)
        return FTL_ERR_UNC;

    rc = ftl_read_page_rr(PPA_BLK(m), PPA_PAGE(m), g_ftl_rbuf, g_ftl_spare);
    if (rc != HAL_NAND_OK) {
        LOGE("ftl", "read fail lba %u ppa %08x rc %d", lba, m, rc);
        return FTL_ERR_UNC;
    }
    memcpy(out, g_ftl_rbuf + PPA_SLOT(m) * LBA_SIZE, LBA_SIZE);
    return FTL_OK;
}

/* append one 4K unit to a stream page buffer; programs when the page is full */
int ftl_write_lba(int st, uint32_t lba, const uint8_t *data)
{
    stream_t *s = &g_ftl.st[st];

    memcpy(s->buf + s->nslot * LBA_SIZE, data, LBA_SIZE);
    s->lba[s->nslot] = lba;
    s->nslot++;
    if (s->nslot == SLOTS_PER_PAGE)
        return ftl_program_stream_page(st);
    return FTL_OK;
}

/* program partially filled page (padding) */
int ftl_flush_stream(int st)
{
    stream_t *s = &g_ftl.st[st];

    if (s->nslot == 0)
        return FTL_OK;
    while (s->nslot < SLOTS_PER_PAGE) {
        memset(s->buf + s->nslot * LBA_SIZE, 0xFF, LBA_SIZE);
        s->lba[s->nslot] = INVALID_U32;
        s->nslot++;
    }
    return ftl_program_stream_page(st);
}

void ftl_trim_lba(uint32_t lba)
{
    if (g_map[lba] == MAP_UNMAPPED)
        return;
    ftl_map_set(lba, MAP_UNMAPPED);
}

/*
 * FORMAT NVM - user data erase
 *   ses 0: map clear only, ses 1: + physical erase of all user blocks
 *   (ckpt 를 먼저 써서 전원 차단 시에도 old map 이 살아나지 않게 함)
 */
int ftl_format(int ses)
{
    uint32_t lba, b;
    int i;

    for (lba = 0; lba < FTL_MAX_LBAS; lba++)
        g_map[lba] = MAP_UNMAPPED;
    g_ftl.map_used = 0;

    for (i = 0; i < NUM_STREAMS; i++) {
        g_ftl.st[i].open_blk = BLK_NONE;
        g_ftl.st[i].wp = 0;
        g_ftl.st[i].nslot = 0;
    }
    refresh_reset();
    bbm_reset();
    jrnl_reset();

    g_ftl.free_cnt = 0;
    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        g_blk[b].valid = 0;
        g_blk[b].flags = 0;
        if (g_blk[b].state == BI_USED || g_blk[b].state == BI_FREE) {
            g_blk[b].state = BI_FREE;
            g_ftl.free_cnt++;
        }
    }
    g_cnt.format_count++;
    if (ckpt_write(0) != 0)
        return -1;

    if (ses == 1) {
        for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
            if (g_blk[b].state == BI_FREE)
                (void)ftl_erase_block(b);
        }
        jrnl_commit(1, 0);
    }
    return 0;
}

/* erase count statistics over good user-pool blocks */
void ftl_ec_stats(uint32_t *min, uint32_t *max, uint32_t *avg)
{
    uint32_t b, n = 0, mn = INVALID_U32, mx = 0;
    uint64_t sum = 0;

    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        if (g_blk[b].state == BI_BAD_FACTORY || g_blk[b].state == BI_BAD_GROWN)
            continue;
        sum += g_blk[b].ec;
        n++;
        if (g_blk[b].ec < mn) mn = g_blk[b].ec;
        if (g_blk[b].ec > mx) mx = g_blk[b].ec;
    }
    if (n == 0)
        mn = 0;
    if (min) *min = mn;
    if (max) *max = mx;
    if (avg) *avg = n ? (uint32_t)(sum / n) : 0;
}

uint32_t ftl_bad_total(void)
{
    uint32_t b, n = 0;

    for (b = 0; b < g_ftl.nblk; b++)
        if (g_blk[b].state == BI_BAD_FACTORY || g_blk[b].state == BI_BAD_GROWN)
            n++;
    return n;
}

/* available spare (%) = remaining spare blocks / initial spare blocks */
uint32_t ftl_avail_spare_pct(void)
{
    uint32_t b, bad = 0, rem;

    if (g_ftl.spare_total == 0)
        return 0;
    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++)
        if (g_blk[b].state == BI_BAD_FACTORY || g_blk[b].state == BI_BAD_GROWN)
            bad++;
    rem = (g_ftl.spare_total > bad) ? (g_ftl.spare_total - bad) : 0;
    return rem * 100 / g_ftl.spare_total;
}

#if 0
/*
 * ---- hybrid mapping (fmt 1.x) remnants ----
 * log block 4개 + data block 매핑. 2017.03 page mapping 전환 후 미사용.
 */
#define LOG_BLOCKS  4
static uint32_t s_log_blk[LOG_BLOCKS];
static uint32_t s_log_owner[LOG_BLOCKS];

static int hyb_merge(uint32_t lbn)
{
    uint32_t i, pg;
    for (i = 0; i < LOG_BLOCKS; i++) {
        if (s_log_owner[i] != lbn)
            continue;
        for (pg = 0; pg < g_ftl.ppb; pg++) {
            /* full merge: copy newest copy of each page to new data block */
        }
        s_log_owner[i] = INVALID_U32;
    }
    return 0;
}
#endif
