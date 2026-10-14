/*
 * ftl_rr.c - read retry / read disturb / refresh
 *
 * ECC fail 시 NAND vendor read-retry table 순서대로 재시도.
 * RR_REFRESH_LVL 이상에서 성공하면 해당 block refresh 예약.
 * block 당 read count 가 RD_LIMIT 초과하면 refresh 예약 (read disturb).
 * refresh 는 fw_tick 에서 1 block 씩 처리.
 *
 *  2017.11 sypark  initial
 *  2018.06 sypark  QLC table
 *  2019.01 dykang  refresh_cancel (erase 된 block 이 다시 refresh 되는 문제)
 */
#include "ftl.h"
#include "hal_nand.h"
#include "fw_log.h"
#include "ring.h"

static const uint8_t s_rr_tab[NAND_RR_MAX] = NAND_RR_TABLE;

static uint32_t s_refq_buf[REFRESH_Q_DEPTH];
static ring_t   s_refq;
static uint8_t  s_ref_reason[FTL_MAX_BLOCKS];

int ftl_read_page_rr(uint32_t blk, uint32_t page, uint8_t *data, uint8_t *spare)
{
    uint32_t cb = 0, i, lvl;
    int rc;

    rc = hal_nand_read(blk, page, data, spare, 0, &cb);

    if (blk >= g_ftl.pool_start && blk < g_ftl.nblk) {
        g_blk[blk].rd_cnt++;
        if (g_blk[blk].rd_cnt > NAND_RD_LIMIT)
            refresh_enqueue(blk, RQ_RD);
    }
    if (rc != HAL_NAND_ECC_FAIL)
        return rc;

    for (i = 0; i < NAND_RR_MAX; i++) {
        lvl = s_rr_tab[i];
        g_cnt.rr_count++;
        rc = hal_nand_read(blk, page, data, spare, lvl, &cb);
        if (rc == HAL_NAND_OK) {
            LOGI("rr", "blk %u pg %u recovered at level %u (%u bits)", blk, page, lvl, cb);
            if (lvl >= NAND_RR_REFRESH_LVL && blk >= g_ftl.pool_start)
                refresh_enqueue(blk, RQ_RR);
            return HAL_NAND_OK;
        }
        if (rc != HAL_NAND_ECC_FAIL)
            return rc;
    }
    LOGE("rr", "blk %u pg %u uncorrectable after %u retries", blk, page, (unsigned)NAND_RR_MAX);
    return HAL_NAND_ECC_FAIL;
}

void refresh_reset(void)
{
    ring_init(&s_refq, s_refq_buf, REFRESH_Q_DEPTH);
    memset(s_ref_reason, 0, sizeof(s_ref_reason));
}

void refresh_enqueue(uint32_t blk, uint32_t reason)
{
    if (g_blk[blk].flags & BF_REFRESH_Q)
        return;
    if (g_blk[blk].state != BI_USED)
        return;
    if (ring_push(&s_refq, blk) != 0) {
        LOGW("rr", "refresh queue full, drop blk %u", blk);
        return;
    }
    g_blk[blk].flags |= BF_REFRESH_Q;
    s_ref_reason[blk] = (uint8_t)reason;
}

/* block erase 시 queue 에서 제거 */
void refresh_cancel(uint32_t blk)
{
    uint32_t v, n, i;

    if (!(g_blk[blk].flags & BF_REFRESH_Q))
        return;
    n = ring_count(&s_refq);
    for (i = 0; i < n; i++) {
        (void)ring_pop(&s_refq, &v);
        if (v != blk)
            (void)ring_push(&s_refq, v);
    }
    g_blk[blk].flags &= ~BF_REFRESH_Q;
}

/* fw_tick: 1 block per call (이미 free/bad 가 된 block 은 건너뜀) */
void refresh_service(void)
{
    uint32_t blk;
    int rc;

    for (;;) {
        if (ring_pop(&s_refq, &blk) != 0)
            return;
        g_blk[blk].flags &= ~BF_REFRESH_Q;
        if (g_blk[blk].state == BI_USED)
            break;
    }

    /* open block 이면 닫고 옮긴다 (남은 page 는 버림) */
    if (g_ftl.st[STREAM_HOST].open_blk == blk)
        ftl_close_stream(STREAM_HOST);
    if (g_ftl.st[STREAM_GC].open_blk == blk)
        ftl_close_stream(STREAM_GC);
    if (g_blk[blk].state != BI_USED)
        return;

    g_ftl.in_gc = 1;
    rc = ftl_relocate_block(blk);
    g_ftl.in_gc = 0;
    if (rc < 0)
        return;

    g_cnt.refresh_count++;
    if (s_ref_reason[blk] == RQ_RR)
        g_cnt.rr_refresh_count++;
    else
        g_cnt.rd_refresh_count++;
    LOGI("rr", "refresh blk %u (%s) moved %d", blk, s_ref_reason[blk] == RQ_RR ? "rr" : "rd", rc);
}
