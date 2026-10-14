/*
 * ftl_dbg.c - FTL debug helpers (consistency check / summary dump)
 *   sim tool (ssdcli "check") 및 asic debug shell 에서 사용. 일반 동작 경로에서는 호출 안 함.
 *
 *  2017.05 sypark
 *  2018.04 dykang  retire queue 상태 반영
 */
#include "ftl.h"
#include "fw_log.h"

static uint16_t s_valid_chk[FTL_MAX_BLOCKS];

static const char *bi_name(uint8_t st)
{
    switch (st) {
    case BI_FREE:        return "FREE";
    case BI_USED:        return "USED";
    case BI_BAD_FACTORY: return "BADF";
    case BI_BAD_GROWN:   return "BADG";
    case BI_SYSTEM:      return "SYS";
    default:             return "?";
    }
}

/*
 * map 과 block 상태가 맞는지 검사. return = error 수
 *  - map 이 가리키는 block 이 USED (또는 relocation 대기 중인 grown bad) 인지
 *  - valid count 재계산 값과 g_blk[].valid 일치
 *  - free count 일치, map_used 일치
 */
int ftl_check_consistency(void)
{
    uint32_t lba, m, b, nfree = 0, used = 0;
    int err = 0;

    memset(s_valid_chk, 0, sizeof(s_valid_chk));
    for (lba = 0; lba < g_ftl.capacity; lba++) {
        m = g_map[lba];
        if (m == MAP_UNMAPPED)
            continue;
        used++;
        if (!MAP_IS_PPA(m))
            continue;
        b = PPA_BLK(m);
        if (b >= g_ftl.nblk || PPA_PAGE(m) >= g_ftl.ppb) {
            LOGE("dbg", "lba %u: bad ppa %08x", lba, m);
            err++;
            continue;
        }
        if (g_blk[b].state != BI_USED && g_blk[b].state != BI_BAD_GROWN) {
            LOGE("dbg", "lba %u -> blk %u state %s", lba, b, bi_name(g_blk[b].state));
            err++;
        }
        s_valid_chk[b]++;
    }
    for (b = 0; b < g_ftl.nblk; b++) {
        if (s_valid_chk[b] != g_blk[b].valid) {
            LOGE("dbg", "blk %u valid %u (map says %u)", b, g_blk[b].valid, s_valid_chk[b]);
            err++;
        }
        if (b >= g_ftl.pool_start && g_blk[b].state == BI_FREE)
            nfree++;
        if (g_blk[b].state == BI_BAD_GROWN && g_blk[b].valid && !(g_blk[b].flags & BF_RETIRE_Q)) {
            LOGE("dbg", "grown bad blk %u has %u valid units but not queued", b, g_blk[b].valid);
            err++;
        }
    }
    if (nfree != g_ftl.free_cnt) {
        LOGE("dbg", "free count %u (blocks say %u)", g_ftl.free_cnt, nfree);
        err++;
    }
    if (used != g_ftl.map_used) {
        LOGE("dbg", "map_used %u (map says %u)", g_ftl.map_used, used);
        err++;
    }
    return err;
}

void ftl_dump_summary(void)
{
    uint32_t b, n[5] = { 0, 0, 0, 0, 0 }, mn, mx, avg;

    for (b = 0; b < g_ftl.nblk; b++)
        if (g_blk[b].state < 5)
            n[g_blk[b].state]++;
    ftl_ec_stats(&mn, &mx, &avg);
    LOGE("dbg", "geo %ux%u cap %u spare %u/%u | free %u used %u badF %u badG %u sys %u",
         g_ftl.nblk, g_ftl.ppb, g_ftl.capacity, g_ftl.spare_total, g_ftl.user_blocks,
         n[BI_FREE], n[BI_USED], n[BI_BAD_FACTORY], n[BI_BAD_GROWN], n[BI_SYSTEM]);
    LOGE("dbg", "ec min %u max %u avg %u | open host %d/%u gc %d/%u | meta ring %u wp %u seq %u",
         mn, mx, avg, (int)g_ftl.st[STREAM_HOST].open_blk, g_ftl.st[STREAM_HOST].wp,
         (int)g_ftl.st[STREAM_GC].open_blk, g_ftl.st[STREAM_GC].wp,
         g_ftl.meta_cur, g_ftl.meta_wp, g_ftl.meta_seq);
    LOGE("dbg", "gc %u wl %u rr %u refresh %u ckpt %u map_used %u",
         g_cnt.gc_count, g_cnt.wl_count, g_cnt.rr_count, g_cnt.refresh_count,
         g_cnt.ckpt_count, g_ftl.map_used);
}

#if 0
/* 2017.05 - per block dump (UART 가 너무 느려서 사용 안 함) */
void ftl_dump_blocks(void)
{
    uint32_t b;
    for (b = 0; b < g_ftl.nblk; b++)
        LOGE("dbg", "blk %3u %-4s ec %5u valid %4u rd %6u", b, bi_name(g_blk[b].state),
             g_blk[b].ec, g_blk[b].valid, g_blk[b].rd_cnt);
}
#endif
