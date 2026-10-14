/*
 * ftl_bbm.c - bad block management
 *
 * factory bad : superblock format 시 hal_nand_is_bad() 로 판별, 사용 안 함
 * grown bad   : program / erase fail 시 retire.  valid data 가 남아 있으면
 *               retire queue 에 넣고 command 처리 후 (bbm_service) relocation.
 *
 *  2018.04 dykang  initial
 *  2018.07 dykang  retire queue (program fail 중 GC 재진입 문제 #1592)
 */
#include "ftl.h"
#include "fw_log.h"
#include "ring.h"

static uint32_t s_retire_buf[RETIRE_Q_DEPTH];
static ring_t   s_retire_q;

void bbm_reset(void)
{
    ring_init(&s_retire_q, s_retire_buf, RETIRE_Q_DEPTH);
}

void bbm_queue(uint32_t blk)
{
    if (g_blk[blk].flags & BF_RETIRE_Q)
        return;
    if (ring_push(&s_retire_q, blk) == 0)
        g_blk[blk].flags |= BF_RETIRE_Q;
    else
        LOGE("bbm", "retire queue full, blk %u", blk);
}

void bbm_retire(uint32_t blk, uint32_t reason)
{
    uint8_t old = g_blk[blk].state;

    if (old == BI_BAD_FACTORY || old == BI_BAD_GROWN)
        return;
    if (old == BI_FREE && g_ftl.free_cnt)
        g_ftl.free_cnt--;

    g_blk[blk].state = BI_BAD_GROWN;
    g_cnt.grown_bad_count++;
    jrnl_add(JK_BAD | blk, reason);
    LOGW("bbm", "retire blk %u reason %u ec %u valid %u", blk, reason, g_blk[blk].ec, g_blk[blk].valid);

    if (g_blk[blk].valid > 0)
        bbm_queue(blk);
}

/* command 처리 후 / fw_tick 에서 호출 */
void bbm_service(void)
{
    uint32_t blk;
    int rc;

    while (ring_pop(&s_retire_q, &blk) == 0) {
        g_blk[blk].flags &= ~BF_RETIRE_Q;
        if (g_blk[blk].valid == 0)
            continue;
        g_ftl.in_gc = 1;
        rc = ftl_relocate_block(blk);
        g_ftl.in_gc = 0;
        LOGI("bbm", "relocated %d units from retired blk %u", rc, blk);
    }
}
