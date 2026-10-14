/*
 * ftl_gc.c - garbage collection / static wear leveling
 *
 * victim (GREEDY): used block 중 valid 최소.
 *   동률이면 erase count 낮은 block, 그것도 같으면 block 번호 작은 block.
 * relocation 은 GC stream 을 사용하고 victim 의 마지막 partial page 는 padding.
 *
 *  2016.06 jhkim   greedy GC
 *  2017.01 jhkim   cost-benefit 실험 (CFG_GC_POLICY) - 양산 미적용
 *  2017.06 sypark  static WL
 *  2018.11 mjlee   idle GC thermal 조건
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"

static uint32_t s_rev[FTL_MAX_PPB * SLOTS_PER_PAGE];   /* slot -> lba of victim */

#if CFG_GC_POLICY == COST_BENEFIT
/* cost-benefit tuning (2017.01 실험값) */
#define CB_AGE_SHIFT        4
#define CB_MIN_AGE          64
#define CB_UTIL_SCALE       1000
#endif

uint32_t gc_select_victim(void)
{
    uint32_t b, best = BLK_NONE;
#if CFG_GC_POLICY == GREEDY
    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        if (g_blk[b].state != BI_USED || ftl_is_open(b))
            continue;
        if (best == BLK_NONE ||
            g_blk[b].valid < g_blk[best].valid ||
            (g_blk[b].valid == g_blk[best].valid && g_blk[b].ec < g_blk[best].ec))
            best = b;
    }
#elif CFG_GC_POLICY == COST_BENEFIT
    uint32_t score, best_score = 0, u, age;

    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        if (g_blk[b].state != BI_USED || ftl_is_open(b))
            continue;
        u = g_blk[b].valid * CB_UTIL_SCALE / g_ftl.slots_per_blk;
        age = (g_cnt.user_seq - g_blk[b].last_seq) >> CB_AGE_SHIFT;
        if (age < CB_MIN_AGE)
            age = CB_MIN_AGE;
        if (u == 0)
            score = 0xFFFFFFFFu;
        else
            score = age * (CB_UTIL_SCALE - u) / (2 * u);
        if (best == BLK_NONE || score > best_score) {
            best = b;
            best_score = score;
        }
    }
#else
#error "unknown CFG_GC_POLICY"
#endif
    return best;
}

/*
 * blk 의 valid data 를 GC stream 으로 옮긴다.
 * return: 옮긴 4K unit 수, -1 = 공간 부족
 * NOTE: P2L table 이 없어서 map 전체를 scan 해서 slot->lba 를 만든다.
 */
int ftl_relocate_block(uint32_t blk)
{
    uint32_t lba, m, pg, sl, idx, moved = 0;
    int rc, any;

    for (idx = 0; idx < g_ftl.slots_per_blk; idx++)
        s_rev[idx] = INVALID_U32;
    for (lba = 0; lba < g_ftl.capacity; lba++) {
        m = g_map[lba];
        if (MAP_IS_PPA(m) && PPA_BLK(m) == blk)
            s_rev[PPA_PAGE(m) * SLOTS_PER_PAGE + PPA_SLOT(m)] = lba;
    }

    for (pg = 0; pg < g_ftl.ppb; pg++) {
        any = 0;
        for (sl = 0; sl < SLOTS_PER_PAGE; sl++)
            if (s_rev[pg * SLOTS_PER_PAGE + sl] != INVALID_U32)
                any = 1;
        if (!any)
            continue;

        rc = ftl_read_page_rr(blk, pg, g_ftl_rbuf, g_ftl_spare);
        if (rc != HAL_NAND_OK) {
            /* 복구 불가 - 해당 LBA 는 UNC 로 표시 (host read 시 error) */
            LOGE("gc", "relocate read fail blk %u pg %u", blk, pg);
            g_cnt.media_errors++;
            for (sl = 0; sl < SLOTS_PER_PAGE; sl++) {
                lba = s_rev[pg * SLOTS_PER_PAGE + sl];
                if (lba != INVALID_U32)
                    ftl_map_set(lba, MAP_UNC);
            }
            continue;
        }
        for (sl = 0; sl < SLOTS_PER_PAGE; sl++) {
            lba = s_rev[pg * SLOTS_PER_PAGE + sl];
            if (lba == INVALID_U32)
                continue;
            if (ftl_write_lba(STREAM_GC, lba, g_ftl_rbuf + sl * LBA_SIZE) != FTL_OK)
                return -1;
            moved++;
        }
    }
    if (ftl_flush_stream(STREAM_GC) != FTL_OK)
        return -1;
    return (int)moved;
}

/* return 1: one victim collected, 0: nothing to do, -1: error */
int gc_run_one(int reason)
{
    uint32_t v;
    int rc;

    v = gc_select_victim();
    if (v == BLK_NONE)
        return 0;
    if (g_ftl.slots_per_blk - g_blk[v].valid < SLOTS_PER_PAGE)
        return 0;                       /* 얻을 공간 없음 (padding 고려) */

    LOGT("gc", "gc%s victim %u valid %u ec %u free %u", reason == GC_IDLE ? "(idle)" : "",
         v, g_blk[v].valid, g_blk[v].ec, g_ftl.free_cnt);
    g_ftl.in_gc = 1;
    rc = ftl_relocate_block(v);
    g_ftl.in_gc = 0;
    if (rc < 0)
        return -1;
    g_cnt.gc_count++;

#if CFG_WL_ENABLE
    if ((g_cnt.gc_count % WL_CHECK_INTERVAL) == 0)
        wl_check();
#endif
    return 1;
}

/*
 * static wear leveling: EC 편차가 WL_THRESHOLD 를 넘으면 가장 cold 한
 * (EC 최소) used block 의 data 를 옮겨서 해당 block 이 다시 할당되게 한다.
 */
void wl_check(void)
{
    uint32_t mn, mx, avg, b, cold = BLK_NONE;
    int rc;

    ftl_ec_stats(&mn, &mx, &avg);
    if (mx - mn <= WL_THRESHOLD)
        return;

    for (b = g_ftl.pool_start; b < g_ftl.nblk; b++) {
        if (g_blk[b].state != BI_USED || ftl_is_open(b))
            continue;
        if (cold == BLK_NONE || g_blk[b].ec < g_blk[cold].ec)
            cold = b;
    }
    if (cold == BLK_NONE)
        return;

    LOGI("wl", "static WL blk %u ec %u (min %u max %u avg %u)", cold, g_blk[cold].ec, mn, mx, avg);
    g_ftl.in_gc = 1;
    rc = ftl_relocate_block(cold);
    g_ftl.in_gc = 0;
    if (rc >= 0)
        g_cnt.wl_count++;
}

/* fw_tick 에서 호출: host idle 이면 victim 1개씩 정리 */
void gc_idle_step(uint32_t idle_ms, uint32_t therm_level)
{
    if (idle_ms < IDLE_GC_DELAY_MS)
        return;
    if (therm_level >= 1)               /* 고온: background GC 연기 */
        return;
    if (g_ftl.free_cnt >= IDLE_GC_FREE_TARGET)
        return;
    (void)gc_run_one(GC_IDLE);
}
